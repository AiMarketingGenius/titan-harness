"""
titan-harness/lib/grok_review.py

CT-0414-07 Phase 2.1 — secondary-AI reviewer module.

Routes A-grade-required artifacts to a second, independent AI provider per
the adversarial-review L2 layer (CLAUDE.md sections 1, 8.3) and the Idea
Builder grading loop (section 12). Designed to be called from:
    - Titan session code (import grok_review; review = grok_review(...))
    - Shell hooks (python3 lib/grok_review.py --artifact ... --rubric ...)
    - The Channels listener mailbox pattern (outbox -> reviewer -> inbox)

Model routing (honors EOM 2026-04-15 dispatch P10 rule —
Sonar Pro = Deep Research ONLY; grading/spec review/adversarial = regular sonar):
    1. If XAI_API_KEY present AND GROK_REVIEWER_ENABLED=1 in env
         -> route via LiteLLM gateway 'grok-4-fast-reasoning' model
    2. Else fall back to LiteLLM gateway 'sonar' (regular Perplexity sonar,
       NOT sonar-pro per dispatch)
    3. Fallback-of-fallback: raise RuntimeError; caller decides whether to
       mark artifact PENDING_GROK_REVIEW or escalate.

The returned grade dict schema:
    {
        "grade": float,                # 0-10 overall
        "dimension_scores": {           # per CLAUDE.md section 12 10-dim rubric
            "correctness": float,
            "completeness": float,
            "honest_scope": float,
            "rollback_availability": float,
            "fit_with_harness_patterns": float,
            "actionability": float,
            "risk_coverage": float,
            "evidence_quality": float,
            "internal_consistency": float,
            "ship_ready_for_production": float
        },
        "risk_tags": [str],             # e.g. ["HARD_LIMIT_CREDS", "MISSING_ROLLBACK"]
        "rationale": str,               # 3-5 sentence summary
        "remediation": str,             # concrete next-step actions
        "reviewer_transport": str,      # which model actually graded
        "policy_version": "v1.4",
        "ts_utc": str                   # ISO 8601
    }

Mailbox pattern (used by Channels listener integration):
    outbox_drop(artifact_path, rubric, context_paths) -> request_id
        Writes /var/lib/titan-channel/mailbox/outbox/<request_id>.json
    inbox_poll(request_id, timeout_sec) -> grade dict | None
        Reads /var/lib/titan-channel/mailbox/inbox/<request_id>.json when
        the reviewer worker has written it back.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from lib.hybrid_retrieval import build_bundle, bundle_to_prompt  # type: ignore
except ImportError:  # allow direct invocation as `python3 lib/grok_review.py ...`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from lib.hybrid_retrieval import build_bundle, bundle_to_prompt  # type: ignore  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "").strip()
XAI_API_KEY = os.environ.get("XAI_API_KEY", "").strip()
GROK_REVIEWER_ENABLED = os.environ.get("GROK_REVIEWER_ENABLED", "0") == "1"
GROK_MODEL = os.environ.get("GROK_REVIEWER_MODEL", "grok-4-fast-reasoning")
FALLBACK_MODEL = os.environ.get("SECONDARY_REVIEWER_FALLBACK_MODEL", "sonar")

MAILBOX_ROOT = Path(os.environ.get("GROK_MAILBOX_ROOT", "/var/lib/titan-channel/mailbox"))
OUTBOX_DIR = MAILBOX_ROOT / "outbox"
INBOX_DIR = MAILBOX_ROOT / "inbox"

POLICY_VERSION = "v1.4"
A_GRADE_FLOOR = 9.4  # per policy.yaml war_room.min_acceptable_grade

_SYSTEM_PROMPT = (
    "You are a senior AI systems reviewer tasked with grading a doctrine, plan, or "
    "spec artifact against the 10-dimension war-room rubric defined in the AMG harness "
    "(CLAUDE.md section 12). Be rigorous. Be concrete. Score each dimension 0-10 with "
    "one-decimal precision. Compute the overall grade as the mean. Flag risks as short "
    "tags (HARD_LIMIT_CREDS, MISSING_ROLLBACK, STALE_DOCTRINE, SCOPE_CREEP, etc.). "
    "Respond with a SINGLE valid JSON object matching exactly this schema "
    "(no prose outside the JSON):\n\n"
    "{\n"
    '  "grade": <float 0-10>,\n'
    '  "dimension_scores": {\n'
    '    "correctness": <float>,\n'
    '    "completeness": <float>,\n'
    '    "honest_scope": <float>,\n'
    '    "rollback_availability": <float>,\n'
    '    "fit_with_harness_patterns": <float>,\n'
    '    "actionability": <float>,\n'
    '    "risk_coverage": <float>,\n'
    '    "evidence_quality": <float>,\n'
    '    "internal_consistency": <float>,\n'
    '    "ship_ready_for_production": <float>\n'
    "  },\n"
    '  "risk_tags": [<strings>],\n'
    '  "rationale": "<3-5 sentences>",\n'
    '  "remediation": "<concrete next-step actions>"\n'
    "}"
)


# ---------------------------------------------------------------------------
# Internal: LiteLLM chat-completions call
# ---------------------------------------------------------------------------

def _litellm_call(model: str, system: str, user: str, timeout_sec: int = 90) -> str:
    if not LITELLM_MASTER_KEY:
        raise RuntimeError(
            "LITELLM_MASTER_KEY not set. Set it in env or /etc/amg/litellm.env before calling grok_review."
        )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{LITELLM_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310 — trusted
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _select_reviewer_model() -> tuple[str, str]:
    """Return (model_name, transport_label)."""
    if GROK_REVIEWER_ENABLED and XAI_API_KEY:
        return GROK_MODEL, f"litellm/{GROK_MODEL}"
    return FALLBACK_MODEL, f"litellm/{FALLBACK_MODEL}"


def _parse_grade_response(raw: str) -> dict[str, Any]:
    # Accept either a pure JSON body or a JSON block wrapped in ```json fences.
    text = raw.strip()
    if text.startswith("```"):
        # strip fence
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    parsed = json.loads(text)
    required = {"grade", "dimension_scores", "risk_tags", "rationale", "remediation"}
    missing = required - set(parsed.keys())
    if missing:
        raise ValueError(f"reviewer JSON missing keys: {sorted(missing)}")
    return parsed


# ---------------------------------------------------------------------------
# Public: direct review (synchronous)
# ---------------------------------------------------------------------------

def grok_review(
    artifact_path: str | os.PathLike[str],
    rubric: str = "war-room-10d",
    context_paths: Optional[list[str]] = None,
    include_mcp_snippets: bool = True,
) -> dict[str, Any]:
    """
    Synchronously review an artifact via the selected secondary-AI reviewer
    (Grok when enabled, else Perplexity regular sonar). Returns a grade dict
    matching the schema in the module docstring.
    """
    bundle = build_bundle(
        artifact_path,
        rubric_name=rubric,
        context_paths=context_paths,
        include_mcp_snippets=include_mcp_snippets,
    )
    user_prompt = bundle_to_prompt(bundle)
    model, transport = _select_reviewer_model()
    raw = _litellm_call(model, _SYSTEM_PROMPT, user_prompt)
    try:
        parsed = _parse_grade_response(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"reviewer {transport} returned non-JSON or malformed response: {exc}\nraw:\n{raw[:500]}"
        ) from exc
    parsed["reviewer_transport"] = transport
    parsed["policy_version"] = POLICY_VERSION
    parsed["ts_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    parsed["a_grade_floor"] = A_GRADE_FLOOR
    parsed["cleared_a_grade"] = float(parsed.get("grade", 0.0)) >= A_GRADE_FLOOR
    return parsed


# ---------------------------------------------------------------------------
# Public: mailbox pattern (async, durable)
# ---------------------------------------------------------------------------

def _ensure_mailbox() -> None:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)


def _request_id(artifact_path: str, ts_epoch: int) -> str:
    h = hashlib.sha256(f"{artifact_path}|{ts_epoch}".encode("utf-8")).hexdigest()[:16]
    return f"req-{ts_epoch}-{h}"


def outbox_drop(
    artifact_path: str | os.PathLike[str],
    rubric: str = "war-room-10d",
    context_paths: Optional[list[str]] = None,
) -> str:
    """
    Durable outbox: write review request to MAILBOX_ROOT/outbox/<request_id>.json.
    The Channels listener worker will consume this, call grok_review(), and
    write the result to MAILBOX_ROOT/inbox/<request_id>.json.

    Returns the request_id for later polling.
    """
    _ensure_mailbox()
    path = Path(artifact_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"artifact not found: {path}")
    ts_epoch = int(time.time())
    req_id = _request_id(str(path), ts_epoch)
    payload = {
        "request_id": req_id,
        "artifact_path": str(path),
        "rubric": rubric,
        "context_paths": context_paths or [],
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "submitted_by": os.environ.get("USER", "titan"),
        "policy_version": POLICY_VERSION,
    }
    (OUTBOX_DIR / f"{req_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return req_id


def inbox_poll(request_id: str, timeout_sec: int = 300, interval_sec: float = 2.0) -> Optional[dict[str, Any]]:
    """
    Poll MAILBOX_ROOT/inbox/<request_id>.json until it appears or timeout elapses.
    Returns the grade dict or None on timeout.
    """
    _ensure_mailbox()
    target = INBOX_DIR / f"{request_id}.json"
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if target.is_file():
            try:
                return json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # Partial write — wait for next tick
                pass
        time.sleep(interval_sec)
    return None


def mailbox_worker_once() -> int:
    """
    Single-pass worker: drains every unhandled outbox request, calls grok_review,
    writes the result to inbox. Returns the number of requests processed.

    Designed to be invoked by a systemd timer or a simple while-true loop in
    titan-channel.ts. Idempotent: already-handled requests (inbox entry exists)
    are skipped.
    """
    _ensure_mailbox()
    processed = 0
    for req_file in sorted(OUTBOX_DIR.glob("req-*.json")):
        req_id = req_file.stem
        out_file = INBOX_DIR / f"{req_id}.json"
        if out_file.is_file():
            continue
        try:
            payload = json.loads(req_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        try:
            result = grok_review(
                payload["artifact_path"],
                rubric=payload.get("rubric", "war-room-10d"),
                context_paths=payload.get("context_paths"),
            )
            result["request_id"] = req_id
            out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
            processed += 1
        except Exception as exc:  # pragma: no cover — runtime safety net
            err = {
                "request_id": req_id,
                "error": str(exc),
                "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "policy_version": POLICY_VERSION,
            }
            out_file.write_text(json.dumps(err, indent=2), encoding="utf-8")
            processed += 1
    return processed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Secondary-AI doctrine/plan reviewer (Grok or sonar fallback)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("review", help="synchronously review an artifact and print JSON result")
    r.add_argument("--artifact", required=True)
    r.add_argument("--rubric", default="war-room-10d")
    r.add_argument("--context", default="", help="comma-separated extra code-context paths")
    r.add_argument("--no-mcp", action="store_true")

    d = sub.add_parser("drop", help="write request to mailbox outbox and print request_id")
    d.add_argument("--artifact", required=True)
    d.add_argument("--rubric", default="war-room-10d")
    d.add_argument("--context", default="")

    p = sub.add_parser("poll", help="poll inbox for a result")
    p.add_argument("--request-id", required=True)
    p.add_argument("--timeout-sec", type=int, default=300)

    sub.add_parser("drain", help="single-pass worker: process every unhandled outbox request")
    sub.add_parser("selftest", help="end-to-end smoke: drop a dummy artifact, drain, assert inbox write")

    args = ap.parse_args()

    if args.cmd == "review":
        extra = [x.strip() for x in args.context.split(",") if x.strip()]
        result = grok_review(
            args.artifact,
            rubric=args.rubric,
            context_paths=extra,
            include_mcp_snippets=(not args.no_mcp),
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("cleared_a_grade") else 3  # exit 3 = graded, sub-A

    if args.cmd == "drop":
        extra = [x.strip() for x in args.context.split(",") if x.strip()]
        req_id = outbox_drop(args.artifact, rubric=args.rubric, context_paths=extra)
        print(req_id)
        return 0

    if args.cmd == "poll":
        result = inbox_poll(args.request_id, timeout_sec=args.timeout_sec)
        if result is None:
            print(json.dumps({"status": "timeout", "request_id": args.request_id}))
            return 4
        print(json.dumps(result, indent=2))
        return 0

    if args.cmd == "drain":
        n = mailbox_worker_once()
        print(json.dumps({"processed": n}))
        return 0

    if args.cmd == "selftest":
        # Dummy artifact in /tmp, drop, drain (will fail LiteLLM call without creds,
        # but must still write an error entry to inbox — verifies the mailbox loop).
        dummy = Path(f"/tmp/grok_review_selftest_{int(time.time())}.md")
        dummy.write_text(
            "# Dummy selftest artifact\n\nThis file exists only to exercise the mailbox loop.\n",
            encoding="utf-8",
        )
        req_id = outbox_drop(str(dummy), rubric="war-room-10d")
        print(f"dropped: {req_id}", file=sys.stderr)
        n = mailbox_worker_once()
        print(f"drained: {n}", file=sys.stderr)
        poll = inbox_poll(req_id, timeout_sec=5, interval_sec=0.5)
        if poll is None:
            print(json.dumps({"selftest": "FAIL", "reason": "no inbox entry"}))
            return 1
        print(json.dumps({"selftest": "PASS", "request_id": req_id, "inbox_keys": sorted(poll.keys())}))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
