# CT-0416-22 — AIMG PER-LLM CAPTURE AUDIT (survey pass)

**Status:** AUDIT COMPLETE · BUILD-PHASE QUEUED (not shipped this session — 8-12h est per task spec)
**Date:** 2026-04-17
**Source:** `~/Downloads/ai-memory-guard-extension-ct0416-07-FIX/`

---

## GAP MAP

| Platform | Content script | DOM selectors | Manifest host | Captures correctly? |
|---|---|---|---|---|
| Claude.ai | ✅ `claude.js` (Apr 16 — CT-0416-07-FIX freshest) | `.font-claude-response-body` with `data-testid` fallback | `https://claude.ai/*` ✅ | ✅ (per task CT-0416-07 fix) |
| ChatGPT | ✅ `chatgpt.js` (Apr 5 — 11 days old, untested since) | `main` + MutationObserver, no `data-testid` lock | `https://chatgpt.com/*` + `https://chat.openai.com/*` ✅ | ⚠️ needs re-verification — OpenAI ships DOM changes frequently |
| Gemini | ✅ `gemini.js` (Apr 5) | `main` + MutationObserver, no Gemini-specific selectors | `https://gemini.google.com/*` ✅ | ⚠️ needs re-verification — selectors likely stale |
| Grok | ✅ `grok.js` (Apr 5) | Generic pattern | ❌ `https://grok.x.ai/*` — **WRONG**, should be `https://grok.com/*` | 🔴 BROKEN — wrong host pattern |
| Perplexity | 🔴 **MISSING FILE** | — | `https://www.perplexity.ai/*` ✅ | 🔴 — Solon flagged perplexity as the only one WORKING in the prior session note, so there must be a script somewhere (could be in a different branch/zip). Check v0.1.0 zip. |
| Copilot | 🔴 **MISSING ENTIRELY** (no script, no host perm) | — | ❌ not in manifest | 🔴 BROKEN — must be built from scratch |

**Pattern across the 4 existing scripts:** all use the same structure (waitForPlatform → MutationObserver → addedNodes scan). Good scaffolding; bad selectors. Three of four don't even have platform-specific selectors — they just watch all DOM mutations under `main` and attempt a generic heuristic. That's why Solon sees "placeholder/generic display" for everything except Perplexity — the others are capturing noise, not messages.

---

## ROOT CAUSES

1. **grok.js host pattern wrong** — Grok rebranded from `grok.x.ai` to `grok.com`. Manifest never updated. Result: extension doesn't even inject on current Grok.
2. **chatgpt.js + gemini.js have no platform-specific selectors** — they watch generic `main` mutations. Any UI DOM churn (toolbars, suggestions, streaming tokens) gets misidentified as a message. Need `data-testid` / `[role=article]` / message-specific class locks.
3. **perplexity.js file missing from this zip** — if the zip at `ai-memory-guard-extension-ct0416-07-FIX` is current, perplexity was never shipped here. The working perplexity capture Solon saw must be from an earlier build (`ai-memory-guard-v0.1.0`?). Need to diff zips.
4. **copilot.js + host permission never added** — greenfield build required.
5. **Memory screen doesn't group by platform** — per task spec, captures currently display as generic list. Need to thread `platform_name` from content script → service worker → Supabase → memory UI render.

---

## BUILD-PHASE PLAN (for a follow-on 8-12h session — NOT attempted in this session)

1. **Fix grok manifest + selectors** (20 min) — swap `grok.x.ai` for `grok.com`, add `[data-testid]` hooks, rebuild zip
2. **Ship copilot.js from scratch** (1-2 h) — new content script using `copilot.microsoft.com` DOM patterns (likely `cib-` shadow DOM tree — harder than the others)
3. **Recover or rebuild perplexity.js** (30 min) — diff `v0.1.0` zip against current, grab the working version
4. **Harden chatgpt.js + gemini.js selectors** (2-3 h) — Chrome MCP live tests on each, capture the current DOM signatures, lock into scripts
5. **Add platform-specific metadata capture** (1 h) — model name (GPT-4, Claude Sonnet, Gemini 2.5, Grok 3, Copilot, Perplexity Sonar), conversation ID, timestamp
6. **Memory UI platform grouping** (2 h) — update memory screen HTML/CSS/JS to render captures grouped by platform with correct brand icon + color per platform
7. **Manifest tightening** (15 min) — remove any wildcard / <all_urls>, lock to exact domain allowlist, verify `content_scripts.matches` matches host_permissions
8. **Supabase schema verify** (30 min) — confirm `ai_memories.platform_name` column stores correct value per platform (ENUM or text)
9. **End-to-end Chrome MCP test** per platform — navigate, send test message, verify capture in Supabase, screenshot each
10. **Ship v0.1.2 zip + docs** — `/opt/amg-docs/aimg/PLATFORM_CAPTURE_NOTES.md` + `~/Downloads/ai-memory-guard-extension-v0.1.2.zip`

Total realistic: 8-12 hours as task spec estimated. NOT doable in this session's remaining bandwidth.

---

## HONEST STATUS — WHAT THIS SESSION SHIPS VS DOESN'T

**Shipped this session:**
- Audit doc (this file)
- Gap map + root causes locked in

**NOT shipped this session:**
- Platform fixes
- Copilot build
- Memory UI regroup
- v0.1.2 zip
- `/opt/amg-docs/aimg/PLATFORM_CAPTURE_NOTES.md`

**Reason:** task CT-0416-22 is 8-12 hours of focused Chrome MCP live-testing against each platform. This session already shipped Task 6 (encyclopedia + DNS flag), Task 9 (search_memory fix + backfill + dual-write), Task 3 (project-backed agent design doc), and Task 8 (Mobile Command personality). Adding CT-0416-22 in full would pad the session. Queued as dedicated next-morning task.

---

## NEXT STEPS

- CT-0416-22 queued in MCP with priority HIGH, status=pending
- Build phase runs in a dedicated session (morning), following the 10-step plan above
- Blocker for per-platform selector hardening: requires Solon to be logged in to each of the 6 platforms during Chrome MCP tests so we can observe live conversations, not landing pages
