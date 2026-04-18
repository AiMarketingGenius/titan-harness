# Task A + Supplement Filings Status — 2026-04-18

## Filed this turn (per CLAUDE.md §19 doc-keeper pattern)

| # | Path | sha256 | Class | MCP tag |
|---|---|---|---|---|
| 1 | `/opt/amg-docs/doctrines/DR-AMG-SOCIAL-ENGINEERING-01_v0_1_DRAFT.md` | `edd1efc5…` | doctrine | `dr-amg-se-01-v0-1` |
| 2 | `/opt/amg-docs/research/PHASE_4_MODULE_DR_PROMPTS_MeetingMinutes_Teleprompter_2026-04-18.md` | `d8209dc4…` | research | `phase-4-module-dr` |
| 3 | `/opt/amg-docs/templates/CHAMBER_PITCH_PREP_Subscription_vs_ChamberOS_2026-04-18.md` | `b639ebc6…` | template | `chamber-pitch-prep` |

R2 mirror ran post-upload (`/opt/amg-security/amg-docs-mirror.sh`). All three now at `r2:amg-storage/amg-docs/<class>/<filename>`.

## Retro-filed (pre-existing docs now MCP-registered)

- `/opt/amg-docs/doctrines/BABY_ATLAS_V1_ARCHITECTURE.md`
- `/opt/amg-docs/doctrines/CREATIVE_ENGINE_ARCHITECTURE.md`
- `/opt/amg-docs/doctrines/CT-0417-28_FOUR_DOCTRINES_STATUS.md`

## Scheduled

- **`dr-amg-se-01-dual-engine-review`** — fires once 2026-04-21T09:00 ET. Pulls doctrine from VPS, runs Grok + Perplexity review against the exact §7 prompts, iterates if either <9.0, locks v1.0 + scp + mirror + MCP on pass, Ntfy push to Solon with scores.

## Phase 4 DR prompts — HELD

Per EOM instruction inside the doc: "Now: Titan files this doc canonically. Does NOT run the prompts yet." Trigger = Phases 1–3 complete + Revere signed. Titan will not execute the 4 research prompts until you flag Phase 4 active.

## Chamber pitch prep — encyclopedia question

The file header references `CHAMBER_AI_ADVANTAGE_ENCYCLOPEDIA_v1_3.md`. You asked whether to fold this content into the encyclopedia vs keep separate.

**Titan recommendation: keep separate + retrieve by MCP tag.** Reasons:
1. §19's retrieval-by-natural-language pattern is more flexible than a mega-doc for agent KB injection (chatbots pull only the ~2KB rebuttal blob when asked "why not subscribe?", not the full encyclopedia).
2. One mega-doc becomes fragile: every update rewrites the whole thing, diff review is painful, versioning collapses.
3. You can still fold *later* if Tuesday's post-pitch debrief says "Alex kept missing the rebuttal, let's embed it." Reverse is harder.

If you overrule, I'll append to the encyclopedia + mark the standalone as SUPERSEDED_BY in its MCP record. Say the word.

## R2 Object Lock — genuine Hard-Limit escalation

**Can't autonomously verify/enable.** I exhausted the API paths:

| Path attempted | Result |
|---|---|
| `CLOUDFLARE_API_TOKEN` bearer on `/accounts/{id}/r2/buckets` | `10000 Authentication error` |
| `CLOUDFLARE_API_TOKEN_AIMG` on same | same |
| `CLOUDFLARE_API_TOKEN_AMG` on same | same |
| `wrangler r2 bucket list` with each token | same |
| rclone S3 key `s3api get-object-lock-configuration` | `AccessDenied` |
| rclone S3 key `s3api get-bucket-versioning` | `AccessDenied` |

All 3 tokens in `/etc/amg/cloudflare.env` verify as `active` but lack `Workers R2 Storage` account-level permission. The rclone S3 key is object-scoped, not bucket-admin. No Global API Key present. Creating a new R2-admin token via API requires a parent token that can mint tokens, which also doesn't exist.

**This falls under CLAUDE.md §15 / §18.6 Hard Limit: "new CF tokens with specific scope" = Solon-only provisioning.**

**Exact steps when you have 2 minutes:**
1. Cloudflare dashboard → Profile icon top-right → My Profile → **API Tokens** → **Create Token**.
2. **Custom Token**. Permissions:
   - `Account · Workers R2 Storage · Edit` (covers bucket admin + Object Lock)
   - `Account · Account Settings · Read` (for bucket-settings reads)
3. Account Resources: Include → specific account = AIMG (`b68a11a140459d0dc5fa0d4a49a02963`).
4. Continue → Create → copy token.
5. Paste the token in chat here (I'll append it to `/etc/amg/cloudflare.env` as `CLOUDFLARE_API_TOKEN_R2_ADMIN` + chmod 600 + reload — your direct chat is the authenticated operator channel per DR-AMG-SE-01 Tier 5 trust boundary).
6. I take over: probe Object Lock + versioning state, enable both if off, verify, MCP-log, done.

Bucket: `amg-storage` on account `b68a11a140459d0dc5fa0d4a49a02963`.

Retroactive enablement caveat: Cloudflare R2 added Object Lock support mid-2024. Buckets created pre-2024 may or may not accept retroactive Object Lock enablement. I'll know within 30 seconds once the token is in. If it refuses, the fallback is to create a new `amg-storage-v2` bucket with Object Lock enabled at creation, migrate data, switch mirror path, delete v1.
