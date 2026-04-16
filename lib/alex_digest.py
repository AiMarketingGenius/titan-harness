"""
lib/alex_digest.py

Weekly Alex digest generator — CT-0415-ADDENDUM-item9.

Every Friday, for every active client, Alex posts a plain-English weekly update
into the client's portal chat thread. Reads MCP task queue + sprint state + recent
decisions for that client, scrubs tool names per CLAUDE.md P10, writes in Alex's
voice, inserts into public.messages as assistant role on the client's existing
Alex chat_session.

Usage (CLI):
    python -m lib.alex_digest generate --client-id <uuid> [--dry-run]
    python -m lib.alex_digest run-weekly              # iterates all active clients
    python -m lib.alex_digest preview --client-id <uuid>

Scheduled via cron: Fridays 16:00 America/New_York.

Trade-secret scrub rules (P10):
  - Never mention Telnyx, n8n, Supabase, Claude, Anthropic, GHL, Stagehand,
    Kokoro, Hermes (internal codename), Titan (internal codename), Aristotle,
    Perplexity, OpenAI.
  - Replace with plain-English client-facing equivalents per SCRUB_MAP.
  - If a source string cannot be safely scrubbed, OMIT it entirely.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("alex_digest")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://egoazyasyrhslluossli.supabase.co")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT", "https://memory.aimarketinggenius.io")

ALEX_AGENT_ID = "alex"

# ---------------------------------------------------------------------------
# Trade-secret scrub table (P10 — client-facing language ONLY)
# ---------------------------------------------------------------------------

SCRUB_MAP = {
    # Voice + telco
    "telnyx": "your business texting and voice platform",
    "telnyx a2p": "your business texting registration",
    "a2p 10dlc": "business texting registration",
    "a2p/10dlc": "business texting registration",
    "kokoro": "your voice agent",
    "hermes": "your voice agent",
    "elevenlabs": "your voice agent",
    # Orchestration
    "n8n": "",
    "titan": "",
    "aristotle": "our research team",
    "perplexity": "our research team",
    # AI stack
    "anthropic": "",
    "claude": "",
    "openai": "",
    "gpt": "",
    "gemini": "",
    "llm": "",
    # Storage + auth
    "supabase": "your portal",
    "postgres": "your portal database",
    # Browser auto
    "stagehand": "our browser automation",
    "playwright": "our browser automation",
    # CRM
    "gohighlevel": "your CRM",
    "ghl": "your CRM",
    # Internal tools
    "mcp": "our internal memory",
    "lovable": "your portal platform",
    "cloudflare": "your content delivery",
    "caddy": "your web server",
    "docker": "",
    "vps": "our servers",
    "hetzner": "our servers",
    "hosthatch": "our servers",
    # Misc technical
    "api": "integration",
    "cron": "scheduled job",
    "systemd": "",
    "webhook": "automated connection",
    "webhooks": "automated connections",
    "oauth": "account connection",
    "sql": "",
    "postgresql": "",
}

FORBIDDEN_TECHNICAL_PATTERNS = [
    re.compile(r"\bct-\d{4}-\d+\b", re.IGNORECASE),        # internal task IDs
    re.compile(r"\b[a-f0-9]{7,40}\b"),                      # commit hashes
    re.compile(r"\b[a-z-]+\.service\b", re.IGNORECASE),     # systemd unit names
    re.compile(r"\blib/[a-z_]+\.py\b"),                     # internal paths
    re.compile(r"\bbin/[a-z_-]+\.sh\b"),                    # internal paths
    re.compile(r"\b[A-Z_]{3,}=[A-Z0-9_-]+\b"),              # env var patterns
    re.compile(r"\btask\s+id[:\s]+[\w-]+\b", re.IGNORECASE),
]


def scrub_text(text: str) -> str:
    """Apply P10 trade-secret scrub to arbitrary text. Case-insensitive replace."""
    if not text:
        return ""
    scrubbed = text
    # Sort by length descending so longer compound phrases match first
    for k in sorted(SCRUB_MAP.keys(), key=len, reverse=True):
        v = SCRUB_MAP[k]
        scrubbed = re.sub(re.escape(k), v, scrubbed, flags=re.IGNORECASE)
    # Drop patterns we can't safely scrub
    for pattern in FORBIDDEN_TECHNICAL_PATTERNS:
        scrubbed = pattern.sub("", scrubbed)
    # Collapse repeated whitespace created by empty replacements
    scrubbed = re.sub(r"[ \t]{2,}", " ", scrubbed)
    scrubbed = re.sub(r"\s*,\s*,", ",", scrubbed)
    scrubbed = re.sub(r"\n{3,}", "\n\n", scrubbed)
    return scrubbed.strip()


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

@dataclass
class ClientContext:
    user_id: str
    business_name: str
    display_name: str
    billing_tier: str
    alex_session_id: Optional[str]
    facts: dict[str, str]  # fact_key -> fact_value


def _psql(sql: str) -> list[dict[str, Any]]:
    """Run SQL via psql and parse JSON output."""
    if not SUPABASE_DB_URL:
        raise RuntimeError("SUPABASE_DB_URL not set")
    import subprocess
    wrapped = f"SELECT json_agg(t) FROM ({sql}) t;"
    result = subprocess.run(
        ["psql", SUPABASE_DB_URL, "-t", "-A", "-c", wrapped],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr}")
    raw = result.stdout.strip()
    if raw in ("", "null"):
        return []
    return json.loads(raw)


def load_client_context(user_id: str) -> ClientContext:
    rows = _psql(f"""
        SELECT id::text AS user_id, display_name, business_name, billing_tier
        FROM public.client_profiles WHERE id = '{user_id}'
    """)
    if not rows:
        raise RuntimeError(f"client_profile not found for {user_id}")
    profile = rows[0]

    # Alex session
    session_rows = _psql(f"""
        SELECT id::text FROM public.chat_sessions
        WHERE user_id = '{user_id}' AND agent_id = 'alex'
        ORDER BY created_at DESC LIMIT 1
    """)
    alex_session_id = session_rows[0]["id"] if session_rows else None

    # Facts
    fact_rows = _psql(f"""
        SELECT fact_key, fact_value FROM public.client_facts
        WHERE client_id = '{user_id}' AND is_active = true
    """)
    facts = {r["fact_key"]: r["fact_value"] for r in fact_rows}

    return ClientContext(
        user_id=user_id,
        business_name=profile.get("business_name") or profile.get("display_name") or "your business",
        display_name=profile.get("display_name") or "there",
        billing_tier=profile.get("billing_tier") or "pro",
        alex_session_id=alex_session_id,
        facts=facts,
    )


def load_week_activity(user_id: str, days: int = 7) -> dict[str, Any]:
    """
    Load what happened this week for this client. Pulls from:
      - operator_tasks where tags contain the client_id or business tag
      - decisions logged against the client
      - completed deliverables
    Returns raw, unsrubbed. Scrub happens at render time.

    NOTE: v1 reads a stub structure. Expand once the per-client tagging is live
    in the operator_tasks table.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Tasks shipped this week tagged with this client
    shipped = _psql(f"""
        SELECT objective, result_summary, updated_at::text
        FROM public.operator_tasks
        WHERE status = 'done'
          AND updated_at > '{since}'
          AND (tags::text ILIKE '%{user_id[:8]}%'
               OR campaign_id ILIKE '%{user_id[:8]}%')
        ORDER BY updated_at DESC LIMIT 20
    """) if _table_exists("operator_tasks") else []

    return {
        "shipped_this_week": shipped,
        "since": since,
    }


def _table_exists(name: str) -> bool:
    rows = _psql(
        f"SELECT tablename FROM pg_tables "
        f"WHERE schemaname='public' AND tablename='{name}'"
    )
    return bool(rows)


# ---------------------------------------------------------------------------
# Digest composer (Alex voice)
# ---------------------------------------------------------------------------

ALEX_INTRO_TEMPLATES = [
    "Hey {name} — Alex here with your Friday update.",
    "Friday check-in, {name}.",
    "Happy Friday, {name}. Quick update on the week.",
]

ALEX_CLOSE_TEMPLATES = [
    "Anything else you want me to prioritize for next week? Shoot me a message here.",
    "Talk to you Tuesday on our standing call. Text Solon direct if anything urgent comes up.",
    "Full week ahead — hit me with any questions over the weekend, I'll see them Monday morning.",
]


def compose_digest(ctx: ClientContext, activity: dict[str, Any]) -> str:
    """Compose the full weekly digest in Alex's voice. Already scrubbed."""
    lines: list[str] = []
    first_name = ctx.display_name.split()[0] if ctx.display_name else "there"

    # Intro (rotate deterministically by week number for variety)
    week = datetime.now().isocalendar()[1]
    lines.append(ALEX_INTRO_TEMPLATES[week % len(ALEX_INTRO_TEMPLATES)].format(name=first_name))
    lines.append("")

    # Shipped
    shipped = activity.get("shipped_this_week") or []
    if shipped:
        lines.append("**What we shipped:**")
        for item in shipped[:6]:
            summary = item.get("result_summary") or item.get("objective") or ""
            clean = scrub_text(summary)
            if clean and len(clean) > 10:
                lines.append(f"- {clean}")
        lines.append("")
    else:
        lines.append("**What we shipped this week:**")
        lines.append("- Quiet week on deliverables — groundwork in motion for next week's ship.")
        lines.append("")

    # What's coming (v1: static scaffold; v2: pulls from upcoming tasks)
    lines.append("**What's coming next week:**")
    lines.append("- Next set of deliverables is lined up. I'll walk through specifics on our Tuesday call.")
    lines.append("")

    # What I need (v1: static; v2: pulls from blocked-on-client tasks)
    lines.append("**What I need from you:**")
    lines.append("- Nothing urgent. If anything blocking comes up, I'll text Solon direct.")
    lines.append("")

    # Close
    lines.append(ALEX_CLOSE_TEMPLATES[week % len(ALEX_CLOSE_TEMPLATES)])
    lines.append("")
    lines.append("— Alex")

    full = "\n".join(lines)
    return scrub_text(full)  # belt + suspenders


# ---------------------------------------------------------------------------
# Post to portal
# ---------------------------------------------------------------------------

def post_digest(ctx: ClientContext, digest: str, dry_run: bool = False) -> dict[str, Any]:
    """Insert assistant message into ctx.alex_session_id."""
    if dry_run:
        return {"action": "dry_run", "len": len(digest), "preview": digest[:300]}

    if not ctx.alex_session_id:
        raise RuntimeError(f"No Alex chat_session for user {ctx.user_id}. Seed one first.")

    # Escape single quotes for SQL literal
    safe = digest.replace("'", "''")
    sql = (
        f"INSERT INTO public.messages (session_id, user_id, agent_id, role, content, direction, metadata) "
        f"VALUES ('{ctx.alex_session_id}', '{ctx.user_id}', 'alex', 'assistant', "
        f"'{safe}', 'outbound', jsonb_build_object('source', 'alex_weekly_digest', "
        f"'generated_at', now()::text)) RETURNING id::text;"
    )
    rows = _psql(f"SELECT id::text AS msg_id FROM ({sql.rstrip(';')}) AS q")
    return {"action": "posted", "message_id": rows[0]["msg_id"] if rows else None}


# ---------------------------------------------------------------------------
# Top-level ops
# ---------------------------------------------------------------------------

def generate_for_client(user_id: str, dry_run: bool = False) -> dict[str, Any]:
    ctx = load_client_context(user_id)
    activity = load_week_activity(user_id)
    digest = compose_digest(ctx, activity)
    result = post_digest(ctx, digest, dry_run=dry_run)
    return {
        "user_id": user_id,
        "business_name": ctx.business_name,
        "digest_length_chars": len(digest),
        "digest_preview": digest[:400],
        **result,
    }


def run_weekly(dry_run: bool = False) -> dict[str, Any]:
    """Iterate all active clients + post weekly digest."""
    rows = _psql("""
        SELECT id::text AS user_id
        FROM public.client_profiles
        WHERE status = 'active' AND billing_tier != 'trial'
    """)
    results = []
    for r in rows:
        try:
            res = generate_for_client(r["user_id"], dry_run=dry_run)
            results.append(res)
        except Exception as e:
            results.append({"user_id": r["user_id"], "error": str(e)})
    return {
        "total_clients": len(rows),
        "succeeded": sum(1 for r in results if "error" not in r),
        "failed": sum(1 for r in results if "error" in r),
        "details": results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Alex weekly digest generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Generate + post for one client")
    g.add_argument("--client-id", required=True)
    g.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("preview", help="Print digest without posting")
    p.add_argument("--client-id", required=True)

    sub.add_parser("run-weekly", help="Iterate all active clients").add_argument(
        "--dry-run", action="store_true"
    )

    t = sub.add_parser("scrub-test", help="Test scrub pipeline on stdin")
    t.add_argument("--text", required=True)

    args = ap.parse_args()

    if args.cmd == "generate":
        print(json.dumps(generate_for_client(args.client_id, dry_run=args.dry_run), indent=2))
        return 0
    if args.cmd == "preview":
        ctx = load_client_context(args.client_id)
        activity = load_week_activity(args.client_id)
        digest = compose_digest(ctx, activity)
        print(digest)
        return 0
    if args.cmd == "run-weekly":
        print(json.dumps(run_weekly(dry_run=args.dry_run), indent=2))
        return 0
    if args.cmd == "scrub-test":
        print(scrub_text(args.text))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
