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
ANTHROPIC_VERSION = '2023-06-01'
DEFAULT_REVISER_MODEL = 'claude-haiku-4-5-20251001'

# sonar-pro pricing per 1M tokens, in CENTS
SONAR_PRO_INPUT_CENTS_PER_M = 500   # $5.00 → 500¢
SONAR_PRO_OUTPUT_CENTS_PER_M = 1500  # $15.00 → 1500¢

# haiku-4-5 pricing per 1M tokens, in CENTS
HAIKU_INPUT_CENTS_PER_M = 80   # $0.80 → 80¢
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
            'min_acceptable_grade': os.environ['POLICY_WAR_ROOM_MIN_GRADE'] or 'B',
            'max_refinement_rounds': int(os.environ['POLICY_WAR_ROOM_MAX_ROUNDS'] or 3),
            'log_table': os.environ['POLICY_WAR_ROOM_TABLE'] or 'war_room_exchanges',
            'cost_ceiling_cents_per_exchange': int(
                os.environ.get('POLICY_WAR_ROOM_COST_CEILING', '25') or 25),
            'slack_channel': os.environ.get('POLICY_WAR_ROOM_SLACK_CHANNEL',
                                            '#amg-war-room'),
            'require_passing_grade_before_lock': os.environ.get(
                'POLICY_WAR_ROOM_REQUIRE_PASSING', '1') == '1',
            'project_id': os.environ.get('POLICY_PROJECT_ID', 'EOM'),
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
        'min_acceptable_grade': 'B',
        'max_refinement_rounds': 3,
        'log_table': 'war_room_exchanges',
        'cost_ceiling_cents_per_exchange': 25,
        'slack_channel': '#amg-war-room',
        'require_passing_grade_before_lock': True,
        'project_id': 'EOM',
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

GRADING_SYSTEM_PROMPT = """You are an independent technical reviewer grading \
plans, architecture decisions, and phase-completion reports produced by an \
autonomous build agent called "Titan" for an AI marketing agency (AMG).

Your job is ADVERSARIAL review. Find real problems. Praise is not your role.
Grade on these dimensions (weighted by trigger_source):

  phase_completion      → evidence quality, test coverage, verification \
gaps, security (RLS, auth), error handling, operational readiness
  plan_finalization     → clarity, feasibility, missing steps, risk, \
acceptance criteria, rollback plan, cost awareness
  architecture_decision → correctness, simplicity vs. over-engineering, \
security implications, alternatives considered, reversibility
  manual                → general technical quality + whatever context the \
user supplied

Output MUST be a single JSON object, no prose wrapper, no code fence, in \
exactly this shape:

{
  "grade": "A" | "B" | "C" | "D" | "F",
  "summary": "one sentence verdict, <= 140 chars",
  "issues": [
    {"severity": "critical|high|medium|low", "text": "specific problem with \
file/line if known"}
  ],
  "recommendations": [
    "concrete actionable change, imperative voice"
  ]
}

Grade scale:
  A = ship as-is, no material issues
  B = ship with minor fixes, no blockers
  C = significant gaps, fix before shipping
  D = fundamental problems, major rework
  F = broken, wrong approach, or unsafe

Return ONLY the JSON object. No markdown, no preamble, no trailing text."""


def _build_grading_user_message(titan_output: str, phase: str,
                                trigger_source: str, context: str) -> str:
    ctx_block = f"\n\nAdditional context:\n{context}" if context else ''
    return (
        f'Phase: {phase}\n'
        f'Trigger: {trigger_source}\n'
        f'{ctx_block}\n\n'
        f'--- TITAN OUTPUT BEGIN ---\n'
        f'{titan_output}\n'
        f'--- TITAN OUTPUT END ---\n\n'
        f'Grade it. JSON only.'
    )


def _parse_grade_json(raw: str) -> tuple[str, list[str], list[str], str]:
    """Extract grade/issues/recommendations/summary from Perplexity response.

    Perplexity sometimes wraps JSON in a code fence or adds a preface
    despite instructions. Strip common wrappers, then json.loads.
    """
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ```
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        # Find first { and last } — crude but handles trailing prose
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            text = text[start:end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return 'ERROR', [f'json-parse-failed: {raw[:200]}'], [], 'unparseable response'

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


# ---------------------------------------------------------------------------
# Revision prompt (Claude Haiku)
# ---------------------------------------------------------------------------

REVISION_SYSTEM_PROMPT = """You are Titan, an autonomous build agent for AMG. \
An independent reviewer (Perplexity sonar-pro) graded your previous output \
and found issues. Produce a REVISED version of the output that addresses \
every issue and incorporates every recommendation.

Rules:
  1. Preserve the original structure and intent. Do not rewrite from scratch.
  2. Address each issue explicitly.
  3. Do not add new scope beyond fixing what the reviewer flagged.
  4. Output only the revised document. No preamble, no commentary, no \
"Here is the revised version:".
"""


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

#: Grades that trigger a Slack ping. A/B stay silent (noise reduction) —
#: Solon only wants to see questionable plans. Every round still lands in
#: Supabase public.war_room_exchanges regardless.
SLACK_NOTIFY_GRADES = {'C', 'D', 'F', 'ERROR'}


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
        """Run the full war-room loop on a piece of Titan output."""
        project_id = project_id or self.policy.get('project_id', 'EOM')
        if trigger_source not in ('phase_completion', 'plan_finalization',
                                  'architecture_decision', 'manual'):
            trigger_source = 'manual'

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
        key = self.creds.get('PERPLEXITY_API_KEY', '')
        if not key:
            return GradeResult(
                grade='ERROR', issues=['PERPLEXITY_API_KEY not set'],
                recommendations=[], summary='no API key',
                raw_response='', input_tokens=0, output_tokens=0,
                cost_cents=0.0, error='PERPLEXITY_API_KEY not set')

        model = self.policy.get('model', 'sonar-pro')
        body = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': GRADING_SYSTEM_PROMPT},
                {'role': 'user',
                 'content': _build_grading_user_message(
                     titan_output, phase, trigger_source, context)},
            ],
            'max_tokens': 1500,
            'temperature': 0.1,
        }

        status, resp = _http_post(
            PERPLEXITY_URL,
            headers={
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json',
            },
            body=body,
            timeout=60,
        )

        if status != 200:
            return GradeResult(
                grade='ERROR', issues=[f'http {status}: {resp[:300]}'],
                recommendations=[], summary=f'http {status}',
                raw_response=resp[:2000], input_tokens=0, output_tokens=0,
                cost_cents=0.0, error=f'http {status}')

        try:
            data = json.loads(resp)
        except json.JSONDecodeError:
            return GradeResult(
                grade='ERROR', issues=['response not json'],
                recommendations=[], summary='not json',
                raw_response=resp[:2000], input_tokens=0, output_tokens=0,
                cost_cents=0.0, error='not json')

        content = (data.get('choices', [{}])[0]
                   .get('message', {}).get('content', ''))
        usage = data.get('usage', {}) or {}
        input_tokens = int(usage.get('prompt_tokens', 0) or 0)
        output_tokens = int(usage.get('completion_tokens', 0) or 0)
        cost = _estimate_sonar_cost(input_tokens, output_tokens)

        grade, issues, recommendations, summary = _parse_grade_json(content)

        return GradeResult(
            grade=grade,
            issues=issues,
            recommendations=recommendations,
            summary=summary,
            raw_response=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_cents=cost,
        )

    def _revise(self, previous_output: str, grade: GradeResult,
                phase: str, trigger_source: str) -> tuple[str, float]:
        """Call Claude Haiku to produce a revised version. Returns (text, cost)."""
        key = self.creds.get('ANTHROPIC_API_KEY', '')
        if not key:
            return '', 0.0

        body = {
            'model': DEFAULT_REVISER_MODEL,
            'max_tokens': 4096,
            'system': REVISION_SYSTEM_PROMPT,
            'messages': [
                {'role': 'user',
                 'content': _build_revision_user_message(
                     previous_output, grade, phase, trigger_source)},
            ],
        }

        status, resp = _http_post(
            ANTHROPIC_URL,
            headers={
                'x-api-key': key,
                'anthropic-version': ANTHROPIC_VERSION,
                'Content-Type': 'application/json',
            },
            body=body,
            timeout=60,
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
        cost = _estimate_haiku_cost(in_tok, out_tok)

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
