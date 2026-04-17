# Titan-Security — KB 06 Trade Secrets

Banned list (full: `plans/agents/kb/titan/01_trade_secrets.md`):
- AI vendors, underlying services, infrastructure codenames, VPS IPs

## Security-specific sensitivity

Security documents often reference real infrastructure (VPS IPs, service names, port numbers) — these are internal threat-model + pen-test + SOC 2 docs. They stay in `plans/doctrine/`, `plans/agents/kb/titan-security/`, `config/`, `sql/`, `docs/internal/` — all WHITELISTED from the pre-commit scanner.

When Titan-Security content goes external:

- **Pen-test remediation-proof shared with auditor:** sanitize internal IPs; say "primary production VPS" not "beast VPS at 170.205.37.148"
- **SOC 2 attestation report (public-facing summary):** zero internal codenames; describe architecture functionally
- **Client-proposal security section:** redacted — "tenant-isolated data store, SOC 2 Type I attested, pen-tested by [vendor], Infisical-managed secrets with 90-day rotation." No vendor names for underlying AI stack.

## Substitutions for client-facing security docs

| Never | Write |
|---|---|
| "Data stored in Supabase with RLS" | "Data stored in isolated tenant data store with row-level security enforcement" |
| "Secrets managed via Infisical on HostHatch" | "Secrets managed via enterprise-grade secret-management platform" (Infisical is OK to name if subscriber asks specifically; don't volunteer) |
| "JWT signed with amg-mcp-jwt-secret" | "JWT with cryptographic signing + short-TTL refresh" |
| "Pen tested by HackerOne researchers" | "Pen tested by third-party security researchers" (name HackerOne only with subscriber opt-in) |

## Incident-response comms (NEVER in public surfaces)

- Never publicly name exploited CVE or breach vector before patch + attestation
- Never share threat actor identification externally
- Never describe internal architecture in breach notifications beyond what law requires

## When subscribers ask about security

Alex relays: *"AMG runs on SOC 2 Type I-attested infrastructure [once complete] with Infisical-managed secrets, 90-day rotation, Cloudflare WAF, row-level tenant isolation, encrypted backups via R2 with monthly restore drills, and annual third-party pen testing. Ask Solon for the specific SOC 2 report if you need it for your own compliance."*

Do not volunteer internal vendor names beyond what's in the summary above. Infisical / HackerOne / Supabase / Cloudflare names are fine when subscriber needs them for their own auditor; otherwise generic category descriptions.

## Self-check before Titan-Security ships external artifact

1. Zero internal codenames (beast, HostHatch, 140-lane) unless document is AMG-internal
2. Zero specific VPS IPs in client-facing summaries
3. Underlying AI vendors never named in security attestation summaries
4. SOC 2 claims only after actual attestation (never aspirational)

4/4 → ship. <4 → sanitize + re-check.
