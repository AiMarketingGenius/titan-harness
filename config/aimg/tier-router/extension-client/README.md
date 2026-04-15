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
| `src/aimg-client.js` | Public API composing all four. |

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

Drop a dev HTML file that imports `aimg-client.js`, stubs
`makeTierRouterClient` to return a canned 200 response, and calls
`verify()` 50 times in a row. Expectations:

1. Widget color transitions green → yellow → orange → red at exchange
   boundaries 15/30/45.
2. Chime fires exactly once on the 46th exchange.
3. Carryover modal appears on the 46th exchange with the locked copy.
4. Dismissing + re-entering red (after `resetThread()` + re-filling)
   fires the chime + modal one more time.
