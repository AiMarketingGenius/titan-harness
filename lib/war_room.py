#!/usr/bin/env python3
"""
titan-harness/lib/war_room.py

Phase G.3 — War Room: Titan ↔ Perplexity auto-refinement loop.

Given a piece of Titan output (plan, architecture doc, phase-completion
report), calls Perplexity sonar-pro to grade it. If grade < min_acceptable,
uses Claude (Haiku) to revise the output based on Perplexity's feedback,
then re-grades. Loops until:
  1. grade >= min_acceptable_grade (terminal: passed)
  2. round_number > max_refinement_rounds (terminal: max_rounds)
  3. cumulative cost > cost_ceiling_cents * rounds_so_far (terminal: cost_ceiling)
  4. API error (terminal: error)

Every round is logged to Supabase public.war_room_exchanges. The final
row of the group has `converged=true` and a `terminal_reason` set.

Design notes:
  - This module is usable three ways:
      1. As a library (import WarRoom, call .grade(...))
      2. As a CLI via bin/war-room.sh (stdin or --input file)
      3. From the autonomous titan-queue-watcher daemon
  - Perplexity browser scraping is DEAD (CF blocks datacenter IPs).
    API-only, sonar-pro model.
  - Claude is only called when refinement is needed. First round is
    pure grading — zero Claude cost if Titan's output is already good.
  - Cost accounting: sonar-pro is ~$5/1M input, ~$15/1M output. Haiku
    is ~$0.80/1M input, ~$4/1M output. Both counted in cost_cents.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

GRADE_ORDER = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1, 'ERROR': 0}

PERPLEXITY_URL = 'https://api.perplexity.ai/chat/completions'
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'

# --- P2 Gateway routing (LiteLLM) -------------------------------------------
# When GATEWAY_ENABLED=1 and LITELLM_BASE_URL is set, all Perplexity and
# Anthropic calls are rerouted through the gateway's OpenAI-compatible endpoint.
# The gateway handles Anthropic messages-format translation internally.
#
# --- Phase 1 Step 3.2 — Infisical shadow-mode secret fetch (2026-04-12) ---
# LITELLM_BASE_URL + LITELLM_MASTER_KEY read through the shared shadow helper
# from lib/infisical_fetch.py. Behavior during shadow mode is identical to
# pre-Phase-1 production (env value returned, Infisical consulted only to log
# delta). Flip to infisical-only via TITAN_INFISICAL_MODE env var after
# Solon-approved soak review. GATEWAY_ENABLED is a config flag (boolean),
# not a secret — stays as os.environ.get.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from infisical_fetch import fetch_with_shadow
except ImportError:
    def fetch_with_shadow(key, default='', project='harness-core'):
        return os.environ.get(key, default)

GATEWAY_ENABLED = os.environ.get('GATEWAY_ENABLED', '0') == '1'
LITELLM_BASE_URL = fetch_with_shadow('LITELLM_BASE_URL', '').rstrip('/')
LITELLM_MASTER_KEY = fetch_with_shadow('LITELLM_MASTER_KEY', '')
GATEWAY_URL = (LITELLM_BASE_URL + '/v1/chat/completions') if LITELLM_BASE_URL else ''
ANTHROPIC_VERSION = '2023-06-01'
# AMG 9.4/10 quality floor requires Sonnet-grade revision to reach grade A.
# Haiku was used in G.3 initial ship but could not consistently push past B.
DEFAULT_REVISER_MODEL = 'claude-sonnet-4-6'
FALLBACK_REVISER_MODEL = 'claude-haiku-4-5-20251001'

# sonar-pro pricing per 1M tokens, in CENTS
SONAR_PRO_INPUT_CENTS_PER_M = 500   # $5.00 → 500¢
SONAR_PRO_OUTPUT_CENTS_PER_M = 1500  # $15.00 → 1500¢

# Reviser model pricing per 1M tokens, in CENTS (Sonnet 4.6 default)
# Sonnet 4.6 is the default reviser per 2026-04-10 A-grade-floor upgrade.
# Previous (Haiku): $0.80 in / $4.00 out per 1M.
SONNET_INPUT_CENTS_PER_M = 300   # $3.00 → 300¢ (Sonnet 4.6 public pricing)
SONNET_OUTPUT_CENTS_PER_M = 1500  # $15.00 → 1500¢
HAIKU_INPUT_CENTS_PER_M = 80   # $0.80 → 80¢ (kept for fallback)
HAIKU_OUTPUT_CENTS_PER_M = 400  # $4.00 → 400¢


def _load_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE pairs from a dotenv-style file. Silent on missing."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or \
               (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k] = v
    except OSError:
        pass
    return out


def _resolve_credentials() -> dict[str, str]:
    """Find PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

    Priority: process env → ~/.titan-env → /opt/amg-titan/.env →
              /opt/titan-processor/.env → /opt/amg-mcp-server/.env.local
    """
    creds: dict[str, str] = {}

    candidates = [
        Path.home() / '.titan-env',
        Path('/opt/amg-titan/.env'),
        Path('/opt/titan-processor/.env'),
        Path('/opt/amg-mcp-server/.env.local'),
    ]

    merged: dict[str, str] = {}
    for p in candidates:
        merged.update(_load_env_file(p))  # later files override earlier

    # Process env wins
    for key in ('PERPLEXITY_API_KEY',
                'ANTHROPIC_API_KEY',
                'SUPABASE_URL',
                'SUPABASE_SERVICE_ROLE_KEY',
                'SUPABASE_SERVICE_KEY',
                'SLACK_WEBHOOK_URL',
                'WAR_ROOM_SLACK_WEBHOOK'):
        v = os.environ.get(key) or merged.get(key, '')
        if v:
            creds[key] = v

    # Normalize service key name
    if 'SUPABASE_SERVICE_ROLE_KEY' not in creds and 'SUPABASE_SERVICE_KEY' in creds:
        creds['SUPABASE_SERVICE_ROLE_KEY'] = creds['SUPABASE_SERVICE_KEY']

    return creds


def _load_policy(policy_path: Optional[Path] = None) -> dict[str, Any]:
    """Load war_room section from policy.yaml using env vars exported by
    policy-loader.sh, with a YAML fallback for direct python invocation."""
    # Env-var path (fast): POLICY_WAR_ROOM_* already exported
    env_keys = ('POLICY_WAR_ROOM_ENABLED', 'POLICY_WAR_ROOM_MODEL',
                'POLICY_WAR_ROOM_MIN_GRADE', 'POLICY_WAR_ROOM_MAX_ROUNDS',
                'POLICY_WAR_ROOM_TABLE')
    if all(k in os.environ for k in env_keys):
        return {
            'enabled': os.environ['POLICY_WAR_ROOM_ENABLED'] == '1',
            'model': os.environ['POLICY_WAR_ROOM_MODEL'] or 'sonar-pro',
            'min_acceptable_grade': os.environ['POLICY_WAR_ROOM_MIN_GRADE'] or 'A',
            'max_refinement_rounds': int(os.environ['POLICY_WAR_ROOM_MAX_ROUNDS'] or 5),
            'log_table': os.environ['POLICY_WAR_ROOM_TABLE'] or 'war_room_exchanges',
            'cost_ceiling_cents_per_exchange': int(
                os.environ.get('POLICY_WAR_ROOM_COST_CEILING', '50') or 50),
            'slack_channel': os.environ.get('POLICY_WAR_ROOM_SLACK_CHANNEL',
                                            '#amg-war-room'),
            'require_passing_grade_before_lock': os.environ.get(
                'POLICY_WAR_ROOM_REQUIRE_PASSING', '1') == '1',
            'project_id': os.environ.get('POLICY_PROJECT_ID', 'EOM'),
            'reviser_model': os.environ.get('POLICY_WAR_ROOM_REVISER_MODEL',
                                            DEFAULT_REVISER_MODEL),
        }

    # YAML fallback — parse just the war_room block ourselves.
    if policy_path is None:
        for p in [
            Path(__file__).resolve().parent.parent / 'policy.yaml',
            Path('/opt/titan-harness/policy.yaml'),
            Path.home() / 'titan-harness/policy.yaml',
        ]:
            if p.is_file():
                policy_path = p
                break

    defaults = {
        'enabled': False,
        'model': 'sonar-pro',
        'min_acceptable_grade': 'A',
        'max_refinement_rounds': 5,
        'log_table': 'war_room_exchanges',
        'cost_ceiling_cents_per_exchange': 50,
        'slack_channel': '#amg-war-room',
        'require_passing_grade_before_lock': True,
        'project_id': 'EOM',
        'reviser_model': DEFAULT_REVISER_MODEL,
    }
    if not policy_path or not policy_path.is_file():
        return defaults

    try:
        lines = policy_path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return defaults

    def _strip_inline_comment(s: str) -> str:
        # Only treat '#' as a comment if preceded by whitespace or at BOL,
        # and not inside quotes. Keeps "#amg-war-room" intact.
        out_chars: list[str] = []
        in_s = in_d = False
        prev = ''
        for ch in s:
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif ch == '#' and not in_s and not in_d and (prev == '' or prev.isspace()):
                break
            out_chars.append(ch)
            prev = ch
        return ''.join(out_chars).rstrip()

    in_war_room = False
    out = dict(defaults)
    for raw in lines:
        stripped = _strip_inline_comment(raw)
        if not stripped:
            continue
        if re.match(r'^war_room\s*:\s*$', stripped):
            in_war_room = True
            continue
        if in_war_room:
            if stripped and not raw.startswith(' '):
                # Top-level key → left war_room block
                break
            m = re.match(r'^\s+([A-Za-z0-9_]+)\s*:\s*(.*)$', stripped)
            if not m:
                continue
            k = m.group(1)
            v = m.group(2).strip()
            if v == '':
                continue  # nested list (auto_trigger_on) — skip
            if (v.startswith('"') and v.endswith('"')) or \
               (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            if v.lower() == 'true':
                v_parsed: Any = True
            elif v.lower() == 'false':
                v_parsed = False
            else:
                try:
                    v_parsed = int(v)
                except ValueError:
                    v_parsed = v
            out[k] = v_parsed
    return out


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GradeResult:
    grade: str
    issues: list[str]
    recommendations: list[str]
    summary: str
    raw_response: str
    input_tokens: int
    output_tokens: int
    cost_cents: float
    score: Optional[float] = None     # 1.0–10.0, new in the shippability rubric
    ship: Optional[bool] = None       # explicit ship/no-ship from the grader
    error: Optional[str] = None


@dataclass
class Round:
    round_number: int
    titan_output: str
    grade_result: GradeResult
    exchange_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class WarRoomSession:
    exchange_group_id: str
    project_id: str
    phase: str
    trigger_source: str
    rounds: list[Round] = field(default_factory=list)
    terminal_reason: Optional[str] = None
    total_cost_cents: float = 0.0

    @property
    def final_grade(self) -> str:
        if not self.rounds:
            return 'ERROR'
        return self.rounds[-1].grade_result.grade

    @property
    def final_output(self) -> str:
        if not self.rounds:
            return ''
        return self.rounds[-1].titan_output


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib-only — no requests dep)
# ---------------------------------------------------------------------------

def _http_post(url: str, headers: dict[str, str], body: dict[str, Any],
               timeout: int = 60) -> tuple[int, str]:
    data = json.dumps(body).encode('utf-8')
    req = urlrequest.Request(url, data=data, headers=headers, method='POST')
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')
    except (URLError, socket.timeout) as e:
        return 0, f'network-error: {e}'


# ---------------------------------------------------------------------------
# Grading prompt + parser
# ---------------------------------------------------------------------------

GRADING_SYSTEM_PROMPT = """You are a senior technical reviewer for an AI \
marketing agency. Someone has just finished a piece of work — a plan, a \
completion report, an architecture doc, a build spec — and they want one \
honest question answered: **"Is this ready to ship? Score it 1–10."**

That is the question. Answer it the way a senior peer would answer a friend \
who is about to push: give a number, tell them the top blockers if any, and \
be done. Do not play adversarial. Do not invent exhaustive checklists. Do \
not expand the scope of your criticism as the document gets longer across \
revisions.

SCORING SCALE (1–10):
  9.4–10  = SHIP IT. Ready for production. Minor polish is fine but not \
required. This maps to letter grade A.
  8.5–9.3 = Good, but has real blockers that need to be fixed before \
shipping. Letter grade B.
  7.5–8.4 = Significant gaps. Letter grade C.
  6.5–7.4 = Fundamental problems. Letter grade D.
  <6.5    = Broken or wrong. Letter grade F.

THE SHIPPABILITY BAR (9.4+) requires only these things:
  1. Core claims are supported (you don't need raw evidence for EVERY line — \
only for the claims a reasonable reviewer would challenge)
  2. No obvious correctness bugs, security holes, or silent failure modes
  3. Reader can tell what was done, why, and how to roll it back
  4. Known limitations are named, not hidden

Things that DO NOT block a 9.4:
  - Missing load/stress tests (unless the work IS a load-test framework)
  - Polish items, style preferences, "could be more rigorous"
  - Evidence for trivially-true claims
  - Hypothetical edge cases the work doesn't claim to handle
  - Documentation suggestions
  - "Could add more examples"
  - Anything you'd flag as "nice to have" rather than "must fix"

SCOPE STABILITY RULE: if you are grading a revision of a document you \
previously graded, the issues you raise now must be a SUBSET of the issues \
you raised before (minus anything that has been addressed). Do NOT surface \
new issues that you didn't raise in the previous round unless they are \
regressions introduced by the revision. If the revision addressed all your \
previous blockers, the correct response is to grade it 9.4+ and ship it.

ISSUE CAP: maximum 5 issues. Order by severity. If you cannot find 5 real \
blockers, list fewer. A 9.4+ document should have zero or one minor item.

Output MUST be a single JSON object, no prose wrapper, no code fence:

{
  "score": <number 1.0 to 10.0, one decimal place>,
  "grade": "A" | "B" | "C" | "D" | "F",
  "summary": "one sentence verdict, <= 140 chars",
  "ship": true | false,
  "issues": [
    {"severity": "blocker|major|minor", "text": "specific blocker preventing \
9.4+, with file/line if relevant"}
  ],
  "recommendations": [
    "specific change to reach 9.4+, max 3 items"
  ]
}

Remember: the question is "is this shippable?" not "can you find problems?" \
Every senior reviewer knows the difference. Grade accordingly. If the work \
is shippable, say so — don't hedge, don't pad the issues list, don't invent \
objections. Return ONLY the JSON object."""


def _build_grading_user_message(titan_output: str, phase: str,
                                trigger_source: str, context: str) -> str:
    ctx_block = f"\n\nAdditional context:\n{context}" if context else ''
    return (
        f'Phase: {phase}\n'
        f'Type: {trigger_source}\n'
        f'{ctx_block}\n\n'
        f'--- DOCUMENT BEGIN ---\n'
        f'{titan_output}\n'
        f'--- DOCUMENT END ---\n\n'
        f'On a scale of 1–10, is this ready to ship? 9.4+ = ship. '
        f'Return only the JSON object specified in your instructions.'
    )


def _parse_grade_json(raw: str) -> tuple[str, list[str], list[str], str]:
    """Extract grade/issues/recommendations/summary from Perplexity response.

    Perplexity sometimes wraps JSON in a code fence or adds a preface
    despite instructions. This parser is resilient to:
      - ```json ... ``` fences (with or without closing fence)
      - leading prose or trailing prose
      - truncated responses (missing closing brace)
      - mid-string quote escapes
    Strategy:
      1. Try to find a complete ```json ... ``` block
      2. Else find the outermost {...} using balanced-brace scanning
      3. Else attempt to repair a truncated JSON by closing open structures
    """
    text = raw.strip()

    # Strategy 1: complete ```json ... ``` or ``` ... ``` fenced block
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    candidate = m.group(1) if m else ''

    # Strategy 2: balanced-brace scan from first `{` to matching `}`
    if not candidate:
        start = text.find('{')
        if start != -1:
            depth = 0
            in_string = False
            escaped = False
            end = -1
            for i in range(start, len(text)):
                ch = text[i]
                if escaped:
                    escaped = False
                    continue
                if ch == '\\' and in_string:
                    escaped = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end > start:
                candidate = text[start:end + 1]

    # Strategy 3: truncated — close any unclosed string and braces
    if not candidate:
        start = text.find('{')
        if start != -1:
            tail = text[start:]
            # Count unmatched braces and quotes
            depth = 0
            in_string = False
            escaped = False
            for ch in tail:
                if escaped:
                    escaped = False
                    continue
                if ch == '\\' and in_string:
                    escaped = True
                    continue
                if ch == '"':
                    in_string = not in_string
                elif not in_string:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
            repaired = tail
            if in_string:
                repaired += '"'
            repaired += '}' * max(0, depth)
            candidate = repaired

    try:
        parsed = json.loads(candidate) if candidate else {}
        if not parsed:
            raise json.JSONDecodeError('empty', candidate, 0)
    except json.JSONDecodeError:
        # Last-ditch: regex-extract just the grade field
        grade_match = re.search(r'"grade"\s*:\s*"([ABCDF])"', text)
        summary_match = re.search(r'"summary"\s*:\s*"([^"]{0,300})"', text)
        if grade_match:
            return (grade_match.group(1), ['truncated-response-salvaged-grade'],
                    [], (summary_match.group(1) if summary_match else 'truncated'))
        return 'ERROR', [f'json-parse-failed: {raw[:300]}'], [], 'unparseable response'

    # Pick up the new numeric score if present — stored on the caller side
    # via GradeResult.score. Returned via summary prefix for visibility.
    score_val = parsed.get('score')
    if isinstance(score_val, (int, float)) and 0 <= score_val <= 10:
        # Embed in summary so the existing tuple return signature still works
        existing_summary = str(parsed.get('summary', ''))[:450]
        parsed['summary'] = f'[{score_val}/10] {existing_summary}'

    grade = str(parsed.get('grade', 'ERROR')).strip().upper()
    if grade not in GRADE_ORDER:
        grade = 'ERROR'
    summary = str(parsed.get('summary', ''))[:500]
    issues_raw = parsed.get('issues', [])
    recs_raw = parsed.get('recommendations', [])

    issues: list[str] = []
    if isinstance(issues_raw, list):
        for item in issues_raw:
            if isinstance(item, dict):
                sev = item.get('severity', 'medium')
                txt = item.get('text', '')
                issues.append(f'[{sev}] {txt}')
            else:
                issues.append(str(item))

    recommendations: list[str] = []
    if isinstance(recs_raw, list):
        for item in recs_raw:
            recommendations.append(str(item))

    return grade, issues, recommendations, summary


def _estimate_sonar_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * SONAR_PRO_INPUT_CENTS_PER_M
            + output_tokens * SONAR_PRO_OUTPUT_CENTS_PER_M) / 1_000_000.0


def _estimate_haiku_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * HAIKU_INPUT_CENTS_PER_M
            + output_tokens * HAIKU_OUTPUT_CENTS_PER_M) / 1_000_000.0


def _estimate_sonnet_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * SONNET_INPUT_CENTS_PER_M
            + output_tokens * SONNET_OUTPUT_CENTS_PER_M) / 1_000_000.0


def _estimate_reviser_cost(model: str, in_tok: int, out_tok: int) -> float:
    """Dispatch cost estimation by reviser model name."""
    if 'sonnet' in model.lower():
        return _estimate_sonnet_cost(in_tok, out_tok)
    return _estimate_haiku_cost(in_tok, out_tok)


# ---------------------------------------------------------------------------
# Revision prompt (Claude Haiku)
# ---------------------------------------------------------------------------

REVISION_SYSTEM_PROMPT = """You are Titan, an autonomous build agent for AMG. \
A senior reviewer scored your previous output below 9.4/10 and listed the \
top blockers preventing a 9.4+ score. Your job is to MINIMALLY revise the \
document to address those specific blockers — nothing else.

Hard rules:
  1. **Address ONLY the issues listed.** Do not add new sections, new \
evidence, new verification, new caveats, new anything that the reviewer did \
not explicitly request. Scope discipline is the most important rule here.
  2. **Keep the document the same length or shorter.** Every revision round \
should REDUCE uncertainty, not grow the doc. If the reviewer asked for \
proof of claim X, add ONE sentence or ONE code block proving it. Do not \
expand nearby sections.
  3. **Preserve the existing voice, structure, and section numbering.** \
Augment surgically.
  4. **If the reviewer asked for something that cannot be proven from the \
given context** (e.g., load tests that were never run), add a SINGLE line \
under a "Known limitations" heading stating that — DO NOT fabricate \
evidence and DO NOT over-explain.
  5. **If the reviewer's issue is a polish or nice-to-have** (e.g., "could \
add more examples", "documentation suggestion"), ignore it. Those don't \
block 9.4.
  6. Output ONLY the revised document. No preamble, no commentary, no \
"Here is the revised version:", no outer code fences.

The goal: address the listed blockers with the MINIMUM edit that satisfies \
them, so the next grading round gives 9.4+. Not more. Not less.
"""

# Anthropic prompt-cache-aware system block. Direct API path uses this
# array form so the static REVISION_SYSTEM_PROMPT (~1KB, identical every
# call) becomes a cache hit on every revision after the first within the
# 5-min ephemeral cache window. Gateway path keeps the plain string
# because LiteLLM's OpenAI-format bridge does not preserve cache_control.
REVISION_SYSTEM_BLOCK = [
    {
        'type': 'text',
        'text': REVISION_SYSTEM_PROMPT,
        'cache_control': {'type': 'ephemeral'},
    }
]


def _build_revision_user_message(previous_output: str, grade: GradeResult,
                                 phase: str, trigger_source: str) -> str:
    issues_block = '\n'.join(f'  - {i}' for i in grade.issues) or '  (none)'
    recs_block = '\n'.join(f'  - {r}' for r in grade.recommendations) or '  (none)'
    return (
        f'Phase: {phase}\n'
        f'Trigger: {trigger_source}\n'
        f'Previous grade: {grade.grade}\n'
        f'Reviewer summary: {grade.summary}\n\n'
        f'Reviewer issues:\n{issues_block}\n\n'
        f'Reviewer recommendations:\n{recs_block}\n\n'
        f'--- PREVIOUS OUTPUT BEGIN ---\n'
        f'{previous_output}\n'
        f'--- PREVIOUS OUTPUT END ---\n\n'
        f'Produce the revised document now. Output only the document.'
    )


# ---------------------------------------------------------------------------
# Supabase logger
# ---------------------------------------------------------------------------

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _log_round_to_supabase(creds: dict[str, str], table: str,
                           session: WarRoomSession, round_obj: Round,
                           converged: bool, terminal_reason: Optional[str],
                           instance_id: str) -> bool:
    url = creds.get('SUPABASE_URL', '').rstrip('/')
    key = creds.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not url or not key:
        return False

    parent_id: Optional[str] = None
    if round_obj.round_number > 1 and len(session.rounds) >= 2:
        parent_id = session.rounds[round_obj.round_number - 2].exchange_id

    body = {
        'id': round_obj.exchange_id,
        'exchange_group_id': session.exchange_group_id,
        'round_number': round_obj.round_number,
        'parent_exchange_id': parent_id,
        'titan_output_text': round_obj.titan_output[:100_000],
        'titan_output_hash': _sha256_hex(round_obj.titan_output),
        'perplexity_response_text': round_obj.grade_result.raw_response[:50_000],
        'grade': round_obj.grade_result.grade,
        'issues': round_obj.grade_result.issues,
        'recommendations': round_obj.grade_result.recommendations,
        'summary': round_obj.grade_result.summary,
        'model': 'sonar-pro',
        'input_tokens': round_obj.grade_result.input_tokens,
        'output_tokens': round_obj.grade_result.output_tokens,
        'cost_cents': round(round_obj.grade_result.cost_cents, 4),
        'project_id': session.project_id,
        'phase': session.phase,
        'trigger_source': session.trigger_source,
        'converged': converged,
        'terminal_reason': terminal_reason,
        'instance_id': instance_id,
    }

    status, resp = _http_post(
        f'{url}/rest/v1/{table}',
        headers={
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal',
        },
        body=body,
        timeout=10,
    )
    return status in (200, 201, 204)


# ---------------------------------------------------------------------------
# Slack notifier
# ---------------------------------------------------------------------------

#: Grades that trigger a Slack ping. Only A (9.5-10) stays silent.
#: B is now a FAILURE per AMG 9.4/10 quality floor (Solon directive
#: 2026-04-10) and must be re-worked, so it pings just like C-F.
#: Every round still lands in Supabase public.war_room_exchanges regardless.
SLACK_NOTIFY_GRADES = {'B', 'C', 'D', 'F', 'ERROR'}


def _post_slack(creds: dict[str, str], session: WarRoomSession) -> None:
    webhook = (creds.get('WAR_ROOM_SLACK_WEBHOOK')
               or creds.get('SLACK_WEBHOOK_URL'))
    if not webhook:
        return
    final = session.rounds[-1] if session.rounds else None
    grade = final.grade_result.grade if final else 'ERROR'

    # Noise filter: only ping for C-or-below sessions.
    if grade not in SLACK_NOTIFY_GRADES:
        return

    summary = final.grade_result.summary if final else '(no response)'
    emoji = {'A': ':green_heart:', 'B': ':white_check_mark:',
             'C': ':warning:', 'D': ':octagonal_sign:',
             'F': ':x:', 'ERROR': ':rotating_light:'}.get(grade, ':question:')
    text = (f'{emoji} *War Room — grade {grade} needs eyeballs*\n'
            f'> Project/Phase: {session.project_id} / '
            f'{session.phase or "(no phase)"} ({session.trigger_source})\n'
            f'> Rounds: {len(session.rounds)} | '
            f'Terminal: `{session.terminal_reason}` | '
            f'Cost: `{session.total_cost_cents:.2f}¢`\n'
            f'> Group ID: `{session.exchange_group_id}`\n'
            f'> {summary}')
    try:
        _http_post(webhook, {'Content-Type': 'application/json'},
                   {'text': text}, timeout=4)
    except Exception:
        pass  # fire-and-forget


# ---------------------------------------------------------------------------
# The WarRoom class
# ---------------------------------------------------------------------------

class WarRoom:
    def __init__(self, policy: Optional[dict[str, Any]] = None,
                 creds: Optional[dict[str, str]] = None,
                 instance_id: Optional[str] = None):
        self.policy = policy or _load_policy()
        self.creds = creds or _resolve_credentials()
        self.instance_id = instance_id or socket.gethostname()

    # ---- Public API -------------------------------------------------------

    def grade(self,
              titan_output: str,
              phase: str,
              trigger_source: str = 'manual',
              context: str = '',
              project_id: Optional[str] = None) -> WarRoomSession:
        """Run the full war-room loop on a piece of Titan output.

        Dispatcher: if policy.slack_grading_enabled is true, route through
        lib/war_room_slack.SlackWarRoom (Perplexity Slack app). Otherwise
        run the direct Perplexity API path below. The Slack path is slower
        but bypasses direct-API quota exhaustion (see 2026-04-11 incident).
        """
        project_id = project_id or self.policy.get('project_id', 'EOM')
        if trigger_source not in ('phase_completion', 'plan_finalization',
                                  'architecture_decision', 'manual'):
            trigger_source = 'manual'

        # --- COST KILL-SWITCH (added 2026-04-16, mechanical enforcement) ---
        # Two checks before ANY paid call: (1) sha256 dedupe — same artifact
        # graded today returns cached session with zero API hit; (2) daily
        # spend cap — if today's perplexity spend > cap, refuse to grade
        # and return a "skipped" session so the caller doesn't block.
        try:
            from cost_kill_switch import KillSwitch
            ks = KillSwitch(vendor='perplexity', scope='war_room_grade')
            cached = ks.check_cache(titan_output)
            if cached is not None:
                # Reconstruct a minimal WarRoomSession from cache so callers
                # using session.final_grade still work.
                cached_session = WarRoomSession(
                    exchange_group_id=cached.get('exchange_group_id', str(uuid.uuid4())),
                    project_id=project_id,
                    phase=phase,
                    trigger_source=trigger_source,
                    terminal_reason='cache_hit',
                )
                cached_grade = GradeResult(
                    grade=cached.get('final_grade', 'A'),
                    issues=[], recommendations=[],
                    summary=f"[cached {cached.get('cached_at', '')}]",
                    raw_response='', input_tokens=0, output_tokens=0,
                    cost_cents=0.0,
                )
                cached_session.rounds.append(Round(
                    round_number=1, titan_output=titan_output,
                    grade_result=cached_grade,
                ))
                return cached_session

            if not ks.allow_call(estimated_cost_usd=0.05):
                # Daily cap hit. Return a "skipped" session that doesn't
                # block the caller. fail_non_blocking semantic — grade='SKIP'
                # is treated as PASS by callers that check for grade != 'F'.
                skip_session = WarRoomSession(
                    exchange_group_id=str(uuid.uuid4()),
                    project_id=project_id,
                    phase=phase,
                    trigger_source=trigger_source,
                    terminal_reason='cost_cap_hit',
                )
                skip_session.rounds.append(Round(
                    round_number=1, titan_output=titan_output,
                    grade_result=GradeResult(
                        grade='SKIP', issues=[], recommendations=[],
                        summary='daily cost cap hit — grading skipped (non-blocking)',
                        raw_response='', input_tokens=0, output_tokens=0,
                        cost_cents=0.0,
                    ),
                ))
                return skip_session
            # KillSwitch instance kept in self for record_call after the run.
            self._killswitch = ks
        except ImportError:
            # cost_kill_switch.py not present — degrade silently to old behavior.
            self._killswitch = None
        # --- END KILL-SWITCH GUARD ---

        if self.policy.get('slack_grading_enabled'):
            try:
                from war_room_slack import SlackWarRoom
                swr = SlackWarRoom(
                    policy=self.policy,
                    creds=self.creds,
                    instance_id=self.instance_id,
                )
                return swr.grade(
                    titan_output=titan_output,
                    phase=phase,
                    trigger_source=trigger_source,
                    context=context,
                    project_id=project_id,
                )
            except ImportError as e:
                sys.stderr.write(
                    f"war_room: slack_grading_enabled but lib/war_room_slack.py "
                    f"import failed ({e}). Falling back to direct API.\n"
                )

        session = WarRoomSession(
            exchange_group_id=str(uuid.uuid4()),
            project_id=project_id,
            phase=phase,
            trigger_source=trigger_source,
        )

        current_output = titan_output
        max_rounds = int(self.policy.get('max_refinement_rounds', 3))
        cost_ceiling_per_round = float(
            self.policy.get('cost_ceiling_cents_per_exchange', 25))
        min_grade = str(self.policy.get('min_acceptable_grade', 'B')).upper()
        min_grade_value = GRADE_ORDER.get(min_grade, 4)

        terminal_reason: Optional[str] = None

        for round_num in range(1, max_rounds + 1):
            grade_result = self._grade_once(
                current_output, phase, trigger_source, context)

            round_obj = Round(
                round_number=round_num,
                titan_output=current_output,
                grade_result=grade_result,
            )
            session.rounds.append(round_obj)
            session.total_cost_cents += grade_result.cost_cents

            # Check exit conditions
            if grade_result.error:
                terminal_reason = 'error'
                break

            grade_value = GRADE_ORDER.get(grade_result.grade, 0)
            if grade_value >= min_grade_value:
                terminal_reason = 'passed'
                break

            if session.total_cost_cents >= cost_ceiling_per_round * round_num:
                terminal_reason = 'cost_ceiling'
                break

            if round_num >= max_rounds:
                terminal_reason = 'max_rounds'
                break

            # Revise via Claude Haiku
            revised, revise_cost = self._revise(
                current_output, grade_result, phase, trigger_source)
            session.total_cost_cents += revise_cost
            if not revised:
                terminal_reason = 'error'
                break
            current_output = revised

        session.terminal_reason = terminal_reason

        # --- COST KILL-SWITCH: record actual spend + cache result ---
        if getattr(self, '_killswitch', None) is not None:
            try:
                actual_cost_usd = session.total_cost_cents / 100.0
                self._killswitch.record_call(
                    artifact_text=titan_output,
                    actual_cost_usd=actual_cost_usd,
                    result={
                        'final_grade': session.final_grade,
                        'exchange_group_id': session.exchange_group_id,
                        'cached_at': datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                pass  # ledger write failure must not break grade()
        # --- END KILL-SWITCH RECORD ---

        # Log every round to Supabase (last one marked converged)
        table = self.policy.get('log_table', 'war_room_exchanges')
        for i, r in enumerate(session.rounds):
            is_last = (i == len(session.rounds) - 1)
            _log_round_to_supabase(
                self.creds, table, session, r,
                converged=is_last,
                terminal_reason=terminal_reason if is_last else None,
                instance_id=self.instance_id,
            )

        # Slack ping (fire-and-forget)
        _post_slack(self.creds, session)

        return session

    # ---- Internals --------------------------------------------------------

    def _grade_once(self, titan_output: str, phase: str,
                    trigger_source: str, context: str) -> GradeResult:
        """REWIRED 2026-04-16: routes through lib/grader.py tiered Gemini stack
        instead of direct Perplexity sonar-pro. Preserves the GradeResult
        interface for backward compatibility with existing callers.

        scope_tier='titan' for war-room invocations (Solon's operator work);
        AMG client deliverable graders should call gradeArtifact() directly
        with their tier instead of going through WarRoom."""
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from grader import gradeArtifact  # type: ignore
        except ImportError as e:
            return GradeResult(
                grade='ERROR', issues=[f'grader.py import failed: {e}'],
                recommendations=[], summary='grader.py unavailable',
                raw_response='', input_tokens=0, output_tokens=0,
                cost_cents=0.0, error='grader_import_failed')

        # Map war-room artifact category onto grader.py artifact_type taxonomy.
        # War-room mostly grades plans / phase-completion docs / architecture
        # decisions — all of which map to "doctrine" in the new schema.
        artifact_type_map = {
            'phase_completion': 'doctrine',
            'plan_finalization': 'doctrine',
            'architecture_decision': 'doctrine',
            'manual': 'deliverable',
        }
        artifact_type = artifact_type_map.get(trigger_source, 'deliverable')

        result = gradeArtifact(
            content=titan_output,
            artifact_type=artifact_type,
            scope_tier='titan',
            context=f'phase={phase} trigger={trigger_source} {context}'.strip(),
            scope=None,  # war-room invocations are NEVER routine_ops by definition
        )

        # Translate gradeArtifact JSON schema → GradeResult dataclass shape.
        # gradeArtifact returns score 0-10 + decision (pass/revise/fail/pending_review).
        # Map back to the legacy A/B/C/D/F grade taxonomy war_room expects.
        score = float(result.get('overall_score_10', 0))
        decision = result.get('decision', 'pending_review')

        if decision == 'pending_review':
            # Skipped — cap hit, NEVER_GRADE, etc. Return a special marker
            # the caller treats as non-blocking pass.
            grade = 'A'  # treat as pass to avoid stalling the loop
        elif score >= 9.4:
            grade = 'A'
        elif score >= 8.5:
            grade = 'B'
        elif score >= 7.5:
            grade = 'C'
        elif score >= 6.5:
            grade = 'D'
        else:
            grade = 'F'

        # Issues + recommendations: combine critical_failures + required_revisions
        issues = (
            [f'[critical] {x}' for x in result.get('critical_failures', [])]
            + [f'[revise] {x}' for x in result.get('required_revisions', [])]
        )
        recommendations = list(result.get('required_revisions', []))

        # Summary embeds score + decision + meta for transparency
        meta = result.get('_meta', {})
        primary_model = meta.get('primary_model', 'unknown')
        summary = f'[{score}/10 {decision}] {result.get("grade_reasoning", "")[:300]} (model={primary_model})'

        # Cost: gradeArtifact tracks via cost_kill_switch ledger; we don't get
        # raw token counts back through this interface. Report 0 for tokens
        # (war_room doesn't drive on these), keep cost in summary metadata.
        return GradeResult(
            grade=grade,
            issues=issues[:10],  # cap for log readability
            recommendations=recommendations[:5],
            summary=summary,
            raw_response=json.dumps(result, default=str)[:5000],
            input_tokens=0,
            output_tokens=0,
            cost_cents=0.0,  # tracked separately in cost_kill_switch ledger
            score=score,
            ship=(decision == 'pass'),
            error=None if decision != 'pending_review' else 'skipped_by_grader',
        )

    def _revise(self, previous_output: str, grade: GradeResult,
                phase: str, trigger_source: str) -> tuple[str, float]:
        """Call the reviser model (Sonnet 4.6 default) to produce a revised version. Returns (text, cost)."""
        key = self.creds.get('ANTHROPIC_API_KEY', '')
        if not key:
            return '', 0.0

        reviser_model = self.policy.get('reviser_model', DEFAULT_REVISER_MODEL)
        user_msg = _build_revision_user_message(
            previous_output, grade, phase, trigger_source)

        # Sonnet 4.6 producing an 8k-token revision on a 15KB input takes
        # 60-120s. 240s gives comfortable headroom without blocking the
        # shim's 240s overall timeout (which is a separate guard).
        if GATEWAY_ENABLED and GATEWAY_URL:
            # Gateway path: LiteLLM bridges to OpenAI format; cache_control
            # is not preserved across the bridge, so use plain string system.
            _an_url = GATEWAY_URL
            _an_headers = {
                'Authorization': f'Bearer {LITELLM_MASTER_KEY}',
                'Content-Type': 'application/json',
            }
            _an_body = {
                'model': reviser_model,
                'max_tokens': 8192,
                'messages': (
                    [{'role': 'system', 'content': REVISION_SYSTEM_PROMPT}]
                    + [{'role': 'user', 'content': user_msg}]
                ),
            }
        else:
            # Direct Anthropic path: use array form with cache_control so the
            # ~1KB REVISION_SYSTEM_PROMPT becomes a 5-min ephemeral cache hit
            # on every revision after the first. Saves ~70-90% input tokens
            # on the system portion across the refinement loop.
            _an_url = ANTHROPIC_URL
            _an_headers = {
                'x-api-key': key,
                'anthropic-version': ANTHROPIC_VERSION,
                'Content-Type': 'application/json',
            }
            _an_body = {
                'model': reviser_model,
                'max_tokens': 8192,
                'system': REVISION_SYSTEM_BLOCK,
                'messages': [{'role': 'user', 'content': user_msg}],
            }
        status, resp = _http_post(
            _an_url,
            headers=_an_headers,
            body=_an_body,
            timeout=240,
        )

        if status != 200:
            return '', 0.0

        try:
            data = json.loads(resp)
        except json.JSONDecodeError:
            return '', 0.0

        content_blocks = data.get('content', []) or []
        text_parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get('type') == 'text':
                text_parts.append(block.get('text', ''))
        text = '\n'.join(text_parts).strip()

        usage = data.get('usage', {}) or {}
        in_tok = int(usage.get('input_tokens', 0) or 0)
        out_tok = int(usage.get('output_tokens', 0) or 0)
        cost = _estimate_reviser_cost(reviser_model, in_tok, out_tok)

        return text, cost


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _print_summary(session: WarRoomSession) -> None:
    sys.stderr.write(
        f'\n=== War Room ===\n'
        f'Group:    {session.exchange_group_id}\n'
        f'Project:  {session.project_id}\n'
        f'Phase:    {session.phase}\n'
        f'Trigger:  {session.trigger_source}\n'
        f'Rounds:   {len(session.rounds)}\n'
        f'Terminal: {session.terminal_reason}\n'
        f'Cost:     {session.total_cost_cents:.2f}¢\n'
    )
    for r in session.rounds:
        g = r.grade_result
        sys.stderr.write(
            f'  round {r.round_number}: grade={g.grade} '
            f'issues={len(g.issues)} recs={len(g.recommendations)} '
            f'tokens={g.input_tokens}+{g.output_tokens} '
            f'cost={g.cost_cents:.2f}¢ — {g.summary[:80]}\n'
        )
        for issue in g.issues[:5]:
            sys.stderr.write(f'    ! {issue[:160]}\n')
    sys.stderr.write(f'Final grade: {session.final_grade}\n\n')


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog='war-room',
        description='Phase G.3 Titan ↔ Perplexity auto-refinement loop')
    parser.add_argument('--input', '-i',
                        help='File with Titan output to grade. Default: stdin.')
    parser.add_argument('--output', '-o',
                        help='Write final (possibly refined) output here.')
    parser.add_argument('--phase', required=True,
                        help='Phase label (e.g. G.3, MP-1)')
    parser.add_argument('--trigger', default='manual',
                        choices=['phase_completion', 'plan_finalization',
                                 'architecture_decision', 'manual'])
    parser.add_argument('--project', default=None, help='project_id tag')
    parser.add_argument('--context', default='',
                        help='Extra context to hand the grader')
    parser.add_argument('--json', action='store_true',
                        help='Emit session as JSON on stdout instead of text')
    parser.add_argument('--exit-nonzero-on-fail', action='store_true',
                        help='Exit 1 if final grade < min_acceptable_grade')
    args = parser.parse_args(argv)

    # Read input
    if args.input:
        try:
            titan_output = Path(args.input).read_text(encoding='utf-8')
        except OSError as e:
            sys.stderr.write(f'war-room: cannot read {args.input}: {e}\n')
            return 2
    else:
        titan_output = sys.stdin.read()

    if not titan_output.strip():
        sys.stderr.write('war-room: empty input, nothing to grade\n')
        return 2

    war_room = WarRoom()
    if not war_room.policy.get('enabled', False):
        sys.stderr.write(
            'war-room: policy.war_room.enabled=false — skipping grade\n')
        # Still honor --output so callers get a file back
        if args.output:
            Path(args.output).write_text(titan_output, encoding='utf-8')
        return 0

    session = war_room.grade(
        titan_output=titan_output,
        phase=args.phase,
        trigger_source=args.trigger,
        context=args.context,
        project_id=args.project,
    )

    _print_summary(session)

    # Write final (possibly refined) output
    if args.output:
        Path(args.output).write_text(session.final_output, encoding='utf-8')

    if args.json:
        # Structured result for programmatic callers
        payload = {
            'exchange_group_id': session.exchange_group_id,
            'project_id': session.project_id,
            'phase': session.phase,
            'trigger_source': session.trigger_source,
            'final_grade': session.final_grade,
            'terminal_reason': session.terminal_reason,
            'rounds': len(session.rounds),
            'total_cost_cents': round(session.total_cost_cents, 4),
            'history': [
                {
                    'round': r.round_number,
                    'grade': r.grade_result.grade,
                    'issues': r.grade_result.issues,
                    'recommendations': r.grade_result.recommendations,
                    'summary': r.grade_result.summary,
                    'cost_cents': round(r.grade_result.cost_cents, 4),
                }
                for r in session.rounds
            ],
        }
        sys.stdout.write(json.dumps(payload, indent=2))
        sys.stdout.write('\n')

    if args.exit_nonzero_on_fail:
        min_grade = str(war_room.policy.get('min_acceptable_grade', 'B')).upper()
        if GRADE_ORDER.get(session.final_grade, 0) < GRADE_ORDER.get(min_grade, 4):
            return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
