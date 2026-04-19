"""First-week deliverable scheduler — commit #9 Kleisthenes CRM Loop.

On tenant provision, enqueues:

  1. Welcome email in public.outbound_email_queue (scheduled_at = now + 15 min).
     Metadata tagged kind='onboarding_first_week' for idempotency.
  2. Kickoff decision posted to MCP tagged `onboarding-kickoff` +
     `client-context:{slug}` so Solon's TodoList / Command Center surfaces it.

Skeleton-first: single welcome email + kickoff decision. Follow-up commits
will expand to full 7-day drip (content calendar, agent activation tasks,
review cadence).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from lib.crm_mcp_bridge import MCPUnavailable, post_decision


ONBOARDING_KIND = "onboarding_first_week"

# System sender for onboarding emails — AMG-internal admin operator.
# (outbound_email_queue.operator_id is NOT NULL; the onboarding email is
# sent BY AMG TO the tenant contact, so we use the internal admin id.)
DEFAULT_SYSTEM_SENDER_OPERATOR_ID = "cccccccc-0000-0000-0000-000000000001"

DEFAULT_WELCOME_DELAY_SECONDS = 15 * 60  # 15 min

DEFAULT_WELCOME_SUBJECT = "Welcome to AI Marketing Genius — your first 7 days"

DEFAULT_WELCOME_BODY_PLAINTEXT = (
    "Hi {name},\n\n"
    "Welcome aboard. We're getting your portal and your 7-agent roster "
    "stood up right now — you'll see Maya (content), Nadia (nurture), "
    "Alex (voice + chat), Jordan (SEO), Sam (social), Riley (reputation), "
    "and Lumina (visual) active in the next 15 minutes.\n\n"
    "First-week plan lands in your inbox tomorrow morning. Reply to this "
    "email if anything's off.\n\n"
    "— Solon"
)


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


def _has_existing_onboarding_email(
    conn: Any, tenant_id: str
) -> str | None:
    """Return email id if an onboarding_first_week row already exists."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM public.outbound_email_queue
             WHERE tenant_id = %s
               AND metadata->>'kind' = %s
             LIMIT 1;
            """,
            (tenant_id, ONBOARDING_KIND),
        )
        row = cur.fetchone()
    return str(row[0]) if row else None


def _enqueue_welcome_email(
    conn: Any,
    tenant_id: str,
    tenant_slug: str,
    tenant_name: str,
    contact_email: str,
    sender_operator_id: str,
    contact_name: str | None = None,
    delay_seconds: int = DEFAULT_WELCOME_DELAY_SECONDS,
    from_alias: str = "onboarding@aimarketinggenius.io",
) -> str:
    name = contact_name or tenant_name
    subject = DEFAULT_WELCOME_SUBJECT
    body = DEFAULT_WELCOME_BODY_PLAINTEXT.format(name=name)
    metadata = {
        "kind": ONBOARDING_KIND,
        "tenant_slug": tenant_slug,
        "tenant_name": tenant_name,
        "delay_seconds": delay_seconds,
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.outbound_email_queue
                (tenant_id, operator_id, from_alias, to_recipients,
                 subject, body_plaintext, status, scheduled_at, metadata)
            VALUES (%s, %s, %s, ARRAY[%s], %s, %s, 'queued',
                    now() + make_interval(secs => %s), %s::jsonb)
         RETURNING id;
            """,
            (
                tenant_id,
                sender_operator_id,
                from_alias,
                contact_email,
                subject,
                body,
                int(delay_seconds),
                json.dumps(metadata),
            ),
        )
        row = cur.fetchone()
    return str(row[0])


def schedule_first_week_deliverables(
    conn: Any,
    tenant_id: Any,
    tenant_slug: str,
    tenant_name: str,
    contact_email: str,
    contact_name: str | None = None,
    delay_seconds: int = DEFAULT_WELCOME_DELAY_SECONDS,
    sender_operator_id: str = DEFAULT_SYSTEM_SENDER_OPERATOR_ID,
    post_mcp_decision: bool = True,
) -> dict[str, Any]:
    """Enqueue first-week onboarding deliverables. Idempotent per tenant.

    Returns:
        {
          "welcome_email_id": str,
          "welcome_was_existing": bool,
          "mcp_decision": "posted" | "skipped" | f"error:{cls}",
        }
    """
    tid = _coerce_uuid(tenant_id, "tenant_id")
    if not contact_email or "@" not in contact_email:
        raise ValueError("contact_email required with '@'")

    existing = _has_existing_onboarding_email(conn, tid)
    if existing is not None:
        welcome_id = existing
        was_existing = True
    else:
        welcome_id = _enqueue_welcome_email(
            conn,
            tid,
            tenant_slug,
            tenant_name,
            contact_email=contact_email,
            sender_operator_id=_coerce_uuid(sender_operator_id, "sender_operator_id"),
            contact_name=contact_name,
            delay_seconds=delay_seconds,
        )
        was_existing = False

    mcp_status = "skipped"
    if post_mcp_decision and not was_existing:
        text = (
            f"Onboarding kickoff — tenant={tenant_slug} ({tenant_name}) · "
            f"welcome email queued id={welcome_id} to {contact_email} · "
            f"sends in ~{delay_seconds // 60} min"
        )
        tags = [
            "onboarding-kickoff",
            f"client-context:{tenant_slug}",
            "crm-memory-bridge",
        ]
        try:
            post_decision(text, tags)
            mcp_status = "posted"
        except MCPUnavailable as exc:
            mcp_status = f"skipped:{type(exc).__name__}"
        except Exception as exc:
            mcp_status = f"error:{type(exc).__name__}"

    return {
        "welcome_email_id": welcome_id,
        "welcome_was_existing": was_existing,
        "mcp_decision": mcp_status,
    }
