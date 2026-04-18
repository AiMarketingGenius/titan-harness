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


# Per-vendor default daily caps in USD. Override via constructor or env var.
# - Global override:  TITAN_COST_CAP_<VENDOR>=N.NN
# - Per-tenant:       TITAN_COST_CAP_TENANT_<TENANT>_<VENDOR>=N.NN
#   Example:          TITAN_COST_CAP_TENANT_REVERE_ANTHROPIC=50.00
# Per-tenant env wins over vendor-global env wins over DEFAULT_DAILY_CAPS_USD.
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
    """One instance per (vendor, scope, tenant). Cheap to construct. Thread-safe via sqlite.

    tenant_id='global' (default) = pre-existing single-tenant behavior. Set to
    a specific slug (e.g. 'revere', 'boston_chamber') to enforce per-Chamber /
    per-subscriber daily caps and spend tracking. Each tenant has independent
    cap enforcement + independent ledger totals. Same artifact cached
    separately per tenant.
    """

    def __init__(
        self,
        vendor: str,
        daily_cap_usd: Optional[float] = None,
        scope: str = 'grading',
        ledger_path: Optional[Path] = None,
        fail_non_blocking: bool = True,
        tenant_id: str = 'global',
    ):
        self.vendor = vendor.lower()
        self.scope = scope
        self.tenant_id = tenant_id.lower()
        self.ledger_path = ledger_path or DEFAULT_LEDGER_PATH
        self.fail_non_blocking = fail_non_blocking

        # Resolve daily cap (priority order, first-match wins):
        #   1. explicit daily_cap_usd arg
        #   2. TITAN_COST_CAP_TENANT_<TENANT>_<VENDOR>=... (per-tenant override)
        #   3. TITAN_COST_CAP_<VENDOR>=... (global vendor override)
        #   4. DEFAULT_DAILY_CAPS_USD[vendor]
        #   5. 1.0 USD absolute fallback
        tenant_env_key = f'TITAN_COST_CAP_TENANT_{self.tenant_id.upper()}_{self.vendor.upper()}'
        global_env_key = f'TITAN_COST_CAP_{self.vendor.upper()}'
        tenant_env_val = os.environ.get(tenant_env_key)
        global_env_val = os.environ.get(global_env_key)
        if daily_cap_usd is not None:
            self.daily_cap_usd = daily_cap_usd
        elif tenant_env_val:
            try:
                self.daily_cap_usd = float(tenant_env_val)
            except ValueError:
                self.daily_cap_usd = DEFAULT_DAILY_CAPS_USD.get(self.vendor, 1.0)
        elif global_env_val:
            try:
                self.daily_cap_usd = float(global_env_val)
            except ValueError:
                self.daily_cap_usd = DEFAULT_DAILY_CAPS_USD.get(self.vendor, 1.0)
        else:
            self.daily_cap_usd = DEFAULT_DAILY_CAPS_USD.get(self.vendor, 1.0)

        self._init_db()

    # ---- DB setup -------------------------------------------------------

    def _init_db(self) -> None:
        """Initialize the sqlite ledger. Fresh installs get the v2 schema with
        tenant_id in the UNIQUE constraint. Existing v1 ledgers (schema without
        tenant_id) get migrated in-place: rows rehomed as tenant_id='global'
        and the UNIQUE constraint re-created to include tenant_id.

        v1 schema limitation: UNIQUE(day, vendor, scope, artifact_sha) meant
        two tenants calling the same artifact same day could silently drop
        the second tenant's record. v2 migration fixes it by including
        tenant_id in UNIQUE — each tenant gets an independent record.
        """
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            existing = con.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='calls'"
            ).fetchone()

            needs_migrate = False
            if existing and existing[0]:
                old_sql = existing[0]
                # v1 schema signature: UNIQUE constraint WITHOUT tenant_id
                if 'tenant_id' not in old_sql:
                    needs_migrate = True

            v2_schema = """
                CREATE TABLE {name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    day TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'global',
                    artifact_sha TEXT NOT NULL,
                    cost_usd REAL NOT NULL,
                    result_json TEXT,
                    UNIQUE(day, vendor, scope, tenant_id, artifact_sha)
                )
            """

            if needs_migrate:
                # In-place migration: create v2 under temp name, copy rows
                # as tenant_id='global', drop old, rename temp -> calls.
                con.execute(v2_schema.format(name='calls_v2'))
                con.execute("""
                    INSERT INTO calls_v2 (id, ts, day, vendor, scope, tenant_id,
                                          artifact_sha, cost_usd, result_json)
                    SELECT id, ts, day, vendor, scope, 'global',
                           artifact_sha, cost_usd, result_json
                    FROM calls
                """)
                con.execute('DROP TABLE calls')
                con.execute('ALTER TABLE calls_v2 RENAME TO calls')
            elif not existing:
                # Fresh install — v2 schema directly.
                con.execute(v2_schema.format(name='IF NOT EXISTS calls'))

            # Indices are idempotent — safe to re-run every init.
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_calls_day_vendor
                ON calls(day, vendor)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_calls_day_vendor_tenant
                ON calls(day, vendor, tenant_id)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_calls_cache_tenant
                ON calls(day, vendor, scope, tenant_id, artifact_sha)
            """)
            con.commit()

    # ---- Public API -----------------------------------------------------

    def check_cache(self, artifact_text: str) -> Optional[Any]:
        """If this exact artifact was already graded today (same vendor+scope+tenant),
        return the cached result_json (decoded). Else None.

        Cache is isolated per tenant — two different tenants calling the same
        artifact don't share cache because each tenant owes the API cost
        separately. Single-tenant (tenant_id='global') users see prior behavior."""
        sha = _sha256_hex(artifact_text)
        day = _today_utc_str()
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            row = con.execute(
                'SELECT result_json FROM calls '
                'WHERE day=? AND vendor=? AND scope=? AND tenant_id=? AND artifact_sha=? '
                'LIMIT 1',
                (day, self.vendor, self.scope, self.tenant_id, sha),
            ).fetchone()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                return None
        return None

    def today_spend_usd(self) -> float:
        """Sum of today's API cost for (vendor, tenant_id). Scope-agnostic —
        a single daily cap governs ALL scopes for the tenant+vendor pair."""
        day = _today_utc_str()
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            row = con.execute(
                'SELECT COALESCE(SUM(cost_usd), 0) FROM calls '
                'WHERE day=? AND vendor=? AND tenant_id=?',
                (day, self.vendor, self.tenant_id),
            ).fetchone()
        return float(row[0] if row else 0.0)

    def today_call_count(self) -> int:
        day = _today_utc_str()
        with sqlite3.connect(self.ledger_path, timeout=5) as con:
            row = con.execute(
                'SELECT COUNT(*) FROM calls '
                'WHERE day=? AND vendor=? AND tenant_id=?',
                (day, self.vendor, self.tenant_id),
            ).fetchone()
        return int(row[0] if row else 0)

    def allow_call(self, estimated_cost_usd: float = 0.05) -> bool:
        """Check daily cap for (vendor, tenant_id). True=allowed, False=denied."""
        spent = self.today_spend_usd()
        if spent + estimated_cost_usd > self.daily_cap_usd:
            self._write_audit_line(
                f'DENIED vendor={self.vendor} tenant={self.tenant_id} scope={self.scope} '
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
                    'INSERT INTO calls (ts, day, vendor, scope, tenant_id, '
                    'artifact_sha, cost_usd, result_json) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (ts, day, self.vendor, self.scope, self.tenant_id,
                     sha, actual_cost_usd, result_json),
                )
                con.commit()
            except sqlite3.IntegrityError:
                # Same (day, vendor, scope, tenant_id, artifact_sha) already
                # recorded today — harmless per-tenant dedup. v2 schema
                # (post-2026-04-18 migration) isolates cache per tenant so
                # two tenants calling the same artifact both get their own
                # records billed independently.
                pass

    def deny_response(self) -> dict[str, Any]:
        """Sentinel response when allow_call() returns False. Caller checks
        for 'skipped': True in the dict to know the kill-switch fired."""
        return {
            'skipped': True,
            'reason': 'daily_cap_hit',
            'vendor': self.vendor,
            'scope': self.scope,
            'tenant_id': self.tenant_id,
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
    """CLI: `python lib/cost_kill_switch.py [--vendor X] [--tenant Y] [--audit-tail N]`

    Lists today's spend per (vendor, tenant, scope) + recent denials. No API calls."""
    import argparse
    p = argparse.ArgumentParser(prog='cost-kill-switch')
    p.add_argument('--vendor', help='filter by vendor name')
    p.add_argument('--tenant', help='filter by tenant_id')
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
        # Detect if v2 schema (tenant_id column present)
        cols = {r[1] for r in con.execute("PRAGMA table_info(calls)").fetchall()}
        has_tenant = 'tenant_id' in cols

        day = _today_utc_str()
        where_parts = ['day=?']
        where_args: list[Any] = [day]
        if args.vendor:
            where_parts.append('vendor=?')
            where_args.append(args.vendor.lower())
        if args.tenant and has_tenant:
            where_parts.append('tenant_id=?')
            where_args.append(args.tenant.lower())
        where_clause = ' AND '.join(where_parts)

        if has_tenant:
            rows = con.execute(
                f'SELECT tenant_id, vendor, scope, COUNT(*), SUM(cost_usd) FROM calls '
                f'WHERE {where_clause} GROUP BY tenant_id, vendor, scope '
                f'ORDER BY SUM(cost_usd) DESC',
                tuple(where_args),
            ).fetchall()
        else:
            rows = con.execute(
                f'SELECT vendor, scope, COUNT(*), SUM(cost_usd) FROM calls '
                f'WHERE {where_clause} GROUP BY vendor, scope '
                f'ORDER BY SUM(cost_usd) DESC',
                tuple(where_args),
            ).fetchall()

    print(f'=== Today ({day}) ===')
    if not rows:
        print('  (no calls recorded)')
    elif has_tenant:
        print(f'  {"tenant":<15} {"vendor":<12} {"scope":<18} {"calls":>8} {"spend_usd":>12}')
        for tenant, vendor, scope, count, spend in rows:
            print(f'  {tenant:<15} {vendor:<12} {scope:<18} {count:>8} ${spend:>11.4f}')
    else:
        print(f'  {"vendor":<12} {"scope":<18} {"calls":>8} {"spend_usd":>12}')
        for vendor, scope, count, spend in rows:
            print(f'  {vendor:<12} {scope:<18} {count:>8} ${spend:>11.4f}')

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
