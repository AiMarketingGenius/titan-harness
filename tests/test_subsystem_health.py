#!/usr/bin/env python3
"""tests/test_subsystem_health.py — MP-3 §4 health flags tests"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.subsystem_health import (
    evaluate_all, health_summary_slack, health_to_orb_inputs,
    SubsystemMetrics, HealthStatus, SUBSYSTEM_NAMES,
)


def _all_healthy_metrics():
    return {name: SubsystemMetrics() for name in SUBSYSTEM_NAMES}


def test_all_healthy():
    results = evaluate_all(_all_healthy_metrics())
    assert all(r.status == HealthStatus.HEALTHY for r in results)
    assert len(results) == 7
    print("✅ test_all_healthy")


def test_inbound_needs_attention_latency():
    m = _all_healthy_metrics()
    m["inbound"].lead_response_latency_hours = 5.0
    results = evaluate_all(m)
    inbound = next(r for r in results if r.name == "inbound")
    assert inbound.status == HealthStatus.NEEDS_ATTENTION
    assert "latency" in inbound.triggers[0].lower()
    print("✅ test_inbound_needs_attention_latency")


def test_inbound_needs_attention_backlog():
    m = _all_healthy_metrics()
    m["inbound"].stale_lead_backlog = 5
    results = evaluate_all(m)
    inbound = next(r for r in results if r.name == "inbound")
    assert inbound.status == HealthStatus.NEEDS_ATTENTION
    print("✅ test_inbound_needs_attention_backlog")


def test_outbound_complaint_rate():
    m = _all_healthy_metrics()
    m["outbound"].complaint_rate_pct = 0.12
    results = evaluate_all(m)
    outbound = next(r for r in results if r.name == "outbound")
    assert outbound.status == HealthStatus.NEEDS_ATTENTION
    print("✅ test_outbound_complaint_rate")


def test_nurture_unsubscribe():
    m = _all_healthy_metrics()
    m["nurture"].unsubscribe_rate_pct = 2.0
    results = evaluate_all(m)
    nurture = next(r for r in results if r.name == "nurture")
    assert nurture.status == HealthStatus.NEEDS_ATTENTION
    print("✅ test_nurture_unsubscribe")


def test_onboarding_stalled():
    m = _all_healthy_metrics()
    m["onboarding"].checklist_step_stalled_hours = 80
    results = evaluate_all(m)
    onboarding = next(r for r in results if r.name == "onboarding")
    assert onboarding.status == HealthStatus.NEEDS_ATTENTION
    print("✅ test_onboarding_stalled")


def test_fulfillment_missed():
    m = _all_healthy_metrics()
    m["fulfillment"].missed_deliverable_hours = 30
    results = evaluate_all(m)
    ful = next(r for r in results if r.name == "fulfillment")
    assert ful.status == HealthStatus.NEEDS_ATTENTION
    print("✅ test_fulfillment_missed")


def test_reporting_failed():
    m = _all_healthy_metrics()
    m["reporting"].report_generation_failed = True
    results = evaluate_all(m)
    rep = next(r for r in results if r.name == "reporting")
    assert rep.status == HealthStatus.NEEDS_ATTENTION
    print("✅ test_reporting_failed")


def test_upsell_churn():
    m = _all_healthy_metrics()
    m["upsell_retain"].churn_signal_detected = True
    results = evaluate_all(m)
    ups = next(r for r in results if r.name == "upsell_retain")
    assert ups.status == HealthStatus.NEEDS_ATTENTION
    print("✅ test_upsell_churn")


def test_missing_metrics():
    results = evaluate_all({})  # No metrics for any subsystem
    assert all(r.status == HealthStatus.UNKNOWN for r in results)
    print("✅ test_missing_metrics")


def test_slack_format():
    results = evaluate_all(_all_healthy_metrics())
    text = health_summary_slack(results)
    assert "7-Subsystem Health" in text
    assert "🟢" in text
    assert "inbound" in text
    print("✅ test_slack_format")


def test_orb_integration():
    m = _all_healthy_metrics()
    m["outbound"].bounce_rate_pct = 5.0
    results = evaluate_all(m)
    orb_inputs = health_to_orb_inputs(results)
    assert len(orb_inputs) == 7
    outbound_orb = next(o for o in orb_inputs if o.name == "outbound")
    assert outbound_orb.status == "needs_attention"
    print("✅ test_orb_integration")


def main():
    print("=" * 60)
    print("MP-3 §4 SUBSYSTEM HEALTH TEST HARNESS")
    print("=" * 60)
    tests = [
        test_all_healthy, test_inbound_needs_attention_latency,
        test_inbound_needs_attention_backlog, test_outbound_complaint_rate,
        test_nurture_unsubscribe, test_onboarding_stalled,
        test_fulfillment_missed, test_reporting_failed,
        test_upsell_churn, test_missing_metrics,
        test_slack_format, test_orb_integration,
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
