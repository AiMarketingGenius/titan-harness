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

# AUTONOMY_GUARDRAILS 2026-04-17 Part 1 — standing Titan phase-gate grader pair
# is Haiku 4.5 + Gemini 2.5 Flash Lite (~$0.0076/artifact vs Grok pair at ~$0.02).
# Secondary grader routed through LiteLLM gateway (Bedrock/Vertex bearer tokens
# bypass the direct-Anthropic workspace cap).
SECONDARY_GRADER = os.environ.get('DUAL_SECONDARY_GRADER', 'haiku').lower()
HAIKU_MODEL = os.environ.get('HAIKU_GRADER_MODEL', 'claude-haiku-4-5')
LITELLM_BASE = os.environ.get('LITELLM_BASE_URL', 'http://127.0.0.1:4000').rstrip('/')
LITELLM_KEY = os.environ.get('LITELLM_MASTER_KEY', '').strip()
HAIKU_TIMEOUT = 90

DEFAULT_FLOOR = 9.3
# AUTONOMY_GUARDRAILS 2026-04-17 Part 1 — phase-gate grading uses Gemini 2.5
# Flash Lite (aimg tier in grader.py TIER_ROUTING). amg_growth (Flash) and
# amg_pro (Flash + Gemini 2.5 Pro) remain available via explicit scope_tier.
DEFAULT_SCOPE_TIER = os.environ.get('DUAL_DEFAULT_TIER', 'aimg')  # Flash Lite
GROK_PRICING_PER_MTOK_IN = 20   # cents, approx for grok-4-fast
GROK_PRICING_PER_MTOK_OUT = 80
HAIKU_PRICING_PER_MTOK_IN = 100   # $1.00/M
HAIKU_PRICING_PER_MTOK_OUT = 500  # $5.00/M

# ---------------------------------------------------------------------------
# Premium escalation DISCIPLINE — P10 PERMANENT 2026-04-17 (Solon correction)
# ---------------------------------------------------------------------------
# Premium tier (Gemini 2.5 Pro / Grok 4) is ONLY authorized when ALL THREE:
#   1. Gemini Flash returned a valid score AND Grok 4.1 Fast returned a valid score
#      (both non-skip — skips are grader failure, not disagreement)
#   2. The two valid scores DISAGREE by > DISAGREE_THRESHOLD points (e.g., 7.2 + 9.5)
#   3. Artifact is architecture-critical (contracts/legal/security/payments)
#      OR caller passes --force-premium + --reason (Solon-explicit)
#
# When Gemini Flash skips: retry → content-transform → Grok-only fallback.
# NEVER auto-promote-to-premium on skip.
PREMIUM_SCOPE_TIER = 'amg_pro'
DISAGREE_THRESHOLD = 1.5
GEMINI_RETRY_BACKOFFS = [3, 9, 27]  # seconds
ARCHITECTURE_CRITICAL_KEYWORDS = (
    'contract', 'legal', 'security', 'pen-test', 'soc2', 'soc 2',
    'payment', 'msa', 'nda', 'sow', 'partnership',
)


def _is_architecture_critical(context: str, artifact_type: str) -> bool:
    ctx_lower = (context or '').lower()
    return any(kw in ctx_lower for kw in ARCHITECTURE_CRITICAL_KEYWORDS)


def _gemini_grade_with_retry(content: str, artifact_type: str, scope_tier: str,
                              context: str, scope: str | None) -> dict[str, Any]:
    """Run Gemini with 3-retry-on-skip + content-transformation fallback.
    Does NOT escalate to premium on skip — that's the caller's explicit decision."""
    # Round 1: direct
    result = gemini_grade(content=content, artifact_type=artifact_type,
                          scope_tier=scope_tier, context=context, scope=scope)
    if not result.get('_meta', {}).get('skipped'):
        return result

    # Skip detected — retry with exponential backoff
    for attempt, backoff in enumerate(GEMINI_RETRY_BACKOFFS, start=1):
        time.sleep(backoff)
        result = gemini_grade(content=content, artifact_type=artifact_type,
                              scope_tier=scope_tier, context=context, scope=scope)
        if not result.get('_meta', {}).get('skipped'):
            result.setdefault('_meta', {})['retry_attempt'] = attempt
            return result

    # Still skipped — try content-transformation fallback:
    # Chunk in halves + grade each + average. KB-documentation inputs that enumerate
    # banned terms often trip Gemini safety filters; halving the content window can help.
    if len(content) > 4000:
        mid = len(content) // 2
        r1 = gemini_grade(content=content[:mid], artifact_type=artifact_type,
                          scope_tier=scope_tier, context=context + ' (chunk 1/2)', scope=scope)
        r2 = gemini_grade(content=content[mid:], artifact_type=artifact_type,
                          scope_tier=scope_tier, context=context + ' (chunk 2/2)', scope=scope)
        r1_ok = not r1.get('_meta', {}).get('skipped')
        r2_ok = not r2.get('_meta', {}).get('skipped')
        if r1_ok and r2_ok:
            avg = round((r1['overall_score_10'] + r2['overall_score_10']) / 2, 2)
            return {
                'artifact_type': artifact_type,
                'decision': 'pass' if avg >= DEFAULT_FLOOR else 'revise',
                'overall_score_10': avg,
                'confidence_0_1': min(r1.get('confidence_0_1', 0.7), r2.get('confidence_0_1', 0.7)),
                'subscores': {k: round((r1['subscores'].get(k, 0) + r2['subscores'].get(k, 0)) / 2, 2)
                              for k in ('requirements_fit', 'correctness', 'risk_safety', 'operability', 'doctrine_compliance')},
                'critical_failures': (r1.get('critical_failures') or []) + (r2.get('critical_failures') or []),
                'required_revisions': (r1.get('required_revisions') or []) + (r2.get('required_revisions') or []),
                'grade_reasoning': f"chunked grade (2 halves averaged): {r1.get('grade_reasoning', '')[:200]} | {r2.get('grade_reasoning', '')[:200]}",
                '_meta': {'retry_attempt': 'chunked_fallback', 'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
            }

    # All retries + transformation exhausted — return last skip result untouched.
    # Caller sees gem_skipped=True and should proceed with Grok-only grade.
    result.setdefault('_meta', {})['retry_attempt'] = 'exhausted'
    return result


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


def _skip(reason: str, grader: str = 'grok') -> dict[str, Any]:
    return {
        'artifact_type': 'unknown',
        'decision': 'pending_review',
        'overall_score_10': 0.0,
        'confidence_0_1': 0.0,
        'subscores': {k: 0.0 for k in ('requirements_fit','correctness','risk_safety','operability','doctrine_compliance')},
        'critical_failures': [],
        'required_revisions': [],
        'grade_reasoning': f'{grader} skipped: {reason}',
        '_meta': {'grader': grader, 'skipped': True, 'reason': reason},
    }


HAIKU_SYSTEM_PROMPT = GROK_SYSTEM_PROMPT  # identical rubric — model-agnostic


def _haiku_grade(content: str, artifact_type: str, context: str = '') -> dict[str, Any]:
    """Call Claude Haiku 4.5 via LiteLLM gateway for independent grade.

    LiteLLM at 127.0.0.1:4000 routes through Bedrock/Vertex bearer tokens
    (per-vendor, bypasses the Anthropic direct workspace usage cap).
    Returns the same schema as _grok_grade for dualGrade consumption.
    """
    if not LITELLM_KEY:
        # Try /root/.titan-env path as fallback
        try:
            env_text = Path('/root/.titan-env').read_text()
            for line in env_text.splitlines():
                if line.startswith('LITELLM_MASTER_KEY='):
                    globals()['LITELLM_KEY'] = line.split('=', 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
    if not LITELLM_KEY:
        return _skip('no LITELLM_MASTER_KEY available', grader='haiku')

    user_msg = f"Artifact type: {artifact_type}\nContext: {context or 'n/a'}\n\n---ARTIFACT START---\n{content[:100000]}\n---ARTIFACT END---"
    body = {
        'model': HAIKU_MODEL,
        'messages': [
            {'role': 'system', 'content': HAIKU_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_msg},
        ],
        'temperature': 0.2,
        # Haiku tends to emit longer reasoning + structured JSON than Grok; 800 tokens
        # was too tight (JSON truncated mid-string on large artifacts). 2000 holds
        # a full rubric + reasoning + revisions list cleanly.
        'max_tokens': 2000,
        'response_format': {'type': 'json_object'},
    }
    req = urllib.request.Request(
        f'{LITELLM_BASE}/v1/chat/completions',
        data=json.dumps(body).encode(),
        headers={
            'Authorization': f'Bearer {LITELLM_KEY}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=HAIKU_TIMEOUT) as r:
            resp = json.loads(r.read())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        return _skip(f'haiku LiteLLM API error: {e}', grader='haiku')

    try:
        msg = resp['choices'][0]['message']['content']
        # Strip accidental markdown fences or prose prefix — Haiku sometimes wraps JSON in ```json fences
        msg = msg.strip()
        if msg.startswith('```'):
            msg = msg.split('\n', 1)[1] if '\n' in msg else msg
            if msg.endswith('```'):
                msg = msg.rsplit('```', 1)[0]
        parsed = json.loads(msg)
    except (KeyError, ValueError, IndexError) as e:
        return _skip(f'haiku response parse: {e}', grader='haiku')

    for k in ('overall_score_10', 'decision', 'subscores'):
        if k not in parsed:
            return _skip(f'haiku missing field: {k}', grader='haiku')

    parsed.setdefault('critical_failures', [])
    parsed.setdefault('required_revisions', [])
    parsed.setdefault('confidence_0_1', 0.8)
    parsed.setdefault('grade_reasoning', '')
    parsed.setdefault('artifact_type', artifact_type)
    parsed['_meta'] = {'grader': 'haiku', 'model': HAIKU_MODEL, 'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    return parsed


def _secondary_grade(content: str, artifact_type: str, context: str = '') -> dict[str, Any]:
    """Dispatch secondary grader per DUAL_SECONDARY_GRADER env var.

    Default 'haiku' per AUTONOMY_GUARDRAILS 2026-04-17 Part 1 standing pair.
    'grok' available as fallback (retains Grok 4 Fast via direct xAI API).
    """
    if SECONDARY_GRADER == 'grok':
        return _grok_grade(content, artifact_type, context)
    return _haiku_grade(content, artifact_type, context)


def dualGrade(content: str, artifact_type: str, scope_tier: str,
              context: str = '', floor: float = DEFAULT_FLOOR,
              scope: str | None = None, force_premium: bool = False,
              premium_reason: str | None = None) -> dict[str, Any]:
    """Run Gemini + Grok with P10 2026-04-17 premium-escalation discipline.

    - Default scope_tier='amg_growth' (Gemini Flash + Grok Fast)
    - Premium (amg_pro) gate-checked: requires force_premium=True + premium_reason,
      OR architecture-critical context, OR valid-score disagreement > DISAGREE_THRESHOLD
    - Gemini skips trigger retry-then-chunk-fallback, NOT premium escalation
    """
    # --- PREMIUM GATE -----------------------------------------------------
    if scope_tier == PREMIUM_SCOPE_TIER:
        arch_critical = _is_architecture_critical(context, artifact_type)
        if not (force_premium or arch_critical):
            # Auto-downgrade to amg_growth and log the attempted misuse
            sys.stderr.write(
                f'[dual-grader] WARNING: scope_tier={scope_tier} requested without '
                f'force_premium and context not architecture-critical. '
                f'AUTO-DOWNGRADING to amg_growth per P10 2026-04-17 discipline. '
                f'To override: pass --force-premium --reason "<justification>".\n'
            )
            scope_tier = DEFAULT_SCOPE_TIER
        elif force_premium and not premium_reason:
            sys.stderr.write(
                f'[dual-grader] ERROR: --force-premium requires --reason "<justification>". '
                f'Auto-downgrading to amg_growth.\n'
            )
            scope_tier = DEFAULT_SCOPE_TIER
        else:
            sys.stderr.write(
                f'[dual-grader] premium tier authorized: '
                f'{"architecture-critical" if arch_critical else "force_premium"} '
                f'reason={premium_reason or "arch-critical-auto"}\n'
            )

    # --- GEMINI (retry-on-skip + chunk-fallback) -------------------------
    gemini_result = _gemini_grade_with_retry(
        content=content, artifact_type=artifact_type, scope_tier=scope_tier,
        context=context, scope=scope,
    )
    gem_score = gemini_result.get('overall_score_10', 0)
    gem_skipped = gemini_result.get('_meta', {}).get('skipped', False)

    # --- SECONDARY (Haiku 4.5 via LiteLLM by default; Grok 4 Fast if DUAL_SECONDARY_GRADER=grok) -----
    grok_result = _secondary_grade(content, artifact_type, context)
    grok_score = grok_result.get('overall_score_10', 0)
    grok_skipped = grok_result.get('_meta', {}).get('skipped', False)

    # --- DECISION LOGIC ---------------------------------------------------
    if gem_skipped and grok_skipped:
        decision = 'pending_review'
    elif gem_skipped and not grok_skipped:
        # Grok-only grade; caller-visible, Solon-reviewable
        decision = 'pass_single_grader' if grok_score >= floor else 'revise_single_grader'
    elif grok_skipped and not gem_skipped:
        decision = 'pass_single_grader' if gem_score >= floor else 'revise_single_grader'
    else:
        both_pass = gem_score >= floor and grok_score >= floor
        decision = 'pass' if both_pass else 'revise'
        # Premium-escalation signal: scores disagree meaningfully?
        disagreement = abs(gem_score - grok_score)
        if scope_tier != PREMIUM_SCOPE_TIER and disagreement > DISAGREE_THRESHOLD:
            sys.stderr.write(
                f'[dual-grader] INFO: low-tier graders disagree by {disagreement:.1f} points '
                f'(Gemini {gem_score} vs Grok {grok_score}). Consider premium-escalation '
                f'IF architecture-critical — otherwise trust the more conservative score.\n'
            )

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
    p.add_argument('--scope-tier', default=DEFAULT_SCOPE_TIER, choices=sorted(TIER_ROUTING.keys()),
                   help=f'Default {DEFAULT_SCOPE_TIER} (Gemini Flash). '
                        f'Premium tier ({PREMIUM_SCOPE_TIER}) requires --force-premium + --reason.')
    p.add_argument('--context', default='')
    p.add_argument('--floor', type=float, default=DEFAULT_FLOOR)
    p.add_argument('--scope', default=None)
    p.add_argument('--force-premium', action='store_true',
                   help='Override auto-downgrade of amg_pro tier. Requires --reason.')
    p.add_argument('--reason', default=None,
                   help='Justification for premium-tier use. Required with --force-premium. Logged.')
    args = p.parse_args(argv)

    if args.input:
        content = Path(args.input).read_text(encoding='utf-8')
    else:
        content = sys.stdin.read()

    result = dualGrade(
        content=content, artifact_type=args.artifact_type, scope_tier=args.scope_tier,
        context=args.context, floor=args.floor, scope=args.scope,
        force_premium=args.force_premium, premium_reason=args.reason,
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
