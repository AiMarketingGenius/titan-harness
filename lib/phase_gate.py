#!/usr/bin/env python3
"""phase_gate.py — DeepSeek V4 Pro single-judge phase gate (interim, pre-Phase 13).

DIR-009 doctrine update 2026-04-29: Phases 1-10 use DeepSeek V4 Pro single-judge
≥9.5 mode with $5 budget cap until Phase 12-13 ships /api/v1/judge/phase-grade.

Usage:
  python3 lib/phase_gate.py --phase 3 --task CT-0429-04 \
    --artifacts plans/dir-009/PHASE_3_GATE_EVIDENCE.md outputs/AGENT_CONFIG_AUDIT.md \
    --output-dir plans/dir-009 \
    --vps-output-dir /opt/amg-titan/reports/dir-009 \
    --threshold 9.5

Reads:
  $DEEPSEEK_API_KEY + $DEEPSEEK_BASE_URL — from /etc/amg/deepseek.env or local env
  --artifacts ... — paths to deliverable files (concatenated as the artifact body)

Writes:
  <output-dir>/PHASE_<N>_GATE_EVIDENCE.md — formatted gate evidence with scores

Cost ledger:
  ~/titan-session/grader-cost-ledger.json — appends one entry per call with cents,
  enforces a daily $5 cap (configurable via --budget-cap-cents).

Exit codes:
  0 — pass (composite ≥ threshold and no dim < 9.0)
  1 — fail (revise + regrade)
  2 — error (API / parse / budget)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DIMENSIONS = [
    "clarity", "technical", "completeness", "risk", "amg_fit",
    "acceptance", "idempotency",
]

RUBRIC_SYSTEM = """You are an AMG production-engineering grader. You judge phase deliverables against a 7-dimension rubric on a 0-10 scale (0.1 precision). You are hostile-but-fair: you score what is actually shown, not what is claimed.

Dimensions (give a single 0.0-10.0 number for each):
1. clarity — naming, structure, readability, no ambiguity
2. technical — correctness, robustness, error handling, no obvious bugs
3. completeness — all stated acceptance criteria addressed; no half-finished work
4. risk — blast radius, idempotency, rollback availability, no destructive surprises
5. amg_fit — adheres to AMG doctrines (existing-substrate-over-new-SaaS, WoZ, public-canon pricing, trade-secret rule)
6. acceptance — explicit acceptance criteria from the parent task are demonstrably met or honestly documented as deferred
7. idempotency — re-running produces same result, no state mutation surprises

Output JSON ONLY (no prose, no markdown), with this exact shape:
{
  "scores": {"clarity": 9.4, "technical": 9.3, "completeness": 9.5, "risk": 9.4, "amg_fit": 9.5, "acceptance": 9.3, "idempotency": 9.5},
  "composite": 9.41,
  "verdict": "pass|fail",
  "rationale": "1-3 sentences explaining the lowest dimension and any caveats"
}

Threshold: composite >= 9.5 AND no dim < 9.0 = pass. Else fail.
"""


def _env(key: str, default: str = "") -> str:
    val = os.environ.get(key, default)
    return val.strip() if val else default


def _load_deepseek_env():
    # Allow caller to source /etc/amg/deepseek.env first, then ~/.titan-env, then process env.
    for path in ("/etc/amg/deepseek.env", os.path.expanduser("~/.titan-env")):
        if os.path.isfile(path):
            try:
                for line in open(path, "r", encoding="utf-8"):
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and not os.environ.get(k):
                        os.environ[k] = v
            except OSError:
                pass


def _read_ledger(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"entries": []}


def _write_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2))


def _today_cents(ledger: dict) -> int:
    today = dt.date.today().isoformat()
    return sum(e["cents"] for e in ledger.get("entries", []) if e.get("date") == today)


def _call_deepseek(system: str, user: str, base_url: str, key: str, model: str, timeout: int = 90):
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "max_tokens": 800,
    }).encode("utf-8")
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _estimate_cents(usage: dict) -> int:
    # DeepSeek V4 Pro pricing approx (as of 2026-04): ~$0.27/1M input, $1.10/1M output (cache miss).
    # Convert to cents with cache-miss assumption (conservative).
    p_in = usage.get("prompt_tokens", 0)
    p_out = usage.get("completion_tokens", 0)
    cents = (p_in * 27 + p_out * 110) / 1_000_000  # cents
    return max(1, int(round(cents)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, required=True)
    ap.add_argument("--task", default="CT-0429-04")
    ap.add_argument("--artifacts", nargs="+", required=True)
    ap.add_argument("--output-dir", default="plans/dir-009")
    ap.add_argument("--vps-output-dir", default="/opt/amg-titan/reports/dir-009")
    ap.add_argument("--threshold", type=float, default=9.5)
    ap.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
    ap.add_argument("--budget-cap-cents", type=int, default=500)
    args = ap.parse_args()

    _load_deepseek_env()
    key = _env("DEEPSEEK_API_KEY")
    base_url = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not key:
        print("phase_gate: ERROR — DEEPSEEK_API_KEY not in env", file=sys.stderr)
        return 2

    # Cost ledger + cap
    ledger_path = Path.home() / "titan-session" / "grader-cost-ledger.json"
    ledger = _read_ledger(ledger_path)
    today_cents = _today_cents(ledger)
    if today_cents >= args.budget_cap_cents:
        print(f"phase_gate: BUDGET_CAP_HIT today={today_cents}c cap={args.budget_cap_cents}c", file=sys.stderr)
        return 2

    # Read + concatenate artifacts
    body_parts = [f"# PHASE {args.phase} ARTIFACT BUNDLE — {args.task}\n"]
    for path in args.artifacts:
        p = Path(path)
        if not p.is_file():
            print(f"phase_gate: WARN — artifact missing: {path}", file=sys.stderr)
            continue
        body_parts.append(f"\n\n## ARTIFACT: {path}\n\n{p.read_text(errors='replace')}\n")
    user_msg = "".join(body_parts)
    if len(user_msg) > 60_000:
        # Truncate from the middle to keep both ends; mark truncation.
        head = user_msg[:30_000]
        tail = user_msg[-30_000:]
        user_msg = head + "\n\n... [middle truncated by phase_gate.py] ...\n\n" + tail

    # Call DeepSeek
    try:
        resp = _call_deepseek(RUBRIC_SYSTEM, user_msg, base_url, key, args.model)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        print(f"phase_gate: API_ERROR {exc}", file=sys.stderr)
        return 2

    usage = resp.get("usage", {})
    cents = _estimate_cents(usage)
    ledger["entries"].append({
        "date": dt.date.today().isoformat(),
        "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": args.phase, "task": args.task,
        "model": args.model, "cents": cents,
        "tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens"),
    })
    _write_ledger(ledger_path, ledger)

    # Parse rubric verdict
    try:
        content = resp["choices"][0]["message"]["content"]
        verdict = json.loads(content)
        scores = verdict["scores"]
        composite = float(verdict.get("composite") or sum(scores.values()) / len(DIMENSIONS))
        rationale = verdict.get("rationale", "")
        passed = composite >= args.threshold and all(scores.get(d, 0) >= 9.0 for d in DIMENSIONS)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"phase_gate: PARSE_ERROR {exc}\nRaw: {content[:500] if 'content' in locals() else '(no content)'}", file=sys.stderr)
        return 2

    # Write evidence
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"PHASE_{args.phase}_GATE_EVIDENCE.md"
    body = [
        f"# DIR-009 Phase {args.phase} — Gate Evidence (DeepSeek V4 Pro single-judge)",
        f"\n**Task:** {args.task}",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"**Model:** {args.model}",
        f"**Threshold:** composite ≥ {args.threshold} AND no dim < 9.0",
        f"**Cost this call:** ~{cents}¢ (today total: {today_cents + cents}¢ / cap {args.budget_cap_cents}¢)",
        "\n## Scores\n",
        "| Dimension | Score |",
        "|---|---|",
    ]
    for d in DIMENSIONS:
        body.append(f"| {d} | {scores.get(d, 'n/a')} |")
    body.append(f"\n**Composite:** {composite:.2f}")
    body.append(f"\n**Verdict:** **{'PASS' if passed else 'FAIL'}**")
    body.append(f"\n## Rationale\n\n{rationale}\n")
    body.append("\n## Artifacts graded\n")
    for path in args.artifacts:
        body.append(f"- `{path}`")
    out_path.write_text("\n".join(body))

    print(f"phase_gate: phase={args.phase} composite={composite:.2f} verdict={'PASS' if passed else 'FAIL'} cents={cents}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
