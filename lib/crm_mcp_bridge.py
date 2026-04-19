"""CRM ↔ MCP bidirectional sync — commit #5 of Kleisthenes CRM Loop.

Every material CRM state transition (lead ingested, status change, agent
reassignment) logs an MCP decision tagged `crm-memory-bridge` +
`client-context:{tenant_slug}` + source/status tags. MCP queries by tenant
slug feed back into CRM context for agents.

Uses the same MCP HTTP pattern as lib/mobile_lifecycle.py — POST to
{MCP_BASE_URL}/api/decisions and GET /api/decisions/recent. httpx required.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None


MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "https://memory.aimarketinggenius.io")
MCP_TIMEOUT = float(os.environ.get("MCP_TIMEOUT", "30.0"))  # writes embed — allow slow path

BRIDGE_TAG = "crm-memory-bridge"


class MCPBridgeError(RuntimeError):
    pass


class MCPUnavailable(MCPBridgeError):
    pass


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")


def _require_httpx() -> None:
    if httpx is None:
        raise MCPBridgeError("httpx not installed — pip install httpx")


def _coerce_uuid(value: Any, field: str) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be str or uuid.UUID")
    s = value.strip().lower()
    if not _UUID_RE.match(s):
        raise ValueError(f"{field} is not a valid UUID: {value!r}")
    return s


def _validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise ValueError(f"invalid tenant_slug: {slug!r}")
    return slug


def tenant_slug_for(conn: Any, tenant_id: Any) -> str:
    """Look up tenant_slug by id (cache in caller if hot-pathed)."""
    tid = _coerce_uuid(tenant_id, "tenant_id")
    with conn.cursor() as cur:
        cur.execute("SELECT slug FROM public.tenants WHERE id = %s;", (tid,))
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"no tenant row for id={tid}")
    return row[0]


def post_decision(text: str, tags: list[str], project_source: str = "titan") -> dict[str, Any]:
    """POST to MCP `/api/decisions`. Raises MCPUnavailable on network / 5xx."""
    _require_httpx()
    if not text.strip():
        raise ValueError("text must not be empty")
    payload = {"project_source": project_source, "text": text, "tags": tags}
    url = f"{MCP_BASE_URL}/api/decisions"
    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
            r = client.post(url, json=payload)
            if r.status_code >= 500:
                raise MCPUnavailable(f"MCP 5xx: {r.status_code}")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as exc:
        raise MCPUnavailable(f"MCP HTTP error: {exc}") from exc


def fetch_decisions_by_tag(
    conn: Any, tag: str, count: int = 20
) -> list[dict[str, Any]]:
    """Query op_decisions table directly for rows carrying `tag`.

    MCP has no GET HTTP endpoint for retrieval — only POST for writes. Reads
    go through the underlying Supabase table. Callers must already have a
    psycopg2 connection (typical: the same one used for CRM mutations).
    """
    if count < 1 or count > 200:
        raise ValueError("count must be 1..200")
    if not isinstance(tag, str) or not tag:
        raise ValueError("tag must be non-empty string")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, decision_text, tags, created_at, project_source, rationale
              FROM public.op_decisions
             WHERE %s = ANY(tags)
               AND COALESCE(archived, FALSE) = FALSE
             ORDER BY created_at DESC
             LIMIT %s;
            """,
            (tag, count),
        )
        rows = cur.fetchall()

    return [
        {
            "id": str(r[0]),
            "text": r[1],
            "tags": list(r[2]) if r[2] else [],
            "created_at": r[3].isoformat() if r[3] else None,
            "project_source": r[4],
            "rationale": r[5],
        }
        for r in rows
    ]


def sync_lead_ingested(
    tenant_slug: str,
    lead: dict[str, Any],
    action: str = "ingested",
) -> dict[str, Any]:
    """Log a decision when a new lead lands.

    `lead` should be the dict returned by lib.crm_lead_intake.ingest_lead.
    """
    _validate_slug(tenant_slug)
    source = lead.get("source", "unknown")
    email = lead.get("contact_email") or "(no-email)"
    lead_id = lead.get("id", "unknown")
    status = lead.get("status", "new")

    text = (
        f"CRM lead {action} — tenant={tenant_slug} source={source} "
        f"email={email} status={status} lead_id={lead_id}"
    )
    tags = [
        BRIDGE_TAG,
        f"client-context:{tenant_slug}",
        f"lead-source:{source}",
        f"lead-status:{status}",
        f"action:{action}",
    ]
    return post_decision(text, tags)


def sync_status_change(
    tenant_slug: str,
    lead_id: Any,
    source: str,
    old_status: str,
    new_status: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Log a decision when a lead transitions status."""
    _validate_slug(tenant_slug)
    lid = _coerce_uuid(lead_id, "lead_id")

    text = (
        f"CRM lead status change — tenant={tenant_slug} source={source} "
        f"lead_id={lid} {old_status} → {new_status}"
    )
    if note:
        text += f" · note: {note}"
    tags = [
        BRIDGE_TAG,
        f"client-context:{tenant_slug}",
        f"lead-source:{source}",
        f"lead-status:{new_status}",
        f"transition:{old_status}->{new_status}",
    ]
    return post_decision(text, tags)


def fetch_tenant_context(
    conn: Any, tenant_slug: str, count: int = 20
) -> list[dict[str, Any]]:
    """Pull recent MCP decisions tagged `client-context:{tenant_slug}`.

    Requires a psycopg2 connection — MCP exposes POST only over HTTP, so
    reads query the underlying op_decisions table directly.
    """
    _validate_slug(tenant_slug)
    return fetch_decisions_by_tag(
        conn, f"client-context:{tenant_slug}", count=count
    )
