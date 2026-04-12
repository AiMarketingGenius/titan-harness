# Library of Alexandria — AMG / Solon OS Canonical Index

**Status:** CANONICAL — single source of truth for everything harvested or authored about Solon / AMG, past and future.
**Model:** thin catalog layer. Files physically live in `plans/` (doctrine) and `/opt/amg-titan/solon-corpus/` (harvested raw corpus on VPS). This tree is an **index + manifest**, never a copy.
**Established:** 2026-04-11 (Solon Mega Directive Part 3, conflict-checked merge plan approved)
**Hercules Triangle applied:** Intent captured in CORE_CONTRACT §0.5 → Harness encoded via `lib/alexandria.py` + `bin/alexandria-preflight.sh` → Mirrored Mac ↔ VPS ↔ GitHub `AiMarketingGenius/titan-harness`.

---

## Sections (7 canonical)

| # | Section | Physical path | What lives there | Manifest |
|---|---|---|---|---|
| 1 | **Solon OS** | `plans/` + `CORE_CONTRACT.md` + `CLAUDE.md` + `INVENTORY.md` + `RADAR.md` | All DRs, blueprints, autopilot-suite plans, control-loop packages, Core / Claude contracts, 5-day inventory, open-queue RADAR. | `solon_os/MANIFEST.md` |
| 2 | **Perplexity Threads** | `/opt/amg-titan/solon-corpus/perplexity/` (VPS) + `library_of_alexandria/perplexity_threads/raw_history_screens/` (repo-local) | Harvested Perplexity thread JSON artifacts + raw full-page screenshots of the Threads list (OCR'd into `perplexity_catalog.md`). | `perplexity_threads/MANIFEST.md` |
| 3 | **Claude Threads** | `/opt/amg-titan/solon-corpus/claude-threads/` (VPS) | Harvested Claude.ai conversation JSONs incl. Croon / Hit Maker / Solon's Promoter creative projects. | `claude_threads/MANIFEST.md` |
| 4 | **Emails** | `/opt/amg-titan/solon-corpus/gmail/` (VPS) | MP-1 Phase 5 Gmail harvest (harvester TBD, OAuth pending). | `emails/MANIFEST.md` |
| 5 | **Looms** | `/opt/amg-titan/solon-corpus/loom/` (VPS) | MP-1 Phase 4 Loom transcripts (creds pending). | `looms/MANIFEST.md` |
| 6 | **Fireflies Meetings** | `/opt/amg-titan/solon-corpus/fireflies/` (VPS) | MP-1 Phase 3 Fireflies transcripts — **48 artifacts on disk** as of 2026-04-11. | `fireflies_meetings/MANIFEST.md` |
| 7 | **Other Sources** | `/opt/amg-titan/solon-corpus/slack/` + `/opt/amg-titan/solon-corpus/mcp-decisions/` (VPS) + catch-all | MP-1 Phase 6 Slack (19 artifacts), Phase 7 MCP decisions, and any future source not in the 6 canonical types. | `other_sources/MANIFEST.md` |

---

## How to use this index

- **Read doctrine** → start at the Solon OS manifest, follow links into `plans/PLAN_*.md` and `CORE_CONTRACT.md`.
- **Find harvested material** → start at the relevant section's manifest. Each one gives the physical path + current artifact count + any search helpers (`grep`, `rg`, or the `lib/alexandria.py` search API).
- **Search the whole library** → `python3 lib/alexandria.py --search "<query>" --section <name>` runs a cross-tree search (doctrine + harvested corpus).
- **Add something new** → the harness preflight (`bin/alexandria-preflight.sh`) enforces that any new doctrine file lands in `plans/`, `baselines/`, `templates/`, `library_of_alexandria/<section>/`, or the VPS `/opt/amg-titan/solon-corpus/` tree. Anything outside those paths triggers a warning at commit/build time.
- **Promote to canon** → when a Perplexity thread / Claude conversation / Loom / Fireflies transcript becomes a doctrine reference, add a link + 1-line description to the relevant section below AND post a Slack update to `#titan-aristotle` via `lib/aristotle_slack.post_update()` so Aristotle sees the promotion.

---

## Canonical cross-references

### Core operating docs (read first)
- [`CORE_CONTRACT.md`](../CORE_CONTRACT.md) — non-bypassable harness invariants, roles, Library rule, Hercules Triangle
- [`CLAUDE.md`](../CLAUDE.md) — session-level operating contract: roles, brevity, RADAR, execution priority
- [`IDEA_TO_EXECUTION_PIPELINE.md`](../IDEA_TO_EXECUTION_PIPELINE.md) — IdeaBuilder: idea → DR → war-room → phased execution
- [`INVENTORY.md`](../INVENTORY.md) — live 5-day build inventory + gap map
- [`RADAR.md`](../RADAR.md) — open queue: never-lose-anything canonical state
- [`RELAUNCH_CLAUDE_CODE.md`](../RELAUNCH_CLAUDE_CODE.md) — how to relaunch a Titan session

### Shipped DRs (A-graded blueprints — live in `plans/`, gitignored)
- **AMG Merchant Stack** — `plans/PLAN_2026-04-11_merchant-stack.md` (A 9.49/10)
- **Thread 1: Sales Inbox + CRM Agent** — `plans/PLAN_2026-04-11_sales-inbox-crm-agent.md` (A 9.46/10)
- **Thread 2: Proposal from Call Notes** — `plans/PLAN_2026-04-11_proposal-from-call-notes.md` (A 9.53/10)
- **Thread 3: Recurring Marketing Engine** — `plans/PLAN_2026-04-11_recurring-marketing-engine.md` (A 9.40/10)
- **Thread 4: Back-Office Autopilot** — `plans/PLAN_2026-04-11_back-office-autopilot.md` (A 9.45/10)
- **Thread 5: Client Reporting Autopilot** — `plans/PLAN_2026-04-11_client-reporting-autopilot.md` (A 9.40/10)
- **Merchant Stack application package** — `plans/merchant-stack-applications/` (Solon action checklist + 3 cover letter drafts + website audit)

### Canonical doctrine (committed to repo, not gitignored)
- **AMG Product Tiers + IP Protection** — [`plans/DOCTRINE_AMG_PRODUCT_TIERS.md`](../plans/DOCTRINE_AMG_PRODUCT_TIERS.md) — three-SKU ladder (subs / white-label / Solon OS custom 3a+3b), IP protection architecture, pricing posture (never underprice), standing rule for all customer-facing surfaces. Established 2026-04-11 via Hercules backfill pass.
- **Hercules Backfill Report** — [`HERCULES_BACKFILL_REPORT.md`](../HERCULES_BACKFILL_REPORT.md) — one-time audit of the recent build era confirming every structural directive is harnessed. Flags 3 structural TODOs (email send-verification gate, pricing engine, Atlas frontend session continuity).

### Solon OS substrate
- [`policy.yaml`](../policy.yaml) — all runtime config (capacity, war_room, autopilot, aristotle, alexandria)
- [`lib/war_room.py`](../lib/war_room.py) — 10-dim A-grade rubric grader
- [`lib/war_room_slack.py`](../lib/war_room_slack.py) — Slack-routed grading path
- [`lib/aristotle_slack.py`](../lib/aristotle_slack.py) — Aristotle first-class agent integration (`#titan-aristotle`)
- [`lib/alexandria.py`](../lib/alexandria.py) — Library search + manifest refresh + preflight helpers

---

## Aristotle integration

Aristotle (Perplexity in `#titan-aristotle` Slack channel) is the strategy + research co-agent. Whenever Titan promotes anything to canon (new DR, MP-1/MP-2 doctrine, curated Perplexity thread), Titan:

1. Updates this file (`ALEXANDRIA_INDEX.md`) and the relevant section manifest
2. Posts a short note + link to `#titan-aristotle` via `lib/aristotle_slack.post_update()`
3. Appends to `RADAR.md` under the appropriate section

This way Aristotle, Titan, and Solon always see the same Library state.

---

## Metrics (refreshed by `lib/alexandria.py --refresh`)

- **Total sections:** 7
- **Doctrine files in `plans/`:** 6 autopilot DRs + 1 merchant stack DR + `control-loop/` + `merchant-stack-applications/`
- **Harvested artifacts (VPS):** 856 baseline (MP-1 Phase 6+7+8 complete, Phase 3 reconciled)
  - Fireflies: 48 files
  - Slack: 19 files
  - MCP decisions: 1 file (tally artifact from Phase 7)
  - Perplexity: 2 files
  - claude threads: 0 (pending Solon sessionKey)
  - Gmail: 0 (pending OAuth + harvester)
  - Loom: 0 (pending creds)
- **Last index refresh:** 2026-04-12 07:41 UTC
