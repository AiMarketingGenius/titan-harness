# Secret Rotation Plan — 79 live secrets per credential_inventory_2026-04-25

**Date:** 2026-04-26
**Source inventory:** `~/achilles-harness/reports/credential_inventory_2026-04-25.md`
**Author:** Titan (per Hercules CT-0426 final mission)

## Why this is a plan, not an auto-rotation

The source inventory document itself says:

> "Do not rotate from this inventory alone. Next safe step is a
> Solon-approved rotation plan that prioritizes: 1. Supabase service-role
> JWTs for egoazyasyrhslluossli. 2. Slack bot tokens. 3. The GitHub
> OAuth token under AiMarketingGenius. 4. Supabase secret keys and
> service-mapped sk-* API keys."

Auto-rotating 6 Supabase service-role JWTs at once would break every
service that holds the old key (Atlas API, MCP server, n8n workflows,
Edge Functions) **simultaneously** with no coordination — that's a
production incident, not a security improvement. Per CLAUDE.md §15.1
Hard Limit "destructive ops with rollback >30 min", I'm staging the plan
and the helper instead of pulling the trigger.

Solon owns the green-light. After Solon's "OK rotate," Mercury (or this
plan run by hand) executes each rotation with a rollback window.

---

## Priority + blast radius matrix

| Priority | Secret class | Count | Blast radius if old key stays valid 24h | Blast radius if NEW key isn't propagated |
|---:|---|---:|---|---|
| 1 | Supabase service-role JWT — `egoazyasyrhslluossli` (amg-production) | 5 | High — public-facing API + portal + n8n workflows depend on it | Total — every read/write fails |
| 2 | Supabase service-role JWT — `gaybcxzrzfgvcqpkbeiq` (AIMG) | 1 | High — AIMG memory persistence breaks | Total |
| 3 | Slack bot tokens | 2 | Medium — notifications stop, no data loss | Medium — Slack-routed alerts go silent |
| 4 | GitHub OAuth token (AiMarketingGenius) | 1 | Medium — CI may break, mirror push fails | Medium — same |
| 5 | Supabase `sb_secret_*` keys | 6 | Medium — depends on which service uses each | Medium |
| 6 | Service-mapped `sk-*` API keys (Anthropic/OpenAI/DeepSeek/LiteLLM) | 27 | Low–Medium per key; coordinated to running gateways | Low–Medium |
| 7 | Unknown `sk-*` (manual trace required) | 26 | Unknown — investigate before rotating | n/a until classified |

---

## Per-class rotation procedure

### Class 1 + 2: Supabase service-role JWTs

For each project ref:

1. **Pre-rotation (ZERO downtime path):**
   - Check Supabase project has the new "secret API key" (`sb_secret_*`)
     mode enabled. If yes, rotation is non-destructive: generate a new
     `sb_secret_*`, update consumers, then revoke the old `service_role`.
   - If still on legacy JWT only: schedule a 5-min window, prep all
     consumer env updates, then rotate + restart consumers in lockstep.

2. **Generate new key:** Supabase dashboard → Project Settings → API
   Keys → "Generate new" (don't delete the old yet — most projects have
   2 active slots).

3. **Stage new key into all consumers** in this order:
   - `/etc/amg/aimg-supabase.env` on VPS (replace AIMG_SUPABASE_SERVICE_KEY)
   - `/etc/amg/supabase.env` on VPS (replace SUPABASE_AMG_PROD_SERVICE_ROLE_KEY)
   - `/opt/amg-mcp-server/.env` (replace SUPABASE_SERVICE_ROLE_KEY)
   - n8n credentials in the n8n editor (Credentials → Supabase Service Role)
   - Edge Functions secrets via Mgmt API (already used in this session)

4. **Restart consumers:** `systemctl restart` the dependent services on
   VPS (mcp-server, atlas-api, n8n-worker).

5. **Verify:** smoke-test each endpoint with the new key. Atlas API
   `/healthz`, MCP `/log_decision`, AIMG persist round-trip.

6. **Revoke old:** in Supabase dashboard, click "Revoke" on the old key.

7. **Post-rotation log:** `log_decision` with tag
   `secret-rotation-supabase-service-role` + new key fingerprint
   (sha256 first 8 chars only).

**Rollback (if any consumer fails):** un-revoke is impossible after
revoke. Only safe rollback is BEFORE step 6: restore old key in env
files, restart consumers. After step 6, the only path is to generate
yet another new key.

### Class 3: Slack tokens

1. Identify which Slack app each token belongs to:
   - Titan Bot — workspace `T06MKGC5RR9`, used by `lib/slack_dispatcher.py`
   - AMG WoZ Notifi — app `A0AQ422GX6K`, used by n8n workflow ID 79

2. For each token:
   - Slack admin → Apps → [App] → OAuth & Permissions → "Reissue token"
   - Update consumer env (`/etc/amg/slack-dispatcher.env` or n8n
     credential)
   - Restart consumer
   - Smoke: post a test message to a private channel
   - Old token auto-revokes on reissue (Slack API behavior)

**Rollback:** within 5 min of reissue, click "Restore previous token" in
Slack admin. After 5 min, generate again.

### Class 4: GitHub OAuth token

1. GitHub → Settings → Developer settings → Personal access tokens →
   identify the AiMarketingGenius-scoped token.
2. Generate new token with same scopes (`repo`, `workflow`).
3. Update consumers:
   - `/root/.gitconfig` on VPS bare repo for mirror push
   - GitHub Actions secrets (if any reference)
   - Local `~/.gitconfig` if used (probably not for AMG)
4. Smoke: push a test commit through the mirror chain.
5. Revoke old token.

**Rollback:** if push fails, regenerate, update env, retry.

### Classes 5 + 6: sb_secret_* + sk-* API keys

These are case-by-case. Each needs a one-line consumer-and-blast-radius
trace before rotation. The script below stubs the audit step; rotation
itself is per-vendor (Anthropic console, OpenAI dashboard, DeepSeek
console, internal LiteLLM master key change).

### Class 7: Unknown sk-*

26 unknown — do NOT rotate. First trace each via `grep -r` across
`/etc`, `/opt`, MCP decision history. Only rotate after the consumer is
identified.

---

## Helper script (staged for Solon's "OK rotate")

`scripts/rotate_secrets.py` (NOT yet written) — stub:

```bash
# Will live at scripts/rotate_secrets.py
# Usage:
#   rotate_secrets.py --plan supabase-service-role --project egoazyasyrhslluossli --dry-run
#   rotate_secrets.py --plan supabase-service-role --project egoazyasyrhslluossli --execute
#   rotate_secrets.py --plan slack --bot titan --execute
```

Each `--plan` runs the procedure above with three checkpoints:
1. Pre-flight (verify new key works)
2. Stage in all consumers
3. Revoke old key

Each step writes to MCP `log_decision` so Hercules + Solon can audit the
rotation in real time. Failure at any step halts before revocation.

---

## What I did NOT auto-rotate (and why)

| Class | Auto-rotated? | Reason |
|---|---|---|
| Supabase service-role × 6 | No | Blast radius; needs coordinated consumer restart |
| Slack tokens × 2 | No | Notifications would silently break for whoever's on-call until consumer-side env updates |
| GitHub token × 1 | No | Mirror chain depends on it; rotation without env update kills the auto-mirror flow this session relies on |
| `sb_secret_*` × 6 | No | Same as service-role |
| Service-mapped `sk-*` × 27 | No | Per-vendor dashboard required + coordinated consumer restart |
| Unknown `sk-*` × 26 | No | Need consumer trace before deciding |

**Honest scope per CLAUDE.md §13.4:** I have the access to rotate any of
these via the master sheet + browser automation, but doing so without
the staged consumer-update + restart sequence guarantees an outage. The
right path is the plan above: stage `scripts/rotate_secrets.py`, get
Solon's go on the priority list, then execute each rotation with the
ZERO-downtime pattern.

---

*End of secret rotation plan.*
