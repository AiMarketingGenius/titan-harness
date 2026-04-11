"""
titan-harness/lib/sales_inbox.py

Thread 1 of the Autopilot Suite — Sales Inbox + CRM Agent.
See plans/PLAN_2026-04-11_sales-inbox-crm-agent.md for the full DR.

Status: STUB module — public API + dataclasses shipped, implementation
phases TODO per the DR's 5-phase plan. Each public function raises
NotImplementedError until wired; callers should expect this and check
policy.yaml autopilot.sales_inbox_enabled before invoking.

Phase wiring:
  Phase 1 gmail-oauth-watch-setup     → scripts/gmail_oauth_bootstrap.py (TODO)
  Phase 2 lead-schema-and-classifier  → classify_thread() below (TODO)
  Phase 3 draft-reply-generator        → draft_reply() below (TODO)
  Phase 4 followup-cadence-engine      → run_cadence() below (TODO)
  Phase 5 precall-brief-generator      → generate_precall_brief() below (TODO)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses matching sql/007 leads + sales_threads + lead_events
# ---------------------------------------------------------------------------

class LeadStage(str, Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    HOT = "hot"
    STALLED = "stalled"
    COLD = "cold"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class LeadEventType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    DRAFT_CREATED = "draft_created"
    DRAFT_SENT = "draft_sent"
    STAGE_CHANGE = "stage_change"
    SCORE_CHANGE = "score_change"
    NUDGE_SENT = "nudge_sent"
    NUDGE_SKIPPED = "nudge_skipped"
    MEETING_DETECTED = "meeting_detected"
    BRIEF_SENT = "brief_sent"


@dataclass
class Lead:
    """Mirrors public.leads. One row per unique contact in the pipeline."""
    id: Optional[str]
    project_id: str
    email: str
    full_name: Optional[str] = None
    company: Optional[str] = None
    domain: Optional[str] = None
    source: Optional[str] = None
    stage: LeadStage = LeadStage.NEW
    score: int = 0
    first_seen_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None
    next_nudge_due: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class SalesThread:
    """Mirrors public.sales_threads. One row per email/Slack-DM conversation."""
    id: Optional[str]
    project_id: str
    lead_id: Optional[str]
    source: str  # 'gmail' | 'slack_dm'
    source_thread_id: str
    subject: Optional[str]
    participants: list[str] = field(default_factory=list)
    message_count: int = 0
    first_message_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    last_inbound_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None
    last_draft_id: Optional[str] = None
    last_draft_grade: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class ClassificationResult:
    """Output of classify_thread()."""
    score: int  # 0-100
    stage: LeadStage
    signals: list[str]
    routing: str  # 'draft_reply' | 'silent' | 'flag_for_solon'
    reasoning: str


@dataclass
class DraftResult:
    """Output of draft_reply()."""
    subject: str
    body_markdown: str
    confidence: str  # 'high' | 'medium' | 'low'
    war_room_grade: Optional[str] = None
    gmail_draft_id: Optional[str] = None
    needs_solon_override: bool = False
    reasoning: str = ""


@dataclass
class PrecallBrief:
    """Output of generate_precall_brief()."""
    meeting_id: str
    attendee_emails: list[str]
    lead_id: Optional[str]
    brief_markdown: str
    war_room_grade: Optional[str] = None
    delivered_to_slack: bool = False


# ---------------------------------------------------------------------------
# Phase 2 — classifier (TODO implementation)
# ---------------------------------------------------------------------------

def classify_thread(thread: SalesThread,
                    latest_message_snippet: str,
                    project_id: str = "EOM") -> ClassificationResult:
    """Given a thread + latest message snippet, return a classification.

    Runs in two stages per the DR:
      1. Cheap heuristic scoring (domain rep, body length, reply history,
         keyword match) — always executed, free, deterministic.
      2. LLM scoring for threads above the heuristic threshold OR flagged
         as hot — routed through lib/llm_client with Haiku 4.5 for
         first-pass, Sonnet 4.6 for draft-reply-required cases.

    TODO: implement Phase 2 heuristic + LLM stages. Currently stubbed.
    """
    raise NotImplementedError(
        "classify_thread: Phase 2 lead-schema-and-classifier not yet "
        "implemented. See plans/PLAN_2026-04-11_sales-inbox-crm-agent.md "
        "Phase 2 spec."
    )


# ---------------------------------------------------------------------------
# Phase 3 — drafter (TODO implementation)
# ---------------------------------------------------------------------------

def draft_reply(thread: SalesThread,
                classification: ClassificationResult,
                voice_seeds_dir: str = "/opt/amg-titan/voice-seeds") -> DraftResult:
    """Generate an A-graded reply draft for a classified thread.

    Drafts are ALWAYS written to Gmail as drafts under the 'titan/drafted'
    label — never auto-sent. War-room grading enforces an A-grade floor
    before any draft lands in Gmail. Below-A drafts are NOT shipped;
    they log a 'needs_solon_override' flag to war_room_exchanges.

    Privacy guard: the context builder used here scopes to the current
    thread only. It never reads other sales_threads rows (cross-client
    bleed guard).

    TODO: implement Phase 3 drafter. Currently stubbed.
    """
    raise NotImplementedError(
        "draft_reply: Phase 3 draft-reply-generator not yet implemented. "
        "See plans/PLAN_2026-04-11_sales-inbox-crm-agent.md Phase 3 spec."
    )


# ---------------------------------------------------------------------------
# Phase 4 — cadence (TODO implementation)
# ---------------------------------------------------------------------------

def run_cadence(project_id: str = "EOM", dry_run: bool = False) -> dict:
    """Daily cron entry point. Scans leads + sales_threads for threads
    due for a cadence nudge, generates cadence-specific drafts, logs
    nudge events. Respects per-lead timezone (business-hours only), max
    4 nudges per lifecycle, breakup email as #5.

    TODO: implement Phase 4 cadence engine. Currently stubbed.
    """
    raise NotImplementedError(
        "run_cadence: Phase 4 followup-cadence-engine not yet implemented. "
        "See plans/PLAN_2026-04-11_sales-inbox-crm-agent.md Phase 4 spec."
    )


# ---------------------------------------------------------------------------
# Phase 5 — pre-call brief (TODO implementation)
# ---------------------------------------------------------------------------

def generate_precall_brief(calendar_event: dict,
                           project_id: str = "EOM") -> PrecallBrief:
    """Build a 1-page pre-call brief for a calendar event. Joins attendee
    emails against leads table, pulls thread history, adds public-signal
    research (LinkedIn, domain, website WebFetch). Delivered to Solon's
    Slack DM at T-30 minutes before meeting.

    TODO: implement Phase 5 pre-call brief generator. Currently stubbed.
    """
    raise NotImplementedError(
        "generate_precall_brief: Phase 5 precall-brief-generator not yet "
        "implemented. See plans/PLAN_2026-04-11_sales-inbox-crm-agent.md "
        "Phase 5 spec."
    )


# ---------------------------------------------------------------------------
# Policy check (always implemented — safe short-circuit)
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    """Return True iff policy.yaml autopilot.sales_inbox_enabled is true.
    Callers should check this before invoking any of the Phase 2-5
    functions above.
    """
    import os
    return os.environ.get("POLICY_AUTOPILOT_SALES_INBOX_ENABLED", "0") == "1"
