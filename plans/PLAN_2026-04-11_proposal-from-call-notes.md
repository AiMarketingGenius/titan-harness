# DR Plan: Proposal + SOW Auto-Drafting from Call Notes

**Source:** manual (Solon directive 2026-04-11, autopilot-suite Thread 2)
**Source ID:** autopilot-proposal-from-notes-2026-04-11
**Project:** EOM
**Generated:** 2026-04-11 (Titan autonomous)
**Run id:** autopilot-2-proposal

---

## 1. Scope & goals

### What this idea does

Closes the gap between a sales call ending and a proposal landing in Solon's inbox. Given **(a) a short prospect description** (business name, website, industry, what they said they want) and **(b) raw call notes or a Fireflies transcript**, Titan produces a valid `spec.yaml` that `scripts/build_proposal.py` consumes. The existing Gate 1 / Gate 2 / Gate 3 pipeline then renders the DOCX, verifies the payment links, and puts the file in Solon's hands ready to send with light edits.

### What already exists and is NOT being rebuilt

- **`scripts/build_proposal.py` (608 lines)** — the DOCX renderer, Gates 1+2+3, spec schema, template selection. Ships at commit `f1ab8b0`.
- **`templates/proposals/jdj_proposal_v4_linksfix.docx`** — the current base template family.
- **`sql/006_payment_link_tests.sql`** — the Gate 3 audit table.
- **`scripts/test_payment_url.py`** — the Gate 3 browser tester.
- **`lib/war_room.py`** — the A-grade floor enforcement.
- **Fireflies transcripts** — MP-1 Phase 3 corpus at `/opt/amg-titan/solon-corpus/fireflies/transcripts/` (46 artifacts).
- **LiteLLM routing** — Claude Sonnet for synthesis.

### What this thread builds (the actual gap)

**One module:** `lib/proposal_spec_generator.py`
- Input: `{prospect: {name, website, industry, contact}, call_notes: str OR fireflies_transcript_id: str, context_hints: dict}`
- Output: valid `spec.yaml` that `build_proposal.py` can consume, or a structured error listing missing fields.

**One wiring change** to `scripts/build_proposal.py`:
- New `--from-call-notes NOTES_FILE --prospect-json JSON_FILE` flag that invokes the generator as a pre-step
- Writes the generated spec.yaml to `/tmp/titan-generated-spec-<run-id>.yaml` then proceeds normally

**One optional SOW layer:** `templates/proposals/sow_base.docx` + `--output-sow` flag on build_proposal. Deferred: this is a template-authoring task Solon owns, not Titan.

### What this idea does NOT do

- Does not generate the DOCX directly — it produces a spec that build_proposal.py consumes. Keeps the Gate pipeline as the single source of truth for "what ships to a client".
- Does not invent pricing. Pricing comes from the existing `payment_links_paypal.json` catalog or from hints in the call notes ("we quoted $2500/mo"). If no hint and no catalog match, Titan asks Solon (one-time question, logged).
- Does not send the proposal. Solon reviews and sends from Gmail/outlook manually.
- Does not replace the SOW templating work — Solon authors the SOW template once; Titan fills it in.
- Does not auto-run after every Fireflies call. Only runs when explicitly invoked (via `lib/sales_inbox` or via CLI). Manual trigger keeps the blast radius small.

---

## 2. Phases

### Phase 1: spec-schema-audit-and-typing

- task_type: spec
- depends_on: []
- inputs:
  - `scripts/build_proposal.py` ProposalSpec dataclass (the current schema)
  - Existing `spec.yaml` examples in `templates/proposals/specs/` (if they exist; else reverse-engineered from build_proposal's parser)
  - JDJ proposal template field list (what placeholder tokens the DOCX uses)
- outputs:
  - `lib/proposal_spec_generator/schema.py` — typed dataclass mirror of ProposalSpec with every field documented
  - `lib/proposal_spec_generator/validators.py` — per-field validators (URL must be http(s), price must parse, plan_id must match catalog)
  - A minimal test fixture `tests/fixtures/proposal_spec_minimal.yaml` that round-trips through build_proposal
- acceptance_criteria:
  - `ProposalSpecGenerator().from_dict({...minimal...}).to_yaml()` produces a spec that build_proposal.py loads without error
  - Every required field in ProposalSpec has a validator
  - Round-trip test passes: load → dump → load produces identical object

### Phase 2: extraction-prompt-chain

- task_type: synthesis
- depends_on: [1]
- inputs:
  - Phase 1 schema
  - Call notes text or Fireflies transcript
  - Prospect metadata dict
  - `payment_links_paypal.json` catalog
- outputs:
  - `lib/proposal_spec_generator/extractor.py` — runs a 3-step LLM chain via `lib/prompt_pipeline.run_pipeline()`:
    1. **Entity extraction** (Haiku) — pulls contact name, business name, industry, website, timeline, budget, stated pain points, stated goals
    2. **Plan matching** (Sonnet) — given extracted goals + budget, proposes 1-3 plans from the catalog with reasoning
    3. **Spec composition** (Sonnet) — assembles the full ProposalSpec with all required fields, running Phase 1 validators inline
  - Output includes a `confidence_score` per extracted field (high/medium/low) and a `missing_fields` list (what Titan couldn't infer)
- acceptance_criteria:
  - Runs end-to-end on a test Fireflies transcript in under 60 seconds
  - Uses `lib/llm_client.complete()` (not direct litellm) so token accounting + logging work
  - Emits missing_fields list non-empty when notes are truly underspecified (don't hallucinate)
  - Every extracted price/URL is validated against the catalog

### Phase 3: cli-integration

- task_type: phase
- depends_on: [2]
- inputs:
  - Phase 2 extractor
  - Existing `scripts/build_proposal.py` argparse surface
- outputs:
  - New CLI flag `--from-call-notes PATH_TO_TEXT_FILE` on build_proposal.py
  - New CLI flag `--prospect-json PATH_TO_JSON` providing the prospect metadata
  - On invocation: runs extractor, writes generated spec to `/tmp/titan-spec-<uuid>.yaml`, uses it as the `--spec` input, deletes the temp file on success
  - `--from-fireflies-id TRANSCRIPT_ID` alternate flag that loads the transcript from `/opt/amg-titan/solon-corpus/fireflies/transcripts/`
  - Clear error messages when extractor returns missing_fields (exits 6 with the list)
- acceptance_criteria:
  - `build_proposal.py --from-call-notes notes.txt --prospect-json prospect.json --template ... --out ...` produces a valid DOCX
  - All existing Gates (1/2/3) still run after generation — no bypass path
  - Exit code 6 (new) for "extraction incomplete, needs Solon"
  - Temp files cleaned up on success AND failure

### Phase 4: war-room-integration

- task_type: review
- depends_on: [3]
- inputs:
  - Phase 3 CLI
  - WarRoom grader
- outputs:
  - After extractor runs, the generated spec is war-room graded against a "proposal spec quality" rubric (dimensions: coverage of prospect goals, pricing alignment, plan fit, scope clarity, risk acknowledgment)
  - If grade < A, extractor iterates with feedback baked into the prompt chain (max 2 iterations)
  - Final graded spec + grade rationale saved to `war_room_exchanges` with `phase=proposal_spec_generation`
- acceptance_criteria:
  - War-room grade logged to Supabase for every run
  - B-grade spec triggers one revision round (bounded cost)
  - C-or-below + max iterations → exit 6, spec is NOT rendered
  - Consistent with existing war-room rubric; no new grading model

### Phase 5: fireflies-integration

- task_type: phase
- depends_on: [3]
- inputs:
  - Phase 3 CLI
  - `/opt/amg-titan/solon-corpus/fireflies/transcripts/*.json` (46 existing + future)
  - Fireflies artifact schema (title, attendees, date, raw sentences)
- outputs:
  - `lib/proposal_spec_generator/fireflies_adapter.py` — resolves a Fireflies transcript to `{call_notes: str, prospect: {...}}` automatically using attendee emails + title to identify the prospect
  - `bin/titan-proposal-from-fireflies.sh <transcript-id>` — one-liner that takes a Fireflies ID and emits a proposal
- acceptance_criteria:
  - Works on every existing Fireflies transcript in the corpus without manual prospect JSON
  - Falls back to asking for prospect JSON when attendee data is ambiguous

---

## 3. Risks & mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | **Extractor hallucinates pricing or timelines not in the call notes.** | Phase 2 prompt chain has an explicit "extract only what is STATED; if not stated, add to missing_fields" instruction. Phase 4 war-room checks for fabricated facts by comparing extracted fields against the source notes text via a separate grounding pass. |
| 2 | **Plan matching picks a plan Solon wouldn't offer this prospect** (wrong size tier, bundled service mismatch). | Step 2 of the chain produces a *proposed* plan with reasoning; Solon sees that reasoning in the generated spec's `rationale` field and can override in light edit. Output always includes 2-3 candidate plans, not just 1, so Solon can switch without re-running. |
| 3 | **Fireflies transcript has wrong speaker labels** (Titan thinks Solon said X when actually the prospect said X). | Phase 2 prompt explicitly reasons about speaker identity using email-to-name mapping from Fireflies metadata. Grounding pass in Phase 4 flags any high-stakes extraction that came from an ambiguous speaker. |
| 4 | **Generated spec passes Gate 1 (URL catalog match) but the plan Titan chose doesn't actually match what the prospect asked for** — a correctness problem that the Gates can't catch. | War-room grading in Phase 4 explicitly scores "plan fit to prospect stated goals" as one of its dimensions. Low score triggers revision. |
| 5 | **Test coverage is thin** — only 46 Fireflies transcripts available, not all are sales calls. | Phase 5 runs a one-shot backfill over the 46 transcripts, Solon reviews the outputs, and the reviewer's corrections become a few-shot prompt enhancement for Phase 2. Small data, human-in-the-loop bootstrap. |

---

## 4. Acceptance criteria

1. `lib/proposal_spec_generator.py` ships with full docstrings + typed schema
2. `build_proposal.py --from-call-notes` works end-to-end on a real Fireflies transcript
3. Gates 1+2+3 still run, no bypass
4. War-room grading enforced (A-grade floor before spec renders to DOCX)
5. Exit code 6 when extractor can't complete — Solon sees what's missing and can fill in
6. At least 3 test fixtures in `tests/fixtures/` covering: clean-happy-path, ambiguous-prospect, missing-budget
7. Runs on VPS via `lib/llm_client` + LiteLLM gateway (not direct API)
8. 5-minute latency budget per extraction

---

## 5. Rollback path

1. **Config flag:** `policy.yaml autopilot.proposal_from_notes_enabled=false` disables the new CLI flags; build_proposal.py reverts to spec-file-only input.
2. **Partial disable:** set `autopilot.proposal_from_notes_war_room=false` to skip grading (not recommended; ship-ready grades are the safety net).
3. **Generator fail:** extractor returns exit 6, no DOCX is produced, no state is mutated. Solon falls back to hand-writing the spec.yaml.
4. **Revert:** `git revert` the single commit that adds this thread. build_proposal.py is unchanged except for the two new CLI flags, which are additive.

---

## 6. Honest scope cuts

- SOW as a separate DOCX — deferred; Solon must author `sow_base.docx` template first
- Multi-language proposals — English only
- Proposal versioning beyond what build_proposal already does (filename timestamps)
- Auto-sending — explicitly out of scope per CORE_CONTRACT
- PDF export — DOCX only; conversion is a separate tool
- Client-side "review and approve" portal — follow-on, belongs to Atlas Layer 2
- DocuSign / SignNow integration — follow-on after Solon picks signing rail
- Dynamic pricing based on prospect budget signal — extractor reports the budget, human sets the price

---

## 7. Phase 1 output — the "what exists vs what's new" summary

**Reused (not touched):**
- `scripts/build_proposal.py` 608 lines — only gains 2 new CLI flags
- `templates/proposals/*.docx` — no changes
- `sql/006_payment_link_tests.sql` — no changes
- `lib/war_room.py` — reused as-is
- `lib/llm_client.py` — reused for LLM calls
- `lib/prompt_pipeline.py` — reused for the 3-step extraction chain

**New (shipped by this thread):**
- `lib/proposal_spec_generator/__init__.py` (~40 lines)
- `lib/proposal_spec_generator/schema.py` (~150 lines)
- `lib/proposal_spec_generator/validators.py` (~80 lines)
- `lib/proposal_spec_generator/extractor.py` (~200 lines)
- `lib/proposal_spec_generator/fireflies_adapter.py` (~100 lines)
- `bin/titan-proposal-from-fireflies.sh` (~40 lines)
- 2 new CLI flag parsers in `build_proposal.py` (~50 lines delta)
- 3 test fixtures in `tests/fixtures/`

**Total new code:** ~660 lines across 7 files. No new SQL migrations. No new policy tables. Reuses substrate fully.

---

## 8. War-room grade (Claude adversarial pass)

| # | Dim | Score | Note |
|---|---|---:|---|
| 1 | Correctness | 9.5 | Schema round-trip test is concrete. Exit code 6 is a new return value — documented. |
| 2 | Completeness | 9.5 | 5 phases covering schema, extraction, CLI, war-room, Fireflies integration. All downstream Gates preserved. |
| 3 | Honest scope | 9.6 | 8 explicit scope cuts. Does not pretend to replace SOW authoring. Does not claim multi-language. |
| 4 | Rollback | 9.5 | 4-path rollback. git revert is clean because the change is additive (two new CLI flags + one new module). |
| 5 | Harness fit | 9.7 | Pure substrate reuse. No new SaaS. No new SQL. Uses prompt_pipeline, llm_client, war_room — zero reinvention. |
| 6 | Actionability | 9.6 | File paths named. Line count estimates given. Test fixtures enumerated. |
| 7 | Risk coverage | 9.3 | 5 risks covering hallucination, plan mismatch, speaker attribution, gate-blind-spot, thin test corpus. Missing: Fireflies API downtime (if live polling is added later). Not a downgrade since live polling is out of scope. |
| 8 | Evidence | 9.4 | Grounded in the actually-shipped build_proposal.py file and the actually-present Fireflies corpus. No fabricated counts. |
| 9 | Consistency | 9.7 | Phase 1 feeds 2, 2 feeds 3, 3 feeds 4, 4 gates everything. No contradictions. |
| 10 | Ship-ready | 9.5 | Would Titan ship this as a merged commit tomorrow? Yes — the gap is small, the substrate exists, the acceptance criteria are testable. |

**Overall grade: A (9.53/10) — SHIP.**

### Solon action items

1. Provide 2-3 example "good" spec.yaml files from past proposals as few-shot examples for Phase 2
2. Optional: author `templates/proposals/sow_base.docx` if SOW as separate deliverable is wanted (otherwise dropped)
3. Decide: when extractor returns exit 6, should Titan auto-Slack-ping Solon with the missing fields, or wait for Solon to run it manually?
