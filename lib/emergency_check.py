"""DIR-2026-04-28-002a Step 3.4 + 3.5 — Emergency-mode harness library.

Used by Titan + Achilles harnesses (and Iris poll loop on VPS) to:
  - read the fast-poll flag with 3-tier fallback (Redis → file → Supabase)
  - poll for pending emergency signals via /api/emergency/pending
  - acknowledge a signal once handled via /api/emergency/acknowledge (HMAC-signed)
  - dispatch on signal_type (KILL/EDIT/PAUSE/RESUME)

Per v3 §3.4 — 3-tier fallback so the heartbeat acceleration mechanism
survives Redis being unreachable AND filesystem being unreachable. Per
v3 §3.5 — top-of-loop check is the same shape on both Titan + Achilles.

Synthetic test mode (SYNTHETIC=1 env var): all signal handlers log + ack
but do NOT take destructive action. Used by scripts/test_emergency_e2e.py.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

DEFAULT_API_BASE = os.environ.get('AMG_API_BASE', 'https://memory.aimarketinggenius.io')
EMERGENCY_FLAG_DIR = pathlib.Path(os.environ.get('AMG_EMERGENCY_FLAG_DIR', os.path.expanduser('~/.amg/emergency')))
REDIS_URL = os.environ.get('AMG_REDIS_URL', 'redis://127.0.0.1:6379/0')
SYNTHETIC_MODE = os.environ.get('SYNTHETIC') == '1'


# ---------------------------------------------------------------------------
# Tier 1 — Redis fast-poll flag read (best-effort; missing redis lib = skip)
# ---------------------------------------------------------------------------
def _read_redis_fast_poll(agent: str) -> Optional[bool]:
    try:
        import redis  # type: ignore
    except ImportError:
        return None
    try:
        r = redis.Redis.from_url(REDIS_URL, socket_timeout=1.0, socket_connect_timeout=1.0)
        val = r.get(f'agent:{agent}:fast_poll')
        if val is None:
            return False  # Redis available, no flag set
        return val in (b'1', '1', b'true', 'true', 1, True)
    except Exception:
        return None  # Redis unreachable → fall through to file


# ---------------------------------------------------------------------------
# Tier 2 — File fast-poll flag read (~/.amg/emergency/{agent}.flag)
# ---------------------------------------------------------------------------
def _read_file_fast_poll(agent: str) -> Optional[bool]:
    flag_path = EMERGENCY_FLAG_DIR / f'{agent}.flag'
    if not flag_path.exists():
        return None  # File doesn't exist — flag not set OR fs not used; defer
    try:
        # Anything in the file = flag set; mtime within last 60s = still hot.
        mtime = flag_path.stat().st_mtime
        return (time.time() - mtime) < 60
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tier 3 — Supabase agent_config.fast_poll read (via REST API)
# ---------------------------------------------------------------------------
def _read_supabase_fast_poll(agent: str) -> Optional[bool]:
    # Issue a small read against agent_config — falls through if endpoint
    # unavailable. Caller treats None as "no signal", which is the safe
    # default (poll at normal cadence).
    try:
        url = f'{DEFAULT_API_BASE}/api/agent-config?agent_id={urllib.parse.quote(agent)}'
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return bool(data.get('fast_poll'))
    except Exception:
        return None


def read_fast_poll_flag(agent: str) -> tuple[bool, str]:
    """3-tier fallback read: Redis → file → Supabase. First non-None wins.

    Returns (flag_value, source) where source is 'redis'|'file'|'supabase'|'none'.
    'none' means no tier returned a definitive answer; default to False (normal cadence).
    """
    for source, fn in [
        ('redis', _read_redis_fast_poll),
        ('file', _read_file_fast_poll),
        ('supabase', _read_supabase_fast_poll),
    ]:
        result = fn(agent)
        if result is not None:
            return (result, source)
    return (False, 'none')


# ---------------------------------------------------------------------------
# Pending-signal fetch (no HMAC — read-only, agent-scoped server-side)
# ---------------------------------------------------------------------------
def fetch_pending_signals(agent: str) -> list[dict[str, Any]]:
    url = f'{DEFAULT_API_BASE}/api/emergency/pending?agent={urllib.parse.quote(agent)}'
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data.get('signals') or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Acknowledge (HMAC-signed)
# ---------------------------------------------------------------------------
def _hmac_sign(secret: str, body: dict[str, Any]) -> str:
    # Match server-side canonicalizeBody(): JS JSON.stringify default uses
    # no whitespace (separators=(',', ':')). Python's default has spaces;
    # we must match exactly for HMAC to verify.
    canonical = json.dumps(body, sort_keys=True, separators=(',', ':'))
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def acknowledge_signal(signal_id: str, agent: str, hmac_secret: str, caller: str = 'eom') -> dict[str, Any]:
    body = {'signal_id': signal_id, 'agent': agent}
    sig = _hmac_sign(hmac_secret, body)
    req = urllib.request.Request(
        f'{DEFAULT_API_BASE}/api/emergency/acknowledge',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'X-Caller-Identity': caller,
            'X-Signature': sig,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {'success': False, 'status': e.code, 'error': e.read().decode('utf-8')}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ---------------------------------------------------------------------------
# Dispatcher — per v3 §3.5 pseudocode (KILL/EDIT/PAUSE/RESUME)
# ---------------------------------------------------------------------------
def handle_signal(signal: dict[str, Any], agent: str, hmac_secret: str, *, synthetic: bool = SYNTHETIC_MODE) -> str:
    """Process one signal. Returns short status string.

    Synthetic mode (SYNTHETIC=1 env): logs + ack but does NOT exit/halt/abort.
    """
    sig_type = signal.get('signal_type')
    sig_id = signal.get('id')
    label = f'[{sig_type} signal_id={sig_id} agent={agent} synthetic={synthetic}]'

    if sig_type == 'KILL':
        if synthetic:
            print(f'{label} synthetic KILL — would log_state_snapshot + abort + sys.exit(0)')
        else:
            # Real KILL handler:
            #   1. log_state_snapshot()
            #   2. abort_current_tool()
            #   3. acknowledge
            #   4. sys.exit(0)
            pass
        ack = acknowledge_signal(sig_id, agent, hmac_secret)
        return f'KILL handled (synthetic={synthetic}) ack={ack.get("success")}'

    if sig_type == 'PAUSE':
        if synthetic:
            print(f'{label} synthetic PAUSE — would halt_at_checkpoint + await_resume')
        ack = acknowledge_signal(sig_id, agent, hmac_secret)
        return f'PAUSE handled (synthetic={synthetic}) ack={ack.get("success")}'

    if sig_type == 'RESUME':
        if synthetic:
            print(f'{label} synthetic RESUME — would resume_from_paused_state')
        ack = acknowledge_signal(sig_id, agent, hmac_secret)
        return f'RESUME handled (synthetic={synthetic}) ack={ack.get("success")}'

    if sig_type == 'EDIT':
        if synthetic:
            print(f'{label} synthetic EDIT — would pause_at_safe_point + await_new_directive_via_iris')
        ack = acknowledge_signal(sig_id, agent, hmac_secret)
        return f'EDIT handled (synthetic={synthetic}) ack={ack.get("success")}'

    return f'UNKNOWN signal_type={sig_type}'


# ---------------------------------------------------------------------------
# Top-of-loop check (used by harnesses every iteration)
# ---------------------------------------------------------------------------
def check_emergency(agent: str, hmac_secret: str, *, synthetic: bool = SYNTHETIC_MODE) -> Optional[str]:
    """Top-of-loop check. Returns first signal handled (or None if no pending).

    Per v3 §3.6 — created_at ASC ordering at the API layer eliminates
    double-fire for concurrent KILLs. The harness picks the first; if a
    second arrives during processing, it stays pending and is handled
    on next tick (or auto-expires per pg_cron).
    """
    pending = fetch_pending_signals(agent)
    if not pending:
        return None
    return handle_signal(pending[0], agent, hmac_secret, synthetic=synthetic)
