"""Tenant provisioning — canonical entry point for new AMG client tenants.

Creates / resolves a row in public.tenants (sql/009_multi_tenant.sql) for a
Chamber / agency client. Idempotent on slug: re-provisioning with the same
slug returns the existing row instead of erroring.

Usage (library):
    from lib.tenant_provisioning import provision_tenant
    t = provision_tenant(
        slug="revere-chamber-demo",
        name="Revere Chamber (Demo)",
        subdomain="revere-chamber-demo",
        plan_tier="chamber-founding",
    )

Usage (CLI):
    python3 -m lib.tenant_provisioning \\
        --slug revere-chamber-demo \\
        --name "Revere Chamber (Demo)" \\
        --subdomain revere-chamber-demo \\
        --plan-tier chamber-founding

Environment:
    SUPABASE_DB_URL  postgres connection string (required)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2 required: apt-get install python3-psycopg2 or pip install psycopg2-binary")


SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")

ALLOWED_PLAN_TIERS = {
    "chamber-standard",
    "chamber-pro",
    "chamber-founding",
    "internal-solo",
    "white-label",
}


def _db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return url


def _validate(slug: str, name: str, subdomain: str | None, plan_tier: str) -> None:
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"invalid slug {slug!r}: must match {SLUG_RE.pattern} "
            "(lowercase, start with letter, 3-64 chars)"
        )
    if not name.strip():
        raise ValueError("name must not be empty")
    if subdomain is not None and not SLUG_RE.match(subdomain):
        raise ValueError(f"invalid subdomain {subdomain!r}: must match {SLUG_RE.pattern}")
    if plan_tier not in ALLOWED_PLAN_TIERS:
        raise ValueError(
            f"plan_tier {plan_tier!r} not in {sorted(ALLOWED_PLAN_TIERS)}"
        )


def provision_tenant(
    slug: str,
    name: str,
    subdomain: str | None = None,
    plan_tier: str = "chamber-standard",
    brand_config: dict[str, Any] | None = None,
    webauthn_rp_id: str | None = None,
    webauthn_rp_name: str | None = None,
    vapid_public_key: str | None = None,
    vapid_subject: str | None = None,
    seed_roster: bool = True,
) -> dict[str, Any]:
    """Provision a tenant row or return the existing row on slug conflict.

    When `seed_roster=True` (default), also seeds the 7-agent default roster
    in the same tx via lib.tenant_roster.seed_default_roster — makes tenant
    provisioning atomic: tenant row + roster land together or not at all.

    Returns a dict with keys: id, slug, name, subdomain, plan_tier, status,
    created_at, was_existing, roster_seeded (count inserted, 0 if already).
    """
    _validate(slug, name, subdomain, plan_tier)

    brand_json = json.dumps(brand_config or {})

    conn = psycopg2.connect(_db_url())
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO public.tenants
                    (slug, name, subdomain, brand_config, webauthn_rp_id,
                     webauthn_rp_name, vapid_public_key, vapid_subject, plan_tier)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO NOTHING
                RETURNING id, slug, name, subdomain, plan_tier, status, created_at;
                """,
                (
                    slug,
                    name,
                    subdomain,
                    brand_json,
                    webauthn_rp_id,
                    webauthn_rp_name,
                    vapid_public_key,
                    vapid_subject,
                    plan_tier,
                ),
            )
            row = cur.fetchone()
            was_existing = False
            if row is None:
                cur.execute(
                    """
                    SELECT id, slug, name, subdomain, plan_tier, status, created_at
                      FROM public.tenants
                     WHERE slug = %s;
                    """,
                    (slug,),
                )
                row = cur.fetchone()
                was_existing = True
                if row is None:
                    raise RuntimeError(
                        f"slug={slug!r} conflicted on INSERT but absent on SELECT"
                    )

        roster_seeded = 0
        if seed_roster:
            from lib.tenant_roster import seed_default_roster
            roster_seeded = seed_default_roster(conn, row["id"])

        conn.commit()
    finally:
        conn.close()

    result = dict(row)
    result["id"] = str(result["id"])
    result["created_at"] = result["created_at"].isoformat() if result["created_at"] else None
    result["was_existing"] = was_existing
    result["roster_seeded"] = roster_seeded
    return result


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="amg-provision-tenant",
        description="Provision a new AMG client tenant (idempotent on slug).",
    )
    parser.add_argument("--slug", required=True, help="URL-safe identifier, 3-64 chars")
    parser.add_argument("--name", required=True, help="Display name")
    parser.add_argument("--subdomain", help="Subdomain for portal.aimarketinggenius.io")
    parser.add_argument(
        "--plan-tier",
        default="chamber-standard",
        choices=sorted(ALLOWED_PLAN_TIERS),
    )
    parser.add_argument(
        "--brand-config",
        help="JSON string for brand_config (logo/palette/typography)",
    )
    parser.add_argument("--webauthn-rp-id", help="WebAuthn RP ID (usually the subdomain)")
    parser.add_argument("--webauthn-rp-name", help="WebAuthn RP display name")
    parser.add_argument("--vapid-public-key")
    parser.add_argument("--vapid-subject")
    parser.add_argument(
        "--no-seed-roster",
        dest="seed_roster",
        action="store_false",
        help="Skip auto-seeding the 7-agent default roster",
    )
    parser.set_defaults(seed_roster=True)
    args = parser.parse_args(argv)

    brand = None
    if args.brand_config:
        try:
            brand = json.loads(args.brand_config)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --brand-config must be valid JSON: {exc}", file=sys.stderr)
            return 2

    try:
        result = provision_tenant(
            slug=args.slug,
            name=args.name,
            subdomain=args.subdomain,
            plan_tier=args.plan_tier,
            brand_config=brand,
            webauthn_rp_id=args.webauthn_rp_id,
            webauthn_rp_name=args.webauthn_rp_name,
            vapid_public_key=args.vapid_public_key,
            vapid_subject=args.vapid_subject,
            seed_roster=args.seed_roster,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except psycopg2.Error as exc:
        print(f"DB ERROR: {exc}", file=sys.stderr)
        return 3

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
