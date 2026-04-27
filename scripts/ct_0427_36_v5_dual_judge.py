#!/usr/bin/env python3
"""CT-0427-36 — v5.0 DRAFT dual-engine cheap-judge per §13 of the megaprompt.

Primary:   Kimi K2.6   — technical soundness + completeness (0-10)
Secondary: Gemini Flash — edge-case coverage + risk identification (0-10)

Floor 9.0/10 from BOTH (per megaprompt §13). Both >=9 -> lock.
Either <9 -> revise; list flagged sections from both judges.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from kimi_api import chat as kimi_chat  # noqa: E402

# Resolve Gemini key from ~/.titan-env if not in env
def _resolve_gemini_key() -> str:
    for k in ("GEMINI_API_KEY_AMG_GRADER", "GEMINI_API_KEY"):
        v = os.environ.get(k)
        if v:
            return v
    env_path = Path.home() / ".titan-env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY_AMG_GRADER=") or line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


KIMI_RUBRIC = """You are a rigorous technical reviewer evaluating a DRAFT megaprompt
that will dispatch a multi-week engineering migration. Score it 0-10 on
TECHNICAL SOUNDNESS and COMPLETENESS only (not edge-case coverage — that
is a separate reviewer's lane).

Dimensions (each 0-10):
1. technical_soundness — are the architectural decisions sound? Tier ladder
   coherent? Cost math accurate? Routing rules implementable? Acceptance
   criteria measurable? Dependencies sequenced correctly?
2. completeness — does it cover what the scope claims? Migration sequence,
   rollback paths, validation gates, cost discipline, IP-sovereignty? Are
   there hand-wave gaps where details should be?

Weight: 50% / 50%. Floor: 9.0/10 overall.

Output STRICT JSON, no markdown fences:
{
  "decision": "pass|revise",
  "overall_score_10": <0-10>,
  "technical_soundness": <0-10>,
  "completeness": <0-10>,
  "flagged_sections": ["§N — what's wrong", ...],
  "required_revisions": ["specific fix 1", ...],
  "reasoning": "two-sentence summary"
}

Be strict. 9.0+ means production-grade dispatchable. Most first drafts do not clear 9.0."""

GEMINI_RUBRIC = """You are a rigorous risk reviewer evaluating a DRAFT megaprompt
that will dispatch a multi-week engineering migration. Score it 0-10 on
EDGE-CASE COVERAGE and RISK IDENTIFICATION only (not technical soundness —
that's a separate reviewer's lane).

Dimensions (each 0-10):
1. edge_case_coverage — what failure modes are NOT handled? API outages,
   quality regressions during migration, cost-cap false trips, key rotation
   breakage, rollback path validation, partial-migration states, race
   conditions on parallel agent runs.
2. risk_identification — are the risk flags realistic? Severity ratings
   honest? Mitigations actually mitigate? Are there hidden risks not flagged
   (e.g. provider lock-in shifting from Anthropic to DeepSeek/Kimi, training-
   data exposure on flat-rate tiers, single-vendor SPOF on Aristotle)?

Weight: 50% / 50%. Floor: 9.0/10 overall.

Output STRICT JSON, no markdown fences:
{
  "decision": "pass|revise",
  "overall_score_10": <0-10>,
  "edge_case_coverage": <0-10>,
  "risk_identification": <0-10>,
  "flagged_sections": ["§N — risk gap or unrealistic mitigation", ...],
  "required_revisions": ["specific fix 1", ...],
  "reasoning": "two-sentence summary"
}

Be strict. 9.0+ means production-grade dispatchable. Most first drafts do not clear 9.0."""

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)


def call_gemini(model: str, system_prompt: str, user_message: str,
                max_tokens: int = 1500, temperature: float = 0.2,
                timeout_s: int = 90) -> dict:
    key = _resolve_gemini_key()
    if not key:
        return {"ok": False, "error": "no GEMINI_API_KEY in env or ~/.titan-env"}
    body = {
        "contents": [{
            "role": "user",
            "parts": [{"text": user_message}],
        }],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    url = GEMINI_ENDPOINT_TEMPLATE.format(model=model, key=key)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            data = json.loads(r.read())
        candidates = data.get("candidates") or []
        if not candidates:
            return {"ok": False, "error": f"no candidates: {data}", "raw": data}
        text = ""
        for part in candidates[0].get("content", {}).get("parts", []):
            text += part.get("text", "")
        return {
            "ok": True, "text": text, "raw": data,
            "latency_ms": int((time.time() - t0) * 1000),
        }
    except urllib.error.HTTPError as e:
        body = e.read()[:500].decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {e.code}: {body}",
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "latency_ms": int((time.time() - t0) * 1000)}


def parse_json_loose(text: str) -> dict | None:
    """Strip markdown fences, parse JSON. Returns None on failure."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # Try last-ditch: find first {...} block
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(t[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print("usage: ct_0427_36_v5_dual_judge.py <draft.md>", file=sys.stderr)
        return 2
    draft_path = Path(argv[0]).expanduser()
    if not draft_path.is_file():
        print(f"draft not found: {draft_path}", file=sys.stderr)
        return 2

    artifact = draft_path.read_text(encoding="utf-8")
    artifact_size = len(artifact)
    print(f"=== CT-0427-36 v5.0 dual-judge ===", file=sys.stderr)
    print(f"draft: {draft_path}  ({artifact_size:,} chars)", file=sys.stderr)
    print(file=sys.stderr)

    # ---- Kimi K2.6 (technical soundness + completeness) ----
    print("[1/2] Calling Kimi K2.6...", file=sys.stderr)
    user_msg = f"Megaprompt to grade:\n\n---START---\n{artifact}\n---END---"
    kimi_resp = kimi_chat(
        system_prompt=KIMI_RUBRIC,
        user_message=user_msg,
        max_tokens=8000,
        temperature=1.0,
        timeout_s=300,
    )
    if not kimi_resp.get("ok"):
        print(f"  KIMI ERROR: {kimi_resp.get('error')}", file=sys.stderr)
        kimi_score_obj = None
    else:
        kimi_score_obj = parse_json_loose(kimi_resp["text"])
        if not kimi_score_obj:
            finish = ((kimi_resp.get("raw") or {}).get("choices") or [{}])[0].get("finish_reason")
            print(f"  KIMI PARSE FAIL  finish={finish}  text_len={len(kimi_resp.get('text', ''))}",
                  file=sys.stderr)
            print(f"  raw text: {kimi_resp.get('text', '')[:500]!r}", file=sys.stderr)
        else:
            print(f"  Kimi score: {kimi_score_obj.get('overall_score_10')}/10  "
                  f"(tech={kimi_score_obj.get('technical_soundness')}, "
                  f"complete={kimi_score_obj.get('completeness')})  "
                  f"cost=${kimi_resp.get('cost_usd_est', 0):.4f}",
                  file=sys.stderr)

    # ---- Gemini (edge cases + risks) — retry chain: flash → flash-lite → pro ----
    print("[2/2] Calling Gemini (retry chain)...", file=sys.stderr)
    gem_resp = None
    gem_score_obj = None
    for attempt, model in enumerate(["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]):
        if attempt > 0:
            time.sleep(3)
        print(f"  attempt {attempt + 1}: {model}", file=sys.stderr)
        gem_resp = call_gemini(
            model=model,
            system_prompt=GEMINI_RUBRIC,
            user_message=user_msg,
            max_tokens=4000,
            temperature=0.2,
        )
        if not gem_resp.get("ok"):
            err = (gem_resp.get("error") or "")[:200]
            print(f"    err: {err}", file=sys.stderr)
            continue
        gem_score_obj = parse_json_loose(gem_resp["text"])
        if gem_score_obj:
            print(f"  Gemini ({model}) score: {gem_score_obj.get('overall_score_10')}/10  "
                  f"(edge={gem_score_obj.get('edge_case_coverage')}, "
                  f"risk={gem_score_obj.get('risk_identification')})",
                  file=sys.stderr)
            gem_resp["model_used"] = model
            break
        else:
            print(f"    parse fail, raw head: {gem_resp.get('text', '')[:200]!r}", file=sys.stderr)

    # ---- Decision ----
    floor = 9.0
    kimi_score = (kimi_score_obj or {}).get("overall_score_10", 0)
    gem_score = (gem_score_obj or {}).get("overall_score_10", 0)
    kimi_pass = isinstance(kimi_score, (int, float)) and kimi_score >= floor
    gem_pass = isinstance(gem_score, (int, float)) and gem_score >= floor
    if kimi_score_obj and gem_score_obj:
        if kimi_pass and gem_pass:
            decision = "lock_v5_0"
        else:
            decision = "revise"
    else:
        decision = "pending_review"

    output = {
        "task": "CT-0427-36",
        "artifact": str(draft_path),
        "floor": floor,
        "decision": decision,
        "kimi_k2_6": {
            "ok": bool(kimi_score_obj),
            "score": kimi_score,
            "passes_floor": kimi_pass,
            "details": kimi_score_obj,
            "cost_usd_est": kimi_resp.get("cost_usd_est"),
            "latency_ms": kimi_resp.get("latency_ms"),
            "error": kimi_resp.get("error"),
        },
        "gemini_2_5_flash": {
            "ok": bool(gem_score_obj),
            "score": gem_score,
            "passes_floor": gem_pass,
            "details": gem_score_obj,
            "latency_ms": gem_resp.get("latency_ms"),
            "error": gem_resp.get("error"),
        },
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if decision == "lock_v5_0" else (1 if decision == "revise" else 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
