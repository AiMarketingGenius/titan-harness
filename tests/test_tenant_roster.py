"""Smoke test for lib/tenant_roster — commit #3 of Kleisthenes CRM Loop.

Uses revere-chamber-demo tenant seeded by commit #1. Exercises:
  1. seed_default_roster seeds 7 agents (or 0 if already seeded)
  2. get_tenant_roster returns all 7 with DEFAULT_ROSTER keys
  3. set_agent_enabled toggles flag
  4. update_agent_config merges JSONB patch
  5. invalid agent_key raises ValueError
  6. invalid tenant_id raises ValueError

Requires SUPABASE_DB_URL + sql/011_tenant_agent_roster.sql applied.
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

from lib.tenant_roster import (  # noqa: E402
    DEFAULT_ROSTER,
    VALID_AGENT_KEYS,
    get_tenant_roster,
    seed_default_roster,
    set_agent_enabled,
    update_agent_config,
)


REVERE_DEMO_ID = "d315bd76-9044-41ad-a619-6803a2fdc0ed"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77

    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    conn.autocommit = False
    try:
        print("[1/6] seed_default_roster idempotent")
        inserted_first = seed_default_roster(conn, REVERE_DEMO_ID)
        print(f"  -> first seed inserted={inserted_first}")
        _assert(inserted_first in (0, 7), f"first seed inserted={inserted_first} (expected 0 or 7)")
        inserted_second = seed_default_roster(conn, REVERE_DEMO_ID)
        print(f"  -> second seed inserted={inserted_second}")
        _assert(inserted_second == 0, f"re-seed should insert 0, got {inserted_second}")

        print("[2/6] get_tenant_roster returns 7")
        roster = get_tenant_roster(conn, REVERE_DEMO_ID)
        _assert(len(roster) == 7, f"roster size={len(roster)}, expected 7")
        got_keys = sorted(r["agent_key"] for r in roster)
        expected_keys = sorted(k for k, _ in DEFAULT_ROSTER)
        _assert(got_keys == expected_keys, f"roster keys {got_keys} != {expected_keys}")
        for r in roster:
            _assert(r["agent_key"] in VALID_AGENT_KEYS, f"unexpected key {r['agent_key']}")
            _assert(isinstance(r["config"], dict), f"config not dict: {type(r['config'])}")
        print(f"  -> all 7 agents present: {got_keys}")

        print("[3/6] set_agent_enabled flips flag")
        ok = set_agent_enabled(conn, REVERE_DEMO_ID, "jordan", False)
        _assert(ok, "set_agent_enabled returned False for jordan")
        post = {r["agent_key"]: r["enabled"] for r in get_tenant_roster(conn, REVERE_DEMO_ID)}
        _assert(post["jordan"] is False, f"jordan still enabled: {post['jordan']}")
        _assert(post["maya"] is True, f"maya flipped by accident: {post['maya']}")
        set_agent_enabled(conn, REVERE_DEMO_ID, "jordan", True)  # restore
        print("  -> jordan disabled + restored cleanly")

        print("[4/6] update_agent_config merges JSONB patch")
        merged = update_agent_config(
            conn, REVERE_DEMO_ID, "alex", {"voice_id": "DZifC2yzJiQrdYzF21KH"}
        )
        _assert(merged.get("voice_id") == "DZifC2yzJiQrdYzF21KH", f"voice_id missing: {merged}")
        merged2 = update_agent_config(
            conn, REVERE_DEMO_ID, "alex", {"persona": "solon-clone"}
        )
        _assert(merged2.get("voice_id") == "DZifC2yzJiQrdYzF21KH", "voice_id clobbered")
        _assert(merged2.get("persona") == "solon-clone", "persona not set")
        print(f"  -> config merged: {merged2}")

        print("[5/6] invalid agent_key raises ValueError")
        try:
            set_agent_enabled(conn, REVERE_DEMO_ID, "not-an-agent", False)
        except ValueError:
            print("  -> rejected bad agent_key")
        else:
            _assert(False, "bad agent_key did not raise ValueError")

        print("[6/6] invalid tenant_id raises ValueError")
        try:
            seed_default_roster(conn, "not-a-uuid")
        except ValueError:
            print("  -> rejected bad tenant_id")
        else:
            _assert(False, "bad tenant_id did not raise ValueError")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("PASS: tenant_roster smoke test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
