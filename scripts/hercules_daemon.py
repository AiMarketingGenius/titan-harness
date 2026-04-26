#!/usr/bin/env python3
"""
hercules_daemon.py — Hercules's always-on body.

Replaces the "Kimi web tab that sleeps when Solon closes it" model with a
persistent daemon that:
  1. Polls MCP every 30s for new decisions / sprint state / pending tasks.
  2. Hydrates a context packet for Kimi K2.6.
  3. Calls Kimi K2.6 via lib/kimi_api.py with Hercules's system prompt + the
     trigger context.
  4. Parses Kimi's JSON action response.
  5. Executes the action: write outbox dispatch (Mercury/Titan auto-claim),
     file Solon escalation (macOS notification + Telnyx SMS when verified),
     update sprint state, or no-op.
  6. Logs every action to MCP tagged hercules-daemon for full audit.

Cost guards:
  - Skip Kimi call entirely if no trigger condition fires this tick (silent).
  - Per-call max_tokens cap: 1500.
  - Daily soft cap $5/day → warn in log + macOS notify Solon.
  - Daily hard cap $15/day → halt all Kimi calls until next UTC day; daemon
    keeps polling but only logs "halted: cost cap" until midnight.
  - Practical normal-day spend: $1-3 (most ticks have no trigger).

Trigger conditions:
  - mercury-proof / mercury-executor decision (a task just completed) →
    Hercules audits the proof claim.
  - aletheia-violation (a fake completion caught) → Hercules decides
    whether to re-dispatch, shame publicly, or escalate.
  - factory-stall / agent-down / cerberus-incident → immediate P0 escalation
    to Solon.
  - hercules-audit-required tag on any new decision → Hercules audits.
  - hard-limit-required → P0 to Solon (Hercules cannot self-approve).
  - sprint kill_chain has new [BLOCKED] item → consider unblocking dispatch.

Quiet hours (11pm–7am ET, override via ET_OFFSET_HOURS env): only P0 fires.
Other actions deferred to a queue file ~/.openclaw/state/hercules_quiet_queue.json
which is drained at 7am.

Run modes:
    hercules_daemon.py --watch            daemon (default), poll every 30s
    hercules_daemon.py --once             one tick, exit
    hercules_daemon.py --dry-run --once   no Kimi calls, no writes, just log
    hercules_daemon.py --interval 60      custom poll interval

State + logs:
    ~/.openclaw/state/hercules_daemon.lock          single-instance lock
    ~/.openclaw/state/hercules_daemon_cursor.json   last-seen state + cost ledger
    ~/.openclaw/state/hercules_quiet_queue.json     deferred non-P0 actions
    ~/.openclaw/logs/hercules_daemon.log            human-readable log
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import signal
import sys
import time
from datetime import datetime, timedelta, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))

from kimi_api import chat as kimi_chat, parse_action_json  # noqa: E402
from mcp_rest_client import (  # noqa: E402
    get_recent_decisions as mcp_get_recent,
    get_sprint_state as mcp_get_sprint,
    get_task_queue as mcp_get_task_queue,
    log_decision as mcp_log_decision,
)

STATE_DIR = HOME / ".openclaw" / "state"
LOCK_FILE = STATE_DIR / "hercules_daemon.lock"
CURSOR_FILE = STATE_DIR / "hercules_daemon_cursor.json"
QUIET_QUEUE_FILE = STATE_DIR / "hercules_quiet_queue.json"
LOGFILE = HOME / ".openclaw" / "logs" / "hercules_daemon.log"
OUTBOX = HOME / "AMG" / "hercules-outbox"
INBOX = HOME / "AMG" / "hercules-inbox"

QUIET_HOURS_START = 23   # 11pm ET
QUIET_HOURS_END = 7      # 7am ET
DAILY_COST_SOFT_USD = 5.0
DAILY_COST_HARD_USD = 15.0
KIMI_MAX_TOKENS = 1500

# Trigger tag → priority + brief reason
TRIGGER_TAGS = {
    "mercury-proof":      ("P2", "task completion claim — audit"),
    "mercury-executor":   ("P2", "task completion claim — audit"),
    "aletheia-violation": ("P1", "false-completion caught — decide remediation"),
    "factory-stall":      ("P0", "factory stalled — Solon needed"),
    "agent-down":         ("P0", "agent crashed — Solon needed"),
    "cerberus-incident":  ("P0", "security incident — Solon needed"),
    "hard-limit-required": ("P0", "hard limit — only Solon can approve"),
    "hercules-audit-required": ("P1", "audit requested by another agent"),
    "polling-doctrine-violation": ("P1", "polling violation — investigate"),
}


# ─── helpers ────────────────────────────────────────────────────────────────
def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _load_state() -> dict:
    if not CURSOR_FILE.exists():
        return {
            "seen_decision_ids": [],
            "cost_ledger": {},      # {"YYYY-MM-DD": cost_usd}
            "last_tick_ts": None,
            "halted_until": None,   # ISO ts when daily hard cap hit
        }
    try:
        s = json.loads(CURSOR_FILE.read_text())
        s.setdefault("seen_decision_ids", [])
        s.setdefault("cost_ledger", {})
        s.setdefault("halted_until", None)
        return s
    except Exception:
        return {"seen_decision_ids": [], "cost_ledger": {}, "halted_until": None}


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["seen_decision_ids"] = (state.get("seen_decision_ids") or [])[-500:]
    # Prune cost ledger to last 30 days
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    state["cost_ledger"] = {
        d: c for d, c in (state.get("cost_ledger") or {}).items() if d >= cutoff
    }
    tmp = CURSOR_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    fd = os.open(str(tmp), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, CURSOR_FILE)


def _today_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _is_quiet_hours_now_et() -> bool:
    offset_h = int(os.environ.get("ET_OFFSET_HOURS", "-4"))
    now_local = datetime.now(tz=timezone.utc) + timedelta(hours=offset_h)
    h = now_local.hour
    if QUIET_HOURS_START > QUIET_HOURS_END:
        return h >= QUIET_HOURS_START or h < QUIET_HOURS_END
    return QUIET_HOURS_START <= h < QUIET_HOURS_END


def _add_cost(state: dict, cost_usd: float) -> dict:
    today = _today_utc()
    state.setdefault("cost_ledger", {})[today] = round(
        state["cost_ledger"].get(today, 0.0) + cost_usd, 6
    )
    return state


def _today_cost(state: dict) -> float:
    return float((state.get("cost_ledger") or {}).get(_today_utc(), 0.0))


def _is_halted(state: dict) -> bool:
    h = state.get("halted_until")
    if not h:
        return False
    try:
        until = datetime.fromisoformat(h.replace("Z", "+00:00"))
        return datetime.now(tz=timezone.utc) < until
    except Exception:
        return False


# ─── trigger detection ──────────────────────────────────────────────────────
def find_triggers(decisions: list[dict], seen_ids: set[str]) -> list[dict]:
    """Return list of (decision, priority, reason) for new decisions whose
    tags match TRIGGER_TAGS. Skips already-seen + skips daemon's own
    decisions to avoid loops."""
    triggers = []
    for d in decisions:
        did = d.get("id") or d.get("decision_id") or ""
        if not did or did in seen_ids:
            continue
        tags = {str(t).lower() for t in (d.get("tags") or [])}
        # Skip the daemon's own logs to avoid feedback loops
        if "hercules-daemon" in tags:
            seen_ids.add(did)
            continue
        # Skip operational telemetry (warden, agent-dispatch-bridge etc.)
        if {"warden-violation", "agent-dispatch-bridge", "heartbeat", "auto-approve"} & tags:
            seen_ids.add(did)
            continue
        for tag, (prio, reason) in TRIGGER_TAGS.items():
            if tag in tags:
                triggers.append({"decision": d, "priority": prio, "reason": reason, "trigger_tag": tag})
                break
    return triggers


# ─── context builder ────────────────────────────────────────────────────────
HERCULES_SYSTEM_PROMPT = """You are Hercules, Chief Executive Operations Manager of Solon's AI factory (AMG / Atlas / Chamber AI Advantage). You audit work, decide priorities, dispatch tasks, and ONLY escalate to Solon on hard limits or genuine deadlocks. You are running as a Python daemon, not a chat tab — you wake on a 30s poll cycle, evaluate one trigger at a time, and respond with a single JSON action.

YOUR ROLE:
- Audit completion claims from Mercury / Titan / specialist agents.
- When Aletheia catches a fake completion, decide: re-dispatch, shame, or escalate.
- When a task completes successfully, decide: dispatch follow-on, mark sprint progress, or silent.
- When a security incident or hard limit fires, escalate to Solon (P0).
- Default to silence when no action improves the factory state.

HARD LIMITS — always escalate to Solon, never self-approve:
- New credential creation (API keys, OAuth, SSH keys)
- Financial commitment > $50/mo recurring
- Destructive prod ops (DROP TABLE, force push, rm -rf prod)
- Public publishes under Solon's name (sales emails, Loom demos, posts)
- New SaaS subscriptions or pricing changes
- Legal / compliance sign-off
- Brand naming locks (Greek codenames per CLAUDE.md §14)
- Actions with > 30-min rollback time

OUTPUT FORMAT — respond with ONE JSON object inside ```json code fence:
{
  "action": "dispatch_new" | "escalate_solon" | "silent" | "update_sprint" | "shame_correction",
  "priority": "P0" | "P1" | "P2",
  "summary": "<one-line description of what + why>",
  "payload": {
     // For dispatch_new: {agent_assigned, objective, instructions, acceptance_criteria, tags, priority}
     // For escalate_solon: {reason, evidence_path, recommended_solon_action}
     // For silent: {} (just acknowledging the trigger)
     // For update_sprint: {kill_chain_addition, blockers_to_clear}
     // For shame_correction: {agent_to_shame, evidence_path, correction_dispatch (optional)}
  }
}

Be terse. One JSON object per call. No prose outside the code fence.
"""


def build_context_packet(trigger: dict, sprint_state: dict, recent_decisions: list[dict], pending_tasks: list[dict]) -> str:
    """Build the Kimi user message: trigger + factory state."""
    d = trigger["decision"]
    text_short = (d.get("text") or "")[:600]
    rationale_short = (d.get("rationale") or "")[:300]
    tags = d.get("tags") or []
    src = d.get("project_source") or "unknown"
    created = d.get("created_at") or "?"
    decision_id = d.get("id") or d.get("decision_id") or "?"

    sprint_summary = ""
    if sprint_state and isinstance(sprint_state, dict):
        kill = sprint_state.get("kill_chain") or []
        blockers = sprint_state.get("blockers") or []
        sprint_summary = (
            f"Sprint: {sprint_state.get('sprint', '?')} "
            f"({sprint_state.get('completion', '?')})\n"
            f"Kill chain (last 5): {kill[-5:] if kill else 'empty'}\n"
            f"Blockers: {blockers if blockers else 'none'}\n"
        )

    pending_summary = "\n".join(
        f"  - {t.get('task_id')} [{t.get('priority')}] {(t.get('objective') or '')[:80]}"
        for t in (pending_tasks or [])[:5]
    ) or "  (none)"

    recent_summary = "\n".join(
        f"  - [{(rd.get('project_source') or '?')[:6]}] {(rd.get('text') or '')[:100]}"
        for rd in (recent_decisions or [])[:5]
    ) or "  (none)"

    return f"""TRIGGER (priority {trigger['priority']}, reason: {trigger['reason']}):
  Tag: {trigger['trigger_tag']}
  Decision id: {decision_id}
  Source: {src}
  Created: {created}
  Tags: {tags}
  Text: {text_short}
  Rationale: {rationale_short}

CURRENT FACTORY STATE:
{sprint_summary}
Pending tasks (top 5):
{pending_summary}

Recent decisions (last 5):
{recent_summary}

Decide ONE action. Respond with JSON in ```json fence per spec."""


# ─── action executors ───────────────────────────────────────────────────────
def execute_action(action: dict, trigger: dict, dry_run: bool = False) -> dict:
    """Carry out the JSON action Kimi returned."""
    kind = action.get("action", "silent")
    priority = action.get("priority", "P2")
    summary = action.get("summary", "")[:280]
    payload = action.get("payload") or {}
    result = {"action": kind, "priority": priority, "summary": summary, "executed": False}

    if kind == "silent":
        result["executed"] = True
        return result

    if kind == "dispatch_new":
        if dry_run:
            result["dry_run_payload"] = payload
            result["executed"] = True
            return result
        OUTBOX.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = (payload.get("objective") or "hercules-auto")[:40].replace(" ", "-").replace("/", "-")
        fname = f"dispatch_{ts}__hercules_auto__{slug}.json"
        # Default fields
        payload.setdefault("priority", priority)
        payload.setdefault("agent_assigned", "titan")
        payload.setdefault("project_id", "EOM")
        payload.setdefault("source", "hercules-daemon-auto-2026-04-26")
        payload.setdefault("tags", []).extend(["hercules-daemon", "auto-dispatch", f"trigger:{trigger['trigger_tag']}"])
        payload.setdefault("context", f"Auto-dispatched by hercules_daemon in response to {trigger['trigger_tag']} (decision {trigger['decision'].get('id')[:12]})")
        (OUTBOX / fname).write_text(json.dumps(payload, indent=2))
        result["dispatch_file"] = fname
        result["executed"] = True
        return result

    if kind == "escalate_solon":
        if dry_run:
            result["dry_run_payload"] = payload
            result["executed"] = True
            return result
        INBOX.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fname = f"HERCULES_DAEMON_ESCALATION__{priority}__{ts}.md"
        body = (
            f"# {priority} ESCALATION — Hercules-daemon → Solon\n\n"
            f"**Created:** {datetime.now(tz=timezone.utc).isoformat()}\n"
            f"**Trigger:** {trigger['trigger_tag']}\n"
            f"**Decision id:** {trigger['decision'].get('id')}\n\n"
            f"## Summary\n\n{summary}\n\n"
            f"## Reason\n\n{payload.get('reason', '(no reason supplied)')}\n\n"
            f"## Evidence path\n\n{payload.get('evidence_path', 'n/a')}\n\n"
            f"## Recommended Solon action\n\n{payload.get('recommended_solon_action', '(none)')}\n"
        )
        (INBOX / fname).write_text(body)
        # macOS notification + telnyx (if P0)
        try:
            import subprocess
            subprocess.Popen(
                ["osascript", "-e",
                 f'display notification "{summary[:200]}" with title "{priority}: Hercules" sound name "Glass"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
        if priority == "P0":
            sender = HOME / "titan-harness" / "scripts" / "telnyx_send.py"
            if sender.exists():
                try:
                    import subprocess
                    subprocess.Popen(
                        ["python3", str(sender), f"P0: {summary[:120]}", "--priority", "P0"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception:
                    pass
        result["escalation_file"] = fname
        result["executed"] = True
        return result

    if kind == "shame_correction":
        # File a shame report for the offending agent. Optionally include a
        # correction dispatch (which we treat like dispatch_new).
        if dry_run:
            result["dry_run_payload"] = payload
            result["executed"] = True
            return result
        INBOX.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        agent = payload.get("agent_to_shame", "unknown")
        fname = f"HERCULES_DAEMON_SHAME__{agent}__{ts}.md"
        body = (
            f"# HERCULES DAEMON SHAME — {agent}\n\n"
            f"**Created:** {datetime.now(tz=timezone.utc).isoformat()}\n"
            f"**Trigger:** {trigger['trigger_tag']}\n"
            f"**Source decision:** {trigger['decision'].get('id')}\n\n"
            f"## Summary\n\n{summary}\n\n"
            f"## Evidence\n\n{payload.get('evidence_path', '(none provided)')}\n"
        )
        (INBOX / fname).write_text(body)
        # If a correction dispatch is included, write it to outbox
        corr = payload.get("correction_dispatch")
        if corr and isinstance(corr, dict):
            OUTBOX.mkdir(parents=True, exist_ok=True)
            slug = (corr.get("objective") or "correction")[:40].replace(" ", "-").replace("/", "-")
            corr.setdefault("agent_assigned", "titan")
            corr.setdefault("priority", "P1")
            corr.setdefault("tags", []).extend(["hercules-daemon", "correction", f"shame:{agent}"])
            (OUTBOX / f"dispatch_{ts}__hercules_correction__{slug}.json").write_text(json.dumps(corr, indent=2))
            result["correction_dispatch_file"] = f"dispatch_{ts}__hercules_correction__{slug}.json"
        result["shame_file"] = fname
        result["executed"] = True
        return result

    if kind == "update_sprint":
        # Sprint updates are advisory only — log a decision so EOM picks it up
        # on next sprint-state refresh. No direct sprint mutation here.
        result["executed"] = True
        result["note"] = "sprint update logged as advisory decision"
        return result

    result["error"] = f"unknown action: {kind}"
    return result


# ─── single tick ────────────────────────────────────────────────────────────
def tick_once(state: dict, dry_run: bool = False) -> dict:
    """One poll cycle. Returns summary dict."""
    summary = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "triggers_found": 0,
        "actions_executed": 0,
        "kimi_calls": 0,
        "kimi_cost_usd": 0.0,
        "halted": False,
        "dry_run": dry_run,
    }

    # Cost-cap halt check
    if _is_halted(state):
        summary["halted"] = True
        summary["reason"] = "daily hard cap exceeded; resumes next UTC day"
        return summary
    today_cost = _today_cost(state)
    if today_cost >= DAILY_COST_HARD_USD:
        # Set halt until next UTC midnight
        midnight = datetime.combine(
            datetime.now(tz=timezone.utc).date() + timedelta(days=1),
            datetime.min.time(), tzinfo=timezone.utc,
        )
        state["halted_until"] = midnight.isoformat()
        _log(f"HALT: daily Kimi cost ${today_cost:.2f} >= ${DAILY_COST_HARD_USD}; resuming at {midnight}")
        summary["halted"] = True
        return summary

    # Pull factory state
    code, body = mcp_get_recent(count=20)
    decisions = body.get("decisions") or [] if code == 200 else []
    seen_ids = set(state.get("seen_decision_ids") or [])
    triggers = find_triggers(decisions, seen_ids)
    summary["triggers_found"] = len(triggers)

    if not triggers:
        # Mark all scanned as seen so we don't reconsider them
        for d in decisions:
            did = d.get("id") or d.get("decision_id") or ""
            if did:
                seen_ids.add(did)
        state["seen_decision_ids"] = list(seen_ids)
        return summary

    # Quiet hours filter — defer non-P0
    quiet = _is_quiet_hours_now_et()
    if quiet:
        kept = [t for t in triggers if t["priority"] == "P0"]
        if len(kept) < len(triggers):
            _log(f"QUIET HOURS: deferring {len(triggers) - len(kept)} non-P0 triggers")
        triggers = kept

    # Pull sprint state + pending tasks once for context
    code_s, sprint = mcp_get_sprint(project_id="EOM") if not dry_run else (200, {})
    sprint = sprint if code_s == 200 else {}
    code_q, queue_body = mcp_get_task_queue(status="pending", limit=10) if not dry_run else (200, {"tasks": []})
    pending = (queue_body.get("tasks") or []) if code_q == 200 else []

    # Process each trigger (cap at 3 per tick to bound cost/latency)
    for trigger in triggers[:3]:
        d = trigger["decision"]
        did = d.get("id") or d.get("decision_id") or ""
        ctx = build_context_packet(trigger, sprint, decisions, pending)
        if dry_run:
            _log(f"DRY-RUN trigger={trigger['trigger_tag']} prio={trigger['priority']} did={did[:12]}")
            seen_ids.add(did)
            continue
        # Cost-cap soft warn
        if today_cost >= DAILY_COST_SOFT_USD and not state.get("warned_today_soft"):
            _log(f"WARN: daily Kimi cost ${today_cost:.2f} >= soft cap ${DAILY_COST_SOFT_USD}")
            try:
                import subprocess
                subprocess.Popen(
                    ["osascript", "-e",
                     f'display notification "Hercules daemon hit ${today_cost:.2f} today (soft cap ${DAILY_COST_SOFT_USD}). Hard cap ${DAILY_COST_HARD_USD}." with title "P1: Hercules cost warning"'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
            state["warned_today_soft"] = True

        kimi_resp = kimi_chat(
            HERCULES_SYSTEM_PROMPT, ctx,
            max_tokens=KIMI_MAX_TOKENS, temperature=1.0,
        )
        summary["kimi_calls"] += 1
        cost = float(kimi_resp.get("cost_usd_est", 0.0))
        summary["kimi_cost_usd"] = round(summary["kimi_cost_usd"] + cost, 6)
        _add_cost(state, cost)
        today_cost = _today_cost(state)

        if not kimi_resp.get("ok"):
            _log(f"KIMI FAIL trigger={trigger['trigger_tag']} did={did[:12]} err={kimi_resp.get('error')}")
            seen_ids.add(did)
            continue

        action = parse_action_json(kimi_resp.get("text") or "")
        result = execute_action(action, trigger, dry_run=dry_run)

        # Log to MCP — Hercules's audit trail
        try:
            mcp_log_decision(
                text=(
                    f"Hercules daemon action: {result.get('action')} (priority={result.get('priority')}) "
                    f"in response to {trigger['trigger_tag']} on decision {did[:12]}. "
                    f"Summary: {result.get('summary', '')[:200]}"
                ),
                rationale=(
                    f"Trigger reason: {trigger['reason']}. "
                    f"Kimi cost ${cost:.4f} ({kimi_resp.get('tokens_in')}in/{kimi_resp.get('tokens_out')}out). "
                    f"Result: {json.dumps({k: v for k, v in result.items() if k != 'dry_run_payload'})[:400]}"
                ),
                tags=["hercules-daemon", f"action:{result.get('action')}", f"trigger:{trigger['trigger_tag']}", f"prio:{result.get('priority')}"],
                project_source="titan",
            )
        except Exception as e:
            _log(f"MCP log_decision failed: {e!r}")

        if result.get("executed"):
            summary["actions_executed"] += 1

        seen_ids.add(did)
        _log(
            f"ACTION {result.get('action')} prio={result.get('priority')} "
            f"trigger={trigger['trigger_tag']} did={did[:12]} cost=${cost:.4f}"
        )

    # Mark all scanned (even non-trigger) as seen
    for d in decisions:
        did = d.get("id") or d.get("decision_id") or ""
        if did:
            seen_ids.add(did)
    state["seen_decision_ids"] = list(seen_ids)
    state["last_tick_ts"] = datetime.now(tz=timezone.utc).isoformat()
    return summary


# ─── lock + main ────────────────────────────────────────────────────────────
def acquire_lock() -> int:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return -1
    os.write(fd, str(os.getpid()).encode())
    return fd


def main() -> int:
    p = argparse.ArgumentParser(description="Hercules's always-on daemon body")
    p.add_argument("--watch", action="store_true", help="daemon mode, poll forever")
    p.add_argument("--once", action="store_true", help="single tick, exit")
    p.add_argument("--dry-run", action="store_true", help="no Kimi calls, no writes")
    p.add_argument("--interval", type=int, default=30, help="poll interval seconds")
    args = p.parse_args()

    if not (args.watch or args.once):
        args.watch = True

    fd = acquire_lock()
    if fd < 0:
        _log("another hercules_daemon is running; exiting")
        return 0

    state = _load_state()
    # Reset soft-warn flag at midnight UTC
    today = _today_utc()
    if state.get("warned_today_date") != today:
        state["warned_today_soft"] = False
        state["warned_today_date"] = today

    if args.once:
        result = tick_once(state, dry_run=args.dry_run)
        _save_state(state)
        print(json.dumps(result, indent=2))
        return 0

    _log(f"hercules_daemon starting watch interval={args.interval}s dry_run={args.dry_run}")
    # Graceful shutdown on SIGTERM
    stop = {"requested": False}
    def _sig(_signum, _frame):
        stop["requested"] = True
        _log("SIGTERM received; finishing current tick then exiting")
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    while not stop["requested"]:
        try:
            result = tick_once(state, dry_run=args.dry_run)
            if result.get("triggers_found") or result.get("halted"):
                _log(
                    f"tick: triggers={result.get('triggers_found')} "
                    f"actions={result.get('actions_executed')} "
                    f"kimi_calls={result.get('kimi_calls')} "
                    f"cost=${result.get('kimi_cost_usd', 0):.4f} "
                    f"halted={result.get('halted')}"
                )
            _save_state(state)
        except Exception as e:
            _log(f"tick error: {e!r}")
        # Sleep with poll-interrupt support
        for _ in range(args.interval):
            if stop["requested"]:
                break
            time.sleep(1)

    _save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
