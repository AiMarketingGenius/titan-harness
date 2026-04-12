#!/usr/bin/env python3
"""
lib/intent_classifier.py
MP-3 §1 — Slack Intent Classifier for titan-bot

Classifies incoming Slack messages into exactly one of 6 intent categories:
  status, approval, task_trigger, emergency_stop, reporting, fallback

Uses deterministic keyword/phrase matching per MP-3 §1 canonical phrases.
No LLM calls — pure pattern matching with ranked fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    STATUS = "status"
    APPROVAL = "approval"
    TASK_TRIGGER = "task_trigger"
    EMERGENCY_STOP = "emergency_stop"
    REPORTING = "reporting"
    FALLBACK = "fallback"


@dataclass
class ClassifiedMessage:
    intent: Intent
    raw_text: str
    confidence: float  # 0.0–1.0
    parameters: dict = field(default_factory=dict)
    matched_pattern: str = ""


# --- Pattern definitions per MP-3 §1 ---

# Emergency stop patterns — highest priority, checked first
_EMERGENCY_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\bstop\s+everything\b", re.I), {"scope": "global"}),
    (re.compile(r"\bstop\s+all\s+changes?\b", re.I), {"scope": "global"}),
    (re.compile(r"\bpause\s+all\b", re.I), {"scope": "global"}),
    (re.compile(r"\bstop\s+outbound\b", re.I), {"scope": "outbound"}),
    (re.compile(r"\bhold\s+(\w+)\b", re.I), {"scope": "subsystem"}),
    (re.compile(r"\bstop\s+all\s+changes?\s+for\s+(.+)", re.I), {"scope": "client"}),
    (re.compile(r"\bpause\s+.*(?:automation|atlas)\b", re.I), {"scope": "global"}),
    (re.compile(r"\bkill\s+(?:it|all|everything)\b", re.I), {"scope": "global"}),
    (re.compile(r"\bhalt\b", re.I), {"scope": "global"}),
    (re.compile(r"\bemergency\s+stop\b", re.I), {"scope": "global"}),
]

# Approval patterns — must be in thread or reference specific item
_APPROVAL_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\bapprove\s+(?:that|it|this)\b", re.I), {"decision": "approve"}),
    (re.compile(r"\bapprove\s+(.+)", re.I), {"decision": "approve"}),
    (re.compile(r"\breject\s+(?:that|it|this)\b", re.I), {"decision": "reject"}),
    (re.compile(r"\breject\s+(.+)", re.I), {"decision": "reject"}),
    (re.compile(r"\bhold\s+(?:that|it|this)\b", re.I), {"decision": "hold"}),
    (re.compile(r"\bhold\s+outbound\s+for\s+(.+)", re.I), {"decision": "hold"}),
    (re.compile(r"\bship\s+it\b", re.I), {"decision": "approve"}),
    (re.compile(r"\b(?:go\s+ahead|proceed|approved|lgtm|ok\s+go)\b", re.I), {"decision": "approve"}),
    (re.compile(r"\byes(?:,?\s+approve)?\b", re.I), {"decision": "approve"}),
]

# Task trigger patterns
_TASK_TRIGGER_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\bstart\s+(?:nurture|onboarding|sweep)\s+(?:for\s+)?(.+)", re.I), {"action": "start"}),
    (re.compile(r"\bkick\s+off\s+(.+)", re.I), {"action": "start"}),
    (re.compile(r"\brun\s+(?:a\s+)?(?:sweep|audit|check)\s+(?:for\s+)?(.+)", re.I), {"action": "run"}),
    (re.compile(r"\bgenerate\s+(?:.*?)\s*report\s+(?:for\s+)?(.+)", re.I), {"action": "generate"}),
    (re.compile(r"\bqueue\s+(?:.*?)\s*content\s+(?:for\s+)?(.+)", re.I), {"action": "queue"}),
    (re.compile(r"\bschedule\s+(.+)", re.I), {"action": "schedule"}),
    (re.compile(r"\btrigger\s+(.+)", re.I), {"action": "trigger"}),
    (re.compile(r"\bexecute\s+(.+)", re.I), {"action": "execute"}),
    (re.compile(r"\bdeploy\s+(.+)", re.I), {"action": "deploy"}),
]

# Reporting patterns
_REPORTING_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\bshow\s+me\s+(?:.*?)(?:kpi|report|snapshot|metric|performance|summary)\b", re.I), {"type": "report"}),
    (re.compile(r"\bshow\s+me\s+(.+?)\s+report\b", re.I), {"type": "client_report"}),
    (re.compile(r"\bpipeline\s+summary\b", re.I), {"type": "pipeline"}),
    (re.compile(r"\bsend\s+me\s+(.+?)\s*(?:snapshot|report|summary)\b", re.I), {"type": "report"}),
    (re.compile(r"\b(?:what(?:'s| is)\s+my\s+)?mrr\b", re.I), {"type": "financial"}),
    (re.compile(r"\bchurn\b", re.I), {"type": "financial"}),
    (re.compile(r"\bshow\s+me\s+atlas\s+kpis?\b", re.I), {"type": "atlas_kpi"}),
    (re.compile(r"\b(?:revenue|billing|earnings)\s+(?:report|summary|snapshot)\b", re.I), {"type": "financial"}),
]

# Status patterns — broadest, checked after more specific intents
_STATUS_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\bwhat\s+did\s+you\s+ship\b", re.I), {"timeframe": "today", "scope": "global"}),
    (re.compile(r"\bwhat\s+(?:broke|failed|went\s+wrong)\b", re.I), {"timeframe": "today", "scope": "failures", "severity": "high"}),
    (re.compile(r"\bwhere\s+is\s+(.+?)(?:'s)?\s+(?:onboarding|project|task)\b", re.I), {"scope": "client"}),
    (re.compile(r"\bshow\s+me\s+(?:the\s+)?health\s+of\s+(?:atlas|the\s+system)\b", re.I), {"scope": "global", "type": "health"}),
    (re.compile(r"\bany\s+fires\b", re.I), {"scope": "global", "severity": "high"}),
    (re.compile(r"\bstatus\b", re.I), {"scope": "global"}),
    (re.compile(r"\bhow\s+(?:are|is)\s+(?:things|it|atlas|everything)\b", re.I), {"scope": "global"}),
    (re.compile(r"\bwhat(?:'s| is)\s+(?:the\s+)?(?:status|state|situation|update)\b", re.I), {"scope": "global"}),
    (re.compile(r"\bany\s+(?:issues|problems|blockers|updates)\b", re.I), {"scope": "global"}),
    (re.compile(r"\bwhat(?:'s| is)\s+(?:going\s+on|happening)\b", re.I), {"scope": "global"}),
    (re.compile(r"\bgive\s+me\s+(?:a\s+)?(?:status|update|rundown|sitrep)\b", re.I), {"scope": "global"}),
]

# Timeframe extraction (applied post-classification)
_TIMEFRAME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btoday\b", re.I), "today"),
    (re.compile(r"\bthis\s+week\b", re.I), "this_week"),
    (re.compile(r"\byesterday\b", re.I), "yesterday"),
    (re.compile(r"\blast\s+week\b", re.I), "last_week"),
    (re.compile(r"\bthis\s+month\b", re.I), "this_month"),
    (re.compile(r"\blast\s+month\b", re.I), "last_month"),
]

# Client name extraction
_CLIENT_PATTERN = re.compile(
    r"\b(?:for|about)\s+(\w+(?:\s+\w+)?)\b"
    r"|\b(\w+)(?:'s)\b",
    re.I,
)


def _extract_timeframe(text: str) -> str:
    for pat, tf in _TIMEFRAME_PATTERNS:
        if pat.search(text):
            return tf
    return "today"


def _extract_client(text: str) -> str | None:
    m = _CLIENT_PATTERN.search(text)
    if m:
        return (m.group(1) or m.group(2) or "").strip() or None
    return None


def _try_patterns(
    text: str,
    patterns: list[tuple[re.Pattern, dict]],
) -> tuple[re.Pattern | None, dict, float]:
    for pat, base_params in patterns:
        m = pat.search(text)
        if m:
            params = dict(base_params)
            # Capture named groups or positional groups as context
            groups = [g for g in m.groups() if g]
            if groups:
                params["target"] = groups[0].strip()
            return pat, params, 0.9
    return None, {}, 0.0


def classify(text: str, is_thread_reply: bool = False, thread_has_approval_item: bool = False) -> ClassifiedMessage:
    """Classify a Slack message into one of 6 MP-3 §1 intent categories.

    Args:
        text: Raw message text from Slack.
        is_thread_reply: Whether this message is a reply in a thread.
        thread_has_approval_item: Whether the parent thread contains a
            pending approval item from Titan.

    Returns:
        ClassifiedMessage with intent, confidence, and extracted parameters.
    """
    text = text.strip()
    if not text:
        return ClassifiedMessage(
            intent=Intent.FALLBACK,
            raw_text=text,
            confidence=1.0,
            matched_pattern="empty_message",
        )

    # Priority 1: Emergency stops (always highest priority)
    pat, params, conf = _try_patterns(text, _EMERGENCY_PATTERNS)
    if pat:
        return ClassifiedMessage(
            intent=Intent.EMERGENCY_STOP,
            raw_text=text,
            confidence=conf,
            parameters=params,
            matched_pattern=pat.pattern,
        )

    # Priority 2: Approvals — but ONLY if in a thread with an approval item
    # or explicitly references a known item by name
    pat, params, conf = _try_patterns(text, _APPROVAL_PATTERNS)
    if pat:
        # Short phrases like "approve that", "ship it" require thread context
        # But explicit approvals with a named target (e.g. "Approve Levar onboarding")
        # should work outside threads
        short_approval = not params.get("target") and len(text.split()) <= 4
        if short_approval and not (is_thread_reply and thread_has_approval_item):
            # Don't classify as approval without thread context — fall through
            pass
        else:
            # Explicit approval with target name, or in correct thread
            if is_thread_reply and thread_has_approval_item:
                params["context"] = "thread_approval"
            return ClassifiedMessage(
                intent=Intent.APPROVAL,
                raw_text=text,
                confidence=conf,
                parameters=params,
                matched_pattern=pat.pattern,
            )

    # Priority 3: Task triggers
    pat, params, conf = _try_patterns(text, _TASK_TRIGGER_PATTERNS)
    if pat:
        params["timeframe"] = _extract_timeframe(text)
        client = _extract_client(text)
        if client:
            params["client"] = client
        return ClassifiedMessage(
            intent=Intent.TASK_TRIGGER,
            raw_text=text,
            confidence=conf,
            parameters=params,
            matched_pattern=pat.pattern,
        )

    # Priority 4: Reporting
    pat, params, conf = _try_patterns(text, _REPORTING_PATTERNS)
    if pat:
        params["timeframe"] = _extract_timeframe(text)
        client = _extract_client(text)
        if client:
            params["client"] = client
        return ClassifiedMessage(
            intent=Intent.REPORTING,
            raw_text=text,
            confidence=conf,
            parameters=params,
            matched_pattern=pat.pattern,
        )

    # Priority 5: Status queries
    pat, params, conf = _try_patterns(text, _STATUS_PATTERNS)
    if pat:
        params["timeframe"] = _extract_timeframe(text)
        client = _extract_client(text)
        if client:
            params["client"] = client
        return ClassifiedMessage(
            intent=Intent.STATUS,
            raw_text=text,
            confidence=conf,
            parameters=params,
            matched_pattern=pat.pattern,
        )

    # Priority 6: Fallback — no match
    return ClassifiedMessage(
        intent=Intent.FALLBACK,
        raw_text=text,
        confidence=1.0,
        matched_pattern="no_match",
    )
