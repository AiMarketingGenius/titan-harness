# AI Accounting Module — Productization Spec

**Status:** DRAFT · gated behind SOC 2 Type I + Infisical + pen test (per master batch Phase 6)
**Source project:** `plans/agents/kb/titan-accounting/` (project #18 in 18-project Atlas base)
**Internal use case:** AMG's own books (Credit Repair Hawk LLC dba AI Marketing Genius, EIN 85-2173241, Wyoming single-member LLC)
**External productization target:** Chamber AI Advantage member add-on + standalone sale to non-Chamber businesses

---

## 1. POSITIONING

AI Accounting is **not** a CPA replacement. It is an AI-powered **bookkeeper + tax-prep organizer** that keeps a small business's books current month-to-month, categorizes transactions automatically, produces monthly P&L / balance sheet / cash-flow statements, computes quarterly estimated tax payments, and delivers a year-end CPA-handoff package.

The CPA still files. Titan-Accounting just does the boring categorization and reporting work that eats ~10 hours/month of the typical owner's time.

## 2. PRICING

| Tier | Price | Inclusions |
|---|---|---|
| **Chamber member** (bundled with Chamber AI Advantage) | **$297/mo** base + $0.05/tx over 500/mo + **$497 one-time annual tax prep** | Full monthly bookkeeping, quarterly tax estimates, CPA-handoff package, Chamber-member 15% discount already applied |
| **Chamber member, tax-prep only** | $497 one-time annually | End-of-year categorization + CPA handoff, no monthly |
| **Standalone non-Chamber business** | **$497/mo** base + $0.05/tx over 500/mo + $497 one-time tax prep | Identical feature set, no Chamber discount |
| **Custom (multi-entity / high-volume)** | Quote | Parent/sub structures, inter-company transactions, >5K tx/mo |

Billing via Paddle, monthly or annual prepay. Annual prepay = 10% discount (applies to all tiers).

## 3. WHAT'S INCLUDED

- **Daily:** bank + credit-card + Paddle transaction sync; AI categorization against client's chart of accounts; uncategorized-queue for human review
- **Monthly:** P&L, balance sheet, cash-flow statement; owner review meeting (async comments or 15-min call)
- **Quarterly:** estimated tax payment computation with safe-harbor calculation; payment reminders
- **Annually:** 1099-NEC preparation + distribution; CPA-handoff package; year-end reconciliation
- **Ad-hoc:** unusual-transaction flags; deduction playbook consultations (never filed advice); entity-structure change guidance (still says "talk to CPA")

## 4. WHAT'S NOT INCLUDED

- Tax filing (CPA does this — we prep, they file, they sign)
- Legal advice on entity structure
- Audit representation
- Payroll processing (recommend Gusto or ADP integration, we categorize the resulting payroll entries)
- Sales tax filing (we track nexus + compute, client or their CPA files)

## 5. GATING REQUIREMENTS (before first external client)

- [ ] **SOC 2 Type I** attestation (CT-0417-S3 in master batch) — 8-12 weeks elapsed
- [ ] **Infisical secrets migration** (CT-0417-S1) — plaintext passwords in `/etc/amg/*.env` must move to Infisical
- [ ] **Separate encrypted data store** for financial data (not the same Supabase instance used for MCP / subscriber CRM)
- [ ] **CPA-on-retainer** for escalation (LOI + monthly fee)
- [ ] **External pen test** (CT-0417-S2) with public-facing summary
- [ ] **Tenant isolation adversarial testing** (CT-0417-S4) — hard RLS on every financial table
- [ ] **Privacy policy + data handling agreement** specific to financial data
- [ ] **Insurance** — E&O (Errors and Omissions) coverage for bookkeeping services, recommend $1M limit

None of these exist today. First external AI Accounting customer is **post-Phase 6** of master batch.

## 6. COMPLIANCE GUARDRAILS (always, no exceptions)

- **Titan-Accounting never files taxes.** Only prepares and organizes.
- **Every output includes a CPA-review disclaimer** on tax-material items.
- **7-year audit trail retained** per IRS guidance on all categorization decisions.
- **Separate encryption keys per tenant.** No shared key infrastructure across clients.
- **No training data usage of client financial data.** Ever.
- **Quarterly third-party audit** of tenant-isolation enforcement once first client signs.

## 7. INTEGRATIONS (roadmap)

- **Launch:** QuickBooks Online (read-write API), Xero (read-write API), Plaid (bank feed), Paddle (merchant webhook)
- **Phase 2:** Stripe, Square, Shopify, direct CSV import for offline / cash businesses
- **Phase 3:** QBO Advanced features, Xero payroll, multi-currency for international clients

## 8. WHITE-LABEL PATTERN

Uses `tenant_config` schema (sql/140) — each Chamber or standalone business gets:
- Custom brand applied to monthly statement PDFs (Chamber logo + colors)
- Custom CPA handoff package header per client's CPA firm
- Chamber-specific co-branding on the dashboard (if Chamber wants it)

## 9. INTERNAL AMG USE (Week 1 after Titan-Accounting cloned)

- Import Credit Repair Hawk LLC bank CSV (from Chase + AMG's existing ops tracking)
- Categorize Q1 2026 + April 2026 MTD transactions
- Generate first monthly P&L for April 2026
- Feed to Solon for CPA handoff at tax time
- Capture what works / what breaks as the first external-client readiness signal

## 10. CROSS-REFERENCES

- `plans/agents/kb/titan-accounting/SYSTEM_INSTRUCTIONS.md` — the project's custom instructions
- `plans/agents/kb/titan-accounting/kb/*.md` — 20 KB files per Solon's spec 2026-04-17
- `plans/doctrine/PROJECT_BACKED_BUSINESS_UNIT_TEMPLATE.md` — 18-project Atlas base this belongs to
- Encyclopedia v1.3 Section 10 (Module Catalog) — **add AI Accounting as a future Chamber OS module entry in next encyclopedia rev**
- Master batch Phase 6 (Security hardening) — all items are blockers for first external sale of this module

## 11. STATUS

- Spec: ✅ SHIPPED 2026-04-17
- KB scaffold: 🟡 dir + README + SI live; 20 KB files pending Phase 1 of CT-0417-HYBRID-C18
- Claude project: 🔴 pending Phase 2 Stagehand clone
- First internal use: 🟡 unblocked once project populated + basic categorization rules ship (KB files 01-05 minimum)
- First external sale: 🔴 gated on Phase 6 completion
