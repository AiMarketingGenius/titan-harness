#!/usr/bin/env python3
"""
tests/test_orb_state_machine.py
MP-3 §3E — Orb Color State Machine Tests
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.orb_state_machine import (
    compute_orb_state, orb_state_to_slack, orb_state_to_json,
    OrbColor, SubsystemHealth, Incident, PendingApproval, ServiceRestart,
)


def _healthy_subsystems():
    return [SubsystemHealth(f"sub_{i}", "healthy") for i in range(7)]


def test_green_all_healthy():
    state = compute_orb_state(_healthy_subsystems(), [], [])
    assert state.color == OrbColor.GREEN
    assert state.pulse == "slow"
    assert "All systems healthy" in state.drivers[0]
    print("✅ test_green_all_healthy")


def test_green_one_approval_under_12h():
    approvals = [PendingApproval("p1", age_hours=6, risk="low")]
    state = compute_orb_state(_healthy_subsystems(), [], approvals)
    assert state.color == OrbColor.GREEN
    print("✅ test_green_one_approval_under_12h")


def test_yellow_subsystem_needs_attention():
    subs = _healthy_subsystems()
    subs[2] = SubsystemHealth("caddy", "needs_attention")
    state = compute_orb_state(subs, [], [])
    assert state.color == OrbColor.YELLOW
    assert "caddy" in state.drivers[0]
    print("✅ test_yellow_subsystem_needs_attention")


def test_yellow_two_approvals_under_24h():
    approvals = [
        PendingApproval("p1", age_hours=10, risk="medium"),
        PendingApproval("p2", age_hours=8, risk="low"),
    ]
    state = compute_orb_state(_healthy_subsystems(), [], approvals)
    assert state.color == OrbColor.YELLOW
    assert "2 approvals" in state.drivers[0]
    print("✅ test_yellow_two_approvals_under_24h")


def test_yellow_degraded_service():
    subs = _healthy_subsystems()
    subs[0] = SubsystemHealth("kokoro_tts", "degraded")
    state = compute_orb_state(subs, [], [])
    assert state.color == OrbColor.YELLOW
    print("✅ test_yellow_degraded_service")


def test_orange_p1_incident():
    incidents = [Incident("P1", "n8n", "workflow execution delayed")]
    state = compute_orb_state(_healthy_subsystems(), incidents, [])
    assert state.color == OrbColor.ORANGE
    assert state.pulse == "medium"
    assert "P1" in state.drivers[0]
    print("✅ test_orange_p1_incident")


def test_orange_approval_over_24h():
    approvals = [PendingApproval("p1", age_hours=26, risk="high")]
    state = compute_orb_state(_healthy_subsystems(), [], approvals)
    assert state.color == OrbColor.ORANGE
    assert "24h" in state.drivers[0]
    print("✅ test_orange_approval_over_24h")


def test_orange_restart_storm():
    restarts = [ServiceRestart("kokoro_tts", restart_count=6, is_storm=True)]
    state = compute_orb_state(_healthy_subsystems(), [], [], restarts)
    assert state.color == OrbColor.ORANGE
    assert "storm" in state.drivers[0].lower()
    print("✅ test_orange_restart_storm")


def test_red_p0_incident():
    incidents = [Incident("P0", "supabase", "database unreachable")]
    state = compute_orb_state(_healthy_subsystems(), incidents, [])
    assert state.color == OrbColor.RED
    assert state.pulse == "fast"
    assert "P0" in state.drivers[0]
    print("✅ test_red_p0_incident")


def test_red_hard_limit_violation():
    state = compute_orb_state(_healthy_subsystems(), [], [], hard_limit_violation=True)
    assert state.color == OrbColor.RED
    assert "Hard Limit" in state.drivers[0]
    print("✅ test_red_hard_limit_violation")


def test_red_multiple_p1s():
    incidents = [
        Incident("P1", "n8n", "workflows stuck"),
        Incident("P1", "caddy", "certificate expired"),
    ]
    state = compute_orb_state(_healthy_subsystems(), incidents, [])
    assert state.color == OrbColor.RED
    assert "Multiple P1s" in state.drivers[0]
    print("✅ test_red_multiple_p1s")


def test_max_severity_wins():
    """Orange from P1 + Yellow from degraded → Orange (max wins)."""
    subs = _healthy_subsystems()
    subs[0] = SubsystemHealth("kokoro", "degraded")
    incidents = [Incident("P1", "n8n", "delayed")]
    state = compute_orb_state(subs, incidents, [])
    assert state.color == OrbColor.ORANGE  # P1 dominates
    print("✅ test_max_severity_wins")


def test_slack_format():
    state = compute_orb_state(_healthy_subsystems(), [], [])
    slack_text = orb_state_to_slack(state)
    assert "🟢" in slack_text
    assert "GREEN" in slack_text
    print("✅ test_slack_format")


def test_json_format():
    incidents = [Incident("P0", "vps", "unreachable")]
    state = compute_orb_state(_healthy_subsystems(), incidents, [])
    j = orb_state_to_json(state)
    assert j["color"] == "red"
    assert j["css_color"] == "#ef4444"
    assert j["pulse"] == "fast"
    assert j["severity"] == 3
    print("✅ test_json_format")


def main():
    print("=" * 60)
    print("MP-3 §3E ORB STATE MACHINE TEST HARNESS")
    print("=" * 60)

    tests = [
        test_green_all_healthy,
        test_green_one_approval_under_12h,
        test_yellow_subsystem_needs_attention,
        test_yellow_two_approvals_under_24h,
        test_yellow_degraded_service,
        test_orange_p1_incident,
        test_orange_approval_over_24h,
        test_orange_restart_storm,
        test_red_p0_incident,
        test_red_hard_limit_violation,
        test_red_multiple_p1s,
        test_max_severity_wins,
        test_slack_format,
        test_json_format,
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
