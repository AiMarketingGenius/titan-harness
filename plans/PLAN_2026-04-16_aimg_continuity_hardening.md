# PLAN — AIMG v0.1.0 → v0.2.0 Continuity Hardening + Sellability Sprint

**Product:** AI Memory Guard (consumer Chrome extension)
**Codebase:** `~/Sites/amg-memory-product/` (git: `1aff17d` feat(ct-0416-07))
**Supabase:** consumer project `gaybcxzrzfgvcqpkbeiq` (**isolated from AMG operator** — no bridge in this sprint)
**Date:** 2026-04-16
**Status:** DRAFT · PENDING_SONAR_A_MINUS (grading block §10; no code lands until graded)
**Author:** Titan · **Constraint set:** explicit continuity (not silent injection) · Claude + Perplexity priority · CRM broker HELD

---

## Executive summary

AIMG v0.1.0 is close to dogfood-ready but not sellable. Diagnosis shows **one critical-severity bug** (Claude capture has been dead since 2026-04-05 — Supabase confirms only 2 Claude rows ever, both timestamped in the same burst), **two trust-destroying UI bugs** ("No memories saved yet" rendered while 8 memories visible; stale "1d ago" on every row because capture is broken), **one actual wiring gap** (generateCarryover only reads hot cache, not Supabase — so if Solon reloads a thread the carryover is empty), and **one surface-area gap** (4-toggle settings is inadequate for a paid product).

The fix sequence is surgical: 5 phases, ~2-3 days of focused work, each phase has explicit pass/fail gates. **No rebuild.** Every phase preserves the existing persistence + Einstein + tier-gated carryover work already shipped in CT-0416-07. **No AMG CRM integration in this sprint.**

Ship target: **v0.2.0** on Chrome Web Store with a "sellable this week" Phase 1+2 cut, **v0.3.0** adds Phase 3+4 trust surface, **v1.0.0** after Phase 5 polish.

---

## Prioritized bug list (ordered by severity + user visibility)

| # | Severity | Where (file:line) | Symptom | Root cause |
|---|---|---|---|---|
| **B1** | 🔴 CRITICAL | `src/claude.js:27-29, 36, 69` | Claude memories stopped capturing ~11 days ago | Selectors `[data-testid="conversation-turn"]`, `[data-testid="assistant-message"]`, `.font-claude-message` are stale — Claude.ai rotated its DOM. Supabase shows 2 Claude rows from 2026-04-05; zero since. |
| **B2** | 🔴 HIGH | `src/popup.js:355-361` (`loadSyncStatus`) | Popup says "No memories saved yet" while stats show 8 memories | `loadSyncStatus()` reads `sync_status.last_sync_at` from chrome.storage.local and renders that banner INDEPENDENTLY from the actual DB row count. When `last_sync_at` is null (fresh install, no recent successful sync) but Supabase has historical rows, the two components contradict each other. |
| **B3** | 🟡 HIGH | `src/popup.js:459-469` (`formatTimeAgo`) | Everything says "1d ago" | Timestamps are mathematically correct — Perplexity rows are ~42h old → `Math.floor(42/24) = 1 day`. Feels wrong because **no new rows are landing** (B1). Secondary: no absolute timestamp on hover; no platform provenance visible. |
| **B4** | 🟡 HIGH | `src/ui/carryover.js:156-163` (`generateCarryover`) | Carryover packet empty if hot cache is cold | `generateCarryover()` only reads `chrome.runtime.sendMessage({type:'GET_HOT_CACHE'})` and filters by `thread_id`. If Solon reloads the thread (or the SW has been restarted), hot cache is empty → carryover is empty. No Supabase fallback. |
| **B5** | 🟢 MEDIUM | `src/popup.js:82-87` | Settings has only 4 toggles | Thin surface. Trust-signal problem for a paid product, not a bug per se. |
| **B6** | 🟢 MEDIUM | `src/ui/carryover.js:18-133` | Continuity UX is reactive (only triggers in red zone) | No explicit "Start fresh with context" button available anytime. User must wait for a trigger card, modal, or banner. |
| **B7** | 🟢 LOW | `src/service-worker.js:571-587` | Extraction is noisy | Regex extractor catches garbage like "my name is [incomplete code fragment]". No dedup against canonical. No noise filter. |
| **B8** | 🟢 LOW | `src/manifest.json:4` | `version: "0.1.0"` never bumps | Store resubmissions require monotonic version strings. Bump on every CT-closing ship. |

---

## 1. Current-State Diagnosis

### B1 — Claude capture dead (CRITICAL, content-script wiring bug)

**Category: content-script wiring bug** — not an extraction bug, not a Supabase query bug, not an auth/RLS bug.

**Evidence:**
```
Supabase query: SELECT platform, COUNT(*), MIN(created_at), MAX(created_at)
                FROM consumer_memories GROUP BY platform;

perplexity : 8 rows  · 2026-04-14 20:58 → 2026-04-14 20:58 (single-burst dogfood test)
claude     : 2 rows  · 2026-04-05 23:26 → 2026-04-05 23:26 (single-burst from 11 days ago)
grok       : 1 row   · 2026-04-05 23:26
gemini     : 1 row   · 2026-04-05 23:26
chatgpt    : 1 row   · 2026-04-05 23:26

Total: 13 rows across 5 platforms. No platform has captured anything in the last 36 hours.
```

All platforms are affected; Claude has been dead longest. This is a **selector rot pattern** — the platforms rotate DOM periodically, and the extension's static selector list can't keep up.

**Claude.ai current DOM (as of April 2026):**
- Old (stale): `[data-testid="conversation-turn"]`, `[data-testid="assistant-message"]`, `.font-claude-message`, `.prose .whitespace-pre-wrap`
- Current (needs verification in live DevTools): `[data-testid^="message-content"]`, wrapper classes have moved to inline Tailwind-arbitrary classes like `grid grid-cols-1 gap-2 py-[1.125rem]`, `.prose` still present but not always the direct child.

**Why MutationObserver fires but nothing captures:** observer fires on document mutations. `node.querySelectorAll('[data-testid="assistant-message"], .font-claude-message')` returns an empty NodeList because selectors don't match. `processMessage()` is never called. `exchangeCounter` stays at 0. The SW receives zero `NEW_RESPONSE` messages. Zero memories land.

**Why older Perplexity still worked briefly:** `.answer-text, [data-testid="answer"], .prose` — Perplexity kept `.prose` longer. Then Perplexity also rotated (hence zero capture there too since 2026-04-14).

### B2 — Popup state contradiction (HIGH, frontend-state bug)

**Category: frontend-state bug.** No Supabase / extraction / auth involvement.

**Evidence (from code read):**
```javascript
// popup.js:270 — loadStats()
const memoryCount = countRes.headers.get('content-range')?.split('/')[1] || swStats.hotCacheSize || 0;
document.getElementById('stat-memories').textContent = memoryCount;  // ← reads Supabase total

// popup.js:320 — loadSyncStatus()
const status = await chrome.runtime.sendMessage({ type: 'GET_SYNC_STATUS' });
// ...
if (status.last_sync_at) {
  lastSavedEl.textContent = `Last saved ${ago}`;
} else if (status.last_sync_status === 'no_auth') {
  lastSavedEl.textContent = 'Not signed in — memories held locally';
} else {
  lastSavedEl.textContent = 'No memories saved yet';  // ← LIE if Supabase has rows but last_sync_at is null
}
```

The two functions are independent. A fresh install (no SW sync events yet) with historical Supabase data will display "No memories saved yet" next to a memory count of 8.

**Fix scope:** single function rewrite.

### B3 — Stale "1d ago" (HIGH, rendering correct but contextually misleading)

**Category: rendering / provenance surface gap.** Also a downstream symptom of B1.

**Evidence:**
- Newest Perplexity row: `2026-04-14 20:58:42 UTC`
- Now: `2026-04-16 ~14:00 UTC`
- Delta: ~41h 2min → `Math.floor(41/24) = 1 day` → `"1d ago"` (mathematically correct)

The "suspicious" feeling comes from:
1. Every row shows ~1d because they all came from one dogfood burst.
2. No new rows landing → nothing will ever read "fresh" until B1 is fixed.
3. No absolute timestamp on hover → user can't audit.
4. Platform provenance shown as `"perplexity · Thread abc123"` is OK but truncated inconsistently.

### B4 — Carryover generation empty on reload (HIGH, wiring bug)

**Category: content-script wiring bug** — specifically data-path gap.

**Evidence (carryover.js:156-163):**
```javascript
const [hotCacheRes, userBag] = await Promise.all([
  chrome.runtime.sendMessage({ type: 'GET_HOT_CACHE' }),
  chrome.storage.local.get('user')
]);

const memories = (hotCacheRes?.memories || []).filter(m =>
  m.provenance?.thread_id === platform.threadId
);
```

**The failure case:** if the SW was idle / restarted by Chrome (MV3 aggressively unloads SWs), `hotCache = []` (service-worker.js:17 — variable reset on SW respawn). The popup can still recover memories via Supabase (popup.js:399-412), but the in-page carryover generator cannot. Result: user clicks "Generate & Copy" and gets an empty summary stub.

**Fix scope:** add a Supabase fallback path in `generateCarryover()`: if hot cache returns < 3 items for the current thread, call SW with `FETCH_THREAD_MEMORIES {thread_id}` and let SW hit Supabase.

### B5 — Settings too thin (MEDIUM, trust-signal gap)

**Category: UX maturity gap, not a bug.**

Current (popup.js:82-87): 4 boolean toggles — showThreadHealth / soundAlert / showWarningBar / enableFactChecker. For a paid product (even Pro $19.99), this is below the bar.

### B6 — Continuity UX reactive-only (MEDIUM, UX gap)

**Category: UX design gap.** Carryover ONLY shows up when the thread enters exchange 35, 46, or 55. No explicit way to generate a carryover on demand from the popup or toolbar.

### B7 — Noisy extraction (LOW, extraction quality)

**Category: extraction bug / quality gate.** Rules capture garbage patterns (code fragments matching the regex accidentally). No dedup vs existing canonical memories. No "mark as noise" feedback loop.

### B8 — Version number (LOW, store policy)

Store submissions need monotonic version bumps. v0.1.0 stays v0.1.0 across 3 CT-0416 ships → review system rejects.

---

## 2. Platform Capture Audit

| Platform | Content script | Selector strategy | Capture trigger | Extraction path | Save path | Known failures |
|---|---|---|---|---|---|---|
| **Claude** | `src/claude.js` | `[data-testid="conversation-turn"]` → `.font-claude-message` → `[data-testid="assistant-message"]` + `.prose .whitespace-pre-wrap` | MutationObserver on childList+subtree; 3s debounce per element | `processMessage()` → `chrome.runtime.sendMessage('NEW_RESPONSE')` → SW `handleNewResponse()` → 30s batch → `extractMemories()` regex rules | SW `syncToSupabase()` → POST `/rest/v1/consumer_memories` | 🔴 DEAD. Selectors stale since ~2026-04-05. |
| **Perplexity** | `src/perplexity.js` | `.answer-text` + `[data-testid="answer"]` + `.prose .whitespace-pre-wrap` | Same pattern | Same | Same | 🔴 DEAD since 2026-04-14. Same selector rot. |
| **ChatGPT** | `src/chatgpt.js` | Inspect needed (wasn't read; 97 lines) | Same pattern expected | Same | Same | 🔴 Presumed dead — 1 row from 2026-04-05 only. Verify in §2.1. |
| **Gemini** | `src/gemini.js` | Inspect needed (98 lines) | Same | Same | Same | 🔴 Presumed dead — 1 row from 2026-04-05 only. |
| **Grok** | `src/grok.js` | Inspect needed; manifest host is `grok.x.ai` but current domain is `grok.com` | Same | Same | Same | 🔴 Double failure — manifest `host_permissions` is stale (grok.x.ai deprecated in favor of grok.com). Content script never injects. |

### 2.1 — Why Perplexity appeared but Claude didn't

**Two factors compounded:**
1. Solon's dogfood use pattern: the overnight dogfood burst on 2026-04-14 was on Perplexity. No one hit Claude.ai with this extension loaded between Apr 5 and Apr 14, so Claude never got a fresh capture attempt.
2. Even if Solon had used Claude.ai in that window, the same selector rot would have killed it. Both are broken; Perplexity looks "alive" because its 2026-04-14 dogfood pre-dated Perplexity's own selector rotation by a few days.

### 2.2 — Explicit per-platform test checklist (manual Solon+Titan dogfood)

For each platform, Solon executes the following sequence with Chrome DevTools open:

```
TEST MATRIX
===========

Setup (per platform):
  1. chrome://extensions → AI Memory Guard → "service worker" → open DevTools
  2. Open target platform in a new thread
  3. Confirm content-script loaded: console log "[AI Memory] <platform> content script active. Thread: <id>"
  4. Confirm platform-detector fired: console log "[AI Memory] Platform detected: <platform>"

Capture test (per platform):
  5. Write one user message, wait for AI response to complete streaming
  6. Wait 4 seconds (3s debounce + 1s network)
  7. In SW console, expect: "[SW] New response from <platform>, <N> chars"
  8. Wait up to 35 seconds (30s batch interval + network)
  9. In SW console, expect: "[SW] Processing batch of <N> responses"
  10. If extraction yields >=1 memory: "[SW] Supabase sync success" + popup counter increments by ≥1
  11. If zero extraction: ℹ️ that's OK if message was casual; try a message with an explicit "I decided to X" or "my role is Y"

Fail conditions per platform:
  - No "content script active" log at step 3 → platform-detector or manifest host mismatch
  - No "New response" log at step 7 → SELECTOR ROT (the bug we expect on most platforms today)
  - No "Processing batch" log at step 9 → SW not respawning on alarm (rare MV3 quirk)
  - No popup counter increment at step 10 → sync failure (token / RLS / network)
```

Run this matrix on each of the 5 platforms; tag each as PASS / FAIL:selectors-stale / FAIL:manifest / FAIL:sync.

---

## 3. Continuity UX Spec (Phase 2 core deliverable)

**Framing:** explicit continuity, user-approved, inspectable. No silent injection. Solon is right — the product's trust story is "capture, QE, warn, and hand you the carryover packet to paste." Not "magic memory."

### 3.1 — Five explicit user flows

#### Flow A — "Start fresh thread with context" (primary user journey)

**When available:** always, via (a) popup "Continue in a new thread" CTA and (b) in-page carryover card/modal/banner when thread enters warm/hot/danger.

**Steps visible to user:**
1. User clicks "Start fresh with context" (popup or in-page card).
2. AIMG shows **preview dialog** with the carryover packet rendered — user SEES exactly what will be copied.
3. Preview dialog has 4 actions:
   - **Copy & Open New Thread** — copies to clipboard + opens new tab on same platform
   - **Copy Only** — clipboard only (for cross-platform use: Claude → Perplexity)
   - **Edit First** — textarea for manual trim before copy
   - **Cancel** — discard
4. After "Copy & Open New Thread": new tab opens on platform's new-thread URL (`claude.ai/new`, `www.perplexity.ai/`, etc.). User pastes manually. Zero autoinject.

#### Flow B — "Copy carryover summary"

Simplest variant of Flow A. Single action. Used on the thread-health card (exchange 35) and the persistent banner (exchange 55).

#### Flow C — "Inject last-thread context"

**Explicitly NOT doing.** Solon's framing: no silent background injection. If user wants to inject, they copy-paste. Period.

#### Flow D — "Use recent memories only"

**Purpose:** lightweight context seed for a brand-new topic. User clicks "Seed from recent memories" in popup → gets last ~10 canonical memories (any thread, any platform) formatted as a brief context block. Clipboard-only.

#### Flow E — "Use thread summary + key decisions + open loops" (FULL carryover)

The Doc-10-structured carryover already wired in `ui/carryover.js:245-334` — goal / completed / decisions / NOT-do / deferred / priority stack / cold-start. **This is the Pro / Pro+ tier deliverable; free tier gets the simpler rule-based summary.**

### 3.2 — Red-zone default behavior

When thread enters red (exchange ≥ 46):
1. **Modal appears** (already wired: `carryover.js:58-108`).
2. Modal shows **preview of the carryover packet** — not just "this is what we'll include" bullet points (§3.3 below).
3. Primary action: **"🚀 Generate & Review Carryover"** → opens §3.1 Flow A preview dialog.
4. Secondary: **Snooze +10** / **Continue in current thread anyway**.

### 3.3 — Packet contents (mandatory fields)

Every carryover packet includes these 7 sections in order. Free tier gets a terser rendering; Pro / Pro+ get full Doc-10.

| # | Section | Free tier | Pro tier | Pro+ tier |
|---|---|---|---|---|
| 1 | **What this thread is about** | `## Continuing from Previous Thread` + first detected decision | `### Goal` — first decision verbatim | Same as Pro, + dedup flag |
| 2 | **Key facts established** | Bulleted `facts` from hot cache + Supabase | `### What was completed` | Same, deduped vs prior carryovers |
| 3 | **Decisions made** | Bulleted `decisions` | `### Key decisions` | Same, deduped |
| 4 | **Corrections** | Bulleted `corrections` | `### Do NOT do` prefixed "Avoid:" | Same, deduped |
| 5 | **Open action items** | Bulleted `actions` | `### Deferred / open items` | Same, deduped |
| 6 | **Unresolved blockers** | (Free tier: omitted) | `### Priority stack for the next thread` — top 3 | Same, deduped |
| 7 | **"Continue from here" prompt** | `Please continue from here.` | `### Cold-start prompt` with code block | Same + dedup note |

Existing code at `carryover.js:200-334` covers 5 of 7 sections cleanly. **Gap:** §6 "unresolved blockers" does not exist as a memory type today — the extractor doesn't produce `blocker`-typed items. Phase 2 adds a `blocker` extraction pattern (regex for "blocked on", "waiting on", "need X before Y", "can't proceed until") and wires it into the 7-section template.

### 3.4 — Claude + Perplexity priority

Both platforms need:
1. Fixed capture (Phase 1).
2. Reliable thread-health counter wired to their current DOM (exchange count = count of user messages).
3. Explicit "Start fresh" in the popup AND as an in-page card button.
4. Preview dialog rendered with a style matching the platform's dark/light mode (detect via `document.documentElement.classList.contains('dark')` or `prefers-color-scheme`).

**Platform-specific new-thread URLs** for Flow A "Copy & Open New Thread":
- Claude: `https://claude.ai/new` — opens new conversation
- Perplexity: `https://www.perplexity.ai/` — opens clean search state
- ChatGPT: `https://chatgpt.com/` — clean state
- Gemini: `https://gemini.google.com/app` — new chat
- Grok: `https://grok.com/` — clean state

### 3.5 — What the packet is NOT

- NOT auto-injected into the input box.
- NOT mutating the new thread's initial state.
- NOT silently fetching cross-thread memories without preview.
- NOT cross-platform without user's explicit paste.

**Every continuity operation flows through clipboard + user paste. The extension never types into the page.**

---

## 4. Settings Expansion Spec

Replace current 4-toggle settings (popup.js:82-87) with grouped settings. **Stay Phase 1 realistic — no overbuild.**

### 4.1 — Six setting groups

#### Group 1 — Capture

Per-platform on/off toggles:
```
✅ Capture from claude.ai
✅ Capture from chatgpt.com
✅ Capture from gemini.google.com
✅ Capture from grok.com
✅ Capture from www.perplexity.ai
─────────────────────
ℹ️ Pause all capture  [temporary hold — does NOT delete existing]
```

Implementation: `chrome.storage.local.set({settings.capture.<platform>: bool})`. Content scripts check this before registering MutationObserver. SW also checks before processing `NEW_RESPONSE`.

#### Group 2 — Continuity

```
🔔 Show thread-health meter      [on/off]
📜 Carryover prompt timing:       [early (ex 25) | standard (35/46/55) | only red zone]
📋 Carryover length:              [short (~400 words) | standard | full]
📋 After generation:               [auto-copy to clipboard | show preview + copy button]
🗂️ Include memories from:          [current thread only | last 3 threads | all canonical]
```

#### Group 3 — Quality Enforcement (QE)

```
🧠 Einstein fact checker           [on/off — Free = 10/day; Basic = 50/day; Plus = 150/day; Pro = 300/day]
⚠️  Show contradiction alerts       [on/off]
⏰ Stale memory warnings            [on/off — warns if a canonical memory has been unchallenged >N days]
```

#### Group 4 — Audio & UI

```
🔊 Red-zone chime                  [on/off]
⚠️ In-page warning bar              [on/off]
📊 Thread health meter              [left edge | top bar | off]
🎨 Theme                            [auto | dark | light]
```

#### Group 5 — Privacy & data

```
🛑 Pause capture globally          [toggle, with last-paused-at display]
🗑️  Delete memories from current thread       [confirm button]
🗑️  Delete ALL my memories                     [confirm + type "DELETE" to proceed]
📤 Export memories                  [downloads JSON of all consumer_memories rows]
🔗 View data in Supabase            [external link to data portal — Pro+ only]
```

#### Group 6 — Account & plan

```
👤 Signed in as: solon@aimarketinggenius.io
🎯 Plan: Free / Basic / Plus / Pro  [badge]
📊 Usage this week: N / limit
📈 Usage this month: N / limit
⬆️ Upgrade plan                     [link — opens Stripe/Paddle/PayPal checkout — gated on payment processor ship]
🚪 Sign out
```

### 4.2 — Implementation approach

- Single `settings` object in `chrome.storage.local` — v1 schema:
  ```javascript
  {
    settings: {
      version: 2,
      capture: { claude: true, chatgpt: true, gemini: true, grok: true, perplexity: true, global_pause: false },
      continuity: { show_health_meter: true, prompt_timing: 'standard', carryover_length: 'standard', auto_copy: false, memory_scope: 'current_thread' },
      qe: { einstein_enabled: true, contradiction_alerts: true, stale_warnings: false },
      ui: { chime: true, warning_bar: true, health_meter_position: 'left', theme: 'auto' },
      privacy: { global_pause: false, last_paused_at: null }
    }
  }
  ```
- Migration: on boot, read `settings.version`. If `< 2`, port the old 4-toggle schema to the new shape + set `version: 2`.
- Settings UI is a scrollable sectioned panel inside the existing popup (not a separate page).

---

## 5. Memory Quality Control

**Goal:** fewer but better memories. Reduce noise, increase trust.

### 5.1 — Stronger thresholds for saving

Current `extractMemories()` (service-worker.js:571-600):
- Regex match → capture everything 10-150/200 chars.
- No content-quality check beyond length.

**Phase 4 additions:**

1. **Minimum signal threshold:** drop if extracted content is mostly punctuation / code / URLs.
   ```javascript
   function isSignal(text) {
     const words = text.split(/\s+/).filter(w => /[a-z]/i.test(w));
     if (words.length < 4) return false;                      // too short
     const codeChars = (text.match(/[{};<>()=]/g) || []).length;
     if (codeChars / text.length > 0.15) return false;        // too code-like
     const urlCount = (text.match(/https?:\/\//g) || []).length;
     if (urlCount > 1) return false;                          // URL dump
     return true;
   }
   ```
2. **Confidence floor:** skip if extracted `confidence < 0.35`.
3. **Repeat-capture guard:** before saving, check hot cache + Supabase recent for `content` that matches first-50-chars case-insensitive. If match found → increment `confidence` by 0.05 (floor 1.0) on the existing row, skip insert. Reuses `invalidateHotCacheByContent` pattern (service-worker.js:544-555).

### 5.2 — Dedup rules

- **Exact duplicate** (first-50-chars match): merge into existing memory, bump confidence.
- **Near duplicate** (cosine similarity > 0.9 via embedding — Phase 4.5): merge.
- **Contradiction** (existing contradictionsQE logic at service-worker.js:169-197): already wired; preserve.
- **Superseded** (new memory explicitly contradicts and is marked `correction`): mark old as `qe_status='superseded'`, new as canonical.

### 5.3 — Suppression list

Add `ui/review.js` + a settings panel for:
- **"Mark as noise"** button on each memory row in popup. Clicking flags the row `qe_status='noise'` in Supabase + hides from default list.
- **"Mark as useful"** button. Bumps confidence by 0.1.
- **Global suppression** patterns user can add: regex / substring that auto-marks new extractions as noise.

### 5.4 — Operator dogfood mode

Special "debug mode" setting in the Privacy group:
- Toggle `settings.privacy.dogfood_mode = true` (only visible if `user.email === 'solon@aimarketinggenius.io'`).
- When on: every memory extraction dumps full extraction trace (platform + raw text + which rule matched + confidence + dedup check result) to SW console AND to a new `debug_extractions` row in Supabase.
- Gives Solon a firehose to review before Chrome Web Store submission.

### 5.5 — Review queue

Dedicated tab in popup:
```
Review Queue  [8]
├── "my name is Solon" — fact — 0.8 conf — 2h ago — claude     [✓ useful | ✗ noise]
├── "decided to go with FastAPI" — decision — 0.9 — 3h — perplexity  [✓ | ✗]
...
```
Operator clicks batch-useful or batch-noise. Phase 4 scope.

---

## 6. Popup / Dashboard Cleanup

### 6.1 — Fix "No memories saved yet" contradiction (B2)

New logic flow in `popup.js:loadSyncStatus()`:

```javascript
async function loadSyncStatus() {
  const syncStatus = await chrome.runtime.sendMessage({ type: 'GET_SYNC_STATUS' });
  const { memoryCount } = await getMemoryCount(); // new helper reading the same Supabase count used by loadStats

  // Priority of banner text:
  if (syncStatus.pending_queue_size > 0) {
    banner.text = `${syncStatus.pending_queue_size} memories queued — click retry`;
    banner.color = 'amber';
  } else if (syncStatus.last_sync_status === 'no_auth') {
    banner.text = 'Sign in to sync';
    banner.color = 'amber';
  } else if (syncStatus.last_sync_status === 'error') {
    banner.text = `Sync paused — ${syncStatus.last_sync_error}`;
    banner.color = 'red';
  } else if (syncStatus.last_sync_at) {
    banner.text = `Last saved ${formatTimeAgo(syncStatus.last_sync_at)}`;
    banner.color = 'gray';
  } else if (memoryCount > 0) {
    banner.text = `${memoryCount} memories from prior sessions — capture resumes on next response`;
    banner.color = 'gray';
  } else {
    banner.text = 'No memories yet. Start a conversation on any AI platform.';
    banner.color = 'gray';
  }
}
```

Result: popup **never** says "No memories saved yet" when Supabase has rows.

### 6.2 — New popup surfaces

| Surface | Location | Data source |
|---|---|---|
| **Sync/capture status per platform** | Header row | SW maintains `sync_status.per_platform = {claude: {last_capture_at, last_sync_at, error}, ...}` — rendered as 5 colored dots |
| **"Last captured from [platform]"** | Under sync banner | `sync_status.most_recent_capture` (SW computes on every `NEW_RESPONSE`) |
| **"Last sync" timestamp** | Under sync banner | `sync_status.last_sync_at` |
| **Memory count — total, useful, needs-review** | Stats row | Supabase counts with `qe_status` filters |
| **"Continue in a new thread" CTA** | Bottom of popup, prominent | Opens carryover preview dialog (§3.1 Flow A) — available anytime |
| **"Review queue" link** | Under stats | Routes to new review panel (§5.5) |

### 6.3 — Popup information density fix

Current popup is ~480 lines of mixed state. Proposed hierarchy:

```
┌─ Header ─────────────────────────────┐
│ 🧠 AI Memory Guard    [Free badge]  │
│  ⚙️    📤     🚪                      │
├─ Per-platform dots ──────────────────┤
│ claude🟢  chatgpt🟡  gemini⚫  grok🔴 perplexity🟢  │
├─ Sync banner ────────────────────────┤
│ ✅ Last saved 3m ago from claude.ai  │
├─ Stats ─────────────────────────────┤
│  147 memories    12 useful    3 review  │
├─ Primary CTA ────────────────────────┤
│ [🔄 Continue in a new thread]        │
├─ Recent memories (5) ────────────────┤
│ ...                                  │
├─ Footer ────────────────────────────┤
│ Search | Review queue | Settings     │
└──────────────────────────────────────┘
```

---

## 7. Timestamp / Provenance Fix

### 7.1 — Fix `formatTimeAgo` edge cases

Current (popup.js:459-469):
```javascript
function formatTimeAgo(timestamp) {
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
```

**Additions:**
- `< 10s` → `"just now"` (was `< 60s`)
- `< 5m` → `"a few moments ago"` (less mechanical)
- Floor switches to `Math.round` for 30-min boundaries (9m30s + rounds to 10m not 9m).
- `< 24h` → `Xh ago` (current behavior; fine)
- `>= 24h < 48h` → `"yesterday at 3:42 PM"` (add clock time — MUCH more useful than "1d ago")
- `>= 48h < 7d` → `"Wed at 3:42 PM"`
- `>= 7d` → `"Apr 10"` or `"Apr 10, 2026"` if year differs

### 7.2 — Add absolute timestamp on hover

Every memory row renders:
```html
<span class="time-ago" title="2026-04-14T20:58:42Z — perplexity thread abc123 exchange #5">1d ago</span>
```

Hovering shows full ISO + platform + thread + exchange number.

### 7.3 — Platform + thread provenance always visible

Memory row format:
```
[fact] My role is founder of AMG.
perplexity · thread abc12345 · exchange #3     yesterday at 3:42 PM
```

Not truncated. If thread id is long, wrap to second line.

### 7.4 — Newest-first ordering

Current `loadRecentMemories` (popup.js:399-412) already uses `order=created_at.desc`. Verify it respects `source_timestamp.desc` fallback when `source_timestamp` is present (which is richer than `created_at` for memories that arrived late).

Proposed query change:
```
?order=source_timestamp.desc.nullslast,created_at.desc&limit=20
```

### 7.5 — Timestamp test cases

Manual dogfood:
| Age | Expected display |
|---|---|
| 5 seconds | "just now" |
| 45 seconds | "a few moments ago" |
| 12 minutes | "12m ago" |
| 3h 10m | "3h ago" |
| 23h 59m | "23h ago" |
| 36 hours (same date offset) | "yesterday at 3:42 PM" |
| 3 days | "Wed at 3:42 PM" |
| 10 days | "Apr 6" |
| 380 days | "Mar 30, 2025" |

Write `ui/time.test.js` with these cases (vanilla Node, zero deps — `node --test`).

---

## 8. Chrome Store Readiness Gap List

Brutally honest. Split into "sellable this week" (Phase 1+2 lands) and "needs another sprint" (Phase 3+4+5).

### 8.1 — Sellable this week (Phase 1+2 landed)

| Item | Status before | After Phase 1+2 | Gate |
|---|---|---|---|
| **Capture works on all 5 platforms** | 🔴 all dead | ✅ all verified via §2.2 test matrix | Phase 1 pass/fail |
| **Popup doesn't contradict itself** | 🔴 B2 | ✅ fixed per §6.1 | Phase 1 |
| **Timestamps believable** | 🟡 B3 | ✅ §7.1-7.5 | Phase 1 |
| **Carryover works on reload** | 🟡 B4 | ✅ Supabase fallback | Phase 2 |
| **Explicit "Start fresh" button anytime** | 🔴 reactive-only | ✅ popup CTA + preview dialog | Phase 2 |
| **Version bumped** | 🔴 stuck at 0.1.0 | ✅ 0.2.0 | every phase |

### 8.2 — Needs another sprint (Phase 3+4+5)

| Item | Current | Needed |
|---|---|---|
| **Settings surface** | 4 toggles | 6 groups per §4.1 |
| **Privacy policy URL** | None | Published at aimemoryguard.com/privacy (already exists per VPS inventory — verify content is current) |
| **Terms of service URL** | None | Same — aimemoryguard.com/terms |
| **Permissions disclosure** | Manifest lists storage/activeTab/tabs/alarms/offscreen | Chrome Web Store requires a **rationale per permission** in the listing. Draft copy needed. |
| **Onboarding flow** | `ui/onboarding.js:141` exists, not reviewed in detail | Verify current flow; add 3-step intro (capture / thread health / carryover) on first install |
| **Billing/upgrade visibility** | None — tier badges render but no upgrade path | Gated on PaymentCloud/Durango ship (separate block per CLAUDE.md §2). Interim: link to /pricing page with "contact us to upgrade" |
| **Help/support docs** | None | Minimum: FAQ page at aimemoryguard.com/faq covering (1) what data is captured (2) where it's stored (3) how to delete (4) how carryover works |
| **Screenshots** | None on record | 5 required for store: popup / thread-health meter / carryover modal / settings / memories list |
| **Demo video / GIF** | None | 30-second demo for store listing — show capture → red zone → carryover → new thread |
| **Content Security Policy in manifest** | Default | Review — MV3 default is fine; just verify no inline script usage |
| **Privacy practices disclosure (Chrome Store form)** | Not filled out | ~30 min work filling the webstore form: data collected, purpose, sharing, security practices |
| **Developer account verification** | Unknown — is aimemoryguard.com's publisher verified? | Confirm with Solon |

### 8.3 — Explicit "NOT in v0.2.0 scope"

- ⛔ Rendering memories from other users (shared memories) — never
- ⛔ Browser-based auth autofill — out of scope forever (privacy)
- ⛔ Any cross-origin fetch outside Supabase + (eventually) Anthropic/OpenAI for Einstein
- ⛔ Analytics (we don't collect; Store needs no disclosure)

---

## 9. Build Order

Every phase ends with a merge-gate: pass/fail criteria must be green before the next phase starts.

### PHASE 1 — Bugs + capture reliability (1 day Titan clock)

**Scope:**
- Fix B1: selector refresh on all 5 content scripts. Use DOM inspection in live DevTools, not guessing.
- Fix B2: popup state contradiction (§6.1).
- Fix B3: timestamps (§7.1).
- Fix B8: version bump to 0.2.0.
- Bump `manifest.json` `host_permissions` for grok (grok.x.ai → grok.com).

**Files touched:**
- `src/claude.js:27-69`
- `src/chatgpt.js` (inspect + fix)
- `src/gemini.js` (inspect + fix)
- `src/grok.js` (inspect + fix)
- `src/perplexity.js:25-66`
- `src/popup.js:320-388` (loadSyncStatus) + `459-469` (formatTimeAgo)
- `src/manifest.json:4,98` (version + host_permissions)
- `src/platform-detector.js:11-16` (add grok.com rule)

**Pass/fail criteria:**
- [ ] §2.2 test matrix PASSES on all 5 platforms (at least 1 memory per platform captured live).
- [ ] Popup never shows "No memories saved yet" when `memoryCount > 0`.
- [ ] Timestamps render "yesterday at 3:42 PM" for rows 24-48h old.
- [ ] `manifest.json.version == "0.2.0"`.
- [ ] Zero regressions: existing popup shows tier badge, settings still open, search still works.

**Fail handling:** if any platform's selectors can't be stabilized in one session, park that platform's content script behind a capture-disabled toggle in settings (Group 1) and ship the 4 working platforms.

---

### PHASE 2 — Continuity UX (1-1.5 days)

**Scope:**
- Fix B4: carryover Supabase fallback.
- Fix B6: explicit "Continue in a new thread" CTA in popup.
- Implement preview dialog (§3.1 Flow A).
- Add `blocker` extraction pattern (§3.3 gap).
- Wire Flow B/D/E from §3.1.
- Ensure Claude + Perplexity look-and-feel is tested first.

**Files touched:**
- `src/ui/carryover.js` — add Supabase fallback at line 156; add preview dialog function; add `generateCarryoverWithPreview()`
- `src/popup.js` — add "Continue in a new thread" button + handler; route to in-page `__AIMEMORY_CARRYOVER.showPreview()` via content-script message
- `src/popup.html` — new CTA element
- `src/service-worker.js:571-600` — add `blockers` regex pattern
- `src/ui/carryover.css` — preview dialog styles

**Pass/fail criteria:**
- [ ] On Claude.ai, clicking popup's "Continue in a new thread" opens an in-page preview modal with the full 7-section carryover rendered.
- [ ] Preview modal has Copy & Open New Thread / Copy Only / Edit First / Cancel.
- [ ] Copy & Open New Thread copies to clipboard AND opens `https://claude.ai/new` in new tab.
- [ ] Carryover packet is NON-empty even if SW was restarted (Supabase fallback works).
- [ ] Same flow works on Perplexity.
- [ ] Free tier sees simple summary; Pro/Pro+ sees Doc-10 with §6 priority stack populated.

---

### PHASE 3 — Settings + trust (1 day)

**Scope:**
- Implement 6-group settings panel (§4.1).
- Settings migration from v1 4-toggle to v2 grouped schema.
- Wire per-platform capture toggles to content scripts + SW.
- Add "Pause all capture" kill switch.
- Add "Export memories" JSON download.
- Add "Delete memories from current thread" + "Delete ALL".

**Files touched:**
- `src/popup.html` — new settings panel markup
- `src/popup.js` — new settings handlers + migration
- `src/service-worker.js` — add `DELETE_THREAD_MEMORIES`, `DELETE_ALL_MEMORIES`, `EXPORT_MEMORIES` handlers
- Each content-script — respect `settings.capture.<platform>` + `settings.privacy.global_pause` before observing

**Pass/fail criteria:**
- [ ] All 6 settings groups render + values persist.
- [ ] Toggling capture:claude=false actually stops Claude captures (verified via SW console: no `NEW_RESPONSE` from claude).
- [ ] Export downloads a JSON file with all the user's `consumer_memories` rows.
- [ ] Delete ALL requires typing "DELETE" to confirm; then actually removes rows via DELETE from Supabase (not soft delete).
- [ ] Old v1 settings users get migrated automatically with zero setting loss.

---

### PHASE 4 — Noise reduction + review tools (1 day)

**Scope:**
- Implement signal threshold + confidence floor (§5.1).
- Dedup by first-50-chars match (§5.2).
- "Mark useful / mark noise" UI on each memory row (§5.3).
- Review queue tab (§5.5).
- Dogfood mode toggle (§5.4) — gated on `user.email === 'solon@aimarketinggenius.io'`.

**Files touched:**
- `src/service-worker.js` — add `isSignal()`, `isDuplicate()`, update `extractMemories()`
- `src/popup.js` + `src/popup.html` — mark useful/noise buttons, review queue view
- `src/ui/review.js` (new) — review queue rendering logic

**Pass/fail criteria:**
- [ ] Code fragments, URL dumps, <4-word extractions are NOT saved (verified via dogfood mode trace).
- [ ] Near-duplicate extractions increment confidence on existing row, no new row created.
- [ ] Mark-noise hides memory from list + sets `qe_status='noise'`.
- [ ] Review queue shows last 20 `qe_status='unverified'` memories with batch actions.
- [ ] Dogfood mode logs appear in `debug_extractions` Supabase table (new table — sql/150_aimg_debug.sql).

---

### PHASE 5 — Store polish (0.5-1 day)

**Scope:**
- Privacy policy + terms review (verify aimemoryguard.com pages are current).
- Permissions disclosure copy for Chrome Web Store listing.
- 5 screenshots + 30s demo GIF.
- Onboarding polish.
- Publisher verification confirmation.
- Store form submission draft.

**Deliverables:**
- `plans/CHROME_STORE_SUBMISSION_CHECKLIST.md` filled out.
- 5 PNG screenshots at `~/Sites/aimemoryguard-site/store-assets/`.
- Demo GIF at `~/Sites/aimemoryguard-site/store-assets/demo.gif` (30s, <5MB).

**Pass/fail criteria:**
- [ ] Chrome Web Store listing draft approved by Solon.
- [ ] Privacy policy URL returns 200 + covers: data collected / storage / deletion / sharing.
- [ ] Permissions rationale ≥1 sentence per permission.
- [ ] All 5 screenshots + demo captured + reviewed.
- [ ] Submission form completed (but NOT submitted — Solon pushes the button).

---

## QA Matrix

| Test | Phase | Platform | Manual / automated |
|---|---|---|---|
| Content-script loads + platform-detector fires | 1 | all 5 | manual |
| 1 live capture end-to-end (write → observe → batch → Supabase) | 1 | all 5 | manual |
| Popup sync banner never contradicts memory count | 1 | any | manual + unit test |
| formatTimeAgo edge cases | 1 | any | `node --test` on ui/time.test.js |
| Carryover works on SW-restart scenario | 2 | Claude + Perplexity | manual (force-reload SW via chrome://extensions) |
| Preview dialog renders + 4 actions work | 2 | Claude + Perplexity | manual |
| "Copy & Open New Thread" opens correct URL | 2 | all 5 | manual |
| 7-section carryover contents per tier | 2 | any | manual (inspect clipboard paste) |
| Settings v1 → v2 migration preserves values | 3 | any | unit test + manual |
| Per-platform capture toggle works | 3 | all 5 | manual |
| Export downloads valid JSON | 3 | any | manual |
| Delete ALL with confirm deletes rows | 3 | any | manual + Supabase query verify |
| Noise filter rejects code fragment | 4 | any | unit test |
| Dedup merges first-50-chars match | 4 | any | unit test |
| Review queue batch actions | 4 | any | manual |
| Dogfood mode writes debug rows | 4 | Solon only | manual + Supabase query |
| Privacy/terms URLs return 200 | 5 | — | curl |
| Demo GIF under 5MB, 30s | 5 | — | `file` + duration |

---

## Go / no-go checklist for Chrome Web Store

### Must-pass before submission

- [ ] All 5 platforms capture live (§2.2 matrix green)
- [ ] Popup never contradicts itself (B2 fixed)
- [ ] Timestamps believable (B3 fixed)
- [ ] Carryover works regardless of SW state (B4 fixed)
- [ ] Version bumped past 0.1.0 (B8)
- [ ] Settings expanded to 6 groups
- [ ] Export + delete tools work
- [ ] Privacy policy + ToS URLs return 200
- [ ] Screenshots + demo GIF uploaded to store draft
- [ ] Permissions rationale written
- [ ] Publisher identity verified with Google
- [ ] Manifest `host_permissions` matches actual platform hostnames (grok.com not grok.x.ai)
- [ ] Zero console errors on a 5-message Claude thread
- [ ] Zero console errors on 5-message Perplexity thread

### Nice-to-have (defer to v0.3.0)

- Noise filter + review queue (Phase 4)
- Dogfood mode (Solon-only feature)
- Animated onboarding
- Pro / Pro+ billing integration (blocked on PaymentCloud/Durango)

---

## 10. Grading Block

**Per §12 + §12.5: this plan is not ready for Solon to execute until graded A- or better.**

**Method used:** Titan drafted; routing for external grading via `lib/war_room.py` (direct Perplexity sonar-pro) per Solon's 2026-04-16 instruction. Aristotle-in-Slack path remains a fallback if sonar-pro quota is exhausted.

**Why this method:** per Solon's directive — "keep the CRM/broker work held, use direct Perplexity sonar-pro for grading." Direct API path is active in the harness; `lib/war_room.py WarRoom.grade()` takes the plan text, submits to sonar-pro with the 10-dimension rubric, returns `{grade, issues, recommendations, dimension_scores, summary}` per the existing GradeResult contract.

**Minimum passing grade:** A- (≥ 9.0 / 10).

**If below A-:** iterate up to 5 rounds per `policy.yaml war_room.max_refinement_rounds: 5`. Do not present as ready to Solon until A- or better.

**Grading dimensions (10):**

| Dimension | Score | Notes |
|---|---|---|
| 1. Correctness (accurate root-cause diagnosis, accurate DOM behavior claims) | — | PENDING — especially the selector-rot claim for Claude needs sonar-pro to pressure-test against April 2026 Claude.ai DOM |
| 2. Completeness (does this cover everything Solon asked for in 10 sections) | — | PENDING |
| 3. Honest scope (are the "sellable this week" claims realistic?) | — | PENDING |
| 4. Rollback availability (per phase) | — | PENDING — Phase 1 is git-revert-safe; Phase 3 settings migration needs a downward migration path |
| 5. Fit with harness patterns (Hercules Triangle, §12 Idea Builder, §17 Ironclad) | — | PENDING |
| 6. Actionability (file:line specificity, pass/fail gates) | — | PENDING |
| 7. Risk coverage (what could go wrong — MV3 service worker unload, Chrome review rejection, DOM rot recurrence) | — | PENDING |
| 8. Evidence quality (Supabase row counts, file:line references verified) | — | PENDING |
| 9. Internal consistency | — | PENDING |
| 10. Ship-ready for production | — | PENDING |

**Overall grade:** PENDING

**Revision rounds:** 0 (this is round 1).

**Decision:** HOLD — do not touch `~/Sites/amg-memory-product/` source until this plan clears A- grade.

---

## 11. Dogfooding model — browser lane vs MCP lane

**Canonical product stance (Solon directive 2026-04-16):** AIMG is a **browser-first consumer continuity product**. It captures only what the Chrome extension can legitimately observe on supported browser LLM surfaces. Titan / Claude Code sessions and operator agents are a **separate lane** and write continuity state through MCP-native logging + carryover, not through the browser extension.

**Rule:** never hack Titan / Claude Code traffic into a browser-visible Claude page just so the extension can scrape it. That is fake dogfooding and it blurs the consumer-product boundary.

### 11.1 — The two lanes

| Lane | Who uses it | How capture happens | Where state lives | Who it's marketed to |
|---|---|---|---|---|
| **Browser lane** | End users on Claude.ai, Perplexity, ChatGPT, Gemini, Grok | Chrome content scripts observe DOM, extract, POST to Supabase consumer project | `consumer_memories` (Supabase project `gaybcxzrzfgvcqpkbeiq`) | **Public AIMG consumer product** |
| **MCP lane** | Titan, Claude Code, operator agents | MCP tool calls: `log_decision`, `log_activity_event`, `generate_carryover`, `log_dual_ai_run`, etc. | Operator CRM broker tables (per the held CRM broker plan) + MCP decision log | Internal AMG ops only |

Both lanes can share a memory model in principle — but provenance must be **explicit and distinct**, never silently merged.

### 11.2 — Provenance discipline (mandatory)

Every memory row (in every table, in both lanes) MUST carry:

```
source_type      ∈ { 'browser_extension', 'mcp_agent', 'manual_entry', 'system' }
source_platform  ∈ { 'claude.ai', 'chatgpt.com', 'www.perplexity.ai', 'gemini.google.com', 'grok.com',    // browser lane
                     'mcp:titan', 'mcp:claude_code', 'mcp:operator_agent',                                  // MCP lane
                     'manual', 'system' }
```

**Specifically for AIMG's `consumer_memories` schema (the browser-lane table):** add a `source_type` TEXT column, default `'browser_extension'`, with a CHECK constraint restricting allowed values. No MCP-lane writes to `consumer_memories`. Ever.

**For the CRM broker's `operator_events` + `memory_items` tables** (held design): already carry an `actor_role` column (per the broker plan at `plans/PLAN_2026-04-16_amg_crm_memory_broker_phase1.md §2 Layer 2 DDL`). Extend the check constraint to require `actor_role` NOT starting with `'extension:*'` — we never want a pretend-extension row in operator tables either.

### 11.3 — No deceptive UI or copy

**Banned in AIMG product surfaces** (popup, settings, onboarding, landing page, store listing, demo GIF):
- Claims like "captures from your AI agents automatically"
- Claims that imply the extension observed Titan / Claude Code traffic when it did not
- Screenshots showing extension-captured memories sourced from MCP-only activity
- Marketing copy that positions AIMG as "AI-for-your-AI" in a way that suggests non-browser capture

**Approved copy** for AIMG:
- "Capture from Claude, ChatGPT, Gemini, Grok, and Perplexity in your browser"
- "Explicit carryover — we show you exactly what you're pasting into the next thread"
- "Browser-first continuity. No silent injection."

### 11.4 — Design recommendations

**For internal AMG use:** optional convergence at the **storage/retrieval** layer is acceptable. Example: a read-side broker tool `search_cross_lane_memory(subject, tenant_id)` could query BOTH the operator CRM memory_items AND the consumer_memories table (Solon's own user_id only), returning a unioned result set for internal Titan context assembly. This is:
- ✅ fine for internal ops where Solon is the single user on both lanes
- ✅ explicitly gated on operator role
- ✅ does NOT write across lanes — read-only union
- ❌ NOT exposed as a public AIMG feature
- ❌ NOT visible in the browser extension UI

**For the public AIMG product:** market only browser-supported continuity. Five platforms, explicit carryover, user pastes. That is the product.

**If we ever productize non-browser capture later:** that is Phase 2+ scope and it must be a **separately-named capability** (e.g., "AI Memory Guard Pro+ Agent Hub" or similar), shipped as a distinct module with its own disclosure, its own UI, and its own permissions. It is NOT hidden behavior inside the extension.

### 11.5 — Contract for Phase 1-5 in this plan

All 5 phases in §9 operate on **browser lane ONLY**. Zero MCP-lane writes into `consumer_memories`. Zero extension-lane writes into operator CRM tables. Every memory row landing from the extension gets `source_type='browser_extension'` + a concrete `source_platform` in the supported 5-platform set.

**Added to Phase 3 scope:** `sql/151_aimg_provenance.sql` — adds the `source_type` + refined `source_platform` check constraints to `consumer_memories`. Apply-gated on this plan clearing A-; nothing lands until then.

---

## 12. Internal dogfood strategy that matches public truth

Solon's directive: AMG's internal testing strategy must not create false marketing signals. Dogfooding is valid only if the evidence reflects what the public product actually does.

### 12.1 — Three rules

1. **Test continuity on Claude.ai + Perplexity as the primary public proof.** These are the flagship browser-lane surfaces. The proof the product works = Solon uses the extension on real Claude.ai and real Perplexity threads, gets real carryovers, demos them to prospects. This is the truth signal.

2. **Treat Titan continuity as MCP-native internal augmentation.** Titan's carryover + memory lives in MCP, CRM broker, and operator event log. That is fine, that is internal infrastructure, that is not AIMG. When Titan needs to demo its own continuity, it demos MCP tools, not a browser extension.

3. **Never use internal-only Titan capture as evidence that the browser product works.** If a screenshot or demo shows memory items that came from Titan, that is disqualified as AIMG proof. Replace with genuine browser-lane capture from Solon's own Claude.ai / Perplexity usage.

### 12.2 — What counts as valid AIMG proof

| Proof type | Valid for AIMG marketing? |
|---|---|
| Screenshot of popup on Solon's laptop after he uses Claude.ai for an hour | ✅ Yes |
| Screenshot of popup showing memories from a Perplexity Pro research session | ✅ Yes |
| Screen recording of carryover flow: red zone → preview → copy → paste into new Claude thread | ✅ Yes (flagship demo) |
| Screenshot of AIMG popup showing rows that were originally written by Titan to the operator CRM | ❌ No — provenance mismatch |
| Demo where Titan "seeds" memories into the extension via backdoor | ❌ Explicitly banned |
| Screenshot of AIMG popup showing consumer_memories rows with `source_type='browser_extension'` + `source_platform='claude.ai'` | ✅ Yes — provenance check passes |

### 12.3 — Measurement rubric for dogfood adequacy

Before declaring AIMG "ready to sell," these dogfood metrics must be green (measured from real Solon usage, not synthetic):

- [ ] ≥ 20 genuine Claude.ai captures over ≥ 3 distinct threads over ≥ 3 distinct days
- [ ] ≥ 15 genuine Perplexity captures over ≥ 3 threads over ≥ 3 days
- [ ] ≥ 1 live carryover flow completed end-to-end (preview → copy → paste into new thread → new thread productive)
- [ ] ≥ 1 red-zone trigger fired + handled (exchange ≥ 46)
- [ ] Zero memories with `source_type` other than `browser_extension` in `consumer_memories` on Solon's user_id
- [ ] Einstein fact-check fired ≥ 3 times on real captures

All measurable via Supabase queries. Wire these into a `plans/AIMG_DOGFOOD_SCORECARD.md` once Phase 1 passes.

### 12.4 — Honest gap flag

Right now (2026-04-16 pre-sprint): **dogfood metrics above are 0 / failing because of B1 (all capture dead).** The entire "is AIMG sellable" question is blocked on Phase 1 landing cleanly. No amount of Titan MCP activity can backfill this. That is the whole point of this discipline: the product either captures legitimately or it doesn't ship.

---

## 13. Open question — optional internal bridge utility (NOT in Phase 1-5)

**Question for Solon:** should we later build a tiny internal-only utility that converts Titan's MCP-native carryover output into a user-pasteable browser bootstrap packet?

### 13.1 — Proposed design

- **Name (placeholder):** `titan-to-browser-bootstrap.py` or similar
- **Location:** `scripts/` in harness, not shipped in the extension
- **Input:** Titan's current task state + memory items from the operator CRM memory_items (operator role only)
- **Output:** a clipboard-ready carryover packet that matches the 7-section format defined in §3.3 of this plan
- **Flow:** Solon runs `titan-to-browser-bootstrap --task <id>` at the CLI, gets a formatted packet, pastes into his own Claude.ai / Perplexity thread manually

### 13.2 — What it is NOT

- ❌ Not silent sync — Solon invokes it explicitly
- ❌ Not auto-injected into the browser
- ❌ Not sending Titan output to `consumer_memories`
- ❌ Not marketed as part of AIMG
- ❌ Not in extension permissions, not in extension UI, not mentioned in store listing

### 13.3 — Why it might be worth building

- Solon routinely needs to carry Titan's session state into a Claude.ai conversation (e.g., asking Claude.ai to review a plan Titan drafted).
- Currently this is manual copy-paste from `plans/` or from Slack carryovers.
- A thin CLI helper formalizes a workflow Solon already does by hand.
- Stays on the right side of the provenance line because it is explicit + operator-only + CLI-invoked.

### 13.4 — Why it might NOT be worth building

- Adds one more thing to maintain.
- Solon already has manual carryover via `mcp__generate_carryover` + Slack.
- If the habit is "copy-paste from plans/", a bash alias is maybe sufficient.
- Tiny utility that scope-creeps into "maybe we should just sync" is the exact failure mode Solon wants to avoid.

### 13.5 — Recommendation

**Park this decision until after AIMG v0.2.0 ships.** The CRM broker + MCP tool surface (`generate_carryover` already exists; Phase 2 of the broker adds `build_context_packet`) will likely cover Solon's internal needs without requiring a new bridge utility. If after 2 weeks of using CRM broker output Solon finds himself manually reformatting carryovers for browser paste, revisit then.

If Solon wants to build it anyway: 30-line Python script, 1-hour ship, low-risk.

---

## Constraints explicitly honored

- ✅ AIMG consumer data stays isolated from AMG operator (no CRM bridge added)
- ✅ **Browser-lane product truth preserved — no Titan traffic hacked into browser captures**
- ✅ **Provenance discipline mandatory across both lanes (source_type + source_platform)**
- ✅ **Public AIMG marketing claims limited to browser-observable capture**
- ✅ **Internal bridge utility parked — not built in this sprint**
- ✅ CRM broker plan remains drafted + preserved at `plans/PLAN_2026-04-16_amg_crm_memory_broker_phase1.md` — unchanged, no SQL applied
- ✅ No silent background memory injection — every continuity operation is explicit + user-approved + inspectable
- ✅ Claude + Perplexity prioritized as Phase 1 targets
- ✅ Code-oriented, file:line specific, not a vague essay
- ✅ 10-section output format matches Solon's spec
- ✅ Phase-by-phase pass/fail gates
- ✅ Grading routed through direct Perplexity sonar-pro via `lib/war_room.py`

## What is NOT in this plan

- ❌ Any Supabase schema write (CRM broker held)
- ❌ Any AMG operator CRM integration
- ❌ Silent injection / autonomous memory overwrites
- ❌ New memory types beyond existing fact/decision/preference/correction/action/narrative/episodic/entity (+ new `blocker` in Phase 2)
- ❌ Migration to a different extension framework
- ❌ Payment processor integration (gated on PaymentCloud/Durango)
- ❌ Cross-user memory sharing
- ❌ Analytics collection

---

*End of plan. Grading pending. Code work held until A-.*
