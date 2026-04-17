# Titan-CRO — KB 06 Trade Secrets

## Rule

Every file Titan-CRO writes to a client-facing path (deploy/, portal/, site/, marketing/, revere-*, chamber-*) is scanned by `hooks/pre-commit-tradesecret-scan.sh` and gated by `hooks/pre-commit-lumina-gate.sh`. Full list: `plans/agents/kb/titan/01_trade_secrets.md`.

## Banned in Titan-CRO client-facing output

- **AI vendors:** Claude, Anthropic, ChatGPT, GPT-*, OpenAI, Gemini, Grok, Perplexity
- **Underlying services:** ElevenLabs, Ollama, nomic-embed-text, Kokoro
- **Infrastructure:** beast, HostHatch, 140-lane, n8n, Stagehand, Supabase
- **VPS IPs:** 170.205.37.148, 87.99.149.253
- **Infrastructure in CSS class names** — `.atlas-banner` is a BORDERLINE case: "atlas" is AMG brand-allowed but "atlas" as a class name leaked via class="atlas" visible in DevTools. After 2026-04-17 learning: prefer `.brand-accent` / `.amg-banner` over `.atlas-*` in CSS to keep devtools-clean.

## Allowed in Titan-CRO client-facing output

- **Atlas** — AMG platform brand (in text/copy/alt-text — but avoid as CSS class name prefix)
- **AMG / AI Marketing Genius** — company brand
- **Agent names:** Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina
- **Web-standard tech** (in code + developer-facing): HTML5 semantic tags, ARIA attributes, CSS custom properties, WebGL, Canvas, IntersectionObserver, MutationObserver — these are platform standards
- **Google Analytics 4 / GTM / Meta Pixel** in tracking code (required for analytics)
- **Google Fonts / Adobe Fonts** in `<link>` tags (subscribers expect these)

## Titan-CRO-specific substitutions

| Never write | Write instead |
|---|---|
| `<meta name="generator" content="Claude"...>` | `<meta name="generator" content="AMG Atlas"...>` or omit |
| `/* Powered by GPT-4 */` (code comment) | `/* Atlas */` or delete the comment |
| `<!-- Supabase stored this -->` (HTML comment) | delete or `<!-- AMG data layer -->` |
| `data-ai-model="claude-sonnet"` | `data-ai-platform="atlas"` or remove the attribute entirely |
| Class names like `.claude-response`, `.gpt-output` | `.agent-response`, `.atlas-output` |
| Debug strings like `console.log("Calling Claude API")` | `console.log("Calling Atlas")` or remove for production |

## CSS class naming — post-2026-04-17 convention

Avoid class names that leak AMG's platform architecture:

- ❌ `.atlas-banner`, `.atlas-stats` (exposed "atlas" to DevTools)
- ✅ `.amg-banner`, `.amg-stats`, `.brand-accent`, `.callout-primary`

The 2026-04-17 Revere v3 failure included `.atlas-banner` — not a scanner-triggering leak per se (Atlas is brand-allowed), but bad hygiene because any inspector sees the class names. Prefer semantic (what the element IS) over platform (what system it belongs to).

## Code comments + dev-facing strings

Comments in HTML/CSS/JS files are visible in view-source. Trade-secret discipline applies:

- ❌ `// Stagehand scrapes this` in deployed JS
- ❌ `<!-- n8n webhook endpoint below -->` in deployed HTML
- ❌ `/* beast-VPS-specific override */` in deployed CSS
- ✅ Delete the comment OR rewrite: `/* production infrastructure override */`

Rule: client-facing files that ship to end-user browsers have ZERO debug leaks, ZERO internal codenames.

## Dev-environment vs production-build

- **Dev build** (local, never deployed): comments + debug strings + console.log fine for engineer productivity
- **Production build**: minifier strips comments; console.log calls either removed OR sanitized before deploy. Source maps should NOT deploy to client-facing paths if they contain internal codenames.

## Asset filename conventions

- ✅ `brand-assets/revere-chamber-logo.png` — descriptive, client-facing fine
- ✅ `brand-assets/revere-chamber-logo-original.png` — the brand-audit archive (exempt from scan via `EXEMPT_PATH_RE`)
- ❌ `brand-assets/claude-generated-logo.png` — trade-secret leak in filename
- ❌ `brand-assets/gpt-4-mockup.svg` — trade-secret leak in filename

## When integrating third-party libraries

Some libraries put their brand in output:
- **Google Fonts** loads from `fonts.googleapis.com` — visible in Network tab. This is fine; it's industry-standard + expected.
- **ElevenLabs SDK** if loaded client-side would show in Network as `api.elevenlabs.io` — AVOID loading client-side. Always proxy through AMG endpoint so subscriber's browser sees `atlas.aimarketinggenius.io/tts` not `api.elevenlabs.io`.
- **Anthropic/OpenAI SDK** client-side — NEVER. Always server-side behind AMG endpoint.

## Self-check before Titan-CRO commits

1. Scan production bundle for banned terms (auto via pre-commit)
2. Check CSS class names for platform leakage (`.atlas-*`, `.claude-*`, `.gpt-*`)
3. Check HTML + JS comments for internal codenames
4. Check `<meta>` generator tag
5. Check data-attributes for leaked AI-model names
6. Check asset filenames
7. Check Network tab (DevTools) for any `api.anthropic.com` / `api.openai.com` / `api.elevenlabs.io` — must proxy through AMG

7/7 → commit. <7 → clean up + re-check.
