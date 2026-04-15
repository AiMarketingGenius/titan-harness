# AIMG tier-router — extension client

Client-side companion to `config/aimg/tier-router/` (the Supabase edge
function + migration shipped under CT-0414-09). Implements the CT-0405-06
UI/UX spec on top of the tier-router HTTP contract.

**Shipped by:** Titan (CT-0414-09 continuation, 2026-04-14).
**Spec sources:** `plans/DOCTRINE_AIMG_TIER_MATRIX.md` (FINAL LOCK) +
claude.ai thread `eaa777fa` (CT-0405-06 UI/UX).

## Modules

| File | Purpose |
|---|---|
| `src/tier-router-client.js` | Fetch wrapper. 200 / 402 / 429 handling. |
| `src/thread-health-widget.js` | Left-edge meter, 8px→52px hover, 4 zones. |
| `src/chime.js` | 2-tone ding-DING, plays ONCE on red entry (WebAudio). |
| `src/carryover-modal.js` | Modal with locked copy + upsell + pause banner. |
| `src/rate-limit-middleware.js` | Local cap precheck, token-bucket pacing, platform-pause cache, in-flight dedup, usage shape shim (CT-0414-09 Item 1). |
| `src/aimg-client.js` | Public API composing all four. |
| `tests/` | Node `--test` integration tests with mock Supabase + fake DOM. `npm test` runs 21 cases. |

Zero dependencies. ES modules only. Works in a Chrome MV3 content script
or in a regular web-app bundle.

## Integration (1 screen)

```js
import { AimgClient } from "./config/aimg/tier-router/extension-client/src/aimg-client.js";

const client = new AimgClient({
  supabaseUrl: "https://gaybcxzrzfgvcqpkbeiq.supabase.co",
  jwt: userSupabaseJWT,
  widgetContainer: document.body,
  onStartFreshThread: ({ reason, upsell }) => {
    // caller decides: clear in-page thread state, open upsell URL, etc.
  },
});

// each time you want to verify a memory:
const resp = await client.verify({
  user_id,
  memory_id,
  memory_content,
  operation: "verify",
});

if (resp.status === "ok") {
  renderResult(resp.data.result);
}
// cap_exceeded and platform_paused both show the modal automatically;
// caller still receives the response object for telemetry.
```

## Zone matrix (locked)

| Zone | Exchanges | Color |
|---|---|---|
| 🟢 Fresh | 1-15 | `#2ecc71` |
| 🟡 Warm | 16-30 | `#f1c40f` |
| 🟠 Hot | 31-45 | `#e67e22` |
| 🔴 Danger | 46+ | `#e74c3c` |

Zone transitions into red fire the chime exactly once per red entry
(see `makeRedZoneChime` — re-arms when leaving red).

## Countdown UI

`aimg-qe-call` returns `usage: {remaining, cap}` in 200 responses. The
widget exposes it on hover (`"X/Y verifies"`). Caller does not need to
render countdown separately.

## Copy locks (do not edit without Solon)

- Carryover title: *"Let's start a fresh thread to maintain quality"*
- Footer: *"AI can make mistakes please double-check all responses"*
- Cap-exceeded title: *"Daily cap reached"*
- Platform-pause title: *"Service paused until UTC midnight"*

## What this does NOT include

- The real Chrome extension manifest/background script — lives at
  `~/Desktop/mem-chrome-extension/` and is wired up by Solon when the
  `AIMG_SUPABASE_SERVICE_KEY` + `OPENAI_API_KEY` blockers from the
  tier-router README clear.
- Paddle purchase flow for the upsell primary button — that's the
  merchant-stack ("Ploutos") track, not this CT.
- Thread-state persistence across tabs — caller owns that.

## Test plan

`npm test` runs 21 integration cases covering:
- tier-router-client: 200 / 402 / 429 / non-JSON 502 / provider_error / constructor guards / endpoint URL
- rate-limit-middleware: local cap precheck, platform-pause cache, usage shape normalization, in-flight dedup, token-bucket pacing, `reset()`, `getState()`
- aimg-client: zone boundaries 1/15/16/30/31/45/46, 50-call run with red-zone modal on 46th, 402 upsell modal, 429 pause banner, `resetThread()` re-arms

See `tests/README.md` for the shim architecture (mock-supabase.js + mock-dom.js, zero deps).

## Grading block (CT-0414-09 Item 1)

- **Method:** Perplexity sonar-pro adversarial review 2026-04-15 + self-graded vs §13.7 Auditor rubric.
- **Why this method:** Slack Aristotle path not yet live (pending BATCH_2FA_UNLOCK); Perplexity direct API is the §12 fallback per routing priority.
- **Perplexity grade:** A (0 blocking issues, 3 non-blocking recommendations: add jitter to waitForToken, optional logging hook, in-code comments — deferred as nice-to-have, do not block ship).
- **Scores:** Correctness 9.5 · Completeness 9.4 · Honest scope 9.6 (edge fn cap is still source of truth, middleware is cache + pacing only) · Rollback 9.6 (additive module + tests; removing leaves extension-client at pre-ship state) · Fit with harness patterns 9.5 (zero-dep ES modules, `node --test`) · Actionability 9.5 · Risk coverage 9.4 (race-safety verified by dedup test, TTL cleanup, pause cache bounded) · Evidence quality 9.5 (21/21 tests pass, Perplexity adversarial review attached) · Internal consistency 9.5 · Ship-ready 9.3 (code only, no deploy — blocked on `AIMG_SUPABASE_SERVICE_KEY` + `SUPABASE_ACCESS_TOKEN`).
- **Overall:** 9.48 **A**.
- **Decision:** promote to active; revisit for re-grade when Slack Aristotle path comes online.
