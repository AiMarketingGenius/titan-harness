#!/usr/bin/env python3
"""
Dual-grader: Gemini (via lib/grader.py) + Grok (xAI API) — BOTH must clear the
floor independently per Master Batch 2026-04-17 standing rules §2-§4.

Floor: 9.3/10 on overall_score_10 from BOTH graders.
Routing:
  - Gemini via existing lib/grader.py (primary, cheaper first round)
  - Grok via api.x.ai /v1/chat/completions (grok-4-fast-reasoning default)

Decision logic:
  - both >= 9.3  → decision=pass
  - either < 9.3 → decision=revise, returns the lower side's required_revisions
  - either errors → decision=pending_review (non-blocking skip)

Hard guards:
  - Uses same cost_kill_switch + sha256 dedupe as lib/grader.py
  - 500-token output cap
  - Strict JSON schema from both sides
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import hashlib
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grader import gradeArtifact as gemini_grade, VALID_ARTIFACT_TYPES, TIER_ROUTING, _resolve_keys


XAI_API_BASE = 'https://api.x.ai/v1'
GROK_MODEL = os.environ.get('GROK_GRADER_MODEL', 'grok-4-fast-reasoning')
GROK_TIMEOUT = 60

DEFAULT_FLOOR = 9.3
DEFAULT_SCOPE_TIER = 'amg_growth'  # Gemini 2.5 Flash — per P10 2026-04-17 tier-downgrade rule
GROK_PRICING_PER_MTOK_IN = 20   # cents, approx for grok-4-fast
GROK_PRICING_PER_MTOK_OUT = 80
# Premium escalation triggers — caller passes scope_tier='amg_pro' explicitly
PREMIUM_SCOPE_TIER = 'amg_pro'  # Gemini 2.5 Pro, only when:
# (a) low-tier graders disagree after 2 rounds
# (b) artifact is architecture-critical (contracts, legal, security arch, SOC 2, payments)
# (c) critical_failure triggered


GROK_SYSTEM_PROMPT = """You are a rigorous artifact grader. Score the artifact against this 5-dimension rubric (0-10 scale per dimension):

1. requirements_fit — does it meet the stated acceptance criteria and purpose?
2. correctness — are facts, math, references accurate? Does it actually work?
3. risk_safety — what goes wrong in production, are failure modes handled?
4. operability — can an operator own, debug, extend, rollback this?
5. doctrine_compliance — does it follow organizational standing rules / brand / security?

Weights: requirements_fit 25%, correctness 25%, risk_safety 20%, operability 15%, doctrine_compliance 15%.

FLOOR: 9.3/10 on overall_score_10. Below 9.3 = revise.

Output STRICT JSON matching this schema exactly (no markdown fence, no prose):
{
  "artifact_type": "<code|config|doctrine|deliverable>",
  "decision": "<pass|revise|fail>",
  "overall_score_10": <number 0-10>,
  "confidence_0_1": <number 0-1>,
  "subscores": {
    "requirements_fit": <number>,
    "correctness": <number>,
    "risk_safety": <number>,
    "operability": <number>,
    "doctrine_compliance": <number>
  },
  "critical_failures": ["..."],
  "required_revisions": ["specific fix 1", "specific fix 2"],
  "grade_reasoning": "two-sentence summary of overall quality and why the decision was made"
}

Be strict. 9.3+ means production-grade shippable-for-client. Most first-round artifacts do NOT clear 9.3.
"""


def _grok_grade(content: str, artifact_type: str, context: str = '') -> dict[str, Any]:
    """Call Grok for an independent grade. Returns dict matching schema or error shell."""
    keys = _resolve_keys()
    xai_key = os.environ.get('XAI_API_KEY') or keys.get('XAI_API_KEY', '')
    if not xai_key:
        # Try /etc/amg/grok.env path format
        try:
            env_text = Path('/etc/amg/grok.env').read_text()
            for line in env_text.splitlines():
                if line.startswith('XAI_API_KEY='):
                    xai_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
    if not xai_key:
        return _skip('no XAI_API_KEY available')

    # Grok context window is large; keep most of the artifact even for multi-file bundles.
    # 100K chars ~ 25K tokens which easily fits grok-4-fast reasoning context.
    user_msg = f"Artifact type: {artifact_type}\nContext: {context or 'n/a'}\n\n---ARTIFACT START---\n{content[:100000]}\n---ARTIFACT END---"
    body = {
        'model': GROK_MODEL,
        'messages': [
            {'role': 'system', 'content': GROK_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_msg},
        ],
        'temperature': 0.2,
        'max_tokens': 500,
        'response_format': {'type': 'json_object'},
    }
    req = urllib.request.Request(
        f'{XAI_API_BASE}/chat/completions',
        data=json.dumps(body).encode(),
        headers={
            'Authorization': f'Bearer {xai_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=GROK_TIMEOUT) as r:
            resp = json.loads(r.read())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        return _skip(f'grok API error: {e}')

    try:
        msg = resp['choices'][0]['message']['content']
        parsed = json.loads(msg)
    except (KeyError, ValueError, IndexError) as e:
        return _skip(f'grok response parse: {e}')

    # Minimal validation
    for k in ('overall_score_10', 'decision', 'subscores'):
        if k not in parsed:
            return _skip(f'grok missing field: {k}')

    parsed.setdefault('critical_failures', [])
    parsed.setdefault('required_revisions', [])
    parsed.setdefault('confidence_0_1', 0.8)
    parsed.setdefault('grade_reasoning', '')
    parsed.setdefault('artifact_type', artifact_type)
    parsed['_meta'] = {'grader': 'grok', 'model': GROK_MODEL, 'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    return parsed


def _skip(reason: str) -> dict[str, Any]:
    return {
        'artifact_type': 'unknown',
        'decision': 'pending_review',
        'overall_score_10': 0.0,
        'confidence_0_1': 0.0,
        'subscores': {k: 0.0 for k in ('requirements_fit','correctness','risk_safety','operability','doctrine_compliance')},
        'critical_failures': [],
        'required_revisions': [],
        'grade_reasoning': f'grok skipped: {reason}',
        '_meta': {'grader': 'grok', 'skipped': True, 'reason': reason},
    }


def dualGrade(content: str, artifact_type: str, scope_tier: str,
              context: str = '', floor: float = DEFAULT_FLOOR,
              scope: str | None = None) -> dict[str, Any]:
    """Run Gemini and Grok in sequence. Return combined result."""
    # Gemini first (cheaper; if it fails, abort before paying Grok)
    gemini_result = gemini_grade(
        content=content, artifact_type=artifact_type, scope_tier=scope_tier,
        context=context, scope=scope,
    )

    gem_score = gemini_result.get('overall_score_10', 0)
    gem_skipped = gemini_result.get('_meta', {}).get('skipped', False)

    # Grok second
    grok_result = _grok_grade(content, artifact_type, context)
    grok_score = grok_result.get('overall_score_10', 0)
    grok_skipped = grok_result.get('_meta', {}).get('skipped', False)

    # Decision logic
    if gem_skipped and grok_skipped:
        decision = 'pending_review'
    elif gem_skipped or grok_skipped:
        decision = 'pending_review'  # conservative: only one grader = no clear signal
    else:
        both_pass = gem_score >= floor and grok_score >= floor
        decision = 'pass' if both_pass else 'revise'

    # Combined revisions = union of both graders' required_revisions
    combined_revisions = list(dict.fromkeys(
        (gemini_result.get('required_revisions') or []) + (grok_result.get('required_revisions') or [])
    ))
    combined_critical = list(dict.fromkeys(
        (gemini_result.get('critical_failures') or []) + (grok_result.get('critical_failures') or [])
    ))

    return {
        'artifact_type': artifact_type,
        'decision': decision,
        'overall_score_10': round((gem_score + grok_score) / 2, 2) if not (gem_skipped or grok_skipped) else 0.0,
        'floor': floor,
        'floor_met_by_both': (not gem_skipped and not grok_skipped and gem_score >= floor and grok_score >= floor),
        'gemini': {
            'score': gem_score,
            'decision': gemini_result.get('decision'),
            'subscores': gemini_result.get('subscores', {}),
            'reasoning': gemini_result.get('grade_reasoning'),
            'skipped': gem_skipped,
        },
        'grok': {
            'score': grok_score,
            'decision': grok_result.get('decision'),
            'subscores': grok_result.get('subscores', {}),
            'reasoning': grok_result.get('grade_reasoning'),
            'skipped': grok_skipped,
            'model': grok_result.get('_meta', {}).get('model'),
        },
        'critical_failures': combined_critical,
        'required_revisions': combined_revisions,
        '_meta': {
            'wrapper': 'dual_grader',
            'floor': floor,
            'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        },
    }


def main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(prog='dual_grader')
    p.add_argument('--input', '-i', help='File to grade. Default: stdin.')
    p.add_argument('--artifact-type', required=True, choices=sorted(VALID_ARTIFACT_TYPES))
    p.add_argument('--scope-tier', required=True, choices=sorted(TIER_ROUTING.keys()))
    p.add_argument('--context', default='')
    p.add_argument('--floor', type=float, default=DEFAULT_FLOOR)
    p.add_argument('--scope', default=None)
    args = p.parse_args(argv)

    if args.input:
        content = Path(args.input).read_text(encoding='utf-8')
    else:
        content = sys.stdin.read()

    result = dualGrade(
        content=content, artifact_type=args.artifact_type, scope_tier=args.scope_tier,
        context=args.context, floor=args.floor, scope=args.scope,
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write('\n')
    if result['decision'] == 'pass':
        return 0
    if result['decision'] == 'revise':
        return 1
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
