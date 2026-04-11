# DOCTRINE — AMG Product Tiers + IP Protection

**Status:** CANONICAL — repo-visible product doctrine. Governs how AMG builds, prices, and protects client-facing deliverables across every SKU.
**Established:** 2026-04-11 (Solon Mega Directive Part 4, backfilled via Hercules Triangle)
**Also persisted at:** MCP memory `project_amg_product_tiers.md` + `feedback_ip_protection.md`
**Supersedes:** nothing. First formalization of the product ladder.

---

## 1. The three-SKU ladder

AMG has three distinct product SKUs. They must stay separated in positioning, pricing, sales funnels, and landing pages. Blurring them kills premium pricing because buyers anchor to the cheapest visible price.

### SKU 1 — AMG Subscription Plans
- **What it is:** pre-built 7-agent marketing workflows — "business in a box"
- **Sales motion:** self-serve funnel on `aimarketinggenius.io`
- **Buyer:** SMB owners who need marketing output without hiring staff
- **Delivery:** instant access, light-touch onboarding
- **Price posture:** entry-level, published pricing, monthly subscription
- **Role in portfolio:** runway funder + top-of-funnel lead source for SKU 2 + SKU 3

### SKU 2 — White-label / Agency layer
- **What it is:** agencies resell AMG plans (or AMG deliverables) under their own brand to their own clients
- **Sales motion:** application-gated channel partner page (not the same funnel as SKU 1)
- **Buyer:** marketing agencies, consultancies, MSPs that want to add AMG capability without building it
- **Delivery:** tenant isolation + branding customization + agency-side AM (account manager) seat
- **Price posture:** discount model on top of SKU 1 + minimum volume commitment + upgrade path to SKU 3 when the agency grows into full Atlas white-label
- **Current gap:** discount %, minimum volume, branding scope, contractual no-compete terms — all TBD, tracked on `RADAR.md` under "Product / Pricing doctrine"
- **Hard rule:** agencies selling AMG plans to do-it-yourself clients go on a bigger plan than agencies using AMG internally as a tool

### SKU 3 — Premium Custom AI Systems (Solon OS / Atlas builds)
The big-fish SKU. What Solon is actually promoting as the flagship.

#### SKU 3a — Atlas-as-template deploy
- **What it is:** AMG's existing infra template-pasted into the client's business; all their business units tied into AMG Atlas infra via tenant API
- **Client access:** UI + their own data only — they do NOT see prompt libraries, agent personas, orchestration code, or trade secrets
- **Delivery speed:** fast + repeatable + high margin — this is the **MRR workhorse**
- **Price posture:** mid-five to low-six figures setup + recurring monthly infra fee
- **Buyer:** businesses that want "the AMG engine running my company" without a bespoke founder-imprinted build

#### SKU 3b — Fully custom OS in client's identity
- **What it is:** Solon OS rebuilt around the client founder's personality and style (their "Oracle / Larry Ellison" imprint — a company-in-the-founder's-image OS)
- **Client access:** customization layer + their own identity-imprinted agents. Still NO rights to resell the OS pattern
- **Delivery:** significantly longer, custom per client, heavy discovery phase
- **Price posture:** six-figure entry minimum, enterprise contract, proprietary + non-reverseable, bespoke retainer
- **Buyer:** founders who want their own OS in their own image for their own company — the trophy SKU

**Pricing-floor hard rule:** SKU 3b must be priced meaningfully above SKU 3a. If 3b is priced too close to 3a, nobody buys 3a and margin collapses. A dedicated pricing DR should land before any SKU 3 landing page goes live.

---

## 2. IP protection — non-negotiable across every SKU

**Why:** Solon has said explicitly — we do not give the OS away for nothing, and we must not create competition for ourselves. Every client-facing deliverable (SKU 1, SKU 2, SKU 3a, SKU 3b) must be architected so the client's engineers CANNOT reverse-engineer, extract, or resell AMG's core IP.

### Technical architecture (enforced at build time)

1. **Tenant-API architecture, not copy-paste orchestration.** Client instances are tenants calling AMG's API on the VPS. They never receive a standalone copy of the orchestration code, prompt library, or agent persona definitions.
2. **Prompts + personas + knowledge bases stay server-side.** Kept behind API gates, never bundled into client deliverables or shipped as config files the client can inspect.
3. **Encrypted configs + no direct DB access.** Client tenants query their own data through AMG's API layer; they do not get direct Supabase/Postgres credentials.
4. **Sandbox boundaries.** Client tenant workloads are isolated from AMG's core runtime. A hostile client engineer inspecting their own tenant environment sees only their data + their UI + API response shapes, never AMG internals.
5. **Template scrubbing.** When deploying SKU 3a (Atlas-as-template), scrub all trade secrets from the template layer. The client's value is the live connection to AMG's infra, not the template code itself.

### Contractual architecture (enforced at sale time)

1. **No-resale clause** in every SKU 3 contract
2. **Non-reverse-engineering clause** in every SKU 2 + SKU 3 contract
3. **Non-compete within defined market** for SKU 2 white-label agencies
4. **IP ownership stays with AMG** for the OS pattern, orchestration logic, and prompt library, even when the customization layer is owned by the client (SKU 3b)

### Standing rule for new customer-facing surfaces

When designing any new customer-facing surface (proposal bot, voice orb, demo shell, Atlas frontend, iPhone PWA), assume a hostile engineer will inspect it — never expose prompts, agent names, or orchestration logic in client-readable paths. Even the `os.aimarketinggenius.io` demo shell (which is Solon's own, not client-facing) should be architected under this rule so the pattern carries into every downstream client deploy.

---

## 3. Pricing posture — never underprice

**Hard rule:** never price custom builds (SKU 3a or SKU 3b) low enough to create competition for AMG. This is a standing Solon directive.

- Custom builds compete with AMG's own subscription funnel if priced too low
- Custom builds compete with AMG's white-label agency channel if priced below SKU 2 + discount
- Custom builds compete with AMG's future enterprise sales if priced below the cost of a comparable in-house build team

**Floor-setting methodology:** before any SKU 3 quote goes out, the pricing engine (TODO — see `HERCULES_BACKFILL_REPORT.md §TODO.2`) must check:
1. Cost-plus floor (AMG infra + AMG labor + margin)
2. Competitor-displacement floor (what it would cost the client to hire + tool + integrate)
3. Value-share floor (AMG captures a defensible % of the economic value the OS delivers to the client)

The quoted price must sit at the **max** of the three floors, not the average.

---

## 4. How Titan applies this doctrine

When drafting any of the following, Titan must frame against this doctrine:

- **Offer docs, proposals, pricing calculators** → always three SKUs visible as distinct options, never blurred
- **Loom demo scripts, sales pages, landing copy** → Solon OS / Atlas (SKU 3) is the premium hero, subscriptions (SKU 1) are the entry point, white-label (SKU 2) is the channel partner track
- **Landing pages** → three separate pages + three separate funnels, not one collapsed funnel
- **Client onboarding flows** → tenant API isolation on day 1, no copy-paste orchestration
- **Client deliverable templates** → scrubbed of trade secrets, template layer stays thin
- **Agency white-label onboarding** → apply discount model only after minimum volume commitment + contractual no-compete signed

When in doubt, Titan refuses to blur the SKUs or underprice custom builds, even if Solon asks in the moment — because the standing doctrine is that doing so creates competition for AMG, which Solon has said explicitly he does not want.

---

## 5. Open gaps (tracked on RADAR.md)

1. **Three-SKU landing-page split** — needs a landing-page DR
2. **White-label agency discount model** — no spec exists yet
3. **Tenant-API architecture reference implementation** — standing principle, needs a reference doc + client-deliverable template audit
4. **SKU 3a vs SKU 3b pricing bands** — floors not yet set; needs a dedicated pricing DR
5. **Pricing engine `lib/pricing_engine.py`** — runtime enforcement of the floors; currently manual

All 5 are listed on `RADAR.md` under "Product / Pricing doctrine (open specs)".

---

## 6. Change log

| Date | Change |
|---|---|
| 2026-04-11 | Initial formalization during Hercules backfill pass. Saved to MCP memory as `project_amg_product_tiers.md` + `feedback_ip_protection.md`, then promoted to repo-visible doctrine in `plans/DOCTRINE_AMG_PRODUCT_TIERS.md`. Cross-referenced from `HERCULES_BACKFILL_REPORT.md` Section N. |
