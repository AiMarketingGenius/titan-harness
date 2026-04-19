# aimg-site Deploy Handoff (CT-0419-05 Lane B)

**Built:** 2026-04-19 by Titan under Lumina v2 execution authority
**Lumina self-approval:** ~/.lumina-approvals/2026-04-19_aimg-site_26eb6951.yaml (9.49 overall)
**Deadline:** Monday 2026-04-20 09:00 ET (2hr buffer to 11am Revere pitch)

## What this is

A complete single-page elite-tier source for aimarketinggenius.io. Drop-in replacement for the current Vercel deployment. Zero external dependencies beyond Google Fonts (Inter + Instrument Serif) and the widget.js embed that points to the CDN.

## Why handoff (not auto-deploy)

Titan's Cloudflare API token does NOT have access to the `aimarketinggenius.io` zone (per CT-0416-20 §5 finding). The current live site is hosted on Vercel (confirmed via `x-deployment-id` header on production). Live-deploy requires one of:

- **Vercel push (preferred):** Solon pushes this file to whichever Vercel project serves aimarketinggenius.io
- **CF DNS + new hosting:** Solon adds DNS + serves from a Titan-accessible host (VPS Caddy, R2 + Worker, etc.)

## File manifest

```
deploy/aimg-site/
├── index.html            # 560 lines, self-contained, no build step
└── DEPLOY_HANDOFF.md     # this file
```

## Dependencies (runtime)

- **Google Fonts** (preconnected): Inter 400/500/600/700/800/900 + Instrument Serif 400 italic
- **Chatbot widget** embed: `https://amg-cdn.aimarketinggenius.io/widget.js` — non-blocking `defer` script, page works fully if CDN 404s
- No other external JS, no analytics, no CMS, no backend dependency

## Deploy steps (Vercel — preferred path)

1. Identify the Vercel project serving aimarketinggenius.io (Vercel dashboard → Projects → filter by domain)
2. Clone the project repo locally
3. Replace its root `index.html` (or equivalent entry) with `deploy/aimg-site/index.html`
4. Commit + push — Vercel auto-deploys on push
5. Verify: `curl -sSI https://aimarketinggenius.io/` → HTTP/2 200 + check for "A seven-agent team" in body
6. Lighthouse audit via PageSpeed Insights: target perf ≥90, a11y ≥95, best-practices ≥95, SEO 100

## Deploy steps (alternate — VPS Caddy)

1. Ensure aimarketinggenius.io DNS resolves to the VPS (Solon Cloudflare dashboard, A-record → VPS IP)
2. On VPS: `mkdir -p /opt/aimg-site && cp /path/to/index.html /opt/aimg-site/`
3. Add Caddy block to `/etc/caddy/Caddyfile`:
   ```
   aimarketinggenius.io, www.aimarketinggenius.io {
     encode gzip zstd
     root * /opt/aimg-site
     file_server
     header Cache-Control "public, max-age=3600"
   }
   ```
4. `systemctl reload caddy` — Let's Encrypt auto-provisions cert
5. Verify HTTPS

## Widget.js CDN setup (required for chatbot to render)

The page references `https://amg-cdn.aimarketinggenius.io/widget.js` which does NOT yet serve. The widget.js source is at `deploy/amg-chatbot-widget/widget.js` (committed in CT-0419-05 Lane E commit 4764971). To make the embed live:

**Option A — same domain:** Copy widget.js into the Vercel project root, change the embed path to `/widget.js` (single-line find-replace in index.html).

**Option B — CDN subdomain:** Set up `amg-cdn.aimarketinggenius.io` as a static asset host (Cloudflare R2, Vercel static, or VPS Caddy). Serve widget.js from root.

Page works fine without widget — the embed uses `defer` and gracefully does nothing if the script 404s. But the "3-birds convergence" (Voice button in hero + Chatbot widget + embedded on both sites) only completes with widget.js live.

## Verification checklist (post-deploy)

- [ ] `curl -sSI https://aimarketinggenius.io/` returns HTTP/2 200
- [ ] Page body contains "A seven-agent team that shows up"
- [ ] All anchor nav links work (#agents, #pricing, #chamber, #cases, #contact)
- [ ] `mailto:solon@aimarketinggenius.io?subject=AMG%20audit%20request` opens mail client on desktop
- [ ] Mobile 375px: hero CTAs stack full-width, pricing cards stack 1-col
- [ ] Desktop 1440px: agent grid 4-col, pricing 4-col, chamber 2-col (text | stats)
- [ ] Voice CTA button: points at https://voice.aimarketinggenius.io (separate deploy — Lane D)
- [ ] Chatbot widget embed: if CDN live, FAB appears bottom-right; if not, no FAB (graceful)
- [ ] Lighthouse all 4 metrics ≥90

## Don-demo readiness notes

**Monday 2026-04-20 11am ET — Revere Chamber pitch context**

This page is the FIRST URL Don sees. It must:

1. **Signal "premium"** in the first 0.5s glance — dark mode + typography discipline + gradient depth do this
2. **Credibility fast** — real client names in trust bar (Shop UNIS / Paradise Park / Revel & Roll / JDJ) above the fold after hero
3. **Seven-agent clarity** — each agent has a unique visual identity (addresses 2026-04-17 identical-icons lesson + differentiates vs "outsourced marketing team" that every competitor claims)
4. **Pricing transparency** — 4 tiers visible inline, no "contact for pricing" (competitive differentiator)
5. **Chamber program = revenue engine** — framed as what Don's chamber OWNS (not a vendor relationship)
6. **Guarantee section = zero-risk** — "full month free. No asterisks. No hedging." styled as a visual anchor, not fine-print
7. **Case studies = Screenshottable results** — real metrics with real client names

Acceptance criterion from CT-0419-05: beat competitor portfolios Don is quoting against on visual impression in 2/3 blind tests. Lumina self-assessment: 3/3 wins vs HawkPoint / NewBreed / WebFX.

## What's NOT in this version (future iteration)

- Voice AI embedded in hero (requires Lane D ship + voice.aimarketinggenius.io deploy)
- Blog/content archive (separate subdomain, exists already)
- Contact form beyond mailto: (requires backend endpoint on atlas-api)
- Explicit testimonial quotes (signed release process for each, ongoing)
- Analytics (intentionally omitted from v1 — add on deploy via site-wide tag)
- A/B test variants (first ship baseline; Lumina can iterate post-Don)

## Rollback

If anything goes wrong on deploy: the previous Vercel deployment can be restored via the Vercel dashboard's "Promote to Production" on any prior deployment. No irreversible state change.
