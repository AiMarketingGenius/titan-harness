#!/usr/bin/env python3
"""tests/test_onboarding_flow.py — MP-3 §5 onboarding flow tests"""

import os, sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.onboarding_flow import (
    create_onboarding, get_onboarding, advance_step, start_step,
    generate_kickoff_brief, process_post_call_summary,
    onboarding_to_client_tile, OnboardingStage, ChecklistStatus,
    STANDARD_CHECKLIST, HARD_LIMIT_STEPS, _onboardings,
)


def _reset():
    _onboardings.clear()


def test_create_onboarding():
    _reset()
    ob = create_onboarding("Levar / JDJ", "jdj")
    assert ob.client_name == "Levar / JDJ"
    assert ob.stage == OnboardingStage.PENDING
    assert len(ob.checklist) == len(STANDARD_CHECKLIST)
    assert all(c.status == ChecklistStatus.NOT_STARTED for c in ob.checklist)
    print("✅ test_create_onboarding")


def test_hard_limit_steps():
    assert "billing_confirmed" in HARD_LIMIT_STEPS
    assert "contract_signed" in HARD_LIMIT_STEPS
    assert "kickoff_approved" in HARD_LIMIT_STEPS
    assert "intake_sent" not in HARD_LIMIT_STEPS
    print("✅ test_hard_limit_steps")


def test_advance_through_stages():
    _reset()
    ob = create_onboarding("JDJ", "jdj")

    # Billing
    ok, msg = advance_step("jdj", "billing_confirmed")
    assert ok
    assert ob.stage == OnboardingStage.PENDING  # still pending

    # Contract
    advance_step("jdj", "contract_signed")
    assert ob.stage == OnboardingStage.PENDING

    # Kickoff → moves to INTAKE
    advance_step("jdj", "kickoff_approved")
    assert ob.stage == OnboardingStage.INTAKE
    # intake_sent should auto-start
    intake = next(c for c in ob.checklist if c.name == "intake_sent")
    assert intake.status == ChecklistStatus.IN_PROGRESS

    print("✅ test_advance_through_stages")


def test_wiring_to_go_live():
    _reset()
    ob = create_onboarding("JDJ", "jdj")
    for step in ["billing_confirmed", "contract_signed", "kickoff_approved",
                  "intake_sent", "nap_collected", "gbp_access", "gsc_ga_access",
                  "logins_received", "wiring_complete"]:
        advance_step("jdj", step)
    assert ob.stage == OnboardingStage.GO_LIVE

    advance_step("jdj", "first_tasks_queued")
    advance_step("jdj", "go_live")
    assert ob.stage == OnboardingStage.ACTIVE
    print("✅ test_wiring_to_go_live")


def test_stall_detection():
    _reset()
    ob = create_onboarding("JDJ", "jdj")
    advance_step("jdj", "billing_confirmed")
    advance_step("jdj", "contract_signed")
    advance_step("jdj", "kickoff_approved")

    # Simulate intake stalled > 72h
    intake = next(c for c in ob.checklist if c.name == "nap_collected")
    intake.status = ChecklistStatus.IN_PROGRESS
    intake.started_at = datetime.now(timezone.utc) - timedelta(hours=80)

    # Re-trigger stage check via advance
    advance_step("jdj", "intake_sent")
    assert ob.stage == OnboardingStage.STALLED
    print("✅ test_stall_detection")


def test_kickoff_brief():
    _reset()
    ob = create_onboarding("Levar / JDJ", "jdj")
    advance_step("jdj", "billing_confirmed")
    advance_step("jdj", "contract_signed")

    brief = generate_kickoff_brief("jdj")
    assert "Levar / JDJ" in brief
    assert "KICKOFF BRIEF" in brief
    assert "2/" in brief  # 2/11 complete
    assert "30-DAY PLAN" in brief
    print("✅ test_kickoff_brief")


def test_post_call_summary():
    _reset()
    create_onboarding("JDJ", "jdj")
    ok, msg = process_post_call_summary("jdj", "Levar confirmed billing at $497/mo, wants GA4 wired first")
    assert ok
    ob = get_onboarding("jdj")
    assert len(ob.notes) == 1
    assert "Levar confirmed" in ob.notes[0]
    print("✅ test_post_call_summary")


def test_client_tile():
    _reset()
    ob = create_onboarding("JDJ", "jdj")
    advance_step("jdj", "billing_confirmed")
    advance_step("jdj", "contract_signed")

    tile = onboarding_to_client_tile(ob)
    assert tile["name"] == "JDJ"
    assert tile["stage"] == "Pending"
    assert tile["open_blockers"] == 0
    assert tile["health_color"] == "green"
    assert "signed" in tile["last_task"].lower() or "contract" in tile["last_task"].lower()
    print("✅ test_client_tile")


def test_tile_with_blockers():
    _reset()
    ob = create_onboarding("JDJ", "jdj")
    # Set two items as blocked
    ob.checklist[4].status = ChecklistStatus.BLOCKED
    ob.checklist[4].blocked_reason = "Client unresponsive"
    ob.checklist[5].status = ChecklistStatus.BLOCKED

    tile = onboarding_to_client_tile(ob)
    assert tile["open_blockers"] == 2
    assert tile["health_color"] == "red"
    print("✅ test_tile_with_blockers")


def test_duplicate_advance():
    _reset()
    create_onboarding("JDJ", "jdj")
    advance_step("jdj", "billing_confirmed")
    ok, msg = advance_step("jdj", "billing_confirmed")
    assert ok
    assert "already complete" in msg
    print("✅ test_duplicate_advance")


def test_unknown_client():
    _reset()
    ok, msg = advance_step("nonexistent", "billing_confirmed")
    assert not ok
    assert "No onboarding" in msg
    print("✅ test_unknown_client")


def main():
    print("=" * 60)
    print("MP-3 §5 ONBOARDING FLOW TEST HARNESS")
    print("=" * 60)
    tests = [
        test_create_onboarding, test_hard_limit_steps,
        test_advance_through_stages, test_wiring_to_go_live,
        test_stall_detection, test_kickoff_brief,
        test_post_call_summary, test_client_tile,
        test_tile_with_blockers, test_duplicate_advance,
        test_unknown_client,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {e}"); failed += 1
    print(f"{'='*60}\nRESULTS: {passed}/{len(tests)} passed, {failed} failed\n{'='*60}")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
