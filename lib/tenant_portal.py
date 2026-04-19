"""Tenant portal handlers — commit #8 Kleisthenes CRM Loop.

Backend functions for portal.aimarketinggenius.io/{slug}/ — designed to be
mounted into atlas_api (commit #10 wires FastAPI routes) or consumed
directly by other services.

Two primary entry points:

    portal_context(conn, slug) -> dict
        Full tenant portal render payload: tenant meta, enabled roster,
        recent leads (last 10), stats strip (lead counts by status).

    portal_ingest_lead(conn, slug, lead_payload) -> dict
        Public-form-safe lead intake. Resolves slug → tenant_id, forces
        source=inbound_form, calls lib.crm_lead_intake.ingest_lead, then
        logs sync_lead_ingested to MCP.
"""

from __future__ import annotations

import re
from typing import Any

from lib.agent_context_loader import load_tenant_context
from lib.crm_lead_intake import ingest_lead
from lib.crm_mcp_bridge import MCPUnavailable, sync_lead_ingested


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")


def _validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise ValueError(f"invalid tenant_slug: {slug!r}")
    return slug


def portal_context(conn: Any, slug: str) -> dict[str, Any]:
    """Render payload for portal.aimarketinggenius.io/{slug}/ home page."""
    _validate_slug(slug)
    ctx = load_tenant_context(conn, slug, lead_limit=10, decisions_limit=10)

    enabled_agents = [a for a in ctx["roster"] if a["enabled"]]
    lead_counts = _lead_counts_by_status(conn, ctx["tenant"]["id"])

    return {
        "tenant": {
            "slug": ctx["tenant"]["slug"],
            "name": ctx["tenant"]["name"],
            "subdomain": ctx["tenant"]["subdomain"],
            "brand_config": ctx["tenant"]["brand_config"],
            "plan_tier": ctx["tenant"]["plan_tier"],
        },
        "roster": enabled_agents,
        "recent_leads": ctx["recent_leads"],
        "lead_counts": lead_counts,
        "recent_decisions_count": len(ctx["recent_decisions"]),
    }


def _lead_counts_by_status(conn: Any, tenant_id: str) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, COUNT(*)
              FROM public.crm_lead_intake
             WHERE tenant_id = %s
             GROUP BY status;
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()
    counts = {s: 0 for s in ("new", "qualified", "disqualified", "contacted", "converted")}
    for status, count in rows:
        counts[status] = int(count)
    counts["total"] = sum(counts.values())
    return counts


def portal_ingest_lead(
    conn: Any,
    slug: str,
    contact_email: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    contact_company: str | None = None,
    message: str | None = None,
    utm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Public-form-safe lead ingest from portal.aimarketinggenius.io/{slug}/api/lead.

    Resolves slug → tenant_id, forces source='inbound_form', captures
    UTMs + message in source_metadata. Posts sync decision to MCP (non-
    fatal if MCP is unavailable)."""
    _validate_slug(slug)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.tenants WHERE slug = %s;", (slug,))
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"no tenant with slug={slug!r}")
    tenant_id = str(row[0])

    meta: dict[str, Any] = {}
    if utm:
        meta["utm"] = utm
    if message:
        meta["inbound_message"] = message[:4000]

    raw = {}
    if message:
        raw["message"] = message

    lead = ingest_lead(
        conn,
        tenant_id,
        "inbound_form",
        contact_email=contact_email,
        contact_name=contact_name,
        contact_phone=contact_phone,
        contact_company=contact_company,
        source_metadata=meta,
        raw_payload=raw,
    )

    mcp_status = "posted"
    try:
        sync_lead_ingested(slug, lead)
    except MCPUnavailable as exc:
        mcp_status = f"skipped:{type(exc).__name__}"
    except Exception as exc:  # defensive — never block CRM write on MCP
        mcp_status = f"error:{type(exc).__name__}"

    return {
        "lead": lead,
        "tenant_slug": slug,
        "mcp_sync": mcp_status,
    }
