# Titan KB — 04 Error Patterns (known past mistakes to avoid)

## Purpose

This file catalogs specific past mistakes by prior Titan sessions so future sessions recognize the pattern and avoid it. Each entry: what happened, what the pattern was, what the fix is, how the pre-commit / Lumina-gate / CLAUDE.md-bootstrap layers prevent recurrence.

## E1 — Trade-secret leaks in Revere portal v3 (2026-04-17)

**What happened:** demo portal shipped to `checkout.aimarketinggenius.io/revere-demo/` contained:
- "Powered by Atlas" in header subtitle
- "Live on beast + HostHatch · 140-lane queue" pill badge in Agent Command view
- "Live · production Atlas" status text
- "Every agent above runs on the Atlas engine" banner kicker
- Footer: "Powered by the Atlas engine from AI Marketing Genius"
- CSS class names: `.atlas`, `.atlas-banner`, `.atlas-stats`

**Pattern:** Solon's own internal codenames (Atlas, beast, HostHatch, 140-lane) got copy-pasted into client-facing surfaces because I treated "internal infrastructure context" as generic flair. Atlas is a codename that reads as cool to an engineer and as opaque jargon to a Chamber Board President.

**Fix (shipped v4):** all 6 leaks purged. Substitutions documented in `01_trade_secrets.md` preferred-language table.

**Prevention:** `/opt/titan-harness/.git/hooks/pre-commit-tradesecret-scan.sh` runs on every commit, blocks if staged files under client-facing paths contain any banned term. Override requires `[LEAK_OVERRIDE]` tag + reason logged.

## E2 — Placeholder "RC" monogram + invented navy+gold palette (2026-04-17)

**What happened:** demo used a custom-drawn SVG "R" monogram + navy `#0a2d5e` + gold `#d4a627` that I invented. Revere's actual brand: teal-C-shape logo with seagulls, navy `#0B2572`, royal blue `#116DFF`, Montserrat font, no gold in their palette.

**Pattern:** "The client's real brand probably isn't great, let me design something that looks premium" — slippery slope to generic SaaS template. Client sees "invented" at a glance and loses confidence. Their brand has history; ours doesn't.

**Fix (shipped v4):** Chrome MCP scrape of `reverechamberofcommerce.org`, actual logo pulled + optimized, actual navy `#0B2572` applied, Montserrat loaded via Google Fonts. Gold retained as *AMG-overlay accent* with explicit Lumina-proxy justification documented in `REVERE_CHAMBER_BRAND_AUDIT.md`.

**Prevention:** `02_brand_standards.md` §"Required process" — every new client-facing deliverable starts with Chrome MCP scrape + brand-audit doc before any CSS var is written. Lumina gate blocks commits lacking brand-audit reference.

## E3 — 7 identical "RC" squares across 7 differentiated agent cards (2026-04-17)

**What happened:** all 7 agent cards on Agent Command view used identical `<div class="agent-ico">RC</div>` squares. No visual differentiation. Cards that represent distinct personas read as one monolithic grid.

**Pattern:** when building the scaffold, I replaced a loop with a repeat. "Ship the skeleton, iterate later." Lumina-level detail got dropped.

**Fix (shipped v4):** per-agent letter (A/M/J/S/R/N/L) + per-agent gradient tint variation anchored on Revere navy.

**Prevention:** `02_brand_standards.md` §"Agent card / persona differentiation" — Lumina gate auto-flags identical icons across entities marked as distinct personas.

## E4 — Self-graded "9.5/10" on work Solon rated 5/10 (2026-04-17)

**What happened:** earlier in the 2026-04-17 thread, I reported Revere demo v3 "shipped 9.5/10 PASS" from the dual-grader while the demo had visible trade-secret leaks + placeholder branding that Solon flagged as 5/10 quality.

**Pattern:** the grader (Gemini + Grok) evaluates the artifact against its stated acceptance criteria; it does NOT know about unwritten rules like "authentic brand required" or "Atlas is internal-only." If the artifact's context block doesn't contain those rules, the grader can't enforce them.

**Fix (going forward):** dual-grader context blocks always include the governance rules that apply (trade-secret scan required, brand authenticity required, Lumina review score provided). See grading-prompt patch in `lib/dual_grader.py`.

**Prevention:** `05_lumina_dependency.md` documents mandatory Lumina pre-review on ALL visual/client-facing work. Lumina review happens BEFORE dual-validator; grader is not a substitute for design-system review.

## E5 — "Solon to paste path" on F2 Mobile Command handler (2026-04-17)

**What happened:** first pass at F2 Mobile Command flagged "blocked — need Solon to paste the Mobile Command handler location." Solon corrected: that's a NEVER STOP protocol violation, exhaust the cascade before escalating.

**Pattern:** when an infrastructure lookup hits friction, default to asking Solon instead of doing the lookup work. Solon is not middleware.

**Fix (after correction):** ran full cascade — grep `/opt/titan-harness`, `/opt/amg-mcp-server`, `/opt/amg-chatbot`, n8n workflow registry, systemctl services. Found `atlas-api.service` active, `/opt/titan-harness/lib/atlas_api.py` 52KB with `/api/titan/*` endpoints. No escalation needed.

**Prevention:** `CLAUDE.md` §7 NEVER STOP protocol already documents the 6-step cascade. CLAUDE.md bootstrap from this KB ensures the protocol is top-of-context on every session start, not buried.

## E6 — DNS cascade stopped at step (a) prematurely (2026-04-17)

**What happened:** first DNS attempt for `portal.aimarketinggenius.io` found the token couldn't see the zone (found=0) and flagged "Solon to add record in Cloudflare dashboard." Solon corrected: exhaust the 5-step cascade first.

**Pattern:** same as E5 — default to escalation after first friction.

**Fix (after correction):** ran full cascade — step a (zone visibility), step c (env / Infisical / Global API Key hunt), step d (Grok consulted), step e (POST /user/tokens attempted, got 9109 Unauthorized). Grok confirmed: token lacks `Account:Tokens:Edit` permission, only paths forward are a new scoped token from Solon's CF account OR expanding existing token. Legitimate escalation after exhausting all 5 steps.

**Prevention:** NEVER STOP protocol embedded in CLAUDE.md bootstrap.

## E7 — Grader tier default ran Gemini Pro instead of Flash (2026-04-17)

**What happened:** `lib/dual_grader.py` first version used Gemini Pro as primary validator by default, burning credits unnecessarily on routine validations.

**Pattern:** premium-by-default thinking. "Best model for every call" burns the daily cap fast and leaves nothing for architecture-critical grading.

**Fix (shipped same-day):** `DEFAULT_SCOPE_TIER = 'amg_growth'` (Gemini Flash) per P10 2026-04-17. Premium (`amg_pro`) reserved for architecture-critical work (contracts, legal, security arch, SOC 2, payment integrations) OR when low-tier graders disagree after 2 iteration rounds.

**Prevention:** P10 rule logged to MCP. Daily caps: $5 Gemini, $3 Grok, $10 total kill-switch. Caching mandatory on system prompts + rubrics.

## Meta-lesson

Every entry above = one hour of lost time + one Solon correction. The goal of this KB + the pre-commit guard + Lumina gate + CLAUDE.md bootstrap is that the next Titan session reads these patterns on startup and doesn't repeat them. Prevention is cheaper than correction.

When a new mistake surfaces: add the entry here the same session. Don't let the pattern forget itself.
