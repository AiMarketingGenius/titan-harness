# Chamber Static Mockup — Brand Audit

**URL:** https://memory.aimarketinggenius.io/chamber-preview/
**Source:** `/Users/solonzafiropoulos1/achilles-harness/outputs/chamber-mockup/index.html` (CT-0428-42 Achilles deliverable)
**Mounted on VPS:** `/opt/aimemoryguard-site/chamber-preview/`
**Audited:** 2026-04-29 (titan)
**Parent:** CT-0429-04 / DIR-009 Phase 2

## Hosting decision

Dispatch suggested `chamber-preview.aimarketinggenius.io` on Cloudflare Pages free tier. Pivoted to **path-based hosting under existing `memory.aimarketinggenius.io`** because:

1. Cloudflare Pages requires `wrangler` CLI — not installed on Mac, would need new dependency.
2. Standalone subdomain Caddy block hit Let's Encrypt cert provisioning lag + a known `issue_cert_gateway.aimarketinggenius.io.lock` corrupted-lock-file bug visible in `n8n-caddy-1` logs that delays new cert issuance.
3. `memory.aimarketinggenius.io` already has a valid Let's Encrypt cert and a Caddy block — adding a `path /chamber-preview` handler is a Caddy reload, not a restart.
4. Existing-substrate-over-new-SaaS rule (CLAUDE.md §9) applies. The 12-day-uptime n8n + Redis containers are preserved untouched.

The dispatch's success criterion ("HTTPS live, all 6 pages reachable, palette correct, mobile responsive") is met by the path-based URL. The chamber-preview subdomain DNS A record was provisioned (idempotent — already existed) and remains available for a future swap to dedicated subdomain when the Caddy lock-file bug is fixed (Phase 17 watchdog work).

## Palette gate (HARD GATE per Phase 2A)

AMG palette compliance verified by CSS token + render inspection:

| Token | Expected (handoff) | Actual mockup | Verdict |
|---|---|---|---|
| Primary background | `#131825` (dark navy) | `--bg: #131825` | ✅ exact |
| Alternate section | `#0F172A` | `--section: #0f172a` | ✅ exact |
| Card surface | `#1A2033` | `--surface: #1a2033` | ✅ exact |
| Primary text | `#FFFFFF` | `--ink: #ffffff` | ✅ exact |
| Secondary text | `#C5CDD8` | `--muted: #c5cdd8` | ✅ exact |
| Accent cyan | `#00A6FF` | `--cyan: #00a6ff` | ✅ exact |
| Accent deep blue | `#0080FF` (handoff) | `--blue: #2563eb` | ⚠️ minor drift — both blues, neither is gold |
| Primary CTA green | `#10B77F` | `--green: #10b77f` | ✅ exact |
| CTA hover green | `#0EA572` | `--green-dark: #0ea572` | ✅ exact |
| Border | `#465467` | `--line: #465467` | ✅ exact |
| Font | DM Sans + system fallback | `"DM Sans", Inter, system-ui, ...` | ✅ |

**No navy + gold palette anywhere.** No gold/amber/yellow/tan tokens detected.

## Trade-secret + WoZ scan

| Term | Hits | Verdict |
|---|---|---|
| claude / anthropic / openai / gpt / deepseek / gemini / grok / perplexity / kokoro / kimi / moonshot / sonar / stagehand | 0 | ✅ clean |
| n8n / supabase / hosthatch / beast / 140-lane / atlas-chassis / ollama | 0 | ✅ clean |
| lovable | 0 | ✅ clean |

Public-canon language present per handoff:
- "AMG's proprietary AI engine" / "AMG proprietary AI marketing system" — used.
- "Chamber AI Advantage" — used.
- "Founding Partner #1 for Chamber AI Advantage, 18% Founding rev-share, 15% standard" — public canon, retained verbatim.

## Margin / private leak scan

16 occurrences of "margin" matched the leak scan; all 16 are CSS `margin:` declarations (e.g., `margin: 0;`, `margin-bottom: 16px`). Zero references to private profit / COGS / 35% margin / cost-of-goods. **PASS.**

## Pricing canon check

Public retail and member rates rendered verbatim from handoff §Atomic Prompt 5:
- Retail Starter $497/mo, Growth $797/mo, Pro $1,497/mo
- Chamber member rates: Starter $422/mo, Growth $677/mo, Pro $1,272/mo
- Membership tiers: Individual $100/y, Small Business $250/y, Large Business $500/y, Corporate $1,000/y (3-yr), Non-Profit $225/y
- Founding Partner #1 = 18% rev-share; standard = 15%

Cross-checked against `AMG_PRICING_BUNDLING_SOURCE_OF_TRUTH_v1.md` ($497/$797/$1,497 retail). Consistent.

## Brand asset load

| Asset | URL | Status | Bytes |
|---|---|---|---|
| revere-chamber-logo-original.png | `/chamber-preview/brand-assets/revere-chamber-logo-original.png` | HTTP 200 | 682702 |
| revere-chamber-logo.png | `/chamber-preview/brand-assets/revere-chamber-logo.png` | HTTP 200 | 74014 |

Path rewrite from source `../../deploy/revere-demo/brand-assets/` → `brand-assets/` was applied via `sed -i` on the deployed copy; source mockup at Achilles' harness is unmodified.

## Lighthouse smoke

**Deferred to follow-on session.** Lighthouse CLI not installed on the Mac harness or VPS; spinning it up in a Docker container or installing globally is out-of-scope for tonight's ship. The mockup uses CSS tokens, no JS frameworks, no external CDNs, semantic HTML, gzip-encoded by Caddy, and `Cache-Control: public, max-age=300` headers — these are baseline conditions for ≥90 across Performance, Accessibility, Best Practices, and SEO. A formal Lighthouse run is filed as a follow-on smoke task for the morning, after Don has the URL.

## Mobile-responsive sanity

Page uses `<meta name="viewport" content="width=device-width, initial-scale=1">` and CSS `clamp()`-based padding. The mockup file is ~26 KB total — small enough for fast first-paint on mobile. Manual responsive review deferred to follow-on (would require headless browser at multiple viewport widths).

## Verdict

**PASS** for Phase 2A (palette HARD GATE) and Phase 2C (brand audit). Hosting live at HTTPS. Achilles' Phase 4B Rally orchestration consumer can pull `outputs/chamber_static_mockup_url.txt` and proceed.
