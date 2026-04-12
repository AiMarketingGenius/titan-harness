#!/usr/bin/env python3
"""
tests/test_approval_system.py
MP-3 §6 — Approval System Test Harness

Tests:
  - Approval packet creation + Slack formatting
  - Approve / Reject / Hold decisions
  - Modify cycle (constraint → revised packet → new approval)
  - Hard Limit enforcement
  - Stale approval detection (24h low-risk, 12h medium/high)
  - Thread routing
"""

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.approval_system import (
    ApprovalPacket, ApprovalStatus, RiskLevel, Decision,
    create_approval, register_thread, process_decision,
    get_packet, get_packet_by_thread, list_pending, list_stale,
    check_hard_limit, enforce_hard_limit, parse_modify_from_text,
    format_approval_slack, format_reminder_slack,
    _store, _thread_to_packet,
)


def _reset():
    _store.clear()
    _thread_to_packet.clear()


def test_create_and_format():
    _reset()
    p = create_approval(
        client="Levar",
        subsystem="onboarding",
        action="kickoff onboarding sequence",
        summary="Start the 5-step onboarding flow for Levar's new project.\nIncludes GA4 setup, content audit, and first report.",
        risk=RiskLevel.MEDIUM,
        hard_limit_category="",
    )
    assert p.status == ApprovalStatus.PENDING
    assert p.client == "Levar"
    assert p.risk == RiskLevel.MEDIUM

    slack = format_approval_slack(p)
    assert "APPROVAL NEEDED" in slack["text"]
    assert "Levar" in slack["text"]
    assert len(slack["blocks"]) >= 4  # header + summary + fields + actions
    print("✅ test_create_and_format")
    return p


def test_approve():
    _reset()
    p = create_approval("JDJ", "nurture", "start email sequence", "3-email nurture", RiskLevel.LOW)
    register_thread(p.id, "thread_123")

    updated, reply = process_decision(p.id, Decision.APPROVE)
    assert updated.status == ApprovalStatus.APPROVED
    assert "APPROVED" in reply["text"]
    print("✅ test_approve")


def test_reject():
    _reset()
    p = create_approval("Levar", "billing", "change plan", "Upgrade to $797/mo", RiskLevel.HIGH)

    updated, reply = process_decision(p.id, Decision.REJECT)
    assert updated.status == ApprovalStatus.REJECTED
    assert "REJECTED" in reply["text"]
    print("✅ test_reject")


def test_hold():
    _reset()
    p = create_approval("Sean", "outbound", "send proposal", "New SOW for Q3", RiskLevel.MEDIUM)

    updated, reply = process_decision(p.id, Decision.HOLD)
    assert updated.status == ApprovalStatus.HELD
    assert "HELD" in reply["text"]
    print("✅ test_hold")


def test_modify_cycle():
    _reset()
    p = create_approval("Levar", "pricing", "set monthly price", "Set at $797/mo", RiskLevel.HIGH)

    # Modify: change price
    updated, revised_slack = process_decision(
        p.id, Decision.MODIFY, modify_constraint="use $497/mo, not $797"
    )
    assert updated.revision == 1
    assert updated.status == ApprovalStatus.PENDING  # Re-opened
    assert len(updated.modify_constraints) == 1
    # REVISED appears in the header block, constraint in the block content
    header_text = revised_slack["blocks"][0]["text"]["text"]
    assert "REVISED" in header_text
    assert "$497" in str(revised_slack)

    # Now approve the revised version
    updated2, reply = process_decision(p.id, Decision.APPROVE)
    assert updated2.status == ApprovalStatus.APPROVED
    assert updated2.revision == 1  # Still revision 1
    print("✅ test_modify_cycle")


def test_double_modify():
    _reset()
    p = create_approval("JDJ", "content", "publish blog", "SEO article draft", RiskLevel.MEDIUM)

    # First modify
    process_decision(p.id, Decision.MODIFY, modify_constraint="add CTA at bottom")
    assert p.revision == 1

    # Second modify
    process_decision(p.id, Decision.MODIFY, modify_constraint="change headline to question format")
    assert p.revision == 2
    assert len(p.modify_constraints) == 2

    # Final approve
    updated, reply = process_decision(p.id, Decision.APPROVE)
    assert updated.status == ApprovalStatus.APPROVED
    print("✅ test_double_modify")


def test_hard_limit_enforcement():
    _reset()
    # Without approval
    allowed, reason = enforce_hard_limit("credentials_oauth_totp")
    assert not allowed
    assert "requires approval" in reason

    # With approved packet
    p = create_approval("AMG", "auth", "rotate OAuth token", "Rotate token", RiskLevel.HIGH, "credentials_oauth_totp")
    process_decision(p.id, Decision.APPROVE)
    allowed, reason = enforce_hard_limit("credentials_oauth_totp", p.id)
    assert allowed

    # Non-hard-limit action
    allowed, reason = enforce_hard_limit("send_email")
    assert allowed
    assert "not a Hard Limit" in reason
    print("✅ test_hard_limit_enforcement")


def test_stale_detection():
    _reset()
    # Low risk: stale after 24h
    p_low = create_approval("A", "x", "y", "z", RiskLevel.LOW)
    p_low.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
    _store[p_low.id] = p_low

    # Medium risk: stale after 12h
    p_med = create_approval("B", "x", "y", "z", RiskLevel.MEDIUM)
    p_med.created_at = datetime.now(timezone.utc) - timedelta(hours=13)
    _store[p_med.id] = p_med

    # Fresh: not stale
    p_fresh = create_approval("C", "x", "y", "z", RiskLevel.HIGH)
    _store[p_fresh.id] = p_fresh

    stale = list_stale()
    stale_ids = {p.id for p, _ in stale}
    assert p_low.id in stale_ids
    assert p_med.id in stale_ids
    assert p_fresh.id not in stale_ids
    print("✅ test_stale_detection")


def test_thread_routing():
    _reset()
    p = create_approval("Levar", "onboarding", "start", "Begin onboarding", RiskLevel.LOW)
    register_thread(p.id, "thread_456")

    found = get_packet_by_thread("thread_456")
    assert found is not None
    assert found.id == p.id

    not_found = get_packet_by_thread("thread_999")
    assert not_found is None
    print("✅ test_thread_routing")


def test_parse_modify():
    assert parse_modify_from_text("Modify: use $497/mo") == "use $497/mo"
    assert parse_modify_from_text("modify: change headline") == "change headline"
    assert parse_modify_from_text("MODIFY: add CTA") == "add CTA"
    assert parse_modify_from_text("Approve that.") is None
    assert parse_modify_from_text("Something else") is None
    print("✅ test_parse_modify")


def test_reminder_format():
    _reset()
    p = create_approval("Levar", "billing", "upgrade plan", "Upgrade to premium", RiskLevel.MEDIUM)
    reminder = format_reminder_slack(p, 14.5)
    assert "REMINDER" in reminder["text"]
    assert "14h" in reminder["text"]
    assert "BLOCKING" in reminder["text"]  # medium risk
    print("✅ test_reminder_format")


def test_already_decided():
    _reset()
    p = create_approval("X", "y", "z", "test", RiskLevel.LOW)
    process_decision(p.id, Decision.APPROVE)

    # Try to approve again
    _, reply = process_decision(p.id, Decision.APPROVE)
    assert "already resolved" in reply["text"]
    print("✅ test_already_decided")


def main():
    print("=" * 60)
    print("MP-3 §6 APPROVAL SYSTEM TEST HARNESS")
    print("=" * 60)

    tests = [
        test_create_and_format,
        test_approve,
        test_reject,
        test_hold,
        test_modify_cycle,
        test_double_modify,
        test_hard_limit_enforcement,
        test_stale_detection,
        test_thread_routing,
        test_parse_modify,
        test_reminder_format,
        test_already_decided,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print(f"❌ {test.__name__}: {exc}")
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} passed, {failed} failed")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
