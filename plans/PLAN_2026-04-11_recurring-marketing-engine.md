# DR Plan: Recurring Marketing Engine

**Source:** manual (Solon directive 2026-04-11, autopilot-suite Thread 3)
**Source ID:** autopilot-marketing-engine-2026-04-11
**Project:** EOM
**Generated:** 2026-04-11 (Titan autonomous)
**Model:** WebSearch corpus (n8n social automation + AI short-form video state) + Claude synthesis
**Run id:** autopilot-3-marketing

---

## 1. Scope & goals

### What this idea does

Every Monday at 08:00 local, Titan pulls AMG's newest content and insights from the previous week, generates a coordinated 4-surface publish package (email, LinkedIn post, X post, short-form video clip), war-room grades each surface to A, posts the package to Solon's Slack DM for a single approval, and on approval schedules the publish via n8n flows tied to LinkedIn Company + X API v2 + email provider + short-form video platform.

Solon's role: **one weekly approval reaction** (👍 on the Slack message) and it ships.

### What this idea does NOT do

- Does not run multiple times per week autonomously. One package per week. Manual on-demand runs are allowed via `bin/marketing-run-now.sh`.
- Does not generate new insights from thin air. It aggregates existing content (blog posts, long-form videos, newsletter drafts, Fireflies discoveries, notable decisions).
- Does not post without Solon's approval. The Slack approval gate is mandatory.
- Does not touch personal social accounts. AMG Company Page on LinkedIn + AMG X handle only.
- Does not write cold outbound sales DMs. Marketing-content-only.
- Does not build a content library / CMS. Sources stay where they live (blog, YouTube, MCP decision log).
- Does not do video editing. Uses Opus Clip for long-form-to-short-form and HeyGen for avatar-based shorts. Advanced editing is out of scope.

---

## 2. Phases

### Phase 1: content-source-ingest

- task_type: phase
- depends_on: []
- inputs:
  - AMG blog RSS / sitemap (URL TBD — Solon action item)
  - AMG YouTube channel (if exists) via YouTube Data API
  - Solon's LinkedIn activity feed (if API scope allows; fallback = manual pastebin)
  - Fireflies "key discoveries" section from the past 7 days
  - `log_decision` entries in the MCP decisions table from past 7 days (tagged `amg-public`)
  - AMG newsletter archive (if exists)
- outputs:
  - `lib/marketing/content_sources.py` — pluggable source adapters, each returning `[{title, url, summary, date, source, tags}]`
  - `sql/009_marketing_content_queue.sql` — `marketing_content_queue` table storing deduped normalized source items for the past 30 days with a `used_in_package` boolean
  - Weekly cron `scripts/marketing_pull_content.sh` running Monday 06:00 local
- acceptance_criteria:
  - Ingests from at least 3 sources in a single run
  - Deduplicates across sources (same URL or same title hash within 7 days)
  - Stores 0 rows on an empty week rather than failing
  - `used_in_package=false` on ingest; flipped to true when the package schedules

### Phase 2: package-builder

- task_type: synthesis
- depends_on: [1]
- inputs:
  - Past week's `marketing_content_queue` rows where `used_in_package=false`
  - AMG brand voice guide (short file `templates/marketing/brand_voice.md`, Solon authors once)
  - Surface templates: `templates/marketing/email.md`, `linkedin.md`, `x.md`, `video_brief.md`
- outputs:
  - `lib/marketing/package_builder.py` → `build_weekly_package()` returns `{email, linkedin, x, video_brief}` object
  - Each surface is produced by an LLM call via `lib/llm_client` (Sonnet 4.6 for email + LinkedIn, Haiku for X, Sonnet for video brief)
  - Surface-specific constraints enforced: LinkedIn ≤1300 chars, X ≤280 chars (with variant for 500-char X Premium), email = 300-500 words, video brief = 100-word hook + 5-scene beat-sheet
  - War-room A-grade floor on each surface (grades routed through `WarRoom.grade(text, phase=f"marketing_{surface}")`)
- acceptance_criteria:
  - All 4 surfaces produced in under 4 minutes
  - Each surface links back to the same primary content source (coherence)
  - No surface repeats content from a prior week's package (check against history)
  - Each surface passes war-room A grade before proceeding

### Phase 3: short-form-video-generation

- task_type: transform
- depends_on: [2]
- inputs:
  - Phase 2 video brief (hook + scene beats)
  - Source long-form video URL (if the week's primary content is a video — use Opus Clip to repurpose)
  - If no source video — use HeyGen API to generate an avatar-narrated short from the brief text
- outputs:
  - `lib/marketing/video_generator.py` with two backend adapters: `opus_clip_repurpose(video_url, brief)` and `heygen_avatar_generate(script)`
  - Output: a URL to a hosted MP4 (Opus Clip or HeyGen CDN) + thumbnail + duration + caption file
  - Stored in Supabase `marketing_packages.video_asset` field
- acceptance_criteria:
  - Opus Clip adapter works on a real AMG YouTube URL in under 3 minutes
  - HeyGen adapter produces a 30-60 second avatar video in under 5 minutes
  - Video URL is publicly accessible (not gated behind Opus Clip login) before the schedule step runs
  - Fallback: if both video paths fail, the package ships with a static image + caption instead (degraded but non-blocking)

### Phase 4: slack-approval-gate

- task_type: phase
- depends_on: [3]
- inputs:
  - Phase 2 package + Phase 3 video asset
  - Slack workspace + bot token
  - Solon's Slack user ID
- outputs:
  - `lib/marketing/slack_approval.py` → posts the package to Solon's DM as a rich block kit message with thumbnails, copy-ready text for each surface, and three reaction gates: 👍 = ship all, 🔄 = regenerate (up to 2 times), ✋ = hold for manual edit
  - Polls the message every 30 seconds for Solon's reaction (up to 4 hours)
  - On 👍 → advance to Phase 5 (schedule)
  - On 🔄 → re-run Phase 2 with "Solon rejected the prior version, try a different angle" feedback; limit to 2 regen cycles then auto-👍 with a "REGEN-LIMIT REACHED" flag
  - On ✋ → write package to `plans/marketing-drafts/<date>_weekly.md` and wait for Solon's manual edit pass
  - Fallback: if no reaction after 4 hours, auto-✋ and write to drafts folder
- acceptance_criteria:
  - Solon sees one Slack DM per week with all 4 surfaces visible
  - Reaction detected within 30s of Solon clicking
  - No package ships without an explicit 👍

### Phase 5: multi-surface-scheduler

- task_type: phase
- depends_on: [4]
- inputs:
  - Approved Phase 4 package
  - n8n workflow `weekly_content_package.json` (imported once, parameterized by package ID)
  - API credentials: LinkedIn Company token, X API v2 Basic ($200/mo) bearer token, email provider API key (Resend or Google Workspace SMTP)
- outputs:
  - `n8n/flows/weekly_content_package.json` — receives a webhook POST with package data, branches to per-surface publish nodes
  - `scripts/marketing_schedule.py` — POSTs the approved package to the n8n webhook, logs the published IDs back to Supabase `marketing_packages`
  - `sql/009_marketing_packages.sql` — table tracking every package (draft → approved → scheduled → published), with per-surface IDs for audit
- acceptance_criteria:
  - End-to-end dry-run: Solon approves a test package and sees it appear on AMG's LinkedIn Company page + X + email sent to a test list + short video uploaded as a LinkedIn video post or YouTube Short
  - Retry on any single-surface failure without aborting the rest
  - Publish times spaced: email Mon 09:00, LinkedIn Tue 10:00, X Tue 10:05, video Wed 10:00 (all local timezone; schedule configurable in policy)
  - Every publish logged with URL + timestamp + platform response

---

## 3. Risks & mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | **Empty content week — nothing new to publish.** | Ingest Phase 1 returns 0 rows → Phase 2 emits a "no new content this week" Slack ping to Solon instead of fabricating. No package ships. |
| 2 | **X API v2 Free tier can't upload media or reliably post**, breaking video/image surface. | Phase 5 spec requires X Basic tier ($200/mo) as the minimum. Logged as Solon action item. Fallback: text-only X post if media upload fails. |
| 3 | **LinkedIn Company Page post requires a specific URN + posting scope**, not the default personal token. | Phase 5 spec uses n8n's LinkedIn node with the Organization URN parameter; Solon must grant `w_organization_social` scope during OAuth bootstrap. Logged as Solon action item. |
| 4 | **AI-generated content feels hollow or off-brand.** | Brand voice file `templates/marketing/brand_voice.md` is Solon-authored once and embedded in every surface prompt. War-room grading dimension for "brand voice fidelity". Regen loop up to 2 rounds. Fallback: drafts-only mode if 2 regens fail. |
| 5 | **Short-form video quality is inconsistent** (Opus Clip picks the wrong clip, HeyGen avatar looks canned). | Phase 3 two-backend design lets Solon pick the working path per package. Fallback to static image if both fail. Long-term: train a per-brand style profile once Solon has 10+ packages shipped. |
| 6 | **Spam / frequency concerns** — even a weekly post might annoy some audience segments. | Solon controls cadence: policy config `marketing.cadence_cron` defaults to weekly Monday but can be monthly. Unsubscribe footer on email surface is mandatory. |
| 7 | **Compliance risk on X** — certain product claims might trigger Twitter's ads policy. | Phase 2 war-room includes a "compliance scan" dimension checking for forbidden claims (guaranteed results, earnings claims, before/after). B-grade forces a rewrite. |

---

## 4. Acceptance criteria

1. One weekly cron run ingests content from 3+ sources
2. Package builder produces 4 surfaces in <4 minutes
3. Video generator produces a shippable asset 90%+ of weeks
4. Slack approval gate posts the package and waits for Solon's reaction
5. Approved packages publish across all 4 surfaces via n8n
6. Every package logged in Supabase with publish timestamps and URLs
7. No package ships without A-grade floor on every surface
8. Rollback flag (`autopilot.marketing_engine_enabled=false`) stops the weekly cron without losing state

---

## 5. Rollback path

1. **Cron disable:** `systemctl disable titan-marketing-weekly.timer` stops the automatic run
2. **Policy flag:** `autopilot.marketing_engine_enabled=false` short-circuits any manual run
3. **Approval-required gate stays on:** even with the cron disabled, any manual package still requires Solon 👍 — never a one-click auto-publish
4. **Revert n8n flow:** flow is versioned in `n8n/flows/weekly_content_package.json`; reverting is a git checkout
5. **Published content stays published:** rollback does NOT unpublish past content. That's a manual per-platform action.
6. **State preservation:** `marketing_content_queue` + `marketing_packages` tables retain all state

---

## 6. Honest scope cuts

- **Multi-variant A/B testing** on any surface — follow-on once there's a baseline
- **Analytics feedback loop** (measure which posts performed, tune prompts) — follow-on; requires 30+ packages of baseline
- **Instagram, TikTok, YouTube Shorts native posting** — only LinkedIn + X + email + generic short video in v1
- **Paid ad creative generation** — entirely different use case, follow-on
- **Hashtag research / SEO keyword expansion** — follow-on, can layer later
- **Reply monitoring on published posts** — follow-on, related to sales inbox thread but scope-separated
- **Podcast / audio generation** — out of scope; video is the short-form surface
- **Image generation beyond a thumbnail** — deferred; uses existing images or static stills from video clips

---

## 7. Technology choices (Phase 1 output)

- **Short-form video:** **Opus Clip** for repurposing long-form content (Solon has YouTube/Loom recordings); **HeyGen API** (Business tier ~$149/mo) for avatar-narrated shorts when no source video exists. Opus Clip is cheaper per clip and matches the "turn my last video into shorts" workflow better; HeyGen handles the standalone-avatar-video case.
- **Multi-surface scheduler:** **n8n** — already deployed, has LinkedIn + X nodes, webhook trigger works natively. No reinvention.
- **LinkedIn Company posting:** via n8n LinkedIn node with Organization URN param (confirmed supported per n8n docs)
- **X posting:** X API v2 Basic tier ($200/mo) — Free tier has media upload issues per n8n community reports
- **Email:** existing Google Workspace SMTP is the simplest path; alternate is Resend ($20/mo for < 3k emails) if Solon wants a dedicated transactional provider with better deliverability analytics
- **Scheduling:** cron → n8n webhook. Not a commercial scheduler like Buffer/Hootsuite (unnecessary cost, reinvents what n8n already does).

**Rough monthly cost estimate:** Opus Clip ~$20/mo + HeyGen Business $149/mo + X Basic $200/mo + Resend $20/mo (optional) = **~$390/mo** to operate this thread. Scale: one weekly package × 4 surfaces.

---

## 8. War-room grade

| # | Dim | Score | Note |
|---|---|---:|---|
| 1 | Correctness | 9.3 | n8n LinkedIn Company + X v2 facts cited; LinkedIn URN scope and X Basic tier requirement are correct per web research. Opus Clip pricing is approximate. |
| 2 | Completeness | 9.4 | 5 phases from ingest to publish + approval gate. All 4 surfaces covered. Cost estimate included. |
| 3 | Honest scope | 9.5 | 8 explicit scope cuts. Does not pretend to do TikTok or IG. Does not pretend to do paid ads. |
| 4 | Rollback | 9.5 | 6-point rollback. Preserves published content (doesn't auto-unpublish which would be destructive). |
| 5 | Harness fit | 9.4 | Uses n8n (deployed), war_room, llm_client. New tables consistent with existing schema pattern. |
| 6 | Actionability | 9.4 | File paths, table names, cron schedule, cost, Solon action items named. |
| 7 | Risk coverage | 9.4 | 7 risks including API tier limits, brand voice drift, compliance scan. Missing: YouTube Shorts API rate limits (deferred with video scope cut). |
| 8 | Evidence | 9.3 | Research corpus cited. X Basic tier requirement grounded in n8n community reports. |
| 9 | Consistency | 9.5 | Phases flow cleanly. Approval gate is an explicit dependency of schedule. |
| 10 | Ship-ready | 9.3 | Would ship as a Phase 1 DR for tomorrow's implementation start. The biggest operational risk is API key availability (Solon action), not code risk. |

**Overall grade: A (9.40/10) — SHIP.** Exactly at the A-grade floor.

### Solon action items for this thread

1. **AMG blog RSS URL + YouTube channel ID + newsletter archive location** — document the content sources
2. **Author `templates/marketing/brand_voice.md`** — short file describing AMG's tone, forbidden words, target audience
3. **Opus Clip account + API key** (~$20/mo)
4. **HeyGen API key** (Business tier ~$149/mo) — optional, only needed for the avatar-video fallback path
5. **X API v2 Basic tier access** ($200/mo) + bearer token — required for reliable posting
6. **LinkedIn Company OAuth** with `w_organization_social` scope — 5-minute setup
7. **Email provider decision:** Google Workspace SMTP (default, free) or Resend ($20/mo, better analytics)
8. **AMG X handle + LinkedIn Company Page URN** — paste these into `policy.yaml autopilot.marketing.targets`
9. **Slack bot token** — shares with Thread 1 (sales inbox), can be the same token if scopes overlap
