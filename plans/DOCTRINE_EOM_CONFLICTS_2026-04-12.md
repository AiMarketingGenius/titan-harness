# DOCTRINE — EOM v2.2 Merge Conflicts (queued for Solon decision)

**Status:** OPEN — 8 conflict items requiring Solon decisions before auto-apply
**Established:** 2026-04-12 during EOM v2.2 merge pass
**Sibling doc:** [`DOCTRINE_EOM_MERGED_2026-04-12.md`](DOCTRINE_EOM_MERGED_2026-04-12.md) — the non-conflicting rules already absorbed
**Conflict-check rule:** per CORE_CONTRACT §0.7, Titan does not auto-apply any rule that overlaps or contradicts existing harness doctrine without explicit Solon approval. Each conflict below has 2-4 options + Titan's recommendation + a decision box.

**Retroactive application:** once Solon decides on each conflict, the accepted path becomes the new canonical rule. Any affected harness file (CORE_CONTRACT, CLAUDE.md, policy.yaml, other DOCTRINE_*.md) gets updated in the same commit cycle with a cross-reference back to this file.

---

## Conflict 1 — Four-Brain Model vs Titan-as-COO role framing

**Source:** EOM v2.2 SI §1 Four-Brain Model (Router / Builder / Researcher / Automator)
**Harness equivalent:** CORE_CONTRACT §0 Titan = "COO / Head of Execution"
**Current framing in merged doctrine §0:** EOM and Titan split — EOM keeps Router + Builder, Titan absorbs Researcher + Automator + COO execution layer.

**Risk:** if Solon wants a single canonical orchestrator (either Titan or EOM), the current split creates routing ambiguity. If he wants them distinct, the current split is correct but needs reinforcement in CORE_CONTRACT §0.

**Options:**
- **A (recommended)** — Keep the split as currently framed in merged doctrine §0. EOM on Claude.ai web handles Router + Builder brains for cross-Claude-project architecture work. Titan in ~/titan-harness handles Researcher + Automator + COO execution. Both share MCP memory server state. Titan surfaces "route to EOM" when a task needs Claude.ai web-side orchestration; EOM surfaces "route to Titan" via kill chain items when code/infra work is needed.
- **B** — Merge EOM into Titan entirely. Retire EOM v2.2 as a separate Claude.ai persona. Titan becomes the sole orchestrator with all 4 brains under the COO umbrella. Clean single-surface but loses EOM's Claude.ai project-building capability (Titan doesn't run Claude.ai web).
- **C** — Keep EOM as primary, reduce Titan to pure execution agent. Titan stops doing research/strategy, becomes the harness runner only. EOM writes the orchestration plans, Titan executes them.

**Titan recommendation:** A. EOM and Titan already work this way in practice (kill chain shows `Titan+EOM` collaboration tagging). The split is well-matched to their respective surfaces (Claude.ai web vs Claude Code). B creates a capability gap (Claude.ai project building); C wastes Titan's strategic reasoning.

**Solon decision:** [ ] A &nbsp;&nbsp; [ ] B &nbsp;&nbsp; [ ] C &nbsp;&nbsp; [ ] other: _______________

---

## Conflict 2 — Agent roster canonicalization: 16+ specialists vs 7 AMG agents

**Source:** EOM v2.2 SI §5 Specialist Project Routing lists 16+ projects (SEO | Social | Content, CRO / Lumina, Paid Ads Strategist, Shield Reputation, Outbound LeadGen Advisor, Creative Hit Maker, Jingle Maker, Solon's Promoter, Croon AI, Solon Therapy, Portal / Lovable, Viktor AI, AI Prompt Creator, and others). `PROJECT_ROUTING_REFERENCE.md` from Jan 16 lists the Dr. SEO-era roster (different names).
**Harness equivalent:** informal "7 AMG agents" referenced in Solon's earlier conversation, no canonical roster committed to the harness.
**Current state:** Titan does not have a single-source-of-truth agent roster in any DOCTRINE_*.md or policy.yaml block.

**Risk:** Titan may route tasks to agents that have been renamed, archived, or merged. The EOM doctrine assumes 16+ active specialists but the "7 AMG agents" framing suggests consolidation has happened.

**Options:**
- **A (recommended)** — Create `plans/DOCTRINE_AMG_AGENT_ROSTER_2026-04-XX.md` as the single source of truth. Populate it by: (1) reading EOM's Doc 01 Project Routing & Arsenal Reference (NOT on disk, requires Claude.ai extraction or Solon paste), (2) cross-checking against Solon's current-state confirmation of what's alive, (3) marking each agent as ACTIVE / ARCHIVED / MERGED-INTO-X / RENAMED. Once canonical, reference from DOCTRINE_EOM_MERGED §9 and CORE_CONTRACT (new §8 Agent roster).
- **B** — Accept EOM's 16+ list as canonical for now, queue an audit pass later. Risk: stale agents get used.
- **C** — Accept the "7 AMG agents" framing as canonical, treat the other ~9 as ancillary / archived. Risk: real work gets misrouted.

**Titan recommendation:** A. This is a high-value-per-hour doctrine investment — ~30 min of Solon's time listing the 16 + marking states would unlock clean routing forever. Needs EOM's Doc 01 content which is NOT on local disk (only in Claude.ai project memory).

**Solon decision:** [ ] A &nbsp;&nbsp; [ ] B &nbsp;&nbsp; [ ] C &nbsp;&nbsp; [ ] other: _______________

---

## Conflict 3 — Payment processor truth: Paddle vs PaymentCloud / Dodo / Durango

**Source:** EOM v2.2 SI §6 NEVER rules: *"NEVER reference Stripe in new documents — Stripe is DEAD. Paddle is the payment processor"*
**Harness equivalent:** `plans/PLAN_2026-04-11_merchant-stack.md` (shipped, A 9.49) lists **PaymentCloud + Dodo Payments + Durango** as primary options with parallel day-1 applications
**MCP sprint state evidence:** Kill chain shows *"Paddle merchant review #3"* as `blocked-external` (resubmitted 2026-04-08, awaiting 1-5 business days). Also shows *"Merchant processor research (Stax/NMI/Worldpay/TSYS/Elavon/Fiserv)"* as queued.

**Resolution (clear once MCP state is consulted):** Paddle is the **primary choice** that AMG is currently trying to land (3rd submission pending). PaymentCloud / Dodo / Durango are the **fallback pipeline** if Paddle denies again. The other processors (Stax/NMI/Worldpay/TSYS/Elavon/Fiserv) are broader market research. **Not a real conflict — both doctrines are compatible.**

**Options:**
- **A (recommended)** — Update merged doctrine §7.2 NEVER rule #3 to: *"NEVER reference Stripe in new client-facing documents. Primary processor is Paddle (pending review #3 outcome). Fallback pipeline is PaymentCloud + Dodo Payments + Durango per harness merchant stack DR, activated only if Paddle denies."* Also update `plans/PLAN_2026-04-11_merchant-stack.md` with a "Primary: Paddle (awaiting review #3), Fallback: these 3 processors" header block.
- **B** — Wait for Paddle outcome, then delete the losing option from doctrine. Risk: no fallback documented during the waiting period.

**Titan recommendation:** A. Parallel tracks are strictly better than sequential — if Paddle denies, AMG can't wait another week to pivot.

**Solon decision:** [ ] A &nbsp;&nbsp; [ ] B &nbsp;&nbsp; [ ] other: _______________

---

## Conflict 4 — AMG pricing numbers currency: $497 / $797 / $1,497 authoritative?

**Source:** EOM v2.2 SI §6 Correct Cost Numbers block (Apr 1, 2026):
- AMG Starter: $497/mo (single platform, $500-$1,500 ad spend)
- AMG Growth: $797/mo (dual platform, $1,500-$5,000 ad spend — ANCHOR)
- AMG Pro: $1,497/mo (full suite, $5,000-$25,000 ad spend)
- Shield Standalone: $97 / $197 / $347

**Harness equivalent:** `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` (shipped today) intentionally did NOT include specific numbers — was waiting for a dedicated pricing DR.

**Risk:** if these numbers are stale (superseded since Apr 1), any Loom demo, proposal, or sales page using them will misprice by the EOM-vs-current-state delta.

**Options:**
- **A (recommended)** — Solon confirms in this session: are these numbers current as of 2026-04-12? If YES → promote to canonical in `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` §1 with the exact numbers. If NO → block until Solon provides current numbers. Either way, add a numbers SOT section to DOCTRINE_AMG_PRODUCT_TIERS.
- **B** — Treat EOM's numbers as authoritative by default (they're the most recent explicit doctrine). Add a "last verified 2026-04-01, pending re-verification" note.
- **C** — Leave pricing unspecified in both doctrine files until a dedicated pricing DR + Aristotle A-grade.

**Titan recommendation:** A with a hard check. This is exactly the kind of claim where the §2 Anti-Hallucination *"Would I bet $500 on every claim?"* check applies — Titan cannot confidently assert these are current without Solon confirming, so the right move is to ask.

**Solon decision (one line):** these numbers are: [ ] current &nbsp;&nbsp; [ ] superseded (new: _______________)

---

## Conflict 5 — Lead-gen outbound gate: EOM says "NEVER start until all systems operational," Autopilot Thread 3 is queued

**Source:** EOM v2.2 SI §6 NEVER rule #6: *"NEVER start lead gen outbound until all systems are fully operational"*
**Harness equivalent:** `policy.yaml autopilot.marketing_engine_enabled: false` (default disabled) — Autopilot Thread 3 Recurring Marketing Engine is architected but the kill switch is OFF. Thread 1 Sales Inbox is inbound-only, not outbound-generating.
**MCP sprint state evidence:** Kill chain doesn't explicitly mention an outbound start date; implicit "systems operational first" sequencing.

**Resolution:** the two doctrines are compatible — Autopilot Thread 3 is BUILT but DISABLED by default. The EOM rule maps to "don't flip the kill switch to true until all upstream systems (Threads 1, 2, 4, 5 + merchant stack + pricing) are verified operational." Not a blocker to shipping the Voice AI demo or the Atlas skin polish.

**Options:**
- **A (recommended)** — Update merged doctrine §7.2 NEVER rule #5 to: *"NEVER flip `policy.yaml autopilot.marketing_engine_enabled=true` until all upstream systems (Autopilot Threads 1+2+4+5 operational, merchant stack locked, pricing authoritative) are verified. Inbound Sales Inbox (Thread 1) and Back-Office (Thread 4) are not constrained by this rule."* Reference from `plans/PLAN_2026-04-11_recurring-marketing-engine.md` gate block.
- **B** — Keep the blanket "never start outbound" language and delay Thread 3 indefinitely. Risk: Thread 3 rots.

**Titan recommendation:** A. The harness already encodes the gate via the kill switch; merged doctrine needs to align with the kill switch, not the blanket language.

**Solon decision:** [ ] A &nbsp;&nbsp; [ ] B &nbsp;&nbsp; [ ] other: _______________

---

## Conflict 6 — Grok as second grader in war-room (add to model_router?)

**Source:** EOM v2.2 SI §1 Accuracy, Verification, and Cross-Checks §5: *"For high-impact artifacts ... you must recommend a Grok + Perplexity dual-audit before Solon treats them as final"*
**Harness equivalent:** `lib/war_room.py` uses Perplexity `sonar-pro` for grading, Claude Sonnet 4.6 for revision. No Grok integration. `policy.yaml models:` routing table has no Grok entry.

**Risk:** adding Grok = new API integration + new cost ceiling + new failure mode. Benefit: dual-model grading catches failure modes a single grader (Perplexity sonar-pro) misses. EOM's rule frames it as mandatory for "high-impact artifacts."

**Options:**
- **A** — Add Grok as second grader alongside Perplexity in war-room, routed via LiteLLM gateway. Requires: xAI API key, LiteLLM gateway config update, `policy.yaml models.routing` entry for `grok` or `grok-validator`, cost ceiling addition (~$0.50/round matching Perplexity). Estimated: ~4 hours of harness work.
- **B (recommended)** — Queue Grok addition as a future enhancement after Slack Aristotle comes online. Rationale: the immediate gap is "Perplexity API is 401'd and Slack Aristotle isn't installed" — adding Grok doesn't fix the current grading infrastructure, it adds a third broken path. Real priority is getting Slack Aristotle live. Grok can come after.
- **C** — Drop the Grok requirement entirely. Perplexity + Titan self-grade is sufficient for non-trophy-tier work. Grok only for SKU 3b fully-custom-OS builds where dual validation is worth the cost.

**Titan recommendation:** B. Order of operations matters. Get Slack Aristotle live first (unlocks cheap reliable grading), then evaluate if Grok adds real signal vs noise.

**Solon decision:** [ ] A &nbsp;&nbsp; [ ] B &nbsp;&nbsp; [ ] C &nbsp;&nbsp; [ ] other: _______________

---

## Conflict 7 — Viktor AI ($200/mo execution agent) — add to harness?

**Source:** EOM v2.2 SI §5 Specialist Project Routing + §6 Correct Cost Numbers: Viktor AI listed as the execution agent at $200/mo. Doc 06A covers "Viktor & Tool Economics."
**Harness equivalent:** Titan handles code execution, Slack tasks, deployment via bash/runners/queue-watcher/mp-runner. No separate "Viktor" layer. `lib/` has no Viktor references.

**Risk:** Viktor may be a parallel layer that EOM-era doctrine assumes exists but Titan harness has superseded. OR Viktor may still be alive and doing work Titan doesn't know about, creating silent duplication.

**Options:**
- **A (recommended)** — Confirm with Solon: is Viktor AI still running as a separate service, or has Titan harness absorbed its role? If still running → add a `viktor_ai:` section to `policy.yaml` with its role boundary (e.g., "Viktor handles Pipedream/Zapier-native workflows; Titan handles Python / bash / LiteLLM workflows"), and document the handoff. If absorbed → archive Viktor references in merged doctrine, no harness change needed.
- **B** — Assume Viktor is still running, add the `viktor_ai:` policy section speculatively. Risk: documenting a dead service.

**Titan recommendation:** A with a direct Solon question. This is the kind of fact Titan can't derive from files alone — either Solon confirms Viktor is alive and running, or confirms it's been replaced.

**Solon decision:** Viktor AI is: [ ] still running (role: _______________) &nbsp;&nbsp; [ ] absorbed by Titan &nbsp;&nbsp; [ ] archived

---

## Conflict 8 — EOM KB Docs 01-10 not on disk (requires extraction)

**Source:** EOM v2.2 SI §7 KB Reference Block + throughout: heavy references to Doc 01 (Project Routing & Arsenal Reference), Doc 02 (Claude Project Builder Framework v2.0), Doc 03 (Research & Intelligence Protocols), Doc 04 (WoZ Architecture & Client Operations), Doc 05 (AMG Business Operations Reference), Doc 06A (Viktor & Tool Economics), Doc 06B (Automation & Process Design), Doc 07 (ADHD-Optimized Operations Framework), Doc 08 (Quality Assurance & Continuous Improvement), Doc 09 (KB Manifest v3.0), Doc 10 (Thread Safety & Anti-Hallucination Protocol — appended Apr 2)
**Harness equivalent:** none — these docs are in Claude.ai project memory, NOT on local disk. Explore agent confirmed.
**What we have on disk:** the SI references + the Thread Safety Gate content (§10 appended to SI). The other 9 KB docs are ~unknown content.

**Risk:** the merged doctrine references rules that live in docs Titan can't see. For example, "First-Pass Verification Gate (Doc 06B §4)" is partially quoted in the SI but the full protocol is in Doc 06B which isn't accessible. Titan is operating on ~70% of EOM's full doctrine.

**Options:**
- **A (recommended)** — Block on Solon extracting Docs 01-10 from the EOM Claude.ai project. Solon can either (a) manually copy-paste each doc into `~/Downloads/` for the next Titan session to merge, or (b) use MP-1 Phase 1 Claude threads harvester (currently blocked on 2FA per `plans/BATCH_2FA_UNLOCK_2026-04-12.md`) to pull everything at once. Option (b) is cleaner because it's one unlock batch.
- **B** — Proceed with partial doctrine (~70%), flag the ~30% gap as "see EOM Claude.ai web project for full content" throughout. Risk: doctrine drift between surfaces.
- **C** — Have Titan write reconstruction drafts of each doc based on the SI's references + best-guess filling, then Solon audits. Risk: hallucinated doctrine.

**Titan recommendation:** A with option (b) — the 2FA batch unlock already unblocks MP-1 Phase 1 Claude harvester, which will pull the EOM project including all 10 KB docs in one pass. Solon doesn't need to manually export anything. The `plans/BATCH_2FA_UNLOCK_2026-04-12.md` Step 1 (Claude.ai sessionKey) is the unlock.

**Solon decision:** [ ] A(a) manual paste &nbsp;&nbsp; [ ] A(b) via MP-1 harvester after 2FA &nbsp;&nbsp; [ ] B &nbsp;&nbsp; [ ] C

---

## Resolution path

Once Solon works through these 8 conflicts (estimated ~15 minutes of his time), Titan will:

1. Update `plans/DOCTRINE_EOM_MERGED_2026-04-12.md` §7 (rules) and §9 (conflicts queue) with the accepted resolutions
2. Update any affected harness files: `CORE_CONTRACT.md`, `CLAUDE.md`, `policy.yaml`, `plans/DOCTRINE_AMG_PRODUCT_TIERS.md`, `plans/PLAN_2026-04-11_merchant-stack.md`, `plans/PLAN_2026-04-11_recurring-marketing-engine.md`
3. Re-grade the updated merged doctrine (round 2) against the 10-dim rubric, iterate if below A
4. Log the decisions via MCP `log_decision` for each conflict
5. Commit + push + mirror as a single "EOM MERGE resolutions" commit
6. Report back in chat with the updated summary

**No conflict resolution is auto-applied.** Titan waits for explicit Solon decision on each of the 8 items above.

---

## Change log

| Date | Change |
|---|---|
| 2026-04-12 | Initial conflict queue created during EOM v2.2 merge pass. 8 items flagged, 5 with "A recommended" path, 2 requiring direct Solon confirmation (pricing currency + Viktor AI status), 1 blocked on Claude.ai harvester unlock. |
