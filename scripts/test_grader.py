#!/usr/bin/env python3
"""
titan-harness/scripts/test_grader.py

Test suite for lib/grader.py per grader-stack-v2 directive.
Exercises all 5 scope_tiers + backup trigger + cost cap + cache dedupe + NEVER_GRADE.

USAGE:
  # Full live test (uses real Gemini + OpenAI keys, ~$0.10 cost):
  python3 scripts/test_grader.py

  # Mock mode (no API calls — tests routing/validation only):
  python3 scripts/test_grader.py --mock

  # Single tier:
  python3 scripts/test_grader.py --tier titan

EXIT CODES:
  0 = all tests passed
  1 = one or more tests failed
  2 = setup/import error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow imports from sibling lib/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))

try:
    from grader import (
        gradeArtifact, _resolve_keys, _validate_response,
        TIER_ROUTING, NEVER_GRADE, MODEL_PRICING,
        BACKUP_SCORE_MIN, BACKUP_SCORE_MAX, BACKUP_CONFIDENCE_BELOW,
        OUTPUT_TOKEN_CEILING,
    )
    from cost_kill_switch import KillSwitch
except ImportError as e:
    print(f"FATAL: cannot import grader/cost_kill_switch: {e}", file=sys.stderr)
    sys.exit(2)


# ANSI colors for output readability
GREEN = '\033[32m'
RED = '\033[31m'
YELLOW = '\033[33m'
DIM = '\033[2m'
RESET = '\033[0m'


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

SAMPLE_CODE = """
def calculate_weekly_revenue(orders):
    total = 0
    for order in orders:
        total += order.amount
    return total
""".strip()

SAMPLE_DOCTRINE = """
# AMG Pricing Tier Doctrine (excerpt)

The three SKUs are: Starter $497/mo, Growth $797/mo, Pro $1,497/mo.
Per Solon directive 2026-04-16: tier 3a (Atlas-as-template) and tier 3b
(fully-custom OS in client identity) must be priced high enough to not create
competition.
""".strip()

SAMPLE_CONFIG = """
# /etc/sysctl.d/99-titan-perf.conf
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq
net.core.somaxconn = 4096
vm.swappiness = 10
""".strip()


# ---------------------------------------------------------------------------
# Test framework (tiny, no pytest dep)
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ''
        self.cost_usd = 0.0

    def __str__(self):
        sym = f'{GREEN}✓{RESET}' if self.passed else f'{RED}✗{RESET}'
        cost = f' {DIM}(${self.cost_usd:.4f}){RESET}' if self.cost_usd else ''
        return f'  {sym} {self.name}{cost}\n      {DIM}{self.message}{RESET}'


def passing(name, msg='', cost=0.0):
    r = TestResult(name)
    r.passed = True
    r.message = msg
    r.cost_usd = cost
    return r


def failing(name, msg, cost=0.0):
    r = TestResult(name)
    r.passed = False
    r.message = msg
    r.cost_usd = cost
    return r


# ---------------------------------------------------------------------------
# Tests (no API call)
# ---------------------------------------------------------------------------

def test_never_grade_filter():
    """NEVER_GRADE scopes return early without any API call."""
    for scope in sorted(NEVER_GRADE):
        result = gradeArtifact(
            content=SAMPLE_CODE, artifact_type='code',
            scope_tier='titan', scope=scope,
        )
        if not result.get('_meta', {}).get('skipped'):
            return failing('never_grade_filter',
                           f'scope {scope!r} did NOT skip — got decision={result.get("decision")}')
        if 'never_grade' not in result.get('grade_reasoning', ''):
            return failing('never_grade_filter',
                           f'scope {scope!r} skipped but reason wrong: {result.get("grade_reasoning")!r}')
    return passing('never_grade_filter',
                   f'all {len(NEVER_GRADE)} NEVER_GRADE scopes correctly returned early')


def test_invalid_scope_tier():
    """Invalid scope_tier returns skipped, no API call."""
    result = gradeArtifact(content=SAMPLE_CODE, artifact_type='code',
                           scope_tier='nonsense_tier')
    if not result.get('_meta', {}).get('skipped'):
        return failing('invalid_scope_tier', 'expected skip on bad tier')
    if 'invalid scope_tier' not in result.get('grade_reasoning', ''):
        return failing('invalid_scope_tier', f'wrong reason: {result.get("grade_reasoning")}')
    return passing('invalid_scope_tier', 'correctly rejected nonsense_tier')


def test_invalid_artifact_type():
    """Invalid artifact_type returns skipped."""
    result = gradeArtifact(content=SAMPLE_CODE, artifact_type='banana',
                           scope_tier='titan')
    if not result.get('_meta', {}).get('skipped'):
        return failing('invalid_artifact_type', 'expected skip')
    return passing('invalid_artifact_type', 'correctly rejected banana')


def test_schema_validator_accepts_good():
    """_validate_response accepts a well-formed dict."""
    good = {
        'artifact_type': 'code', 'decision': 'pass', 'overall_score_10': 9.5,
        'confidence_0_1': 0.9,
        'subscores': {'requirements_fit': 9.5, 'correctness': 9.5,
                      'risk_safety': 9.5, 'operability': 9.5, 'doctrine_compliance': 9.5},
        'critical_failures': [], 'evidence': [], 'required_revisions': [],
        'grade_reasoning': 'looks good',
    }
    valid, err = _validate_response(good)
    if not valid:
        return failing('schema_accepts_good', f'rejected good response: {err}')
    return passing('schema_accepts_good', 'well-formed dict accepted')


def test_schema_validator_rejects_bad():
    """_validate_response rejects malformed dicts."""
    cases = [
        ({}, 'empty dict'),
        ({'artifact_type': 'code'}, 'missing keys'),
        ({'artifact_type': 'banana', 'decision': 'pass', 'overall_score_10': 9.5,
          'confidence_0_1': 0.9, 'subscores': {k: 9.5 for k in
          ['requirements_fit', 'correctness', 'risk_safety', 'operability', 'doctrine_compliance']},
          'critical_failures': [], 'evidence': [], 'required_revisions': [],
          'grade_reasoning': 'x'}, 'bad artifact_type'),
        ({'artifact_type': 'code', 'decision': 'pass', 'overall_score_10': 15.0,
          'confidence_0_1': 0.9, 'subscores': {k: 9.5 for k in
          ['requirements_fit', 'correctness', 'risk_safety', 'operability', 'doctrine_compliance']},
          'critical_failures': [], 'evidence': [], 'required_revisions': [],
          'grade_reasoning': 'x'}, 'score out of range'),
    ]
    for bad, why in cases:
        valid, _ = _validate_response(bad)
        if valid:
            return failing('schema_rejects_bad', f'accepted bad case: {why}')
    return passing('schema_rejects_bad', f'all {len(cases)} bad cases rejected')


def test_cost_cap_blocks_when_exceeded():
    """KillSwitch blocks calls when daily spend >= cap. Uses test ledger."""
    test_ledger = Path('/tmp/titan-grader-test-ledger.db')
    test_ledger.unlink(missing_ok=True)
    Path(str(test_ledger) + '-wal').unlink(missing_ok=True)
    Path(str(test_ledger) + '-shm').unlink(missing_ok=True)

    # Use a vendor scope that won't pollute production ledger
    ks = KillSwitch(vendor='test_vendor', daily_cap_usd=0.01,
                    scope='grader_test', ledger_path=test_ledger)

    # Empty ledger: small call should be allowed
    if not ks.allow_call(estimated_cost_usd=0.001):
        return failing('cost_cap_blocks', 'fresh ledger refused tiny call')

    # Record 0.02 spend (over cap)
    ks.record_call('cap-test-artifact', actual_cost_usd=0.02)

    # Now should refuse
    if ks.allow_call(estimated_cost_usd=0.001):
        test_ledger.unlink(missing_ok=True)
        return failing('cost_cap_blocks', 'cap-exceeded ledger still allowed call')

    test_ledger.unlink(missing_ok=True)
    Path(str(test_ledger) + '-wal').unlink(missing_ok=True)
    Path(str(test_ledger) + '-shm').unlink(missing_ok=True)
    return passing('cost_cap_blocks', 'fail-closed when cap exceeded')


def test_dedupe_returns_cache():
    """Same artifact called twice → second call hits cache (no API)."""
    test_ledger = Path('/tmp/titan-grader-test-ledger2.db')
    test_ledger.unlink(missing_ok=True)
    Path(str(test_ledger) + '-wal').unlink(missing_ok=True)
    Path(str(test_ledger) + '-shm').unlink(missing_ok=True)

    ks = KillSwitch(vendor='test_dedupe_vendor', daily_cap_usd=10.0,
                    scope='grader_test', ledger_path=test_ledger)
    payload = {'final_grade': 'A', 'cached_at': '2026-04-16T22:00:00Z'}
    ks.record_call('dedupe-artifact-text', actual_cost_usd=0.001, result=payload)

    cached = ks.check_cache('dedupe-artifact-text')
    if cached is None:
        test_ledger.unlink(missing_ok=True)
        return failing('dedupe_returns_cache', 'expected cache hit, got None')
    if cached.get('final_grade') != 'A':
        test_ledger.unlink(missing_ok=True)
        return failing('dedupe_returns_cache', f'cached payload wrong: {cached}')

    miss = ks.check_cache('different-text')
    if miss is not None:
        test_ledger.unlink(missing_ok=True)
        return failing('dedupe_returns_cache', f'expected None for different text, got {miss}')

    test_ledger.unlink(missing_ok=True)
    Path(str(test_ledger) + '-wal').unlink(missing_ok=True)
    Path(str(test_ledger) + '-shm').unlink(missing_ok=True)
    return passing('dedupe_returns_cache', 'cache hit on same artifact, miss on different')


def test_routing_table_complete():
    """Every tier has a primary model defined and pricing exists for it."""
    for tier, (primary, backup, pv, bv) in TIER_ROUTING.items():
        if primary not in MODEL_PRICING:
            return failing('routing_complete', f'{tier}: primary {primary} has no pricing')
        if backup and backup not in MODEL_PRICING:
            return failing('routing_complete', f'{tier}: backup {backup} has no pricing')
    return passing('routing_complete',
                   f'all {len(TIER_ROUTING)} tiers have valid models + pricing')


# ---------------------------------------------------------------------------
# Tests (live API — only if --live, costs ~$0.10)
# ---------------------------------------------------------------------------

def test_live_grade_titan_tier():
    """Real API call: grade SAMPLE_CODE with scope_tier=titan."""
    result = gradeArtifact(
        content=SAMPLE_CODE, artifact_type='code',
        scope_tier='titan', context='unit test of grader.py',
    )
    if result.get('_meta', {}).get('skipped'):
        return failing('live_titan', f'skipped: {result.get("grade_reasoning")}')
    valid, err = _validate_response(result)
    if not valid:
        return failing('live_titan', f'invalid schema: {err}')
    score = result['overall_score_10']
    decision = result['decision']
    return passing('live_titan',
                   f'gemini-2.5-flash: score={score}, decision={decision}, '
                   f'meta={result.get("_meta", {}).get("primary_model")}')


def test_live_grade_aimg_tier():
    """Real API call: grade SAMPLE_CONFIG with scope_tier=aimg (Flash-Lite)."""
    result = gradeArtifact(
        content=SAMPLE_CONFIG, artifact_type='config',
        scope_tier='aimg', context='aimg routing test',
    )
    if result.get('_meta', {}).get('skipped'):
        return failing('live_aimg', f'skipped: {result.get("grade_reasoning")}')
    valid, err = _validate_response(result)
    if not valid:
        return failing('live_aimg', f'invalid schema: {err}')
    return passing('live_aimg',
                   f'gemini-2.5-flash-lite: score={result["overall_score_10"]}, '
                   f'decision={result["decision"]}')


def test_live_grade_amg_pro_tier():
    """Real API call: grade SAMPLE_DOCTRINE with scope_tier=amg_pro (Pro model)."""
    result = gradeArtifact(
        content=SAMPLE_DOCTRINE, artifact_type='doctrine',
        scope_tier='amg_pro', context='pro tier doctrine grading test',
    )
    if result.get('_meta', {}).get('skipped'):
        return failing('live_amg_pro', f'skipped: {result.get("grade_reasoning")}')
    valid, err = _validate_response(result)
    if not valid:
        return failing('live_amg_pro', f'invalid schema: {err}')
    return passing('live_amg_pro',
                   f'gemini-2.5-pro: score={result["overall_score_10"]}, '
                   f'decision={result["decision"]}, used_backup={result.get("_meta", {}).get("used_backup", False)}')


def test_live_keys_present():
    """Both Gemini grader key + OpenAI key resolve from /etc/amg/*.env."""
    keys = _resolve_keys()
    missing = []
    if 'GEMINI_API_KEY_AMG_GRADER' not in keys:
        missing.append('GEMINI_API_KEY_AMG_GRADER (need /etc/amg/gemini.env)')
    if 'OPENAI_API_KEY' not in keys:
        missing.append('OPENAI_API_KEY (need /etc/amg/openai.env)')
    if missing:
        return failing('live_keys_present', f'missing: {", ".join(missing)}')
    return passing('live_keys_present',
                   f'gemini grader key + OpenAI key both resolved')


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

NO_API_TESTS = [
    test_never_grade_filter,
    test_invalid_scope_tier,
    test_invalid_artifact_type,
    test_schema_validator_accepts_good,
    test_schema_validator_rejects_bad,
    test_cost_cap_blocks_when_exceeded,
    test_dedupe_returns_cache,
    test_routing_table_complete,
]

LIVE_TESTS = [
    test_live_keys_present,
    test_live_grade_titan_tier,
    test_live_grade_aimg_tier,
    test_live_grade_amg_pro_tier,
]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--mock', action='store_true',
                   help='skip live API tests')
    p.add_argument('--live-only', action='store_true',
                   help='only run live API tests')
    args = p.parse_args(argv)

    print(f'\n{DIM}=== lib/grader.py test suite ==={RESET}\n')

    results: list[TestResult] = []

    if not args.live_only:
        print(f'{DIM}--- no-API tests (free) ---{RESET}')
        for t in NO_API_TESTS:
            r = t()
            results.append(r)
            print(r)

    if not args.mock:
        print(f'\n{DIM}--- live API tests (real cost ~$0.10) ---{RESET}')
        for t in LIVE_TESTS:
            r = t()
            results.append(r)
            print(r)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total_cost = sum(r.cost_usd for r in results)

    print(f'\n{DIM}=== summary ==={RESET}')
    print(f'  {GREEN}passed:{RESET}  {passed}')
    print(f'  {RED if failed else DIM}failed:{RESET}  {failed}')
    if total_cost:
        print(f'  {DIM}total cost:{RESET} ${total_cost:.4f}')

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
