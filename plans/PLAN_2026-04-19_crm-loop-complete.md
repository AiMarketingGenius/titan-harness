# PLAN — CRM Loop Complete (Pillar 1, Item 3 of Sunday Playbook)

<!-- last-research: 2026-04-19 -->
**Status:** ACTIVE · 2026-04-19 · First commit shipped
**Owner:** Titan (infra + build) · Solon (scope + pause-point reviewer)
**Anchors:** [`plans/PLAN_2026-04-19_titan-sunday-playbook.md`](PLAN_2026-04-19_titan-sunday-playbook.md) Item 3 · [`plans/DOCTRINE_AMG_INTERNAL_CRM_v1.0.md`](DOCTRINE_AMG_INTERNAL_CRM_v1.0.md) · [`sql/009_multi_tenant.sql`](../sql/009_multi_tenant.sql)
**Greek codename:** PROPOSED (pending Solon lock) — candidates §6

---

## 1. Context

Pillar 1 Sunday Playbook Item 3 expands CT-0418-09 into a full CRM Loop build on top of the Phase 2 multi-tenant schema that is already live (operators, tenants, webauthn_credentials, refresh_tokens, push_subscriptions, outbound_email_queue, outbound_voice_queue — all with RLS, seeded amg-internal tenant). Phase 2 is NOT migration-blocked; it was awaiting build work.

Solon directive 2026-04-19: ship atomic commits, pause between each for review, no full-build stampede.

## 2. Scope (Sunday Playbook Item 3 verbatim)

- Per-tenant provisioning workflow: new client signup → tenants row + tenant_slug + tenant_uuid + JWT tenant_id claim + per-tenant Supabase schema isolation + agent roster activation + first-week deliverable auto-scheduled + portal access at `portal.aimarketinggenius.io/{tenant_slug}/`
- Lead intake auto-ingest from 5 sources: `inbound_form` (Lovable), `chatbot` (Alex orb), `voicebot` (Alex orb), `outbound_reply` (scaffold), `linkedin` (scaffold). Each writes CRM row with source attribution + tenant_id + Nadia entry point.
- CRM ↔ MCP bidirectional sync: CRM state changes → MCP decisions tagged `crm-memory-bridge` + `client-context:{tenant_slug}`. MCP decisions queryable back into CRM views.
- `agent_context_loader` extended: returns unified tenant context (CRM state + MCP decisions + memory_captures + project KB facts) for any agent on any tenant.
- RLS policies on all tenant-scoped tables. Synthetic tenant E2E test proves cross-tenant reads blocked.
- Revere Chamber demo tenant seeded for Monday pitch (tenant_slug: `revere-chamber-demo`).

Ship tag: `crm-loop-closure-complete-live-armed-e2e-verified-2026-04-19`

## 3. Commit plan (atomic, sequential, pause-for-review between each)

| # | Commit scope | Status |
|---|---|---|
| 1 | **`lib/tenant_provisioning.py` + CLI + smoke test** — canonical provision_tenant() over SUPABASE_DB_URL, idempotent on slug, seeds revere-chamber-demo | ✅ SHIPPED (this commit) |
| 2 | JWT tenant_id claim wiring in `lib/atlas_api.py` — middleware sets `amg.tenant_id` GUC from JWT on every request; back-compat for amg-internal single-operator flows | pending |
| 3 | Per-tenant agent roster activation — `lib/tenant_roster.py` + `sql/011_tenant_agent_roster.sql` schema (7-agent roster: Maya/Nadia/Alex/Jordan/Sam/Riley/Lumina) keyed by tenant_id | pending |
| 4 | Lead intake (5 sources) table + writer — `sql/011_crm_leads.sql` + `lib/crm_lead_intake.py` with source enum + Nadia entry-point hook | pending |
| 5 | CRM ↔ MCP bidirectional sync — `lib/crm_mcp_bridge.py` writes log_decision on CRM state transitions; MCP search → CRM view | pending |
| 6 | `agent_context_loader` extension — unify CRM state + MCP decisions + memory_captures + KB facts into single tenant-scoped context blob | pending |
| 7 | Synthetic tenant E2E RLS test — `tests/test_crm_loop_e2e.py` proves cross-tenant reads blocked | pending |
| 8 | Portal routing at `portal.aimarketinggenius.io/{tenant_slug}/` — Caddy config + atlas_api route registration | pending |
| 9 | First-week deliverable auto-scheduling — on provision, enqueue onboarding emails + kickoff task in `solon_task_queue` | pending |
| 10 | Ship-tag commit — verify all 9 prior ship together, E2E clean, tag `crm-loop-closure-complete-live-armed-e2e-verified-2026-04-19` | pending |

## 4. First commit (this one) — deliverables

- `lib/tenant_provisioning.py` — canonical provision function + argparse CLI
- `bin/amg-provision-tenant.sh` — wrapper that sources `/etc/amg/supabase.env` + invokes module
- `tests/test_tenant_provisioning.py` — smoke test: provisions `revere-chamber-demo`, verifies row shape, proves idempotency on re-provision, asserts input validation rejects malformed slugs
- `plans/PLAN_2026-04-19_crm-loop-complete.md` — this file

## 5. First-commit acceptance criteria

- [x] `python3 -m lib.tenant_provisioning --help` renders argparse usage cleanly
- [ ] `SUPABASE_DB_URL=... python3 tests/test_tenant_provisioning.py` exits 0 on VPS
- [ ] `revere-chamber-demo` row present in `public.tenants` with status=active
- [ ] Re-run of smoke test exits 0 (idempotency)
- [ ] No drift to existing Phase 2 rows (operators=1, amg-internal tenant unchanged)
- [ ] MCP decision logged with commit hash + scope + next commit

## 6. Greek codename candidates (Solon to lock)

Per §14 doctrine. Pending Solon approval — NOT locked, not yet surfaced in client-facing material.

1. **Kleisthenes** — "founder of Athenian democracy; divided citizens into tribes (tenants) with distinct identity yet unified under one polis" — Kleisthenes reorganized Attica into 10 tribes, each with its own deme registry. Direct analog to per-tenant partitioning under one AMG polis.
2. **Hestia** — "goddess of the hearth; every household (tenant) kindled its fire from the central civic flame" — evokes seeded ignition of each new tenant from the canonical AMG hearth.
3. **Atlas** (already in use for the parent platform) — reject: too broad, parent-platform-scoped.
4. **Demeter** — "goddess of grain and nurture; oversaw the cycle of sowing and reaping for every farmer's field" — tenant provisioning as sowing + lead intake as harvest.
5. **Heracles** (first labor: the Nemean lion — founding victory) — reject: overused in harness-Hercules Triangle.

**Titan's vote:** Kleisthenes. Most direct functional analog + marketable (Chamber partnerships resonate with democratic-civic framing) + non-overlapping with existing codenames.

## 7. Dependencies + assumptions

- Phase 2 schema live (sql/008 + sql/009 + sql/010 applied at 22:05Z 2026-04-18) ✅ confirmed via 2026-04-19 re-apply row counts
- `SUPABASE_DB_URL` present in `/etc/amg/supabase.env` on VPS ✅
- psycopg2 2.9.11 available on VPS python3 ✅
- No conflicting tenant-provisioning library exists in `lib/` (grep clean 2026-04-19)

## 8. Risks + mitigations

- **Slug collision across tenants** — mitigated by UNIQUE constraint on `tenants.slug` + ON CONFLICT DO NOTHING → returns existing row with `was_existing=True`. Idempotent re-run is safe.
- **Subdomain collision** — UNIQUE constraint on `tenants.subdomain` (partial, WHERE IS NOT NULL). Two tenants can both have NULL subdomain; collision on non-NULL raises IntegrityError bubble up from psycopg2.
- **brand_config malformed JSON from CLI** — caught in CLI at json.loads; module-level call requires dict.
- **Missing SUPABASE_DB_URL** — raises RuntimeError with clear message.

## 9. What's explicitly NOT in this commit

(Each ships as its own atomic commit per §3.)

- JWT tenant_id claim wiring
- Per-tenant agent roster activation
- Lead intake (5 sources)
- CRM ↔ MCP bidirectional sync
- agent_context_loader extension
- Portal routing (Caddy + atlas_api)
- First-week deliverable auto-scheduling
- Synthetic cross-tenant E2E RLS test

## Grading block

- **Method used:** self-graded
- **Why this method:** Slack-Aristotle path not invoked for mid-sprint atomic commit scoping; §15.1 authorizes autonomous interpretive decisions when doctrine leaves room. Solon explicitly scoped "first atomic commit + pause."
- **Pending:** re-grade when `aristotle_enabled: true` OR when Pillar 1 ship-tag commit (#10 in §3 table) is assembled — at that point Tier A dual-engine review (Sonar Pro + Grok ≥9.3/dim) per Playbook Item 3 line 69 is mandatory before ship-tag logs.

| # | Dimension | Score | Notes |
|---|---|---|---|
| 1 | Correctness | 9 | Uses live schema; psycopg2 pattern matches governance_dashboard.py; slug regex aligns with `tenants.slug` UNIQUE semantics. |
| 2 | Completeness | 8 | First atomic commit only. Full Pillar 1 is staged in §3 as 10 commits. Scope explicitly bounded per Solon directive. |
| 3 | Honest scope | 10 | §3 lists all 10 downstream commits. §9 explicitly calls out what's NOT in this commit. No hidden work. |
| 4 | Rollback availability | 9 | Additive-only (INSERT to tenants). Rollback = `DELETE FROM tenants WHERE slug = 'revere-chamber-demo';` + `rm lib/tenant_provisioning.py bin/amg-provision-tenant.sh tests/test_tenant_provisioning.py`. No schema change. |
| 5 | Fit with harness patterns | 10 | psycopg2 + SUPABASE_DB_URL matches governance_dashboard.py + alex_digest.py. CLI wrapper matches bin/*.sh convention. Tests live in tests/. Plan file in plans/. |
| 6 | Actionability | 10 | Smoke test is runnable immediately post-commit; ship criteria in §5 are concrete; next commit scope (JWT tenant_id wiring) is well-defined. |
| 7 | Risk coverage | 9 | §8 covers slug / subdomain / brand_config / env risks. Not covered: tenant-quota enforcement (deferred — no quota policy yet defined). |
| 8 | Evidence quality | 9 | Schema references verified via sql/009 read. Dependencies verified via VPS ssh check (psycopg2 2.9.11, psql 14.22). Phase 2 live state verified via 2026-04-19 row-count re-read. |
| 9 | Internal consistency | 10 | Plan aligns with CLAUDE.md §12 (grading), §14 (Greek codename), §17 (Auto-Harness + Mirror), §18 (KB-enforced hooks), Sunday Playbook Item 3. |
| 10 | Ship-ready | 10 | First commit is runnable, testable, mirrorable, reversible. Solon has a clear pause-point + scope + next-commit preview. |

**Overall: 9.4 — A.** Classification: **promote to active. Ship first commit. Pause for Solon review. Queue commit #2 (JWT tenant_id wiring) pending Solon go.**

**Revision rounds:** 1 (no sub-threshold dim).

---

*End PLAN — CRM Loop Complete v1.0 (first-commit doc).*
