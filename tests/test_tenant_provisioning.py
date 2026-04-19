"""Smoke test for lib/tenant_provisioning.

Provisions `revere-chamber-demo` (Playbook §3 line 76), verifies the row lands,
re-provisions to prove idempotency, and exits non-zero on any regression.

Requires SUPABASE_DB_URL in env (or /etc/amg/supabase.env sourced prior).
Safe to re-run: the demo tenant is left in place between runs.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from lib.tenant_provisioning import (  # noqa: E402
    ALLOWED_PLAN_TIERS,
    provision_tenant,
)


DEMO_SLUG = "revere-chamber-demo"
DEMO_NAME = "Revere Chamber (Demo)"
DEMO_SUBDOMAIN = "revere-chamber-demo"
DEMO_PLAN = "chamber-founding"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SKIP: SUPABASE_DB_URL not set", file=sys.stderr)
        return 77  # autotools skip code

    _assert(DEMO_PLAN in ALLOWED_PLAN_TIERS, f"{DEMO_PLAN} missing from ALLOWED_PLAN_TIERS")

    print(f"[1/3] Provision demo tenant: slug={DEMO_SLUG}")
    first = provision_tenant(
        slug=DEMO_SLUG,
        name=DEMO_NAME,
        subdomain=DEMO_SUBDOMAIN,
        plan_tier=DEMO_PLAN,
        brand_config={"palette": "amg-navy-teal", "source": "demo-seed"},
    )
    print(f"  -> id={first['id']} status={first['status']} was_existing={first['was_existing']}")

    _assert(first["slug"] == DEMO_SLUG, f"slug mismatch: {first['slug']}")
    _assert(first["name"] == DEMO_NAME, f"name mismatch: {first['name']}")
    _assert(first["plan_tier"] == DEMO_PLAN, f"plan_tier mismatch: {first['plan_tier']}")
    _assert(first["status"] == "active", f"status not active: {first['status']}")
    try:
        uuid.UUID(first["id"])
    except ValueError:
        _assert(False, f"id not a UUID: {first['id']}")

    print(f"[2/3] Re-provision same slug (idempotency check)")
    second = provision_tenant(
        slug=DEMO_SLUG,
        name=DEMO_NAME,
        subdomain=DEMO_SUBDOMAIN,
        plan_tier=DEMO_PLAN,
    )
    print(f"  -> id={second['id']} was_existing={second['was_existing']}")
    _assert(second["id"] == first["id"], "re-provisioned id changed")
    _assert(second["was_existing"] is True, "expected was_existing=True on re-provision")

    print(f"[3/3] Validation rejects bad slug")
    bad_cases = [
        ("Upper-Case-Slug", ValueError),
        ("a", ValueError),            # too short
        ("-leading-hyphen", ValueError),
        ("trailing-hyphen-", ValueError),
        ("has_underscore", ValueError),
    ]
    for bad_slug, exc_type in bad_cases:
        try:
            provision_tenant(slug=bad_slug, name="x")
        except exc_type:
            print(f"  -> rejected {bad_slug!r} as expected")
        except Exception as exc:
            _assert(False, f"{bad_slug!r} raised {type(exc).__name__} not {exc_type.__name__}")
        else:
            _assert(False, f"{bad_slug!r} did not raise {exc_type.__name__}")

    print("PASS: tenant_provisioning smoke test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
