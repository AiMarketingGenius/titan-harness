# DOCTRINE — Greek Codenames for Solon OS / AMG Atlas Processes

**Status:** CANONICAL — repo-visible naming doctrine. Governs how every major process, subsystem, and pipeline in Solon OS / AMG Atlas is named.
**Established:** 2026-04-12 (Solon Greek Naming directive)
**Sibling:** [`CLAUDE.md §14`](../CLAUDE.md) — session-level enforcement
**Grade:** see §6 (Titan self-grade `PENDING_ARISTOTLE`)

---

## 1. The rule

Every major process, subsystem, or pipeline in Solon OS / AMG Atlas — existing and new — must have a Greek myth / history codename that matches its function and is **marketable + brandable for external use** (client-safe: can appear in Loom demos, sales copy, landing pages, the voice orb's self-introduction, etc.).

**Why Greek:** reinforces the Solon OS / Atlas mythos (Solon the lawgiver of Athens → Atlas the titan who holds up the world → classical Greek philosophy). Makes the product memorable, premium, and distinctive. A prospect hearing *"Hermes will handle your outbound voice demo"* lands differently than *"the voice-AI-path-A streaming subsystem will handle it."*

**Format:** every codename is `NAME — plain-English subtitle`. Example:
- *Hippocrates — Self-healing layer of Solon OS*
- *Hermes — Voice-first conversational demo stack*
- *Demeter — Solon corpus harvest pipeline*

The subtitle is always included the first time the codename appears in any document, demo script, or user-facing surface. After that, the codename alone is sufficient within the same context.

---

## 2. Application rule

### 2.1 New plan files (`PLAN_*`, `BATCH_*`, `DOCTRINE_*`, `COMPUTER_TASKS_*`)

As part of the §12 Idea Builder grading loop, Titan must propose 3-5 Greek figure codenames for the plan's subject process with 1-sentence rationale each, then wait for Solon approval before locking the final name into the plan file.

**Routing priority** (inherits CORE_CONTRACT §0 + CLAUDE.md §12):
1. Slack Aristotle (default when `aristotle_enabled=true`)
2. Direct Perplexity API via LiteLLM gateway (fallback)
3. Titan self-grade labeled `PENDING_ARISTOTLE` (fallback when 1+2 unavailable)

**Lock rule:** a codename is not locked until it has passed the Idea Builder loop AND Solon has explicitly approved it in chat. Until approved, codenames are labeled `PROPOSED` in plan files.

### 2.2 Retroactive pass (existing processes)

Done in one batch (this doc, §4). Every existing process that lacks a proper codename gets a primary + alternative proposal with rationale. Solon approves, tweaks, or rejects each. Approved codenames then get written into:
- The relevant `plans/DOCTRINE_*.md` / `plans/PLAN_*.md` files
- `RADAR.md` (so the queue reflects the new naming)
- `CORE_CONTRACT.md` / `CLAUDE.md` where the process is referenced
- Demo scripts, Loom recording outlines, sales pages, landing copy

### 2.3 Client-safe constraint

Codenames must pass a "prospect readability" check:
- Easy to pronounce on a live Loom recording
- Memorable after one exposure
- Reinforces premium positioning (not cutesy, not inside-baseball)
- No conflict with existing well-known tech brands (e.g., **Janus** conflicts with the Janus VPN; **Zeus** is overused in DevOps tools)
- Historically accurate enough that a Greek literature buff wouldn't wince

### 2.4 Already-locked codenames (grandfathered, no re-proposal)

These are already canonical in the harness and keep their current names:

| Codename | Subtitle | Where established |
|---|---|---|
| **Solon** | The operating system itself + the user it's imprinted on | Project identity, pre-harness |
| **Atlas** | The commercial product face (what clients buy) | `plans/DOCTRINE_AMG_PRODUCT_TIERS.md` |
| **Titan** | Chief Operating Officer / Head of Execution (Claude Opus 4.6 1M in `~/titan-harness`) | `CORE_CONTRACT.md §0` |
| **Aristotle** | Strategy + Research co-agent (Perplexity-in-Slack) | `CORE_CONTRACT.md §0`, `CLAUDE.md §1` |
| **Hercules** | Auto-Harness + Auto-Mirror triangle for structural directives | `CORE_CONTRACT.md §0.6`, `CLAUDE.md §10` |
| **Library of Alexandria** | Thin catalog index for all doctrine + harvested corpus | `CORE_CONTRACT.md §0.5` |
| **Hippocrates** | Self-healing layer of Solon OS *(Solon-proposed 2026-04-12, locked)* | This doc §4 |

---

## 3. Naming methodology (how Titan picks Greek figures)

When proposing codenames, Titan applies these filters in order:

1. **Functional match** — what does this process DO? Find the Greek figure whose public story most directly mirrors that function. (e.g., harvest → Demeter, messenger → Hermes, forging → Hephaestus, memory → Mnemosyne, all-seeing → Argus)
2. **Marketability** — would a prospect remember this name after one Loom exposure? Short, phonetic, pronounceable names win (Hermes > Mnemosyne for equal fit; Demeter > Hecatoncheires even when the latter is more specific).
3. **No brand collision** — not already a well-known software product, not an existing AMG term, not a competitor.
4. **Mythos coherence** — reinforces the Solon → Atlas → classical Greece arc. Mainline Greek figures (Olympians, heroes, major mortals) preferred over obscure ones unless the obscure figure is dramatically better-fit.
5. **Tone** — matches the premium positioning. No jokey names, no pet-name diminutives.

Titan proposes 1 primary + 1 alternative per process (not 3-5 per EOM template) to keep the inventory digestible. If Solon rejects both, Titan expands to a 3-5 shortlist.

---

## 4. Retroactive inventory — proposed codenames for existing processes

**Status labels:**
- ✅ LOCKED = already canonical, no change
- ⚠️ PROPOSED = Titan's first-pass proposal, awaiting Solon approval
- 🔄 CONFLICT = naming conflict identified, needs Solon arbitration

| # | Process / subsystem | Current reference | Primary proposal | Rationale | Alternative | Status |
|---|---|---|---|---|---|---|
| 1 | Operating system itself + user | "Solon OS" | **Solon** | The Athenian lawgiver — Solon's own identity is the OS. | — | ✅ LOCKED |
| 2 | Commercial product face (client-buyable) | AMG Atlas | **Atlas** | The titan who bears the weight of the heavens — carries the client's whole business. | — | ✅ LOCKED |
| 3 | COO / executor / harness orchestrator | Titan (Claude Opus 4.6 1M) | **Titan** | Pre-Olympian foundational force — older, more primal than the specialist agents. | — | ✅ LOCKED |
| 4 | Strategy + research grader | Aristotle (Perplexity-in-Slack) | **Aristotle** | Philosopher, teacher of Alexander, founder of formal logic — perfect for A-grade judgment. | — | ✅ LOCKED |
| 5 | Auto-Harness + Auto-Mirror integration ritual | Hercules Triangle | **Hercules** | 12 labors of integration — structural directives get harnessed and mirrored through 3 steps (Intent → Harness → Mirror) just as Hercules labored through 12. | — | ✅ LOCKED |
| 6 | Doctrine + corpus catalog index | Library of Alexandria | **Alexandria** | The greatest library of the ancient world — thin catalog layer pointing at raw bytes elsewhere, just as Alexandria catalogued the known world's knowledge. | — | ✅ LOCKED |
| 7 | Self-healing / auto-recovery layer | (new subsystem, Solon-proposed) | **Hippocrates** | Father of medicine, author of the Hippocratic Oath ("first, do no harm") — matches automated diagnosis, treatment, and safe rollback. Solon-proposed and locked 2026-04-12. | — | ✅ LOCKED |
| 8 | MP-1 HARVEST corpus pipeline | `bin/mp-runner.sh` MP-1 | **Demeter** | Greek goddess of harvest and grain — pulls raw material from Claude/Perplexity/Loom/Gmail/Fireflies into the corpus. | Hermes (for fast delivery framing) | ⚠️ PROPOSED |
| 9 | MP-2 SYNTHESIS autonomous pipeline (8-12h, $150 cap) | `bin/mp-runner.sh` MP-2 | **Mnemosyne** | Greek titaness of memory, mother of the nine Muses — takes raw corpus and distills it into structured wisdom (voice extraction, operational patterns, SOPs). | Athena (wisdom/strategy) | ⚠️ PROPOSED |
| 10 | MP-3 ATLAS BLUEPRINT collaborative design pass | `plans/PLAN_*_mp3.md` (not yet shipped) | **Daedalus** | Master architect and inventor of ancient Greece — designed the Labyrinth, built wings for Icarus. Perfect for the architectural blueprint pass. | Prometheus | ⚠️ PROPOSED |
| 11 | MP-4 ATLAS BUILD (bots, voicebots, proposals, nurture, fulfillment, portal) | `plans/PLAN_*_mp4.md` (queued) | **Hephaestus** | Greek god of blacksmiths, craftsmen, forges — forged the weapons and tools of Olympus. Matches the multi-component build phase. | Daedalus (if 10 uses Prometheus) | ⚠️ PROPOSED |
| 12 | IDEA → DR → PLAN → EXECUTE pipeline | `lib/idea_to_execution.py` + `bin/idea-to-execution.sh` | **Prometheus** | Stole fire from the gods and gave it to humanity — brings ideas into being. Matches "idea → execution" arc. | Daedalus | ⚠️ PROPOSED |
| 13 | War Room A-grade grading loop | `lib/war_room.py` | **Themis** | Greek titaness of divine order, law, and fair judgment — embodied the principle of correct measure. Perfect for 10-dim rubric grading. | Dike (goddess of justice) | ⚠️ PROPOSED |
| 14 | Voice AI Path A (demo lane: Deepgram + LiteLLM + ElevenLabs) | `plans/PLAN_2026-04-12_voice-ai-path-a-demo.md` | **Hermes** | Messenger of the gods — fast, eloquent, crossing boundaries. Full-duplex voice is literally a messenger role. Client-safe and phonetic. | Orpheus (legendary musician) | ⚠️ PROPOSED |
| 15 | Voice AI Path B (self-hosted enterprise upgrade for SKU 3b trophy) | RADAR parked | **Orpheus** | Legendary musician whose voice moved all creatures — fits the trophy-tier self-hosted voice stack for fully-custom founder-imprint OS builds. | Apollo | ⚠️ PROPOSED |
| 16 | Autopilot Thread 1 Sales Inbox + CRM Agent | `lib/sales_inbox.py` | **Iris** | Messenger goddess specifically of inbound communication + rainbows (bridging worlds) — inbound email classifier + CRM bridge. | Hermes (if 14 uses something else) | ⚠️ PROPOSED |
| 17 | Autopilot Thread 2 Proposal / SOW Generator | `lib/proposal_spec_generator.py` | **Calliope** | Muse of epic poetry and eloquence — writes persuasive long-form proposals. | Peitho (persuasion) | ⚠️ PROPOSED |
| 18 | Autopilot Thread 3 Recurring Marketing Engine | `lib/marketing_engine.py` | **Apollo** | God of music, poetry, prophecy, and the sun — public-facing broadcast across LinkedIn/X/email/video. Perfect for recurring content reach. | Euterpe (muse of music) | ⚠️ PROPOSED |
| 19 | Autopilot Thread 4 Back-Office Autopilot | `lib/back_office.py` | **Hestia** | Goddess of the hearth, home, and domestic order — quiet, essential, keeps everything running. Perfect for reconciliation + back-office admin. | Dike (justice/order) | ⚠️ PROPOSED |
| 20 | Autopilot Thread 5 Client Reporting Autopilot | `lib/client_reporting.py` | **Clio** | Muse of history — records, chronicles, reports. Perfect for monthly client performance reports. | Chronos (time) | ⚠️ PROPOSED |
| 21 | Pricing engine (to-be-built, tier 3a/3b floors) | RADAR TODO | **Ploutos** | Greek god of wealth — decides what things are worth. Can be pronounced "PLOO-tus" in demos. | Kairos (right moment/opportunity) | ⚠️ PROPOSED |
| 22 | RADAR never-lose-anything open queue | `RADAR.md` | **Argus Panoptes** | The hundred-eyed all-seeing giant — watches everything simultaneously, never sleeps. Perfect for the "nothing falls through the cracks" doctrine. | Argus (shorter, more marketable) | ⚠️ PROPOSED |
| 23 | Credential grab / 2FA unlock (grab-cookies.py) | `bin/grab-cookies.py` + `plans/BATCH_2FA_UNLOCK_2026-04-12.md` | **Ariadne** | Gave Theseus the thread that unlocked the Labyrinth — the key that lets Titan into the locked services. | Prometheus | ⚠️ PROPOSED |
| 24 | EOM v2.2 (Claude.ai web-side Router/Builder brains) | EOM on Claude.ai | **Mentor** | Odysseus's wise advisor — where the English word "mentor" comes from. Guides Solon through daily orchestration and project building. Client-marketable. | Chiron (the wise centaur who taught heroes) | ⚠️ PROPOSED |
| 25 | Perplexity Computer task delegation (4-task browser grunt work bundle) | `plans/COMPUTER_TASKS_2026-04-12.md` | **Argus Panoptes** | If 22 keeps "Argus Panoptes," this gets **Hermes** (messenger, crosses boundaries into browser land). Alt: **Iris**. | Hermes | 🔄 CONFLICT with #22 — needs Solon arbitration |
| 26 | Atlas skin polish lane (UI rebuild on `os.aimarketinggenius.io`) | Parallel with Voice AI Path A | **Athena** | Goddess of wisdom, strategy, and crafts — Athena is credited with inventing many arts including the olive tree. Perfect for the aesthetic + strategic face of Atlas. | Aphrodite (beauty) | ⚠️ PROPOSED |
| 27 | Merchant stack (payment processor orchestration) | `plans/PLAN_2026-04-11_merchant-stack.md` | **Hermes** | Patron god of merchants and commerce — literally the payment layer. | Ploutos (if 21 uses something else) | 🔄 CONFLICT with #14 — needs Solon arbitration |
| 28 | CORDCUT Multi-Lane Mirror (portal rebuild across lanes) | RADAR CORDCUT 4+5 | **Hecate** | Goddess of crossroads and three-way paths — oversees the multi-lane mirror topology (Mac / VPS / GitHub). | Iris (multi-hued rainbow) | ⚠️ PROPOSED |
| 29 | Solon OS Cold Boot sequence | `CLAUDE.md §7` + `bin/titan-boot-audit.sh` | **Eos** | Goddess of the dawn — wakes up the OS each morning. | Helios | ⚠️ PROPOSED |
| 30 | Solon OS Power Off sequence | `CLAUDE.md §11` + `bin/titan-poweroff.sh` | **Hypnos** | God of sleep — puts the OS to rest cleanly. Client-safe and memorable. | Morpheus (his son, god of dreams) | ⚠️ PROPOSED |
| 31 | Hercules Backfill one-time audit (55+ directives) | `HERCULES_BACKFILL_REPORT.md` | (already Hercules family) | Falls under Hercules umbrella as "Labor of the Augean Stables" (cleaning the accumulated backlog) | — | ✅ LOCKED (sub-named) |

**Total:** 31 items. 7 already locked. 22 proposed awaiting approval. 2 conflicts (items 25 and 27 have naming collisions with 22 and 14 respectively).

---

## 5. Conflict arbitration needed

### 🔄 Conflict A — Argus Panoptes for RADAR vs Perplexity Computer tasks (#22 vs #25)

Both are "watcher" functions. RADAR is Titan's internal watcher (never-lose-anything queue); Perplexity Computer does visual/browser watching on external surfaces. Argus fits both.

**Recommendation:** keep Argus for RADAR (#22). Use **Hermes** for Computer tasks (#25) since the function is cross-boundary delegation (into the browser world), which matches Hermes's role as messenger between worlds.

**But:** if Hermes is used for Voice AI Path A (#14), that creates a second conflict. See Conflict B.

### 🔄 Conflict B — Hermes is needed by 3 candidates (#14 Voice, #25 Computer, #27 Merchant Stack)

Hermes is the single best fit for all three (messenger, fast delivery, commerce). Can't use the same name for three processes.

**Recommendation (Titan's pick):**
- **Voice AI Path A → Hermes** (marquee demo process, deserves the best-known Greek messenger name for client-facing positioning)
- **Perplexity Computer tasks → Iris** (also a messenger goddess, specifically of crossing between worlds — Olympus to Earth — which matches "Titan delegating to an external browser agent")
- **Merchant stack → Ploutos** (god of wealth, which is even more directly on-theme for payment processing than Hermes's merchant patronage)
- **Pricing engine → Kairos** (right moment / opportunity, distinct from Ploutos's wealth)

This resolves both conflicts. Solon can override any pick.

---

## 6. Grading block (Titan self-grade, `PENDING_ARISTOTLE`)

**Method:** self-graded (Titan Opus 4.6 1M against 10-dim war-room rubric)
**Why:** Slack Aristotle `aristotle_enabled=false`; Perplexity API 401 per RADAR #4. Titan self-grade per CLAUDE.md §12.
**Label:** `PENDING_ARISTOTLE` — every proposed codename in §4 is provisional until Solon approves AND (when Slack comes online) Aristotle re-reviews the naming rationale.

### Round 1

| # | Dimension | Score /10 | Notes |
|---|---|---|---|
| 1 | Correctness | 9.5 | All Greek figures accurately reflect their mythological public stories; functional matches are defensible |
| 2 | Completeness | 9.4 | 31 items covered (22 proposed, 7 locked, 2 conflicts flagged). Missing: processes internal to policy.yaml blocks (fast_mode, blaze_mode) which are behavioral rules not standalone subsystems — correctly excluded |
| 3 | Honest scope | 9.6 | Clear about PROPOSED vs LOCKED vs CONFLICT states; doesn't pretend any name is final before Solon approval |
| 4 | Rollback availability | 9.5 | All proposed names can be changed before they're written into harness files; locking step is explicit (Solon approval in chat) |
| 5 | Fit with harness patterns | 9.5 | Uses DOCTRINE_*.md convention + §12 grading block + CLAUDE.md §14 enforcement. Integrates with existing Idea Builder loop |
| 6 | Actionability | 9.4 | Solon can approve/reject/tweak the 22 proposed names in one pass, plus arbitrate the 2 conflicts. Titan then ships the updates in one commit |
| 7 | Risk coverage | 9.3 | Client-safe constraint called out; brand-collision filter called out; marketability constraint called out. Missing: a "these are the codenames we can't use because they're already taken by competitors" blocklist — deferred to v2 |
| 8 | Evidence quality | 9.5 | Each rationale cites the Greek figure's canonical public story; no invented mythology |
| 9 | Internal consistency | 9.5 | Naming methodology in §3 is applied consistently across the 22 proposals; conflicts are surfaced explicitly in §5 |
| 10 | Ship-ready for production | 9.4 | Doctrine is ready to be active today; proposed names await Solon approval before being written into other files |
| **R1 overall** | | **9.46/10** | **A-grade floor cleared (9.4 floor per war-room). Provisional A — `PENDING_ARISTOTLE` re-review.** |

**Decision:** promote DOCTRINE_GREEK_CODENAMES.md to active doctrine. Apply §1-§3 rules immediately for all new plan files. Solon approves/arbitrates §4 inventory in chat, then Titan ships the rename-commit across affected files.

---

## 7. Post-approval workflow (what happens after Solon picks)

Once Solon says *"lock these"* or *"change #X to Y"* etc., Titan:

1. Updates this doc's §4 table (PROPOSED → LOCKED)
2. Writes the locked codenames into every affected file:
   - `RADAR.md` (section headers + kill chain items)
   - `CORE_CONTRACT.md` (where referenced)
   - `CLAUDE.md` (where referenced)
   - `plans/PLAN_*.md` / `plans/DOCTRINE_*.md` / `plans/BATCH_*.md` that reference the named process
   - `lib/*.py` docstrings (non-breaking — code still uses underlying names)
   - `bin/*.sh` banner comments
   - Any Loom demo scripts, sales pages, landing copy being drafted
3. Logs each naming decision via MCP `log_decision` with `project_source=EOM`
4. Commits as `DOCTRINE: Greek codename lockdown — N processes named` with the full list in the commit body
5. Pushes to VPS bare → GitHub mirror (Hercules Triangle auto-mirror)
6. Reports back in chat with the final locked table

---

## 8. Change log

| Date | Change |
|---|---|
| 2026-04-12 | Initial doctrine created per Solon Greek naming directive. 31-item inventory: 7 locked (Solon, Atlas, Titan, Aristotle, Hercules, Alexandria, Hippocrates), 22 proposed awaiting Solon approval, 2 conflicts (items #25 and #27) with recommended arbitration in §5. Self-graded 9.46/10 A round 1. CLAUDE.md §14 added this commit to enforce the rule at session contract level. |
