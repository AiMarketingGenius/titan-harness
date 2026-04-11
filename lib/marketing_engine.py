"""
titan-harness/lib/marketing_engine.py

Thread 3 of the Autopilot Suite — Recurring Marketing Engine.
See plans/PLAN_2026-04-11_recurring-marketing-engine.md for the full DR.

Weekly cadence: pull content → build 4-surface package (email, LinkedIn,
X, short-form video) → war-room grade each → Slack approval gate →
schedule via n8n → publish.

Status: STUB module — public API + dataclasses shipped, implementation
TODO per the DR's 5-phase plan.

Phase wiring:
  Phase 1 content-source-ingest        → ingest_content_sources() (TODO)
  Phase 2 package-builder              → build_weekly_package() (TODO)
  Phase 3 short-form-video-generation  → generate_video_asset() (TODO)
  Phase 4 slack-approval-gate          → request_approval() (TODO)
  Phase 5 multi-surface-scheduler      → schedule_package() (TODO)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses matching sql/007 marketing_content_queue + marketing_packages
# ---------------------------------------------------------------------------

class PackageStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REGENERATING = "regenerating"
    HOLDING = "holding"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class ContentSourceItem:
    """One row in marketing_content_queue."""
    id: Optional[str]
    source: str              # 'amg_blog' | 'youtube' | 'linkedin' | 'fireflies' | 'decisions' | 'newsletter'
    source_url: Optional[str]
    title: str
    summary: Optional[str]
    raw_excerpt: Optional[str]
    tags: list[str] = field(default_factory=list)
    published_at: Optional[datetime] = None
    dedupe_hash: str = ""
    used_in_package: bool = False


@dataclass
class SurfacePackage:
    """Generated content for one surface of a weekly package."""
    surface: str             # 'email' | 'linkedin' | 'x' | 'video_brief'
    body: str
    char_count: int
    war_room_grade: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class WeeklyPackage:
    """One row in marketing_packages."""
    id: Optional[str]
    project_id: str
    week_iso: str            # '2026-W15'
    primary_content_ids: list[str]
    email: SurfacePackage
    linkedin: SurfacePackage
    x: SurfacePackage
    video_brief: SurfacePackage
    video_asset_url: Optional[str] = None
    video_asset_thumbnail: Optional[str] = None
    status: PackageStatus = PackageStatus.DRAFT
    slack_approval_ts: Optional[str] = None
    regen_count: int = 0


# ---------------------------------------------------------------------------
# Phase 1 — content source ingest (TODO)
# ---------------------------------------------------------------------------

def ingest_content_sources(project_id: str = "EOM",
                           since_days: int = 7) -> list[ContentSourceItem]:
    """Pull fresh content from all configured sources and dedupe.

    Adapters (sub-modules, each TODO):
      - amg_blog_adapter  (RSS / sitemap scrape)
      - youtube_adapter   (YouTube Data API v3)
      - linkedin_adapter  (if API scope allows; manual pastebin fallback)
      - fireflies_adapter (reads /opt/amg-titan/solon-corpus/fireflies/)
      - decisions_adapter (reads MCP decisions tagged 'amg-public')
      - newsletter_adapter (if archive URL provided)

    TODO: implement Phase 1. Currently stubbed.
    """
    raise NotImplementedError(
        "ingest_content_sources: Phase 1 content-source-ingest not yet "
        "implemented. See plans/PLAN_2026-04-11_recurring-marketing-engine.md "
        "Phase 1 spec."
    )


# ---------------------------------------------------------------------------
# Phase 2 — package builder (TODO)
# ---------------------------------------------------------------------------

def build_weekly_package(content_items: list[ContentSourceItem],
                         project_id: str = "EOM",
                         brand_voice_path: str = "templates/marketing/brand_voice.md") -> WeeklyPackage:
    """Given fresh content items, build a 4-surface package with
    war-room A-grade floor on each surface.

    Surface constraints:
      email       : 300-500 words
      linkedin    : ≤1300 chars
      x           : ≤280 chars (or ≤500 for X Premium variant)
      video_brief : 100-word hook + 5-scene beat sheet

    Each surface uses a surface-specific prompt routed through
    lib/llm_client.complete() with model selected via
    lib/model_router.resolve_model().

    TODO: implement Phase 2. Currently stubbed.
    """
    raise NotImplementedError(
        "build_weekly_package: Phase 2 package-builder not yet implemented. "
        "See plans/PLAN_2026-04-11_recurring-marketing-engine.md Phase 2 spec."
    )


# ---------------------------------------------------------------------------
# Phase 3 — video generator (TODO)
# ---------------------------------------------------------------------------

def generate_video_asset(video_brief: SurfacePackage,
                         source_video_url: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Produce a short-form video asset. Two paths:
      1. opus_clip_repurpose — if source_video_url provided
      2. heygen_avatar_generate — if no source video

    Returns (video_url, thumbnail_url). Returns (None, None) on
    degraded fallback (static image path).

    Requires env vars: OPUS_CLIP_API_KEY, HEYGEN_API_KEY.

    TODO: implement Phase 3. Currently stubbed.
    """
    raise NotImplementedError(
        "generate_video_asset: Phase 3 short-form-video-generation not yet "
        "implemented. Requires OPUS_CLIP_API_KEY + HEYGEN_API_KEY."
    )


# ---------------------------------------------------------------------------
# Phase 4 — Slack approval (TODO)
# ---------------------------------------------------------------------------

def request_approval(package: WeeklyPackage,
                     solon_user_id: str,
                     poll_timeout_s: int = 14400) -> WeeklyPackage:
    """Post the package to Solon's Slack DM, wait for reaction.

    Reactions:
      👍 = ship all
      🔄 = regenerate (max 2)
      ✋ = hold for manual edit

    Auto-✋ after poll_timeout_s (default 4 hours) with no reaction.

    TODO: implement Phase 4. Uses SLACK_BOT_TOKEN + chat.postMessage +
    reactions.get. Currently stubbed.
    """
    raise NotImplementedError(
        "request_approval: Phase 4 slack-approval-gate not yet implemented."
    )


# ---------------------------------------------------------------------------
# Phase 5 — scheduler (TODO)
# ---------------------------------------------------------------------------

def schedule_package(package: WeeklyPackage,
                     n8n_webhook_url: Optional[str] = None) -> dict:
    """POST the approved package to the n8n webhook that fans it out to
    LinkedIn Company / X API v2 / email provider / short-video surface.

    Returns a dict of {surface: (status, published_url)}.

    Requires:
      - n8n flow 'weekly_content_package' imported and active
      - LinkedIn Company OAuth with w_organization_social
      - X API v2 Basic tier bearer token
      - Email provider API (Google Workspace SMTP or Resend)

    TODO: implement Phase 5. Currently stubbed.
    """
    raise NotImplementedError(
        "schedule_package: Phase 5 multi-surface-scheduler not yet "
        "implemented. Requires LinkedIn/X/Email API keys + n8n flow."
    )


def is_enabled() -> bool:
    """True iff policy.yaml autopilot.marketing_engine_enabled is true."""
    import os
    return os.environ.get("POLICY_AUTOPILOT_MARKETING_ENGINE_ENABLED", "0") == "1"
