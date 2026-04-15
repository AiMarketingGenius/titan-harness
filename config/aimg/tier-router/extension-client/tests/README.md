# extension-client tests

Zero-dep integration tests for the AIMG tier-router extension-client.
Uses Node's built-in `node:test` runner + `node:assert/strict`. No jsdom,
no Jest, no Vitest.

## Run

```bash
cd config/aimg/tier-router/extension-client
node --test tests/
```

Or individually:
```bash
node --test tests/tier-router-client.test.js
node --test tests/rate-limit-middleware.test.js
node --test tests/aimg-client.test.js
```

## Coverage

| File | What it exercises |
|---|---|
| `tier-router-client.test.js` | 200 / 402 / 429 / non-JSON 502 / provider_error 502 / constructor guards / endpoint URL |
| `rate-limit-middleware.test.js` | local cap precheck, platform-pause cache, usage shape normalization, in-flight dedup, token-bucket pacing, `reset()`, `getState()` |
| `aimg-client.test.js` | zone boundaries (1/15/16/30/31/45/46), 50-call run triggers modal on 46th, 402 → upsell modal, 429 → pause banner, `resetThread()` re-arms |

## Shims

- `mock-supabase.js` — replaces `globalThis.fetch` with canned responses.
- `mock-dom.js` — provides minimal `document` / `window` / `AudioContext`
  so the widget + modal + chime modules can run under Node without jsdom.

## What tests do NOT verify

- Actual audio output (WebAudio graph is stubbed — tests verify oscillator
  construction, not listener experience).
- Real Supabase RPC semantics — the `aimg_try_increment` plpgsql function
  is validated by the SQL migration's own test suite, not here.
- Cross-tab thread state — caller owns that per the main README.
- Real network latency or Supabase rate-limit headers.

## Known limitation

Tests run sequentially because the fake DOM + mock `fetch` are global
singletons. Do not pass `--test-concurrency` > 1.
