#!/usr/bin/env python3
"""
lib/intent_handlers.py
MP-3 §1 — Intent Handler Stubs for titan-bot

Each handler:
  1. Logs the command + parsed parameters to MCP (via Supabase log).
  2. Returns a structured Slack reply payload per MP-3 §1 return formats.

Handlers are stubs — correct structure/headers/sections but placeholder content.
Full data integration comes in later MP-3 checkpoints.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

from lib.intent_classifier import ClassifiedMessage, Intent


# --- MCP / Supabase logging ---

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _log_to_mcp(intent: str, raw_text: str, parameters: dict, result: str = "") -> None:
    """Log intent classification + handling to MCP decision log."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[intent_handlers] WARN: no Supabase creds, skipping MCP log", file=sys.stderr)
        return

    entry = {
        "text": f"[titan-bot] intent={intent} | {raw_text[:100]}",
        "project_source": "EOM",
        "rationale": json.dumps({
            "intent": intent,
            "parameters": parameters,
            "result_summary": result[:200] if result else "",
        }),
        "tags": [f"intent_{intent}", "titan_bot", "slack_command"],
    }

    try:
        data = json.dumps(entry).encode("utf-8")
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/decisions",
            data=data,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        req.add_header("Prefer", "return=minimal")
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        print(f"[intent_handlers] MCP log failed: {exc!r}", file=sys.stderr)


# --- Slack message formatting helpers ---

def _slack_blocks(header: str, sections: list[str], footer: str = "") -> dict:
    """Build a Slack Block Kit message payload."""
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header[:150]}},
    ]
    for section in sections:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": section},
        })
    if footer:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": footer},
        ]})
    return {"blocks": blocks, "text": header}  # text is fallback for notifications


# --- Per-intent handlers ---

def handle_status(msg: ClassifiedMessage) -> dict:
    """MP-3 §1-A: Status query → structured daily ops summary."""
    timeframe = msg.parameters.get("timeframe", "today")
    scope = msg.parameters.get("scope", "global")
    client = msg.parameters.get("client")

    header = f"Atlas Status — {timeframe}"
    if client:
        header = f"{client} Status — {timeframe}"

    sections = [
        "*Shipments*\n• _Querying completed tasks..._",
        "*Failures / Degraded*\n• _Checking subsystem health..._",
        "*Pending Approvals*\n• _Loading approval queue..._",
    ]
    footer = "📊 <https://ops.aimarketinggenius.io|Open Atlas Dashboard>"

    _log_to_mcp("status", msg.raw_text, msg.parameters, f"status response: {header}")
    return _slack_blocks(header, sections, footer)


def handle_approval(msg: ClassifiedMessage) -> dict:
    """MP-3 §1-B: Approval action → execute/reject/hold + log."""
    decision = msg.parameters.get("decision", "approve")
    target = msg.parameters.get("target", "the pending item")
    context = msg.parameters.get("context", "explicit")

    action_verb = {"approve": "Approved", "reject": "Rejected", "hold": "Held"}.get(decision, "Processed")

    header = f"{action_verb}: {target}"
    sections = [
        f"*Outcome:* {action_verb} — `{target}`",
        f"*Next steps:* {'Executing approved action...' if decision == 'approve' else 'Action cancelled.' if decision == 'reject' else 'Action frozen until further notice.'}",
    ]
    footer = "📋 Logged to MCP | <https://ops.aimarketinggenius.io|View in Dashboard>"

    _log_to_mcp("approval", msg.raw_text, msg.parameters, f"{action_verb}: {target}")
    return _slack_blocks(header, sections, footer)


def handle_task_trigger(msg: ClassifiedMessage) -> dict:
    """MP-3 §1-C: Task trigger → check prereqs, start workflow."""
    action = msg.parameters.get("action", "start")
    target = msg.parameters.get("target", "workflow")
    client = msg.parameters.get("client")

    header = f"Task Triggered: {action} {target}"
    sections = [
        f"*Action:* {action.title()} — `{target}`" + (f" for *{client}*" if client else ""),
        "*Prerequisites:* _Checking Hard Limit dependencies..._",
        "*Status:* Queued — awaiting prerequisite check",
    ]
    footer = "⏱ ETA will be posted when workflow starts"

    _log_to_mcp("task_trigger", msg.raw_text, msg.parameters, f"triggered: {action} {target}")
    return _slack_blocks(header, sections, footer)


def handle_emergency_stop(msg: ClassifiedMessage) -> dict:
    """MP-3 §1-D: Emergency stop → kill non-read operations."""
    scope = msg.parameters.get("scope", "global")
    target = msg.parameters.get("target")

    if scope == "global":
        header = "🛑 EMERGENCY STOP — All Non-Read Operations Halted"
        effects = [
            "• Outbound communications: STOPPED",
            "• Nurture sequences: PAUSED",
            "• Automated fulfillment edits: FROZEN",
            "• Public-facing changes: BLOCKED",
            "• Monitoring + logging: STILL ACTIVE",
        ]
    elif scope == "client" and target:
        header = f"🛑 CLIENT HOLD — {target}"
        effects = [
            f"• All changes for *{target}*: FROZEN",
            "• Monitoring: STILL ACTIVE",
        ]
    else:
        scope_label = target or scope
        header = f"🛑 SUBSYSTEM HOLD — {scope_label}"
        effects = [
            f"• `{scope_label}` subsystem: PAUSED",
            "• Jobs preserved as 'held'",
        ]

    sections = [
        "*Scope:* " + (f"Global — all automation" if scope == "global" else f"`{target or scope}`"),
        "*Effects:*\n" + "\n".join(effects),
        "*To resume:* Send `Resume` or `Resume [subsystem/client]`",
    ]

    _log_to_mcp("emergency_stop", msg.raw_text, msg.parameters, f"STOP: scope={scope}")
    return _slack_blocks(header, sections)


def handle_reporting(msg: ClassifiedMessage) -> dict:
    """MP-3 §1-E: Reporting request → KPI snapshot + dashboard link."""
    report_type = msg.parameters.get("type", "report")
    timeframe = msg.parameters.get("timeframe", "today")
    client = msg.parameters.get("client")

    header = f"Report: {client or 'Atlas'} — {timeframe}"
    sections = [
        "*Summary:* _Loading metrics..._",
        "*Key Metrics:*\n"
        "• MRR: _loading..._\n"
        "• Active clients: _loading..._\n"
        "• Subsystem errors: _loading..._\n"
        "• Reviewer Loop usage: _loading..._",
    ]
    footer = "📈 <https://ops.aimarketinggenius.io|Open full report in Atlas>"

    _log_to_mcp("reporting", msg.raw_text, msg.parameters, f"report: {report_type} {timeframe}")
    return _slack_blocks(header, sections, footer)


def handle_fallback(msg: ClassifiedMessage) -> dict:
    """MP-3 §1-F: Unknown intent → log, canned guidance, no action."""
    _log_to_mcp("unknown_intent", msg.raw_text, msg.parameters, "fallback: no action taken")

    return {
        "text": (
            "I didn't understand that command. Here are the things I can handle: "
            "*Status* · *Approvals* · *Task triggers* · *Emergency stops* · *Reports*. "
            "Try rephrasing or ask 'What can you do?'"
        ),
    }


# --- Dispatcher ---

_HANDLER_MAP = {
    Intent.STATUS: handle_status,
    Intent.APPROVAL: handle_approval,
    Intent.TASK_TRIGGER: handle_task_trigger,
    Intent.EMERGENCY_STOP: handle_emergency_stop,
    Intent.REPORTING: handle_reporting,
    Intent.FALLBACK: handle_fallback,
}


def dispatch(msg: ClassifiedMessage) -> dict:
    """Route a classified message to the correct handler and return the Slack payload."""
    handler = _HANDLER_MAP.get(msg.intent, handle_fallback)
    return handler(msg)
