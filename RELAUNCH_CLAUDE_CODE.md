# RELAUNCH_CLAUDE_CODE — how to restart a Titan session

**Last verified:** 2026-04-11 after mirror reconciliation (commit `28d3b70`).

## 1. Which folder to open

**Always open this exact path in the Claude Code desktop app (and the mobile CLI):**

```
/Users/solonzafiropoulos1/titan-harness
```

Alias path (via symlink, identical): `~/bin/titan-harness`

**Never** open from:
- Any iCloud Drive path (`~/Library/Mobile Documents/…`) — macOS evicts silently and kills bash.
- `~/bin/titan-harness.legacy.bak` — that's the pre-mirror tree, kept only as a safety net.

## 2. Flags + session behavior

When the session opens:
1. **Type `/fast` once** in the Claude Code terminal. Toggles fast-mode output streaming (same Opus 4.6 model, faster TTFT). You have to do this; I can't toggle it from inside the session.
2. Confirm bash is alive: `pwd && ls` should show the titan-harness tree including `CORE_CONTRACT.md`, `IDEA_TO_EXECUTION_PIPELINE.md`, `policy.yaml`, `lib/`, `scripts/`, `sql/`.
3. Titan will auto-load memory from `~/.claude/projects/-Users-solonzafiropoulos1-bin-titan-harness/memory/` — this is already populated with 50+ feedback/project/reference files.

## 3. First message to Titan on a fresh session

Copy-paste this exactly:

```
RESUME FROM NEXT_TASK.md (mirror complete)
```

That triggers Titan to:
1. Read `~/titan-session/NEXT_TASK.md`
2. Read `MEMORY.md` index + all relevant memory files
3. Run `get_bootstrap_context` (standing rules + sprint state + recent decisions)
4. Run `get_sprint_state EOM` to confirm the kill chain
5. Report back with a terse boot status + next action

## 4. What's true as of this save (things Titan already knows but the fresh session will need to verify)

- **Mirror status:** `~/titan-harness` (Mac), `/opt/titan-harness` (VPS working tree), `/opt/titan-harness.git` (bare) all at commit **`28d3b70`**. `.gitignore` excludes `__pycache__/`, `*.pyc`, `*.bak.*`, `plans/`, secrets.
- **Gate 3 work (held):** `scripts/build_proposal.py` has a local Mac-only edit adding `verify_gate3_payment_link_tests()` + `--skip-gate3` flag + exit code 5. Untracked: `scripts/test_payment_url.py`, `sql/006_payment_link_tests.sql`. **Not committed, not pushed.** Solon held the ship. To resume Gate 3: apply sql/006 to Supabase via the SQL Editor, run `scripts/test_payment_url.py` against a real URL, commit the build_proposal.py edit + the two untracked files, push.
- **AMG Atlas naming:** CLEARED 2026-04-11. House-brand rule = AMG always leads. "AMG Atlas" ships. Memory: `project_atlas_naming_trademark_risk.md`.
- **Slack war-room via Perplexity:** direction set but NOT yet wired. Solon wants `#titan-perplexity-warroom` (or similar name) with Perplexity Slack app invited, war-room replies flow back via Slack API. Architecture sketch is in the recent decision log; code not written.
- **MP-1 HARVEST:** 43% complete. Phases 6 (Slack, 37 artifacts) + 7 (MCP decisions, 773) + 8 (manifest) done. Phases 1 + 2 + 5 need their harvester scripts WRITTEN (they don't exist on VPS). Phase 3 Fireflies reconciled from disk (46 artifacts). Phase 4 Loom needs creds. Solon wants Phase 1 + 2 (+ 4) harvesters pre-built before a batched 2FA/credential session. See `/opt/amg-titan/solon-corpus/.checkpoint_mp1.json` on VPS for current state.
- **CORDCUT scoping corrected:** CORDCUT = Phases 4 + 5 only (Portal Rebuild + Multi-Lane Mirror v1.1). NEXT_TASK.md's "Phase 2 — CORDCUT 1-3 verify" was a misread. 5 prereqs block starting Phase 4-5: no portal Caddy block, no portal source tree, missing `PROMPT_2_MULTI_LANE_MIRROR_v1.1_EXECUTION.md` spec, no CT-0408-24 artifacts, "Lovable edits complete" unconfirmed.

## 5. Hard rules Titan must honor (burned to memory, reminder for fresh session)

- No AskUserQuestion dialogs — plain chat only.
- Silent COO mode: lead with action, no preamble, terse.
- Only IC 009/035/042 matter for TM analysis; evaluate "AMG [X]" as composite with house-brand distinctiveness; ignore cross-class hits.
- A-grade floor (9.4+) is mandatory on every war-room deliverable.
- Never launch Claude Code from an iCloud-backed path.
- Trade-secret list stays out of client-facing output.
- All the other feedback memories — read `MEMORY.md` index and follow the rules they encode.

## 6. Fresh-session sanity check (Titan should run these within the first minute)

```bash
git -C ~/titan-harness log --oneline -1   # should print: 28d3b70 Merge origin/master...
ls ~/titan-harness/CORE_CONTRACT.md       # should exist
git -C ~/titan-harness status -s           # expected: M scripts/build_proposal.py + 2 untracked
```

If any of those fail, STOP and alert Solon — the mirror drifted.
