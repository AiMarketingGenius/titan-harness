"""Tenant agent roster — commit #3 of Kleisthenes CRM Loop.

Manages each tenant's instance of the 7-agent AMG roster
(Maya / Nadia / Alex / Jordan / Sam / Riley / Lumina). Wraps the
public.tenant_agent_roster table (sql/011_tenant_agent_roster.sql).

Roster seeding is idempotent — safe to call on provision and again on
reconfiguration. Per-agent enable/disable + config patch for tenant-level
customization (voice IDs, persona overrides, prompt tokens).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any


DEFAULT_ROSTER: list[tuple[str, str]] = [
    ("maya",   "Content Strategist"),
    ("nadia",  "Nurture & Follow-up"),
    ("alex",   "Voice + Chat"),
    ("jordan", "SEO & Rankings"),
    ("sam",    "Social Presence"),
    ("riley",  "Reputation & Reviews"),
    ("lumina", "Visual & Brand"),
]

VALID_AGENT_KEYS = frozenset(k for k, _ in DEFAULT_ROSTER)


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _coerce_uuid(value: Any, field: str) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be str or uuid.UUID")
    s = value.strip().lower()
    if not _UUID_RE.match(s):
        raise ValueError(f"{field} is not a valid UUID: {value!r}")
    return s


def _validate_agent_key(agent_key: str) -> None:
    if agent_key not in VALID_AGENT_KEYS:
        raise ValueError(
            f"agent_key {agent_key!r} not in {sorted(VALID_AGENT_KEYS)}"
        )


def seed_default_roster(conn: Any, tenant_id: Any) -> int:
    """Insert all 7 default agents for the tenant. Returns count inserted
    (0 if already seeded via ON CONFLICT DO NOTHING)."""
    tid = _coerce_uuid(tenant_id, "tenant_id")
    inserted = 0
    with conn.cursor() as cur:
        for agent_key, role_title in DEFAULT_ROSTER:
            cur.execute(
                """
                INSERT INTO public.tenant_agent_roster (tenant_id, agent_key, role_title)
                VALUES (%s, %s, %s)
                ON CONFLICT (tenant_id, agent_key) DO NOTHING;
                """,
                (tid, agent_key, role_title),
            )
            inserted += cur.rowcount
    return inserted


def get_tenant_roster(conn: Any, tenant_id: Any) -> list[dict[str, Any]]:
    """Return the full roster for a tenant, ordered by agent_key."""
    tid = _coerce_uuid(tenant_id, "tenant_id")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT agent_key, role_title, enabled, config,
                   activated_at, updated_at
              FROM public.tenant_agent_roster
             WHERE tenant_id = %s
             ORDER BY agent_key;
            """,
            (tid,),
        )
        rows = cur.fetchall()
    return [
        {
            "agent_key": row[0],
            "role_title": row[1],
            "enabled": row[2],
            "config": row[3] if row[3] is not None else {},
            "activated_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
        }
        for row in rows
    ]


def set_agent_enabled(conn: Any, tenant_id: Any, agent_key: str, enabled: bool) -> bool:
    """Flip enabled flag. Returns True if a row updated, False if agent missing."""
    tid = _coerce_uuid(tenant_id, "tenant_id")
    _validate_agent_key(agent_key)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.tenant_agent_roster
               SET enabled = %s
             WHERE tenant_id = %s AND agent_key = %s;
            """,
            (bool(enabled), tid, agent_key),
        )
        return cur.rowcount > 0


def update_agent_config(
    conn: Any, tenant_id: Any, agent_key: str, config_patch: dict[str, Any]
) -> dict[str, Any]:
    """Merge config_patch into the agent's config JSONB (existing keys overwritten).
    Returns the merged config post-update."""
    tid = _coerce_uuid(tenant_id, "tenant_id")
    _validate_agent_key(agent_key)
    if not isinstance(config_patch, dict):
        raise ValueError("config_patch must be a dict")
    patch_json = json.dumps(config_patch)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.tenant_agent_roster
               SET config = config || %s::jsonb
             WHERE tenant_id = %s AND agent_key = %s
         RETURNING config;
            """,
            (patch_json, tid, agent_key),
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError(f"no roster row for tenant={tid} agent={agent_key}")
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])
