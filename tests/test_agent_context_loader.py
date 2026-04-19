"""Smoke test for lib/agent_context_loader — commit #6 Kleisthenes.

Validates:
  1. Full load for revere-chamber-demo returns tenant + 7-agent roster + leads + decisions
  2. agent_key filter scopes roster to 1 row
  3. lead_limit=0 / decisions_limit=0 returns empty lists
  4. Invalid slug / agent_key / limits raise ValueError
  5. Unknown slug raises LookupError

Requires SUPABASE_DB_URL + sql/011 + sql/012 applied + revere-chamber-demo seeded.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 required")

from lib.agent_context_loader import VALID_AGENT_KEYS, load_tenant_context  # noqa: E402


SLUG = "revere-chamber-demo"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    try:
        print(f"[1/5] Full load for {SLUG}")
        ctx = load_tenant_context(conn, SLUG, lead_limit=10, decisions_limit=10)
        _assert(isinstance(ctx, dict), f"ctx not dict")
        _assert(ctx["tenant"]["slug"] == SLUG, f"tenant slug mismatch")
        _assert(len(ctx["roster"]) == 7, f"roster size={len(ctx['roster'])}, expected 7")
        _assert(isinstance(ctx["recent_leads"], list), "recent_leads not list")
        _assert(isinstance(ctx["recent_decisions"], list), "recent_decisions not list")
        _assert(ctx["memory_captures"] == [], "memory_captures should be empty scaffold")
        _assert(ctx["kb_facts"] == [], "kb_facts should be empty scaffold")
        print(f"  -> tenant={ctx['tenant']['name']}")
        print(f"  -> roster={len(ctx['roster'])} agents")
        print(f"  -> recent_leads={len(ctx['recent_leads'])}")
        print(f"  -> recent_decisions={len(ctx['recent_decisions'])}")

        print("[2/5] agent_key filter scopes roster to 1")
        scoped = load_tenant_context(conn, SLUG, agent_key="alex", lead_limit=0, decisions_limit=0)
        _assert(len(scoped["roster"]) == 1, f"agent_key=alex roster size={len(scoped['roster'])}")
        _assert(scoped["roster"][0]["agent_key"] == "alex", f"roster[0]={scoped['roster'][0]}")
        print(f"  -> alex scoped roster: {scoped['roster'][0]['role_title']}")

        print("[3/5] zero-limit excludes feeds")
        light = load_tenant_context(conn, SLUG, lead_limit=0, decisions_limit=0)
        _assert(light["recent_leads"] == [], "recent_leads should be empty on limit=0")
        _assert(light["recent_decisions"] == [], "recent_decisions should be empty on limit=0")
        print("  -> limits honored")

        print("[4/5] invalid inputs raise ValueError")
        bad_cases = [
            lambda: load_tenant_context(conn, "BAD-SLUG-UPPER"),
            lambda: load_tenant_context(conn, SLUG, agent_key="nobody"),
            lambda: load_tenant_context(conn, SLUG, lead_limit=-1),
            lambda: load_tenant_context(conn, SLUG, decisions_limit=999),
        ]
        for i, fn in enumerate(bad_cases, 1):
            try:
                fn()
            except ValueError:
                print(f"  -> case {i}: rejected")
            else:
                _assert(False, f"bad case {i} did not raise ValueError")

        print("[5/5] unknown slug raises LookupError")
        try:
            load_tenant_context(conn, "nonexistent-tenant-slug")
        except LookupError:
            print("  -> rejected unknown slug")
        else:
            _assert(False, "unknown slug did not raise LookupError")
    finally:
        conn.close()

    print("PASS: agent_context_loader smoke test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
