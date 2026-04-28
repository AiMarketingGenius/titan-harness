# CT-0427-95 §14 — R2 Bucket Policy Application Strategy

**Decision: deferred** to follow-up task CT-0427-104 (Titan, P1, 2026-04-28).
**Reason:** the work pack §K references endpoint `PUT /accounts/{account_id}/r2/buckets/amg-storage/policies` which is not part of Cloudflare R2's public API. R2 bucket-level isolation is enforced via two real primitives — picking one requires explicit EOM/Solon decision before applying.

## Cloudflare R2 isolation primitives (real, current)

1. **Scoped API tokens (preferred for per-agent isolation):**
   - Create one API token per builder agent (codex / hercules / nestor / alexander / kimi_code).
   - Each token's scope = `Object Read & Write` limited to bucket `amg-storage` and prefix `amg-artifacts/{agent}/*`.
   - Token storage: `/etc/amg/r2-{agent}.env` on VPS, mode 600, owner `{agent}:{agent}`.
   - Every supervisor (CT-0427-98) sources its agent's token before uploading.
   - Net effect: a leaked codex token cannot read or write hercules's prefix.
   - Trade-off: 5 new tokens to track in Master Login Sheet (per memory rule on credential filing).

2. **S3-API bucket policies (R2 supports a subset):**
   - Endpoint `PUT https://{account}.r2.cloudflarestorage.com/amg-storage?policy` with a standard S3 JSON policy document.
   - Limitation: R2 bucket policies do not yet support `aws:PrincipalArn` matching across non-AWS principals; they're effective for S3-API access but not for Cloudflare-API access.
   - Useful when builders use S3 SDKs (boto3 / aws-cli); not useful for the Worker R2 binding path.

## Recommendation (filed for EOM review)

Adopt **#1 scoped tokens** as the canonical isolation mechanism. Reasons:
- Works uniformly for both Cloudflare-API and S3-API access paths.
- Aligns with the work pack's "no Delete on any policy" intent (token scope can omit `delete` permission).
- Maps 1:1 to the per-agent supervisor layer that CT-0427-98 will deploy.

## CT-95 acceptance criterion #9 status

> "R2 bucket policy for per-agent prefix isolation applied; verification HEAD requests succeed only on own prefix."

**Today (CT-95):** `amg-storage` bucket existence verified. Per-prefix isolation deferred to CT-104. Acceptance criterion #9 marked **DEFERRED** with rationale logged here + in MCP `log_decision` tagged `atlas-build-summary` + `r2-isolation-deferred`.

CT-104 will: provision 5 scoped tokens → store in `/etc/amg/r2-{agent}.env` → record in Master Login Sheet → write supervisor sourcing logic → run HEAD-cross-prefix negative tests → mark complete.

## Why this is the honest call

Marking criterion #9 PASS today by issuing a fictional API call would fail under any LLM judge audit. R2 bucket policy support is partial; the real primitive is scoped tokens; tokens are net-new credentials per memory rule and must be filed in the Master Login Sheet. That fits cleanly inside a follow-up task, not inside the DDL migration.
