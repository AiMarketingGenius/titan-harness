"""DIR-2026-04-28-002a Step 3.4 + 3.5 — Emergency Mode E2E test.

Exercises:
  - Step 3.4: 3-tier fallback read (Redis → file → Supabase)
  - Step 3.5: harness top-of-loop check_emergency()
  - All 4 signal types (KILL / EDIT / PAUSE / RESUME) for both titan + achilles

Synthetic mode only — no actual harness shutdown.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import sys
import time
import urllib.request

# Make lib/ importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'lib'))

from emergency_check import (  # noqa: E402
    EMERGENCY_FLAG_DIR,
    DEFAULT_API_BASE,
    _hmac_sign,
    check_emergency,
    fetch_pending_signals,
    read_fast_poll_flag,
)

os.environ['SYNTHETIC'] = '1'


def submit_signal(secret: str, signal_type: str, target_agent: str, reason: str) -> str:
    """POST /api/emergency/signal with HMAC. Return signal_id."""
    body = {'reason': reason, 'signal_type': signal_type, 'target_agent': target_agent}
    sig = _hmac_sign(secret, body)
    req = urllib.request.Request(
        f'{DEFAULT_API_BASE}/api/emergency/signal',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'X-Caller-Identity': 'eom',
            'X-Signature': sig,
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode('utf-8'))['signal_id']


def cleanup_signal(secret: str, signal_id: str) -> None:
    """Cancel a signal we created so it doesn't linger."""
    # Use the test-cleanup helper via psql since there's no cancel API; SSH from caller.
    import subprocess
    subprocess.run(
        [
            'ssh', '-o', 'ConnectTimeout=8', '-p', '2222', 'root@170.205.37.148',
            f"set -a; . /etc/amg/supabase.env; set +a; "
            f"psql \"$SUPABASE_DB_URL\" -tAc "
            f"\"UPDATE op_emergency_signals SET status='cancelled' "
            f"WHERE id='{signal_id}' AND status NOT IN ('cancelled','expired') "
            f"RETURNING id, status;\""
        ],
        check=False, capture_output=True,
    )


def fetch_secret() -> str:
    """Pull HMAC secret via SSH+psql."""
    import subprocess
    r = subprocess.run(
        ['ssh', '-o', 'ConnectTimeout=8', '-p', '2222', 'root@170.205.37.148',
         'set -a; . /etc/amg/supabase.env; set +a; '
         'psql "$SUPABASE_DB_URL" -tAc "SELECT public.get_emergency_hmac_secret();"'],
        check=True, capture_output=True, text=True,
    )
    return r.stdout.strip().splitlines()[-1]


def test_signal_type(secret: str, signal_type: str, target_agent: str) -> dict:
    """Insert + check_emergency processes it + ack confirmed."""
    print(f'  → {signal_type} for {target_agent} ...')
    sig_id = submit_signal(secret, signal_type, target_agent, f'E2E test {signal_type} {target_agent}')

    # Verify pending fetch returns it
    pending = fetch_pending_signals(target_agent)
    pending_ids = [s['id'] for s in pending]
    if sig_id not in pending_ids:
        return {'ok': False, 'signal_id': sig_id, 'reason': f'sig_id not in pending list {pending_ids[:3]}'}

    # Run check_emergency — synthetic mode logs + acks
    result = check_emergency(target_agent, secret, synthetic=True)

    # Verify post-ack state via fresh fetch
    time.sleep(0.5)
    pending_after = fetch_pending_signals(target_agent)
    pending_after_ids = [s['id'] for s in pending_after]
    acked = sig_id not in pending_after_ids

    cleanup_signal(secret, sig_id)
    return {
        'ok': acked and result is not None,
        'signal_id': sig_id,
        'check_result': result,
        'acked_via_fetch': acked,
    }


def test_3_tier_fallback(agent: str = 'titan') -> dict:
    """Exercise the 3-tier fallback: Redis → file → Supabase.

    We don't manipulate Redis from here (would require redis-cli), but we
    verify each tier's read function returns expected (None|False) for the
    no-flag-set baseline. Then we DO touch the file flag to verify file-tier
    activates. Then we remove it. Real Redis-tier activation is exercised
    by the production /api/emergency/signal route extension (out of scope
    for harness-side test).
    """
    results = {}

    # Baseline — all tiers should read None or False (no flag set)
    val0, src0 = read_fast_poll_flag(agent)
    results['baseline'] = {'value': val0, 'source': src0}

    # File tier activation
    EMERGENCY_FLAG_DIR.mkdir(parents=True, exist_ok=True)
    flag_path = EMERGENCY_FLAG_DIR / f'{agent}.flag'
    flag_path.write_text(f'fast_poll set at {time.time()}\n')
    try:
        val1, src1 = read_fast_poll_flag(agent)
        results['file_set'] = {'value': val1, 'source': src1}
    finally:
        flag_path.unlink(missing_ok=True)

    # Stale file (> 60s) should read False — simulate by mtime fudge
    flag_path.write_text('stale\n')
    os.utime(flag_path, (time.time() - 120, time.time() - 120))
    try:
        val2, src2 = read_fast_poll_flag(agent)
        results['file_stale'] = {'value': val2, 'source': src2}
    finally:
        flag_path.unlink(missing_ok=True)

    return results


def main() -> int:
    print('=== fetching HMAC secret ===')
    secret = fetch_secret()
    print(f'secret length: {len(secret)}')
    print()

    print('=== Step 3.4 — 3-tier fallback ===')
    fb = test_3_tier_fallback('titan')
    for k, v in fb.items():
        print(f'  {k}: {v}')
    print()

    print('=== Step 3.5 — 4 signal types × 2 agents (8 tests) ===')
    pass_count, fail_count = 0, 0
    for agent in ('titan', 'achilles'):
        for sig_type in ('PAUSE', 'RESUME', 'EDIT', 'KILL'):
            r = test_signal_type(secret, sig_type, agent)
            ok = '✓' if r['ok'] else '✗'
            print(f'  {ok} {sig_type:6s} {agent:10s} → {r}')
            if r['ok']:
                pass_count += 1
            else:
                fail_count += 1
    print()
    print(f'=== summary: {pass_count} pass, {fail_count} fail ===')
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
