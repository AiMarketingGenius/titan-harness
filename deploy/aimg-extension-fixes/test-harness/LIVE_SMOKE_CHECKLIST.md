# AI Memory Guard — Live Smoke Checklist (Monday pre-demo)

**Purpose:** Solon runs this before the Don Martelli pitch Monday to confirm the cross-LLM context injection fires cleanly on all 4 platforms with his real logged-in sessions. Takes ~4 minutes if everything's clean.

**Prerequisites:**
- AI Memory Guard extension v0.1.6 loaded unpacked from `deploy/aimg-extension-fixes/` via `chrome://extensions` (Developer mode → Load unpacked)
- Solon's usual Chrome profile with active Claude / ChatGPT / Gemini / Perplexity sessions

---

## Per-platform (run in order):

### ☐ Claude (claude.ai)
1. Open new tab → `https://claude.ai/new`
2. Wait ~2 sec → **AI Memory Guard** offer card appears bottom-center with "Inject N verified context items into this new Claude thread?"
3. Preview list shows Don Martelli / Revere Chamber / 280 members badges
4. Click **Inject N items** (primary green button)
5. Confirm the input box now contains a markdown block starting with `**Context from my AI Memory Guard vault (verified across Claude):**` and enumerated demo claims
6. Screenshot → save as `deploy/aimg-extension-fixes/test-harness/evidence/claude-injected-2026-04-20.png`

### ☐ ChatGPT (chatgpt.com)
1. Open new tab → `https://chatgpt.com/`
2. Wait ~2 sec → offer card appears with "new ChatGPT thread" phrasing
3. Click **Inject N items**
4. Input field at bottom of screen now contains the same markdown block
5. Screenshot → `chatgpt-injected-2026-04-20.png`

### ☐ Gemini (gemini.google.com)
1. Open new tab → `https://gemini.google.com/app`
2. Wait ~2 sec → offer card appears with "new Gemini thread" phrasing
3. Click **Inject N items**
4. Input field (`rich-textarea` Angular component) now contains the block
5. Screenshot → `gemini-injected-2026-04-20.png`

### ☐ Perplexity (perplexity.ai)
1. Open new tab → `https://www.perplexity.ai/`
2. Wait ~2 sec → offer card appears with "new Perplexity thread" phrasing
3. Click **Inject N items**
4. "Ask anything" textarea now contains the block
5. Screenshot → `perplexity-injected-2026-04-20.png`

---

## Fail-mode checks (quick sanity):

### ☐ Dismiss flow
1. On any platform, open new tab → wait for offer card → click × (dismiss) or **Not now** (ghost button)
2. Card disappears cleanly
3. Reloading same URL within same tab session → card does NOT re-appear (storage.session de-dup)

### ☐ Already-open-thread flow (card should NOT fire)
1. Claude: `https://claude.ai/chat/<any-existing-conversation-uuid>`
2. ChatGPT: `https://chatgpt.com/c/<any-existing-conversation-uuid>`
3. Gemini: `https://gemini.google.com/app/<any-existing-conversation-id>`
4. Perplexity: `https://www.perplexity.ai/search/<any-existing-search-slug>`
5. Offer card should NOT appear on any of these (ongoing-thread URLs). If it does → FAIL.

### ☐ User-preference disable (one spot check)
1. Open extension popup → if there's a "Cross-LLM inject" toggle, disable it
2. Open a fresh claude.ai/new tab → offer card must NOT appear
3. Re-enable toggle, refresh → offer card appears again

---

## Evidence checklist pre-demo

- [ ] 4 screenshots saved to `test-harness/evidence/`
- [ ] 0 offer-card leaks on ongoing-thread URLs
- [ ] Dismiss + re-show flow both work
- [ ] Injected block length on each platform ≥ 300 characters
- [ ] Solon comfortable narrating the injection beat in Demo Beat 2e

---

## Regression indicators (log to MCP if any fire)

- Card appears but never renders preview list → platform selector change; check `gemini.js` / `perplexity.js` SELECTORS block
- "Inject" button click does nothing → `injectIntoInput` fallback path; check input selectors in `cross-llm-inject.js:PLATFORM_CONFIG[platform].inputSelectors`
- Card fires on ongoing-thread URL → `isNewThreadUrl` regex drift (platform site DOM / URL pattern changed)
- No card at all → extension not loaded OR `window.__AIMEMORY_PLATFORM` not set (check `platform-detector.js` PLATFORM_RULES hostname)
