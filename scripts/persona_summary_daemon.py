#!/usr/bin/env python3
"""persona_summary_daemon.py — rolling 24h conversation summary for the 3
Kimi chiefs (hercules, nestor, alexander).

Runs every 4 hours via launchd (com.amg.persona-summary-daemon). For each
persona:
  1. Read last 24h of sqlite conversation rows from ~/.openclaw/state/<persona>_convo.db
  2. Compress with Kimi K2 to ~500 words preserving open questions, decisions,
     blockers, next actions, named entities (clients, projects, files)
  3. Write to AMG Memory (op_decisions) with tag summary:<persona>:rolling_24h

The cold-start hydration in scripts/hercules_api_runner.py reads this summary
on every persona launch — gives Hercules a compressed memory of "what we've
been working on" without re-reading the full conversation log.

Cost: ~$0.005 per persona per run × 3 personas × 6 runs/day = ~$0.09/day.
Falls under the per-chief $5/day cap by 50x margin.

Run modes:
    persona_summary_daemon.py --once          # summarize all 3, exit
    persona_summary_daemon.py --persona X     # summarize one persona only
    persona_summary_daemon.py --watch         # daemon, run every --interval seconds (4h default)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from mcp_rest_client import log_decision as mcp_log_decision  # noqa: E402

KIMI_ENDPOINT = "https://api.moonshot.ai/v1/chat/completions"
MODEL = "kimi-k2.6"
PERSONAS = ("hercules", "nestor", "alexander")
STATE_DIR = HOME / ".openclaw" / "state"
LOG_FILE = HOME / ".openclaw" / "logs" / "persona_summary_daemon.log"
DEFAULT_INTERVAL_SEC = 4 * 60 * 60  # 4 hours
SSH_HOST = "amg-staging"

SUMMARY_PROMPT = """You are a memory compactor for AMG factory chiefs. Your job:
take the conversation log below for persona={persona} from the last 24 hours
and compress it to a ~500-word structured summary that preserves only the
load-bearing operational state.

OUTPUT FORMAT (markdown, no preamble):

## Open questions
- (one bullet per unanswered question or pending decision)

## Decisions made
- (one bullet per concrete decision, with rationale if non-obvious)

## Blockers
- (one bullet per active blocker — what is blocked, on whom, since when)

## Next actions
- (numbered list — concrete next steps the persona owns)

## Named entities
- Clients: ...
- Projects: ...
- Files / artifacts: ...
- Other people / agents referenced: ...

RULES:
- Keep it under 500 words total.
- Drop pleasantries, banter, exploratory ramblings, repeated context.
- Preserve specific numbers, dates, file paths, task IDs verbatim.
- If the log is empty or near-empty, return "## No material activity in last 24h."
"""


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def _resolve_kimi_key() -> str:
    for env_var in ("MOONSHOT_API_KEY", "KIMI_API_KEY"):
        v = os.environ.get(env_var)
        if v:
            return v
    out = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", SSH_HOST,
         "grep -E '^(MOONSHOT_API_KEY|KIMI_API_KEY)=' /etc/amg/moonshot.env 2>/dev/null | head -1 | cut -d= -f2-"],
        capture_output=True, text=True, timeout=15,
    )
    key = out.stdout.strip()
    if not key:
        local = HOME / ".config" / "amg" / "kimi.env"
        if local.exists():
            for line in local.read_text().splitlines():
                if line.startswith("MOONSHOT_API_KEY=") or line.startswith("KIMI_API_KEY="):
                    return line.split("=", 1)[1].strip()
        raise RuntimeError("Kimi API key not found")
    return key


def _convo_db(persona: str) -> pathlib.Path:
    return STATE_DIR / f"{persona}_convo.db"


def _load_last_24h(persona: str) -> list[dict]:
    """Pull conversation rows from this persona's sqlite db where ts >= now-24h.
    Returns user/assistant content only; tool calls + system messages are dropped
    (they're noise for the summary). Returns chronologically (oldest first)."""
    db = _convo_db(persona)
    if not db.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT ts, role, content FROM messages "
        "WHERE ts >= ? AND role IN ('user','assistant') AND content IS NOT NULL "
        "  AND content != '' "
        "  AND tool_calls_json IS NULL "
        "ORDER BY id ASC",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [{"ts": ts, "role": role, "content": content} for ts, role, content in rows]


def _build_log_text(messages: list[dict]) -> str:
    out: list[str] = []
    for m in messages:
        out.append(f"[{m['ts'][:19]} {m['role']}]")
        out.append(m["content"][:4000])
        out.append("")
    return "\n".join(out)


def _call_kimi(api_key: str, prompt: str) -> tuple[dict, str]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system",
             "content": "You compact long conversation logs into structured 500-word summaries. Output ONLY the markdown summary, no preamble."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
        # Kimi K2.6 enforces temperature=1 only — 0.x values return HTTP 400
        # invalid_request_error. Determinism is enforced by the prompt's
        # rigid format constraints (markdown headers + word cap), not temp.
        "temperature": 1,
    }
    req = urllib.request.Request(
        KIMI_ENDPOINT, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    choices = resp.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {resp}")
    msg = choices[0].get("message") or {}
    return resp, (msg.get("content") or "").strip()


def summarize_one(persona: str, api_key: str | None = None) -> dict:
    """Generate one rolling 24h summary for a single persona. Idempotent;
    safe to run repeatedly. Returns {ok, persona, message_count, summary, cost}."""
    if api_key is None:
        api_key = _resolve_kimi_key()
    msgs = _load_last_24h(persona)
    if not msgs:
        # Still write a "no activity" entry so cold-start hydration knows the
        # daemon ran and the persona was simply quiet.
        empty_text = f"## No material activity in last 24h.\n(generated {datetime.now(timezone.utc).isoformat()})"
        try:
            mcp_log_decision(
                text=f"summary:{persona}:rolling_24h — no activity in last 24h",
                rationale=empty_text,
                tags=[f"summary:{persona}:rolling_24h", "rolling-memory", "no-activity"],
                project_source=persona,
            )
        except Exception as e:
            _log(f"persona={persona} no-activity log_decision FAILED: {e!r}")
        _log(f"persona={persona} no messages in last 24h, logged 'no-activity' marker")
        return {"ok": True, "persona": persona, "message_count": 0,
                "summary": empty_text, "cost_usd": 0.0}

    log_text = _build_log_text(msgs)
    # Truncate to keep input reasonable (Kimi can handle ~128k context, but
    # 500 messages is plenty for a 24h window on chiefs that talk a lot).
    if len(log_text) > 80_000:
        log_text = log_text[-80_000:]
    prompt = SUMMARY_PROMPT.format(persona=persona) + "\n\n=== CONVERSATION LOG (last 24h) ===\n\n" + log_text

    try:
        resp, content = _call_kimi(api_key, prompt)
    except Exception as e:
        _log(f"persona={persona} Kimi call FAILED: {e!r}")
        return {"ok": False, "persona": persona, "error": repr(e)}

    usage = resp.get("usage") or {}
    cost = (usage.get("prompt_tokens", 0) * 0.55 + usage.get("completion_tokens", 0) * 2.20) / 1_000_000

    # Write to MCP. Tag with summary:<persona>:rolling_24h so cold-start
    # hydration finds it via search_memory. The 'rolling-memory' tag lets us
    # purge old entries en masse if the schema ever needs to change.
    try:
        mcp_log_decision(
            text=f"summary:{persona}:rolling_24h — {len(msgs)} messages compressed (${cost:.4f})",
            rationale=content[:3500],
            tags=[f"summary:{persona}:rolling_24h", "rolling-memory",
                  f"messages:{len(msgs)}", f"cost:${cost:.4f}"],
            project_source=persona,
        )
    except Exception as e:
        _log(f"persona={persona} log_decision FAILED: {e!r}")
        return {"ok": False, "persona": persona, "error": f"log_decision: {e!r}"}

    _log(f"persona={persona} summarized {len(msgs)} msgs cost=${cost:.4f} summary_len={len(content)}")
    return {"ok": True, "persona": persona, "message_count": len(msgs),
            "summary": content, "cost_usd": round(cost, 5)}


def run_all() -> list[dict]:
    api_key = _resolve_kimi_key()
    return [summarize_one(p, api_key=api_key) for p in PERSONAS]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true",
                   help="summarize all 3 personas once + exit")
    p.add_argument("--persona", choices=PERSONAS, default=None,
                   help="summarize a single persona only")
    p.add_argument("--watch", action="store_true",
                   help="daemon mode: run every --interval seconds")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SEC,
                   help="watch interval seconds (default 14400 = 4h)")
    args = p.parse_args()

    if args.persona:
        result = summarize_one(args.persona)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1

    if args.once or not args.watch:
        results = run_all()
        print(json.dumps(results, indent=2, default=str))
        return 0 if all(r.get("ok") for r in results) else 1

    _log(f"persona_summary_daemon starting watch interval={args.interval}s")
    while True:
        try:
            results = run_all()
            ok_count = sum(1 for r in results if r.get("ok"))
            _log(f"watch run: {ok_count}/{len(results)} OK")
        except Exception as e:
            _log(f"watch ERROR: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
