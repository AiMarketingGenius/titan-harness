# AIMG Extension Fixes — CT-0416-22 partial ship (2026-04-17)

## What's in this directory

Patched files that replace/add equivalents in `~/Downloads/ai-memory-guard-extension-ct0416-07-FIX/` to produce v0.1.2.

- **`manifest.json`** — version bump 0.1.1 → 0.1.2; `grok.x.ai` → `grok.com`; added `copilot.microsoft.com` host permission + content-script block; strict allowlist (no wildcards).
- **`perplexity.js`** — recovered from `~/Downloads/ai-memory-guard-v0.1.0/`. The CT-0416-07-FIX zip was missing this file despite the manifest referencing it; v0.1.0 had the working version. 99 LOC, same MutationObserver pattern as chatgpt.js.
- **`copilot.js`** — new scaffold. Follows the established pattern (waitForPlatform → MutationObserver → dedupe → dispatch). Selectors target `cib-` web-component tree (Microsoft's shadow-DOM structure). Selector-locking against live Copilot output is Phase 2 of CT-0417-02 (needs Solon Chrome-MCP session).

## What's NOT in this directory (still pending CT-0417-02 Phase 2)

- Selector hardening for `chatgpt.js` / `gemini.js` — both currently watch generic `main` mutations with no platform-specific DOM locks. Needs Chrome MCP live tests with Solon's actual account conversations to capture current DOM signatures.
- Memory UI per-platform grouping (re-render `ui/carryover.js` or the memory display screen to group captures by `platform_name` with correct brand icon per platform).
- Supabase verification — `ai_memories` table should already have `platform_name` column per manifest intent; verify schema + populate correctly on capture-side dispatch.
- Chrome MCP e2e pass — navigate each platform, send test prompt, verify Supabase row written with correct `platform_name` + `model_used` + `thread_url`.
- v0.1.2 zip packaging + Chrome Web Store draft upload.

## Apply these patches

```bash
cd ~/Downloads/ai-memory-guard-extension-ct0416-07-FIX/
cp ~/titan-harness/deploy/aimg-extension-fixes/manifest.json  ./manifest.json
cp ~/titan-harness/deploy/aimg-extension-fixes/perplexity.js  ./perplexity.js
cp ~/titan-harness/deploy/aimg-extension-fixes/copilot.js     ./copilot.js
zip -r ../ai-memory-guard-v0.1.2.zip . -x 'node_modules/*' '.git/*'
```

## Changes vs CT-0416-22 audit gap-map

| Audit item | Gap-map status | This-session status |
|---|---|---|
| grok.js manifest `grok.x.ai` → `grok.com` | 🔴 BROKEN | ✅ FIXED (manifest.json v0.1.2) |
| perplexity.js MISSING | 🔴 missing file | ✅ RECOVERED (from v0.1.0) |
| copilot.js MISSING + no host perm | 🔴 greenfield | ✅ scaffolded + host perm added |
| chatgpt.js / gemini.js stale selectors | ⚠️ needs verification | 🔴 DEFERRED — Phase 2, needs Chrome MCP live test |
| Memory UI platform-grouping | 🔴 pending | 🔴 DEFERRED — Phase 2 |
| Supabase platform_name verify | 🔴 pending | 🔴 DEFERRED — Phase 2 |
| v0.1.2 zip ship | 🔴 pending | ⚠️ PARTIAL — patches staged, Solon can re-zip via the apply-block above |

## Next-session Phase 2 plan

Per `plans/deployments/CT-0416-22_AIMG_AUDIT.md` §"Build-Phase Plan" items 4-10:
1. Chrome MCP live tests on chatgpt.com / gemini.google.com / grok.com / copilot.microsoft.com / claude.ai / perplexity.ai (Solon logged in)
2. Capture current DOM signatures + update selectors in each `*.js`
3. Memory UI rebuild with platform-grouping
4. Manifest lock-down validation
5. Supabase `platform_name` / `model_used` / `thread_url` populated correctly
6. Full e2e per platform with screenshot verification
7. Build + ship v0.1.2 zip
8. Write `/opt/amg-docs/aimg/PLATFORM_CAPTURE_NOTES.md` for future maintenance

Estimated 5-8 hours of focused work post-Solon-session.
