"""Lead intake — commit #4 of Kleisthenes CRM Loop.

Five canonical sources write through ingest_lead():
    inbound_form   — Lovable / landing-page form
    chatbot        — Alex orb (web chat)
    voicebot       — Alex orb (voice)
    outbound_reply — reply to outbound email / SMS campaign
    linkedin       — DM or InMail

Dedup: (tenant_id, source, contact_email) UNIQUE when email not null. Re-ingest
merges source_metadata into raw_payload and returns the existing row.

Nadia entry: auto-scheduled 5 min from insert (trigger-side belt-and-suspenders,
or passed explicitly via nadia_offset_seconds).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any


VALID_SOURCES = frozenset({
    "inbound_form",
    "chatbot",
    "voicebot",
    "outbound_reply",
    "linkedin",
})

VALID_STATUSES = frozenset({
    "new",
    "qualified",
    "disqualified",
    "contacted",
    "converted",
})

VALID_AGENTS = frozenset({
    "maya", "nadia", "alex", "jordan", "sam", "riley", "lumina",
})

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _coerce_uuid(value: Any, field: str) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be str or uuid.UUID")
    s = value.strip().lower()
    if not _UUID_RE.match(s):
        raise ValueError(f"{field} is not a valid UUID: {value!r}")
    return s


def _validate_email(email: str | None) -> str | None:
    if email is None:
        return None
    email = email.strip().lower()
    if not email:
        return None
    if not _EMAIL_RE.match(email):
        raise ValueError(f"invalid email: {email!r}")
    return email


def ingest_lead(
    conn: Any,
    tenant_id: Any,
    source: str,
    contact_email: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    contact_company: str | None = None,
    source_metadata: dict[str, Any] | None = None,
    raw_payload: dict[str, Any] | None = None,
    assigned_agent: str | None = None,
    nadia_offset_seconds: int | None = None,
) -> dict[str, Any]:
    """Ingest a new lead or upsert by (tenant, source, email).

    Returns dict: {id, tenant_id, source, contact_email, status,
    nadia_entry_scheduled_at, created_at, was_existing}.
    """
    tid = _coerce_uuid(tenant_id, "tenant_id")
    if source not in VALID_SOURCES:
        raise ValueError(f"source {source!r} not in {sorted(VALID_SOURCES)}")
    if assigned_agent is not None and assigned_agent not in VALID_AGENTS:
        raise ValueError(f"assigned_agent {assigned_agent!r} not in {sorted(VALID_AGENTS)}")
    email = _validate_email(contact_email)

    meta_json = json.dumps(source_metadata or {})
    payload_json = json.dumps(raw_payload or {})

    nadia_clause = "now() + make_interval(secs => %s)" if nadia_offset_seconds is not None else "NULL"
    nadia_params = [nadia_offset_seconds] if nadia_offset_seconds is not None else []

    # The partial unique index crm_lead_intake_tenant_source_email_uq
    # (WHERE contact_email IS NOT NULL) requires the matching predicate on
    # ON CONFLICT. NULL-email rows fall through (no conflict possible) —
    # expected for voicebot intake before email is captured.
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO public.crm_lead_intake
                (tenant_id, source, source_metadata, contact_name, contact_email,
                 contact_phone, contact_company, raw_payload, assigned_agent,
                 nadia_entry_scheduled_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s, {nadia_clause})
            ON CONFLICT (tenant_id, source, contact_email)
                WHERE contact_email IS NOT NULL
                DO NOTHING
            RETURNING id, tenant_id, source, contact_email, status,
                      nadia_entry_scheduled_at, created_at;
            """,
            [
                tid, source, meta_json, contact_name, email,
                contact_phone, contact_company, payload_json, assigned_agent,
            ] + nadia_params,
        )
        row = cur.fetchone()
        was_existing = False
        if row is None:
            cur.execute(
                """
                UPDATE public.crm_lead_intake
                   SET raw_payload = raw_payload || %s::jsonb,
                       source_metadata = source_metadata || %s::jsonb
                 WHERE tenant_id = %s AND source = %s AND contact_email = %s
             RETURNING id, tenant_id, source, contact_email, status,
                       nadia_entry_scheduled_at, created_at;
                """,
                (payload_json, meta_json, tid, source, email),
            )
            row = cur.fetchone()
            was_existing = True
            if row is None:
                raise RuntimeError(
                    f"upsert conflicted but could not locate existing row for "
                    f"tenant={tid} source={source} email={email!r}"
                )

    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "source": row[2],
        "contact_email": row[3],
        "status": row[4],
        "nadia_entry_scheduled_at": row[5].isoformat() if row[5] else None,
        "created_at": row[6].isoformat() if row[6] else None,
        "was_existing": was_existing,
    }


def list_leads(
    conn: Any,
    tenant_id: Any,
    status: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Feed query. Scoped to tenant, optional status + source filter."""
    tid = _coerce_uuid(tenant_id, "tenant_id")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status {status!r} not in {sorted(VALID_STATUSES)}")
    if source is not None and source not in VALID_SOURCES:
        raise ValueError(f"source {source!r} not in {sorted(VALID_SOURCES)}")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be 1..500")

    clauses = ["tenant_id = %s"]
    params: list[Any] = [tid]
    if status is not None:
        clauses.append("status = %s")
        params.append(status)
    if source is not None:
        clauses.append("source = %s")
        params.append(source)
    where = " AND ".join(clauses)
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, source, contact_name, contact_email, contact_phone,
                   contact_company, status, assigned_agent,
                   nadia_entry_scheduled_at, created_at
              FROM public.crm_lead_intake
             WHERE {where}
             ORDER BY created_at DESC
             LIMIT %s;
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        {
            "id": str(r[0]),
            "source": r[1],
            "contact_name": r[2],
            "contact_email": r[3],
            "contact_phone": r[4],
            "contact_company": r[5],
            "status": r[6],
            "assigned_agent": r[7],
            "nadia_entry_scheduled_at": r[8].isoformat() if r[8] else None,
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def update_lead_status(
    conn: Any, tenant_id: Any, lead_id: Any, status: str
) -> bool:
    """Transition a lead's status. Returns True if row updated."""
    tid = _coerce_uuid(tenant_id, "tenant_id")
    lid = _coerce_uuid(lead_id, "lead_id")
    if status not in VALID_STATUSES:
        raise ValueError(f"status {status!r} not in {sorted(VALID_STATUSES)}")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.crm_lead_intake
               SET status = %s
             WHERE tenant_id = %s AND id = %s;
            """,
            (status, tid, lid),
        )
        return cur.rowcount > 0
