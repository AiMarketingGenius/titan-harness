#!/usr/bin/env python3
"""
titan-harness/lib/cost_kill_switch.py

Mechanical cost guard for ANY function that calls a paid LLM API.
Built 2026-04-16 in response to Perplexity bill spike (570 calls/day, $54.47).

The doctrine paragraph in CLAUDE.md §12 ("don't grade routine ops") was a
suggestion. This module is enforcement. It physically refuses to let an
expensive call happen if either of the following is true:

  1. Daily total spend has hit the hard cap (default $5/day per vendor)
  2. The exact same artifact was already graded today (sha256 dedupe)

It also gives you a "fail-non-blocking" mode so a graders being down can
NEVER halt production work. (This was the second-order failure that caused
the entire Sonar-gate halt earlier tonight.)

Zero-dependency: stdlib only (sqlite3 + hashlib + os + datetime).

Usage from inside any LLM-calling function:

    from cost_kill_switch import KillSwitch

    ks = KillSwitch(vendor='perplexity', daily_cap_usd=5.0)

    # Before the API call:
    cached = ks.check_cache(artifact_text)
    if cached is not None:
        return cached  # already graded today, free

    if not ks.allow_call(estimated_cost_usd=0.05):
        # Daily cap hit. Caller decides what to do.
        return ks.deny_response()  # returns a sentinel "skipped" GradeResult

    # ... actual API call ...
    result = call_perplexity(...)

    # After the call:
    ks.record_call(artifact_text, actual_cost_usd, result)

The sqlite ledger lives at ~/.titan-cost-ledger.db (or
TITAN_COST_LEDGER env override). It's append-only, ~50 bytes per call.
A 1-year history fits in <2MB.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_LEDGER_PATH = Path(
    os.environ.get('TITAN_COST_LEDGER', str(Path.home() / '.titan-cost-ledger.db'))
)


# Per-vendor default daily caps in USD. Override via constructor or env var
# TITAN_COST_CAP_<VENDOR>=N.NN (e.g. TITAN_COST_CAP_PERPLEXITY=10.00).
DEFAULT_DAILY_CAPS_USD = {
    'perplexity': 5.0,
    'anthropic':  10.0,
    'openai':     5.0,
    'gemini':     2.0,
    'grok':       2.0,
}


def _today_utc_str() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8', errors='replace')).hexdigest()


class KillSwitch:
    """One instance per (vendor, scope). Cheap to construct. Thread-safe via sqlite."""

    def __init__(
        self,
        vendor: str,
        daily_cap_usd: Optional[float] = None,
        scope: str = 'grading',
        ledger_path: Optional[Path] = None,
        fail_non_blocking: bool = True,
    ):
        self.vendor = vendor.lower()
        self.scope = scope
        self.ledger_path = ledger_path or DEFAULT_LEDGER_PATH
        self.fail_non_blocking = fail_non_blocking

        # Resolve daily cap: explicit arg > env > default
        env_key = f'TITAN_COST_CAP_{self.vendor.upper()}'
        env_val = os.environ.get(env_key)
        if daily_cap_usd is not None:
            self.daily_cap_usd = daily_cap_usd
        elif env_val:
            try:
                self.daily_cap_usd = float(env_val)
            except ValueError:
                self.daily_cap_usd = DEFAULT_DAILY_CAPS_USD.get(self.vendor, 1.0)
        else:
            self.daily_cap_usd = DEFAULT_DAILY_CAPS_USD.get(self.vendor, 1.0)

        self._init_db()

    # ---- DB setup -------------------------------------------------------

    def _init_db(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    day TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    artifact_sha TEXT NOT NULL,
                    cost_usd REAL NOT NULL,
                    result_json TEXT,
                    UNIQUE(day, vendor, scope, artifact_sha)
                )
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_calls_day_vendor
                ON calls(day, vendor)
            """)
            con.commit()

    # ---- Public API -----------------------------------------------------

    def check_cache(self, artifact_text: str) -> Optional[Any]:
        """If this exact artifact was already graded today (same vendor+scope),
        return the cached result_json (decoded). Else None."""
        sha = _sha256_hex(artifact_text)
        day = _today_utc_str()
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            row = con.execute(
                'SELECT result_json FROM calls '
                'WHERE day=? AND vendor=? AND scope=? AND artifact_sha=? '
                'LIMIT 1',
                (day, self.vendor, self.scope, sha),
            ).fetchone()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                return None
        return None

    def today_spend_usd(self) -> float:
        day = _today_utc_str()
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            row = con.execute(
                'SELECT COALESCE(SUM(cost_usd), 0) FROM calls '
                'WHERE day=? AND vendor=?',
                (day, self.vendor),
            ).fetchone()
        return float(row[0] if row else 0.0)

    def today_call_count(self) -> int:
        day = _today_utc_str()
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            row = con.execute(
                'SELECT COUNT(*) FROM calls '
                'WHERE day=? AND vendor=?',
                (day, self.vendor),
            ).fetchone()
        return int(row[0] if row else 0)

    def allow_call(self, estimated_cost_usd: float = 0.05) -> bool:
        """Check daily cap. Returns True if call is allowed. False = denied."""
        spent = self.today_spend_usd()
        if spent + estimated_cost_usd > self.daily_cap_usd:
            self._write_audit_line(
                f'DENIED vendor={self.vendor} scope={self.scope} '
                f'spent_today=${spent:.4f} cap=${self.daily_cap_usd:.2f} '
                f'attempted=${estimated_cost_usd:.4f}'
            )
            return False
        return True

    def record_call(
        self,
        artifact_text: str,
        actual_cost_usd: float,
        result: Optional[Any] = None,
    ) -> None:
        """Record an actual API call to the ledger. Idempotent on (day, vendor,
        scope, artifact_sha) — if you call record twice with same artifact,
        the second insert is silently ignored (we already had the answer)."""
        sha = _sha256_hex(artifact_text)
        day = _today_utc_str()
        ts = datetime.now(timezone.utc).isoformat()
        try:
            result_json = json.dumps(result, default=str) if result is not None else None
        except (TypeError, ValueError):
            result_json = None
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            try:
                con.execute(
                    'INSERT INTO calls (ts, day, vendor, scope, artifact_sha, '
                    'cost_usd, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (ts, day, self.vendor, self.scope, sha, actual_cost_usd, result_json),
                )
                con.commit()
            except sqlite3.IntegrityError:
                # Already recorded today — that's the whole point of dedupe.
                pass

    def deny_response(self) -> dict[str, Any]:
        """Sentinel response when allow_call() returns False. Caller checks
        for 'skipped': True in the dict to know the kill-switch fired."""
        return {
            'skipped': True,
            'reason': 'daily_cap_hit',
            'vendor': self.vendor,
            'scope': self.scope,
            'today_spend_usd': self.today_spend_usd(),
            'cap_usd': self.daily_cap_usd,
            'fail_non_blocking': self.fail_non_blocking,
        }

    # ---- Audit log ------------------------------------------------------

    def _write_audit_line(self, line: str) -> None:
        """Append-only audit log so Solon can grep what got blocked."""
        log_path = self.ledger_path.with_suffix('.audit.log')
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(timezone.utc).isoformat()} {line}\n')
        except OSError:
            pass


# ---------------------------------------------------------------------------
# CLI entrypoint — read-only inspection
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    """CLI: `python lib/cost_kill_switch.py [--vendor X] [--reset]`

    Lists today's spend per vendor + recent denials. No API calls."""
    import argparse
    p = argparse.ArgumentParser(prog='cost-kill-switch')
    p.add_argument('--vendor', help='filter by vendor name')
    p.add_argument('--ledger', default=str(DEFAULT_LEDGER_PATH),
                   help='ledger db path')
    p.add_argument('--audit-tail', type=int, default=20,
                   help='show last N audit log lines')
    args = p.parse_args(argv)

    ledger = Path(args.ledger)
    if not ledger.exists():
        print(f'(no ledger yet at {ledger})')
        return 0

    with sqlite3.connect(ledger, timeout=5) as con:
        day = _today_utc_str()
        if args.vendor:
            rows = con.execute(
                'SELECT vendor, scope, COUNT(*), SUM(cost_usd) FROM calls '
                'WHERE day=? AND vendor=? GROUP BY vendor, scope',
                (day, args.vendor.lower()),
            ).fetchall()
        else:
            rows = con.execute(
                'SELECT vendor, scope, COUNT(*), SUM(cost_usd) FROM calls '
                'WHERE day=? GROUP BY vendor, scope ORDER BY SUM(cost_usd) DESC',
                (day,),
            ).fetchall()

    print(f'=== Today ({day}) ===')
    if not rows:
        print('  (no calls recorded)')
    else:
        print(f'  {"vendor":<12} {"scope":<12} {"calls":>8} {"spend_usd":>12}')
        for vendor, scope, count, spend in rows:
            print(f'  {vendor:<12} {scope:<12} {count:>8} ${spend:>11.4f}')

    audit_log = ledger.with_suffix('.audit.log')
    if audit_log.exists() and args.audit_tail > 0:
        print(f'\n=== Last {args.audit_tail} audit lines ===')
        try:
            lines = audit_log.read_text(encoding='utf-8').splitlines()
            for line in lines[-args.audit_tail:]:
                print(f'  {line}')
        except OSError as e:
            print(f'  (cannot read audit log: {e})')

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
