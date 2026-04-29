# Chamber — Lovable Post-Signature Handoff

**Status:** Plan only. Do NOT execute tonight (capital-discipline pivot 2026-04-29).
**Trigger:** Don signs the Founding-Partner engagement OR Solon issues `lovable_chamber_provision_approved` tag in MCP.
**Authored:** 2026-04-29 (titan, DIR-009 Phase 2D)
**Parent:** CT-0429-04 / CT-0428-44

## Why this plan exists

The original CT-0428-44 path was Lovable provisioning of the 6-page Chamber mockup. Solon's 2026-04-29 directive deferred Lovable spend until Don signs — Lovable credits cost 6-18 per page (estimated ~36-108 credits total) and shouldn't burn before commitment. Tonight's Phase 2 ship hosts the existing static mockup ([CHAMBER_STATIC_MOCKUP_BRAND_AUDIT.md](CHAMBER_STATIC_MOCKUP_BRAND_AUDIT.md)) for Don's Wed-EOD review at $0 cost. This file is the runbook for the post-signature build.

## Trigger conditions (any one)

1. Don's countersigned Founding-Partner engagement letter logged via `log_decision` tag `chamber_engagement_signed` with PDF link.
2. Solon manually green-lights via `log_decision` tag `lovable_chamber_provision_approved` (text-only, no signature required).
3. Achilles' Rally orchestrator (Phase 4) signals `chamber_lovable_build_authorized`.

Whichever lands first kicks off this runbook. Until one of the above lands, the static mockup at https://memory.aimarketinggenius.io/chamber-preview/ remains the reviewable surface.

## Lovable provisioning sequence

Atomic prompts only — one Lovable prompt per page per memory rule. The prompts are already drafted in the Achilles handoff (`/Users/solonzafiropoulos1/achilles-harness/outputs/CT-0428-42_LOVABLE_BUILD_HANDOFF_v1.md`).

| # | Page | Lovable prompt source | Estimated credits |
|---|---|---|---|
| 1 | Home | Atomic Prompt 1 of handoff | 6 |
| 2 | About | Atomic Prompt 2 | 3-6 |
| 3 | Events | Atomic Prompt 3 | 3-6 |
| 4 | Business Directory | Atomic Prompt 4 | 6 |
| 5 | Member Benefits | Atomic Prompt 5 | 6 |
| 6 | Contact | Atomic Prompt 6 | 3 |

Total estimated: 27-36 credits (lower bound 6×3, upper 6×6). Allocate 50-credit budget cap for safety.

Constraints repeated from handoff:
- AMG palette only (`#131825` background, `#10B77F` CTA green, `#00A6FF` accent — no navy+gold).
- Public-canon pricing only ($497 / $797 / $1,497 retail, $422 / $677 / $1,272 member, 18% Founding / 15% standard rev-share).
- No vendor / model / tool names client-facing.
- Real Revere Chamber logo at `deploy/revere-demo/brand-assets/revere-chamber-logo-original.png`.
- Mobile responsive, no overlapping text.
- DM Sans font (not Montserrat).

Send Lovable prompts ONE AT A TIME. Wait for each page to render + accept before sending the next. Per Lovable atomic-prompt memory rule, batched prompts cause cross-contamination.

## DNS swap (after Lovable URL acquired)

Once the Lovable build is live and Solon approves the visual review:

1. Lovable returns a `*.lovable.app` URL — capture it via `log_decision` tag `chamber_lovable_url_acquired` with the URL in the text.
2. Add CNAME record: `chamber-preview.aimarketinggenius.io` → `*.lovable.app` (or whatever Lovable's custom domain instructions specify). Use `CLOUDFLARE_API_TOKEN_AMG` token + zone `aac0e6e47362ded88bf88304dfaa9d10`.
3. Configure Lovable custom domain `chamber-preview.aimarketinggenius.io` per Lovable's instructions. Verify HTTPS issuance.
4. Lovable URL replaces the static path-based URL for Don's review — update Achilles' Rally orchestration packet accordingly.
5. KEEP the static path under `memory.aimarketinggenius.io/chamber-preview/` live for 14 days post-cutover as a fallback if Lovable rendering glitches.
6. After 14 days clean, remove the Caddy `@chamber` path handler to retire the fallback.

## Production-hosting after engagement closes

For the actual chamberaiadvantage.org production site (post-Don signature, post-MSA, post-Founding-Partner kickoff):
- Provision Lovable production project (separate from preview) tied to `chamberaiadvantage.org`.
- DNS for `chamberaiadvantage.org` zone is managed at Squarespace per Solon's records — needs explicit Solon click to update nameservers OR add CNAME record (biometric-MFA territory, Hard Limit #5 if new credentials needed).
- Lighthouse smoke ≥90 on Performance + Accessibility + Best Practices + SEO before announce.
- Two-judge gate (Phase 12 Sonar-Pro-Mirror + Lumina) before public-facing launch.

## Cost cap + abort conditions

- Hard cap: 50 Lovable credits. If consumption hits 40, halt + flag_blocker before continuing.
- Abort if any rendered page leaks vendor/tool names — scrub Lovable prompt + restart on that page.
- Abort if palette regression (any gold tokens) — flag + revise atomic prompt.
- Abort if Lovable starts trying to push to GitHub from inside the build — explicit Lovable rule violation.

## Cross-coordination

- Achilles Phase 4B Rally orchestrator: HARD WAIT on `chamber_lovable_build_authorized` tag. Until that tag fires, Rally consumes the static mockup URL.
- Achilles' delivery packet (Phase 4D) gets updated with the Lovable URL once swap is complete.
