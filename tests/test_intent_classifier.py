#!/usr/bin/env python3
"""
tests/test_intent_classifier.py
MP-3 §1 — Intent Classifier Test Harness

Tests all 6 intent categories with canonical phrases from MP-3 §1 plus edge cases.
Prints classification results and Slack payloads for each test case.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.intent_classifier import classify, Intent
from lib.intent_handlers import dispatch


def _fmt_payload(payload: dict) -> str:
    """Format Slack payload for display."""
    if "blocks" in payload:
        header = payload["blocks"][0]["text"]["text"] if payload.get("blocks") else ""
        sections = [b["text"]["text"] for b in payload.get("blocks", []) if b.get("type") == "section"]
        return f"  Header: {header}\n" + "\n".join(f"  Section: {s[:80]}" for s in sections)
    return f"  Text: {payload.get('text', '')[:120]}"


# Test cases: (description, message, expected_intent, is_thread, thread_has_approval)
TEST_CASES = [
    # --- STATUS (A) ---
    ("Status: ship query", "What did you ship today?", Intent.STATUS, False, False),
    ("Status: failures", "What broke today?", Intent.STATUS, False, False),
    ("Status: client specific", "Where is Levar's onboarding at?", Intent.STATUS, False, False),
    ("Status: health check", "Show me the health of Atlas.", Intent.STATUS, False, False),
    ("Status: fires", "Any fires I need to know about?", Intent.STATUS, False, False),
    ("Status: informal", "How are things?", Intent.STATUS, False, False),
    ("Status: update request", "Give me a status update", Intent.STATUS, False, False),

    # --- APPROVAL (B) ---
    ("Approval: approve in thread", "Approve that.", Intent.APPROVAL, True, True),
    ("Approval: ship it in thread", "Ship it.", Intent.APPROVAL, True, True),
    ("Approval: explicit target", "Approve Levar onboarding kickoff.", Intent.APPROVAL, False, False),
    ("Approval: reject", "Reject that billing change.", Intent.APPROVAL, True, True),
    ("Approval: approve without thread → fallback", "Approve that.", Intent.FALLBACK, False, False),

    # --- TASK TRIGGER (C) ---
    ("Task: start nurture", "Start nurture for Levar.", Intent.TASK_TRIGGER, False, False),
    ("Task: run sweep", "Run a sweep for JDJ.", Intent.TASK_TRIGGER, False, False),
    ("Task: kick off onboarding", "Kick off onboarding for Sean.", Intent.TASK_TRIGGER, False, False),
    ("Task: generate report", "Generate this month's report for Levar.", Intent.TASK_TRIGGER, False, False),
    ("Task: queue content", "Queue next week's content for JDJ.", Intent.TASK_TRIGGER, False, False),

    # --- EMERGENCY STOP (D) ---
    ("Stop: everything", "Stop everything.", Intent.EMERGENCY_STOP, False, False),
    ("Stop: outbound", "Stop outbound.", Intent.EMERGENCY_STOP, False, False),
    ("Stop: pause all", "Pause all Atlas automation until I say resume.", Intent.EMERGENCY_STOP, False, False),
    ("Stop: client hold", "Stop all changes for Levar.", Intent.EMERGENCY_STOP, False, False),
    ("Stop: hold subsystem", "Hold nurture.", Intent.EMERGENCY_STOP, False, False),

    # --- REPORTING (E) ---
    ("Report: Atlas KPIs", "Show me Atlas KPIs for this week.", Intent.REPORTING, False, False),
    ("Report: client report", "Show me Levar report.", Intent.REPORTING, False, False),
    ("Report: pipeline", "Pipeline summary.", Intent.REPORTING, False, False),
    ("Report: performance", "Send me Levar's performance snapshot.", Intent.REPORTING, False, False),
    ("Report: financial", "What's my MRR and churn right now?", Intent.REPORTING, False, False),

    # --- FALLBACK (F) ---
    ("Fallback: random", "Hey how's the weather?", Intent.FALLBACK, False, False),
    ("Fallback: gibberish", "asdfgh123", Intent.FALLBACK, False, False),
    ("Fallback: empty", "", Intent.FALLBACK, False, False),
    ("Fallback: off-topic question", "Can you order me lunch?", Intent.FALLBACK, False, False),
]


def run_tests() -> int:
    passed = 0
    failed = 0
    total = len(TEST_CASES)

    print(f"{'='*70}")
    print(f"MP-3 §1 INTENT CLASSIFIER TEST HARNESS")
    print(f"{'='*70}")
    print()

    for desc, text, expected, is_thread, has_approval in TEST_CASES:
        result = classify(text, is_thread_reply=is_thread, thread_has_approval_item=has_approval)
        ok = result.intent == expected
        status = "✅ PASS" if ok else "❌ FAIL"

        if ok:
            passed += 1
        else:
            failed += 1

        print(f"{status} | {desc}")
        print(f"  Input: \"{text}\"")
        print(f"  Expected: {expected.value} | Got: {result.intent.value} (conf={result.confidence})")
        if result.parameters:
            print(f"  Params: {result.parameters}")

        # Show Slack payload for representative cases
        if ok:
            payload = dispatch(result)
            print(_fmt_payload(payload))

        print()

    print(f"{'='*70}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*70}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
