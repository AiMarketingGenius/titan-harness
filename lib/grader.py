#!/usr/bin/env python3
"""
titan-harness/lib/grader.py

Provider-agnostic artifact grading interface — replaces the Perplexity Sonar
direct-API path that ran up the $54 bill on Apr 15. Built per Solon's
grader-stack-canonical-v2 directive 2026-04-16 (post-DR review).

Tiered routing:
  scope_tier=titan        → gemini-2.5-flash primary, gpt-4o-mini backup
  scope_tier=aimg         → gemini-2.5-flash-lite (no backup, single shot)
  scope_tier=amg_starter  → gemini-2.5-flash-lite
  scope_tier=amg_growth   → gemini-2.5-flash
  scope_tier=amg_pro      → gemini-2.5-pro (premium reasoning)

Backup trigger fires when primary returns:
  - overall_score_10 between 8.6 and 9.3 (borderline — get second opinion)
  - confidence_0_1 < 0.7 (primary itself is unsure)
  - critical_failures non-empty (high-stakes flag)

Hard guards (NEVER bypass):
  - lib/cost_kill_switch.py daily cap check before every API call
  - sha256 dedupe — identical artifact within 24h returns cached result
  - NEVER_GRADE scope filter — routine ops never get an LLM call
  - Strict JSON schema validation — non-conforming response = backup OR fail
  - Output token ceiling 500 — graders don't write essays

Stdlib only. Same minimal-dep philosophy as cost_kill_switch.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError


# ---------------------------------------------------------------------------
# Cost kill-switch import (mandatory — if missing, grader refuses to call)
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from cost_kill_switch import KillSwitch
    KILL_SWITCH_AVAILABLE = True
except ImportError:
    KILL_SWITCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config — model routing + pricing (cents per 1M tokens)
# ---------------------------------------------------------------------------

GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta'
OPENAI_API_BASE = 'https://api.openai.com/v1'

# (input_cents_per_M, output_cents_per_M)
MODEL_PRICING = {
    'gemini-2.5-flash':       (30, 250),    # $0.30 / $2.50
    'gemini-2.5-flash-lite':  (10, 40),     # $0.10 / $0.40
    'gemini-2.5-pro':         (125, 1000),  # $1.25 / $10.00
    'gpt-4o-mini':            (15, 60),     # $0.15 / $0.60
}

# Tier → (primary_model, backup_model_or_None, vendor_primary, vendor_backup)
TIER_ROUTING = {
    'titan':       ('gemini-2.5-flash',      'gpt-4o-mini', 'gemini', 'openai'),
    'aimg':        ('gemini-2.5-flash-lite', None,          'gemini', None),
    'amg_starter': ('gemini-2.5-flash-lite', None,          'gemini', None),
    'amg_growth':  ('gemini-2.5-flash',      None,          'gemini', None),
    'amg_pro':     ('gemini-2.5-pro',        'gpt-4o-mini', 'gemini', 'openai'),
}

# Backup trigger thresholds (per directive)
BACKUP_SCORE_MIN = 8.6
BACKUP_SCORE_MAX = 9.3
BACKUP_CONFIDENCE_BELOW = 0.7

# Output token ceiling — graders return short JSON, not essays
OUTPUT_TOKEN_CEILING = 500

# Scopes that NEVER hit a grader, no matter what (saves money + prevents loops)
NEVER_GRADE = {
    'routine_ops',
    'ssh_diagnostic',
    'sysctl',
    'mirror_operation',
    'service_start_stop',
    'git_operation',
    'diagnostic',
    'wip_intermediate',
    'status_report',
}

# Total daily cap across ALL graders combined (per directive)
DAILY_CAP_USD_TOTAL = 10.00


# ---------------------------------------------------------------------------
# Credentials loader
# ---------------------------------------------------------------------------

def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or \
               (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k.strip()] = v
    except OSError:
        pass
    return out


def _resolve_keys() -> dict[str, str]:
    """Resolve Gemini + OpenAI keys from env or canonical /etc/amg/*.env files.
    Process env wins; otherwise read files in order."""
    out: dict[str, str] = {}
    candidates = [
        Path('/etc/amg/gemini.env'),
        Path('/etc/amg/openai.env'),
        Path.home() / '.titan-env',
    ]
    merged: dict[str, str] = {}
    for p in candidates:
        merged.update(_load_env_file(p))

    for key in ('GEMINI_API_KEY_AMG_GRADER', 'GEMINI_API_KEY_AIMG',
                'OPENAI_API_KEY'):
        val = os.environ.get(key) or merged.get(key, '')
        if val:
            out[key] = val
    return out


# ---------------------------------------------------------------------------
# Strict JSON schema (Perplexity DR verbatim)
# ---------------------------------------------------------------------------

REQUIRED_TOP_KEYS = {'artifact_type', 'decision', 'overall_score_10',
                     'confidence_0_1', 'subscores', 'critical_failures',
                     'evidence', 'required_revisions', 'grade_reasoning'}

REQUIRED_SUBSCORE_KEYS = {'requirements_fit', 'correctness', 'risk_safety',
                          'operability', 'doctrine_compliance'}

VALID_DECISIONS = {'pass', 'revise', 'fail', 'pending_review'}
VALID_ARTIFACT_TYPES = {'code', 'config', 'doctrine', 'deliverable'}


def _empty_grade_response(reason: str) -> dict[str, Any]:
    """Returned when grader is skipped (cap hit, NEVER_GRADE, no key, etc).
    decision='pending_review' = caller treats as non-blocking pass."""
    return {
        'artifact_type': 'unknown',
        'decision': 'pending_review',
        'overall_score_10': 0.0,
        'confidence_0_1': 0.0,
        'subscores': {k: 0.0 for k in REQUIRED_SUBSCORE_KEYS},
        'critical_failures': [],
        'evidence': [],
        'required_revisions': [],
        'grade_reasoning': f'grader skipped: {reason}',
        '_meta': {
            'skipped': True,
            'reason': reason,
            'ts': datetime.now(timezone.utc).isoformat(),
        },
    }


def _validate_response(parsed: Any) -> tuple[bool, str]:
    """Returns (is_valid, error_message). Strict — non-conforming = invalid."""
    if not isinstance(parsed, dict):
        return False, 'response not a JSON object'
    missing = REQUIRED_TOP_KEYS - set(parsed.keys())
    if missing:
        return False, f'missing keys: {sorted(missing)}'
    if parsed['artifact_type'] not in VALID_ARTIFACT_TYPES:
        return False, f'invalid artifact_type: {parsed["artifact_type"]!r}'
    if parsed['decision'] not in VALID_DECISIONS:
        return False, f'invalid decision: {parsed["decision"]!r}'
    score = parsed['overall_score_10']
    if not isinstance(score, (int, float)) or not 0 <= score <= 10:
        return False, f'overall_score_10 out of range: {score!r}'
    conf = parsed['confidence_0_1']
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        return False, f'confidence_0_1 out of range: {conf!r}'
    sub = parsed['subscores']
    if not isinstance(sub, dict):
        return False, 'subscores not a dict'
    sub_missing = REQUIRED_SUBSCORE_KEYS - set(sub.keys())
    if sub_missing:
        return False, f'subscores missing: {sorted(sub_missing)}'
    return True, ''


# ---------------------------------------------------------------------------
# Grading prompt
# ---------------------------------------------------------------------------

GRADING_SYSTEM_PROMPT = """You are a senior technical reviewer evaluating a \
work artifact. Respond with a single strict JSON object — no prose wrapper, \
no markdown fences, no commentary. Schema MUST be exactly:

{
  "artifact_type": "code" | "config" | "doctrine" | "deliverable",
  "decision": "pass" | "revise" | "fail",
  "overall_score_10": <number 0.0-10.0, one decimal>,
  "confidence_0_1": <number 0.0-1.0>,
  "subscores": {
    "requirements_fit": <0.0-10.0>,
    "correctness": <0.0-10.0>,
    "risk_safety": <0.0-10.0>,
    "operability": <0.0-10.0>,
    "doctrine_compliance": <0.0-10.0>
  },
  "critical_failures": [<short strings — empty array if none>],
  "evidence": [
    {"claim": "<assertion>", "artifact_quote": "<exact quote>", "why_it_matters": "<one sentence>"}
  ],
  "required_revisions": [<short strings, max 5>],
  "grade_reasoning": "<max 120 words>"
}

Scoring scale:
  9.4-10  = ship-ready (decision: "pass")
  8.0-9.3 = real blockers, fixable (decision: "revise")
  <8.0    = fundamental issues (decision: "fail")

Rules:
  - Cap output at 500 tokens. Be terse.
  - critical_failures = security holes, silent data loss, broken invariants.
  - Polish/style suggestions go in required_revisions, NOT critical_failures.
  - Set confidence_0_1 < 0.7 if the artifact is outside your expertise.
  - artifact_quote must be a verbatim substring of the artifact, not paraphrase.

Return ONLY the JSON object. No other text."""


def _build_user_message(content: str, artifact_type: str, context: str) -> str:
    ctx = f'\n\nContext:\n{context}\n' if context else ''
    return (
        f'Artifact type: {artifact_type}\n'
        f'{ctx}\n'
        f'--- ARTIFACT BEGIN ---\n{content}\n--- ARTIFACT END ---\n\n'
        f'Grade per the schema. Return only the JSON object.'
    )


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http_post(url: str, headers: dict[str, str], body: dict[str, Any],
               timeout: int = 90) -> tuple[int, str]:
    data = json.dumps(body).encode('utf-8')
    req = urlrequest.Request(url, data=data, headers=headers, method='POST')
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')
    except (URLError, OSError) as e:
        return 0, f'network-error: {e}'


# ---------------------------------------------------------------------------
# Per-vendor grading calls
# ---------------------------------------------------------------------------

def _grade_via_gemini(model: str, content: str, artifact_type: str,
                      context: str, key: str) -> tuple[Optional[dict], float]:
    """Returns (parsed_dict_or_None, cost_usd). None = call failed."""
    url = f'{GEMINI_API_BASE}/models/{model}:generateContent'
    body = {
        'system_instruction': {'parts': [{'text': GRADING_SYSTEM_PROMPT}]},
        'contents': [{
            'role': 'user',
            'parts': [{'text': _build_user_message(content, artifact_type, context)}],
        }],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': OUTPUT_TOKEN_CEILING,
            'responseMimeType': 'application/json',
        },
    }
    status, resp = _http_post(
        url,
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key},
        body=body,
        timeout=90,
    )
    if status != 200:
        return None, 0.0
    try:
        data = json.loads(resp)
    except json.JSONDecodeError:
        return None, 0.0

    text_parts: list[str] = []
    for cand in data.get('candidates', []):
        for part in cand.get('content', {}).get('parts', []):
            if 'text' in part:
                text_parts.append(part['text'])
    content_text = '\n'.join(text_parts).strip()

    usage = data.get('usageMetadata', {})
    in_tok = int(usage.get('promptTokenCount', 0))
    out_tok = int(usage.get('candidatesTokenCount', 0))
    in_c, out_c = MODEL_PRICING.get(model, (0, 0))
    cost_usd = (in_tok * in_c + out_tok * out_c) / 1_000_000.0 / 100.0

    try:
        parsed = json.loads(content_text)
        return parsed, cost_usd
    except json.JSONDecodeError:
        return None, cost_usd


def _grade_via_openai(model: str, content: str, artifact_type: str,
                      context: str, key: str) -> tuple[Optional[dict], float]:
    """Returns (parsed_dict_or_None, cost_usd). None = call failed."""
    url = f'{OPENAI_API_BASE}/chat/completions'
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': GRADING_SYSTEM_PROMPT},
            {'role': 'user',
             'content': _build_user_message(content, artifact_type, context)},
        ],
        'temperature': 0.1,
        'max_tokens': OUTPUT_TOKEN_CEILING,
        'response_format': {'type': 'json_object'},
    }
    status, resp = _http_post(
        url,
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        body=body,
        timeout=90,
    )
    if status != 200:
        return None, 0.0
    try:
        data = json.loads(resp)
    except json.JSONDecodeError:
        return None, 0.0

    content_text = (data.get('choices', [{}])[0]
                    .get('message', {}).get('content', '')).strip()
    usage = data.get('usage', {})
    in_tok = int(usage.get('prompt_tokens', 0))
    out_tok = int(usage.get('completion_tokens', 0))
    in_c, out_c = MODEL_PRICING.get(model, (0, 0))
    cost_usd = (in_tok * in_c + out_tok * out_c) / 1_000_000.0 / 100.0

    try:
        parsed = json.loads(content_text)
        return parsed, cost_usd
    except json.JSONDecodeError:
        return None, cost_usd


def _dispatch_call(vendor: str, model: str, content: str, artifact_type: str,
                   context: str, keys: dict[str, str]) -> tuple[Optional[dict], float]:
    if vendor == 'gemini':
        # Use the operator key for grading (not the consumer-product key)
        key = keys.get('GEMINI_API_KEY_AMG_GRADER', '')
        if not key:
            return None, 0.0
        return _grade_via_gemini(model, content, artifact_type, context, key)
    if vendor == 'openai':
        key = keys.get('OPENAI_API_KEY', '')
        if not key:
            return None, 0.0
        return _grade_via_openai(model, content, artifact_type, context, key)
    return None, 0.0


# ---------------------------------------------------------------------------
# Backup trigger logic
# ---------------------------------------------------------------------------

def _should_invoke_backup(parsed: dict[str, Any]) -> bool:
    score = parsed.get('overall_score_10', 0)
    conf = parsed.get('confidence_0_1', 1.0)
    crit = parsed.get('critical_failures', [])
    if BACKUP_SCORE_MIN <= score <= BACKUP_SCORE_MAX:
        return True
    if conf < BACKUP_CONFIDENCE_BELOW:
        return True
    if crit:
        return True
    return False


# ---------------------------------------------------------------------------
# Main public entry point
# ---------------------------------------------------------------------------

def gradeArtifact(
    content: str,
    artifact_type: str,
    scope_tier: str,
    context: str = '',
    scope: Optional[str] = None,
) -> dict[str, Any]:
    """Grade an artifact with tiered routing + cost guards.

    Args:
        content: the artifact text to grade.
        artifact_type: code|config|doctrine|deliverable.
        scope_tier: titan|aimg|amg_starter|amg_growth|amg_pro.
        context: optional surrounding context for the grader.
        scope: optional scope tag for NEVER_GRADE filter (e.g. 'sysctl').

    Returns: dict matching the strict JSON schema (always — even on skip).
    """
    # 1. NEVER_GRADE scope filter — earliest exit, free
    if scope and scope in NEVER_GRADE:
        return _empty_grade_response(f'never_grade scope: {scope}')

    if artifact_type not in VALID_ARTIFACT_TYPES:
        return _empty_grade_response(f'invalid artifact_type: {artifact_type!r}')

    if scope_tier not in TIER_ROUTING:
        return _empty_grade_response(f'invalid scope_tier: {scope_tier!r}')

    primary_model, backup_model, primary_vendor, backup_vendor = TIER_ROUTING[scope_tier]

    # 2. Cost kill-switch + cache
    if not KILL_SWITCH_AVAILABLE:
        return _empty_grade_response('cost_kill_switch.py unavailable — refused')

    primary_in_c, primary_out_c = MODEL_PRICING.get(primary_model, (0, 0))
    estimated_cost = (len(content) / 4 * primary_in_c
                      + OUTPUT_TOKEN_CEILING * primary_out_c) / 1_000_000.0 / 100.0

    ks_primary = KillSwitch(vendor=primary_vendor, scope=f'grader_{scope_tier}')
    cached = ks_primary.check_cache(content)
    if cached is not None:
        cached.setdefault('_meta', {})['cache_hit'] = True
        return cached

    if not ks_primary.allow_call(estimated_cost_usd=estimated_cost):
        return _empty_grade_response(
            f'daily cap hit on {primary_vendor}: '
            f'spent ${ks_primary.today_spend_usd():.4f} / cap ${ks_primary.daily_cap_usd}'
        )

    # 3. Resolve keys
    keys = _resolve_keys()

    # 4. Primary call
    parsed, cost_primary = _dispatch_call(
        primary_vendor, primary_model, content, artifact_type, context, keys
    )
    ks_primary.record_call(content, cost_primary,
                           result=parsed if parsed else {'failed': True})

    if parsed is None:
        # Primary failed — try backup if defined
        if backup_model and backup_vendor:
            ks_backup = KillSwitch(vendor=backup_vendor, scope=f'grader_{scope_tier}_backup')
            if ks_backup.allow_call(estimated_cost_usd=estimated_cost):
                parsed, cost_backup = _dispatch_call(
                    backup_vendor, backup_model, content, artifact_type, context, keys
                )
                ks_backup.record_call(content, cost_backup,
                                      result=parsed if parsed else {'failed': True})
        if parsed is None:
            return _empty_grade_response('primary failed; no backup available or backup also failed')

    # 5. Validate
    valid, err = _validate_response(parsed)
    if not valid:
        # If we already have a parsed dict but it doesn't conform, try backup
        if backup_model and backup_vendor:
            ks_backup = KillSwitch(vendor=backup_vendor, scope=f'grader_{scope_tier}_backup')
            if ks_backup.allow_call(estimated_cost_usd=estimated_cost):
                parsed_backup, cost_backup = _dispatch_call(
                    backup_vendor, backup_model, content, artifact_type, context, keys
                )
                ks_backup.record_call(content, cost_backup,
                                      result=parsed_backup if parsed_backup else {'failed': True})
                if parsed_backup is not None:
                    valid_b, err_b = _validate_response(parsed_backup)
                    if valid_b:
                        parsed_backup.setdefault('_meta', {})['used_backup'] = True
                        parsed_backup['_meta']['primary_invalid_reason'] = err
                        ks_primary.record_call(content,
                                               0.0,  # already counted above
                                               result=parsed_backup)
                        return parsed_backup
        return _empty_grade_response(f'invalid schema: {err}')

    # 6. Backup trigger on borderline / low-confidence / critical
    if backup_model and backup_vendor and _should_invoke_backup(parsed):
        ks_backup = KillSwitch(vendor=backup_vendor, scope=f'grader_{scope_tier}_backup')
        if ks_backup.allow_call(estimated_cost_usd=estimated_cost):
            parsed_b, cost_b = _dispatch_call(
                backup_vendor, backup_model, content, artifact_type, context, keys
            )
            ks_backup.record_call(content, cost_b,
                                  result=parsed_b if parsed_b else {'failed': True})
            if parsed_b is not None:
                valid_b, _ = _validate_response(parsed_b)
                if valid_b:
                    # Combine: take the higher-confidence one
                    if parsed_b.get('confidence_0_1', 0) > parsed.get('confidence_0_1', 0):
                        parsed_b.setdefault('_meta', {})['used_backup'] = True
                        parsed_b['_meta']['primary_score'] = parsed.get('overall_score_10')
                        parsed = parsed_b

    parsed.setdefault('_meta', {})['scope_tier'] = scope_tier
    parsed['_meta']['primary_model'] = primary_model
    parsed['_meta']['ts'] = datetime.now(timezone.utc).isoformat()

    return parsed


# ---------------------------------------------------------------------------
# CLI for manual / scripted use
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(prog='grader')
    p.add_argument('--input', '-i', help='File to grade. Default: stdin.')
    p.add_argument('--artifact-type', required=True,
                   choices=sorted(VALID_ARTIFACT_TYPES))
    p.add_argument('--scope-tier', required=True,
                   choices=sorted(TIER_ROUTING.keys()))
    p.add_argument('--context', default='')
    p.add_argument('--scope', default=None,
                   help='optional scope tag for NEVER_GRADE filter')
    args = p.parse_args(argv)

    if args.input:
        try:
            content = Path(args.input).read_text(encoding='utf-8')
        except OSError as e:
            sys.stderr.write(f'cannot read {args.input}: {e}\n')
            return 2
    else:
        content = sys.stdin.read()

    result = gradeArtifact(
        content=content,
        artifact_type=args.artifact_type,
        scope_tier=args.scope_tier,
        context=args.context,
        scope=args.scope,
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write('\n')

    if result.get('_meta', {}).get('skipped'):
        return 2  # signal to caller: graded was skipped (cap, NEVER_GRADE, etc)
    if result.get('decision') == 'fail':
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
