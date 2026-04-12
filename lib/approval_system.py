#!/usr/bin/env python3
"""
lib/approval_system.py
MP-3 §6 — Approval and Override Doctrine

Implements:
  - Structured approval packets (Slack Block Kit with Approve/Reject/Details buttons)
  - Hard Limit enforcement ("no approval → no action")
  - Modify cycle: parse "Modify: [constraint]" → revised packet → new Approve/Reject
  - Reminder policy: 24h for low-risk, 12h for medium/high-risk
  - MCP logging for all approval events
  - In-memory approval state with thread tracking
"""

from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.request
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# --- Types ---

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"      # Modify received, revised packet pending
    HELD = "held"              # Deferred
    EXPIRED = "expired"


class Decision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    HOLD = "hold"


# --- Hard Limits (MP-3 §6-E) ---

HARD_LIMIT_ACTIONS = [
    "credentials_oauth_totp",
    "money_operations_over_50",
    "destructive_production_data",
    "doctrine_edits",
    "public_facing_changes",
    "external_comms_alter_tone",
]


@dataclass
class ApprovalPacket:
    """A structured approval request per MP-3 §6-A."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    client: str = ""
    subsystem: str = ""
    action: str = ""
    summary: str = ""
    risk: RiskLevel = RiskLevel.LOW
    status: ApprovalStatus = ApprovalStatus.PENDING
    hard_limit_category: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None
    decision_by: str = ""
    thread_ts: Optional[str] = None
    modify_constraints: list[str] = field(default_factory=list)
    revision: int = 0  # increments on each Modify cycle


# --- Approval Store (in-memory) ---

_store: dict[str, ApprovalPacket] = {}
_thread_to_packet: dict[str, str] = {}  # thread_ts → packet_id


def get_packet(packet_id: str) -> Optional[ApprovalPacket]:
    return _store.get(packet_id)


def get_packet_by_thread(thread_ts: str) -> Optional[ApprovalPacket]:
    pid = _thread_to_packet.get(thread_ts)
    return _store.get(pid) if pid else None


def list_pending() -> list[ApprovalPacket]:
    return [p for p in _store.values() if p.status == ApprovalStatus.PENDING]


def list_stale(now: Optional[datetime] = None) -> list[tuple[ApprovalPacket, float]]:
    """Return pending packets past their reminder threshold with age in hours."""
    now = now or datetime.now(timezone.utc)
    stale = []
    for p in list_pending():
        age_hours = (now - p.created_at).total_seconds() / 3600
        threshold = 24.0 if p.risk == RiskLevel.LOW else 12.0
        if age_hours >= threshold:
            stale.append((p, age_hours))
    return stale


# --- MCP Logging ---

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _log_approval_event(event_type: str, packet: ApprovalPacket, extra: dict | None = None) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[approval_system] WARN: no Supabase creds, skipping MCP log", file=sys.stderr)
        return

    entry = {
        "text": f"[approval] {event_type}: {packet.client}/{packet.subsystem} — {packet.action} (risk={packet.risk.value})",
        "project_source": "EOM",
        "rationale": json.dumps({
            "packet_id": packet.id,
            "event": event_type,
            "status": packet.status.value,
            "risk": packet.risk.value,
            "revision": packet.revision,
            **(extra or {}),
        }),
        "tags": ["approval", event_type, f"risk_{packet.risk.value}"],
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
        print(f"[approval_system] MCP log failed: {exc!r}", file=sys.stderr)


# --- Slack Formatting ---

def format_approval_slack(packet: ApprovalPacket) -> dict:
    """Build Slack Block Kit approval packet per MP-3 §6-A."""
    title = f"APPROVAL NEEDED — {packet.client} — {packet.subsystem} — {packet.action}"
    if packet.revision > 0:
        title = f"REVISED (v{packet.revision + 1}) — {title}"

    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}[packet.risk.value]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title[:150]},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": packet.summary},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Risk:* {risk_emoji} {packet.risk.value.upper()}"},
                {"type": "mrkdwn", "text": f"*Packet ID:* `{packet.id}`"},
            ],
        },
    ]

    if packet.modify_constraints:
        constraints_text = "\n".join(f"• {c}" for c in packet.modify_constraints)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Applied constraints:*\n{constraints_text}"},
        })

    # Action buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Approve"},
                "style": "primary",
                "action_id": f"approve_{packet.id}",
                "value": packet.id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Reject"},
                "style": "danger",
                "action_id": f"reject_{packet.id}",
                "value": packet.id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📋 More Details"},
                "action_id": f"details_{packet.id}",
                "value": packet.id,
            },
        ],
    })

    # Text fallback for notifications
    text_fallback = (
        f"APPROVAL NEEDED: {packet.client} / {packet.subsystem} / {packet.action}\n"
        f"Risk: {packet.risk.value}\n"
        f"{packet.summary}\n"
        f"Reply: Approve / Reject / Modify: [constraint] / Hold"
    )

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Reply in thread: `Approve` · `Reject` · `Modify: [constraint]` · `Hold`"},
        ],
    })

    return {"blocks": blocks, "text": text_fallback}


def format_reminder_slack(packet: ApprovalPacket, age_hours: float) -> dict:
    """Build a reminder message for stale approvals."""
    risk_label = "medium/high-risk — BLOCKING" if packet.risk != RiskLevel.LOW else "low-risk"
    return {
        "text": (
            f"⏰ REMINDER: Approval `{packet.id}` pending for {age_hours:.0f}h ({risk_label})\n"
            f"*{packet.client}* / *{packet.subsystem}* — {packet.action}\n"
            f"Reply: `Approve` · `Reject` · `Modify: [constraint]`"
        ),
    }


# --- Core Operations ---

def create_approval(
    client: str,
    subsystem: str,
    action: str,
    summary: str,
    risk: RiskLevel = RiskLevel.LOW,
    hard_limit_category: str = "",
) -> ApprovalPacket:
    """Create a new approval packet and store it."""
    packet = ApprovalPacket(
        client=client,
        subsystem=subsystem,
        action=action,
        summary=summary,
        risk=risk,
        hard_limit_category=hard_limit_category,
    )
    _store[packet.id] = packet
    _log_approval_event("created", packet)
    return packet


def register_thread(packet_id: str, thread_ts: str) -> None:
    """Associate a Slack thread with a packet for thread-aware approval routing."""
    _thread_to_packet[thread_ts] = packet_id
    packet = _store.get(packet_id)
    if packet:
        packet.thread_ts = thread_ts


def process_decision(
    packet_id: str,
    decision: Decision,
    decided_by: str = "solon",
    modify_constraint: str = "",
) -> tuple[ApprovalPacket | None, dict]:
    """Process a decision on an approval packet.

    Returns (updated_packet, slack_reply_payload).
    For Modify: returns the REVISED packet and its new approval Slack payload.
    """
    packet = _store.get(packet_id)
    if not packet:
        return None, {"text": f"⚠️ Approval packet `{packet_id}` not found."}

    if packet.status not in (ApprovalStatus.PENDING, ApprovalStatus.MODIFIED):
        return packet, {"text": f"⚠️ Packet `{packet_id}` already resolved ({packet.status.value})."}

    now = datetime.now(timezone.utc)
    packet.decided_at = now
    packet.decision_by = decided_by

    if decision == Decision.APPROVE:
        packet.status = ApprovalStatus.APPROVED
        _log_approval_event("approved", packet)
        reply = {
            "text": (
                f"✅ *APPROVED:* {packet.client} / {packet.subsystem} — {packet.action}\n"
                f"Executing approved action. Logged to MCP."
            ),
        }
        return packet, reply

    elif decision == Decision.REJECT:
        packet.status = ApprovalStatus.REJECTED
        _log_approval_event("rejected", packet)
        reply = {
            "text": (
                f"❌ *REJECTED:* {packet.client} / {packet.subsystem} — {packet.action}\n"
                f"Action cancelled. Logged to MCP."
            ),
        }
        return packet, reply

    elif decision == Decision.HOLD:
        packet.status = ApprovalStatus.HELD
        _log_approval_event("held", packet)
        reply = {
            "text": (
                f"⏸ *HELD:* {packet.client} / {packet.subsystem} — {packet.action}\n"
                f"Action frozen until further notice. Logged to MCP."
            ),
        }
        return packet, reply

    elif decision == Decision.MODIFY:
        # Modify cycle: draft revised packet, post new approval, wait for Approve/Reject
        packet.status = ApprovalStatus.MODIFIED
        packet.modify_constraints.append(modify_constraint)
        packet.revision += 1
        packet.status = ApprovalStatus.PENDING  # Re-open for new decision
        packet.decided_at = None
        _log_approval_event("modified", packet, {"constraint": modify_constraint})
        # Return the revised approval Slack payload
        return packet, format_approval_slack(packet)

    return packet, {"text": "⚠️ Unknown decision type."}


def check_hard_limit(action_category: str) -> bool:
    """Check if an action requires Hard Limit approval.

    Returns True if the action is a Hard Limit and must not execute
    without explicit approval.
    """
    return action_category in HARD_LIMIT_ACTIONS


def enforce_hard_limit(action_category: str, packet_id: str | None = None) -> tuple[bool, str]:
    """Enforce the Hard Limit gate: no approval → no action.

    Returns (allowed, reason).
    """
    if not check_hard_limit(action_category):
        return True, "not a Hard Limit action"

    if not packet_id:
        return False, f"Hard Limit: {action_category} requires approval. No packet found."

    packet = _store.get(packet_id)
    if not packet:
        return False, f"Hard Limit: approval packet {packet_id} not found."

    if packet.status != ApprovalStatus.APPROVED:
        return False, f"Hard Limit: packet {packet_id} is {packet.status.value}, not approved."

    return True, f"Hard Limit cleared: packet {packet_id} approved."


def parse_modify_from_text(text: str) -> str | None:
    """Parse a 'Modify: [constraint]' command from a Slack message.

    Returns the constraint text, or None if the message isn't a Modify command.
    """
    import re
    m = re.match(r"^\s*modify\s*:\s*(.+)", text, re.I)
    return m.group(1).strip() if m else None
