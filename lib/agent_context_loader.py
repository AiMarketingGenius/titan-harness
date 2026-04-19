"""Unified agent context loader — commit #6 of Kleisthenes CRM Loop.

Given a tenant_slug (optionally with agent_key), returns a consolidated
context blob for any AMG agent to consume. Combines:

    - tenant row (id, slug, name, subdomain, brand_config, plan_tier)
    - agent roster (full list or single agent)
    - recent lead intake rows (last N)
    - recent MCP decisions tagged client-context:{slug} (last N)

Skeleton-first: memory_captures + KB facts are scaffolded but not populated
(tables don't exist yet in the Phase 2 schema — follow-up commit will wire
them in after their schema lands). The function signature is stable so
callers don't need to change.

Python companion to deploy/aimg-extension-fixes/lib/mcp_agent_context_loader.js
— server-side equivalent consumed by atlas_api + agent orchestrators.
"""

from __future__ import annotations

import re
from typing import Any

from lib.crm_mcp_bridge import fetch_tenant_context


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")

VALID_AGENT_KEYS = frozenset({
    "maya", "nadia", "alex", "jordan", "sam", "riley", "lumina",
})


def _validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise ValueError(f"invalid tenant_slug: {slug!r}")
    return slug


def _fetch_tenant(conn: Any, slug: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, slug, name, subdomain, brand_config, plan_tier, status,
                   webauthn_rp_id, webauthn_rp_name, created_at
              FROM public.tenants
             WHERE slug = %s;
            """,
            (slug,),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"no tenant with slug={slug!r}")
    return {
        "id": str(row[0]),
        "slug": row[1],
        "name": row[2],
        "subdomain": row[3],
        "brand_config": row[4] if row[4] else {},
        "plan_tier": row[5],
        "status": row[6],
        "webauthn_rp_id": row[7],
        "webauthn_rp_name": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
    }


def _fetch_roster(
    conn: Any, tenant_id: str, agent_key: str | None = None
) -> list[dict[str, Any]]:
    clauses = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if agent_key is not None:
        if agent_key not in VALID_AGENT_KEYS:
            raise ValueError(f"agent_key {agent_key!r} not in {sorted(VALID_AGENT_KEYS)}")
        clauses.append("agent_key = %s")
        params.append(agent_key)
    where = " AND ".join(clauses)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT agent_key, role_title, enabled, config, activated_at, updated_at
              FROM public.tenant_agent_roster
             WHERE {where}
             ORDER BY agent_key;
            """,
            params,
        )
        rows = cur.fetchall()
    return [
        {
            "agent_key": r[0],
            "role_title": r[1],
            "enabled": r[2],
            "config": r[3] if r[3] else {},
            "activated_at": r[4].isoformat() if r[4] else None,
            "updated_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]


def _fetch_recent_leads(conn: Any, tenant_id: str, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, contact_name, contact_email, contact_company,
                   status, assigned_agent, nadia_entry_scheduled_at, created_at
              FROM public.crm_lead_intake
             WHERE tenant_id = %s
             ORDER BY created_at DESC
             LIMIT %s;
            """,
            (tenant_id, limit),
        )
        rows = cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "source": r[1],
            "contact_name": r[2],
            "contact_email": r[3],
            "contact_company": r[4],
            "status": r[5],
            "assigned_agent": r[6],
            "nadia_entry_scheduled_at": r[7].isoformat() if r[7] else None,
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]


def load_tenant_context(
    conn: Any,
    tenant_slug: str,
    agent_key: str | None = None,
    lead_limit: int = 10,
    decisions_limit: int = 10,
) -> dict[str, Any]:
    """Unified tenant context for agent consumption.

    Returns dict:
        tenant: {id, slug, name, subdomain, brand_config, plan_tier, ...}
        roster: list of roster rows (all 7 or scoped to agent_key if provided)
        recent_leads: list of up to `lead_limit` leads
        recent_decisions: list of up to `decisions_limit` MCP decisions tagged
                          client-context:{tenant_slug}
        memory_captures: [] (scaffold — table not yet live)
        kb_facts: [] (scaffold — table not yet live)
    """
    _validate_slug(tenant_slug)
    if lead_limit < 0 or lead_limit > 200:
        raise ValueError("lead_limit must be 0..200")
    if decisions_limit < 0 or decisions_limit > 200:
        raise ValueError("decisions_limit must be 0..200")

    tenant = _fetch_tenant(conn, tenant_slug)
    roster = _fetch_roster(conn, tenant["id"], agent_key=agent_key)
    recent_leads = _fetch_recent_leads(conn, tenant["id"], lead_limit) if lead_limit else []
    recent_decisions = (
        fetch_tenant_context(conn, tenant_slug, count=decisions_limit)
        if decisions_limit else []
    )

    return {
        "tenant": tenant,
        "roster": roster,
        "recent_leads": recent_leads,
        "recent_decisions": recent_decisions,
        "memory_captures": [],  # TODO: wire in when memory_captures table lands
        "kb_facts": [],         # TODO: wire in when kb_facts table lands
    }
