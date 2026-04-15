# AIMG tier router — deployment guide

**CT-0414-09 ship artifact.** Implements AIMG TIER MATRIX FINAL LOCK
(2026-04-14, Solon directive). Single-model GPT-4o-mini across all
four tiers; API-side cap enforcement + platform cost ceiling + upsell
response on overage.

## Matrix (LOCKED — no further iteration)

| Tier | Price | Daily cap | Mo. cost/user (GPT-4o-mini @ ~$0.0002/call) | Margin |
|---|---|---|---|---|
| Free | $0 | 20 calls/day | ~$0.12 | loss (CAC) |
| Basic | $4.99 | 50 calls/day | ~$0.30 | 94% |
| Plus | $9.99 | 150 calls/day | ~$0.90 | 91% |
| Pro | $19.99 | 300 calls/day | ~$1.80 | 91% |

Platform ceiling: **$5/day hard, $3/day Slack alert, auto-pause until UTC midnight.**

## Files

- `supabase/functions/aimg-qe-call/index.ts` — Deno edge function. Routes per tier, enforces cap, returns countdown metadata for UI.
- `supabase/migrations/20260414_aimg_usage.sql` — `aimg_usage` table + `aimg_increment_usage(p_user_id, p_day, p_cost_usd)` RPC for atomic per-user daily counter.

## Required secrets (set before deploy)

In the AIMG Supabase project (ref `gaybcxzrzfgvcqpkbeiq`):

```bash
supabase secrets set OPENAI_API_KEY="sk-..."
supabase secrets set AMG_ADMIN_SLACK_WEBHOOK="https://hooks.slack.com/services/..."
# Optional overrides:
supabase secrets set AIMG_PLATFORM_DAILY_CAP_USD="5"
supabase secrets set AIMG_PLATFORM_DAILY_ALERT_USD="3"
supabase secrets set AIMG_COST_PER_CALL_USD="0.0002"
```

`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are auto-injected into edge functions.

## Deploy

```bash
# from titan-harness root (needs supabase CLI + project link to gaybcxzrzfgvcqpkbeiq)
supabase link --project-ref gaybcxzrzfgvcqpkbeiq
supabase db push --db-url "$AIMG_SUPABASE_DB_URL"     # applies migration
supabase functions deploy aimg-qe-call --project-ref gaybcxzrzfgvcqpkbeiq
```

## Chrome-extension integration

Replace any direct `api.openai.com` or `api.perplexity.ai` call in the extension with:

```js
const resp = await fetch(
  `${SUPABASE_URL}/functions/v1/aimg-qe-call`,
  {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${userSupabaseJWT}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id,
      memory_id,
      memory_content,
      operation: "verify",   // or "extract"
    }),
  },
);
const json = await resp.json();

if (resp.status === 402) {
  showUpsellPrompt(json.upsell);   // "Upgrade to Plus for 150/day"
} else if (resp.status === 429) {
  showPlatformPauseBanner(json.retry_after_utc);
} else {
  renderResult(json.result);
  renderCountdown(json.usage);     // "X/Y daily verifies remaining"
}
```

## UI/UX spec (unchanged — CT-0405-06 thread eaa777fa)

The tier router integrates with but does NOT replace the existing UI spec:

- **Thread Health meter** (in-product label) / **Hallucinometer** (marketing brand name). Left-edge vertical 8px→52px on hover. Zones 🟢 1-15 / 🟡 16-30 / 🟠 31-45 / 🔴 46+ exchanges.
- **2-tone ding-DING chime** at 40% volume plays ONCE on entering red. Not a siren (P-validated).
- **Extension toolbar badge states** reflect current zone.
- **Auto-carryover modal** wording: *"Let's start a fresh thread to maintain quality..."*
- **Footer**: *"AI can make mistakes please double-check all responses"*
- **Countdown**: *"X/Y daily verifies remaining"* shown next to the Thread Health meter.

These are extension-side (not edge-function-side). No change to their spec from this CT.

## Known blockers / must be provided by Solon

1. `AIMG_SUPABASE_SERVICE_KEY` — not present in `/root/.titan-env` or `/opt/n8n/.env` on VPS. Needed for `bin/aimg-preserve-baseline.sh` to export the 8-row Phase 1 evidence. Once available, drop it as:
   ```
   AIMG_SUPABASE_SERVICE_KEY=<key>  → /root/.titan-env
   ```
   Then: `bash /tmp/aimg-preserve-baseline.sh` (already uploaded).

2. `OPENAI_API_KEY` — not present in VPS env. Required before edge function will serve requests.

3. `users.tier` column on the AIMG users table — migration SQL comments include the `alter table` to add it if absent. Verify first with `\d+ public.users`.

## Rollback

```bash
supabase functions delete aimg-qe-call --project-ref gaybcxzrzfgvcqpkbeiq
# Revert migration:
supabase db reset   # DANGER: full schema reset — only use on staging
# Or hand-rollback:
# drop function public.aimg_increment_usage; drop table public.aimg_usage;
```

## Test plan

Before flipping extension traffic:

1. Deploy to staging Supabase project (or a throwaway). Hit `/functions/v1/aimg-qe-call` with a seed user_id, verify 200 response + countdown data.
2. Loop 21 calls to trigger cap (free tier). Expect `402 tier_cap_exceeded` with upsell payload.
3. Seed `aimg_usage` with `cost_usd_sum = 5.01` for today. Expect `429 platform_cost_ceiling` on next call + Slack alert.
4. Upgrade test user to `pro`, confirm 300/day cap applies.
