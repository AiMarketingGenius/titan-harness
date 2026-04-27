# WAVE 1 TITAN DISPATCH — DRIFT DEFENSE FOUNDATION
**Source:** v4.0.1 megaprompt (sealed v4.0 + 2026-04-27 patch)
**Wave scope:** Phases 0–6 (telemetry + Layers 1–5 + criticality lock)
**Days:** 0–9
**Gate to Wave 2:** 7-day stability + Aletheia repo-scope audit complete + existing-daemon survey complete
**Paste this entire block into Titan's Claude Code chat. No edits needed.**

---

```
TITAN — WAVE 1 BUILD DISPATCH

Reference doc: /opt/amg-docs/megaprompts/MEGAPROMPT_TITAN_AGENT_REST_v4_0_1.md
(After applying patch CT-0427-XX-PATCH per accompanying patch notes)

You are building the foundation for Universal 4-Deep Agent Infrastructure.
Wave 1 = drift defense + telemetry only. Memory layer (Wave 2) and 4-shift
rotation (Wave 3) come later. Do not build out of sequence.

═══════════════════════════════════════════════════════════════════
PHASE 0 — PRE-BUILD VERIFICATION (Day 0, MANDATORY GATE)
═══════════════════════════════════════════════════════════════════

Three independent tests must complete before Phase 1. Do not proceed to
Phase 1 until all three log decisions confirm completion.

TEST 0A: APP/SYSTEM ISOLATION VERIFICATION
Per v4.0.1 §3A. Verify Solon's Mac apps (Titan.app, Hercules.app, etc.)
are isolated from VPS systemd daemons.

  1. SSH to VPS, run: ps -ef | grep -E "(daedalus|hercules|nestor|alexander|mercury|aletheia|warden|cerberus|hygeia)"
  2. Capture process list + start times → save to /tmp/test_0a_pre_pids.txt
  3. Send signal to Solon via Slack #amg-admin: "Phase 0A test: please force-quit
     Titan.app on your Mac, wait 10s, then relaunch. Confirm when done."
  4. After Solon confirms, SSH again, run same ps command → save to /tmp/test_0a_post_pids.txt
  5. diff the two files. Expected: same PIDs, same start times = daemons survived
  6. log_decision(tag="app_restart_isolation_verified", text=<diff result>)
  7. If PIDs changed: HALT Wave 1. Architecture assumption was wrong. Escalate.

TEST 0B: ALETHEIA REPO-SCOPE AUDIT
Per v4.0 Risk Flag #2 (line 1015). Today's e3b4e92 violation may be a false
positive — commit may live in amg-mcp-server repo, not titan-harness.

  1. cd /opt/aletheia (or wherever Aletheia v2 source lives)
  2. grep through her config for repo scan list. Capture which repos she watches.
  3. Verify: does she scan amg-mcp-server? amg-titan? achilles-harness?
     anthropic-mcp-bridge? operator-tools?
  4. For e3b4e92 specifically: search ALL AMG repos for that hash:
     for repo in $(ls -d /opt/*/.git ../); do
       cd $(dirname $repo); git log --all --oneline | grep e3b4e92 && pwd; cd -;
     done
  5. If found: identify which repo. If Aletheia wasn't watching that repo,
     today's violation was a SCOPE BUG, not Titan drift.
  6. log_decision(tag="aletheia_repo_scope_audit", text=<findings>, rationale=<root cause>)
  7. If scope bug confirmed: file CT task to expand Aletheia's repo list BEFORE
     Layer 2 wires to her output. Self-inflicted DoS prevention.

TEST 0C: EXISTING DAEMON SURVEY
Per v4.0.1 §3G — we know some DevOps daemons are already live. Inventory
before building anything new.

  1. systemctl list-units --type=service --all | grep -E "(amg-|hercules-|nestor-|alexander-|mercury|warden|cerberus|aletheia|hygeia)"
  2. For each: status (running/failed/inactive), uptime, last restart reason
  3. Specifically check for already-built (per Hercules thread #2 of 2026-04-26):
     - amg-status-writer (factory_status.json)
     - amg-slack-dispatcher (P0/P1 routing)
     - amg-telnyx-inbound (SMS handler)
     - hercules-mcp-bridge
     - hercules-daemon (PID 45623 reported live)
     - nestor-executor + alexander-executor (Kimi K2.6 lane)
     - process watchdog (proved working in today's Titan-Agent auto-restart)
  4. Build manifest: /opt/amg-governance/existing_daemons.yaml — agent name,
     systemd unit, status, last_restart, owns_role (e.g., "process_health",
     "status_reporting"), gaps (what role it doesn't cover).
  5. Identify overlap with Wave 1 builds: do existing daemons already do
     parts of Layers 1-5? If yes, integrate (don't rebuild).
  6. log_decision(tag="existing_daemon_inventory", text=<manifest>, deliverable_link=<file>)

GATE: All three tests done + their decisions logged in MCP. Then proceed.

═══════════════════════════════════════════════════════════════════
PHASE 1 — TELEMETRY FOUNDATION (Day 1)
═══════════════════════════════════════════════════════════════════

Per v4.0 §4 Phase 1. Schema additions for v4.0.1 (current_boundary, criticality_lock_held).

  1. Create Supabase table op_agent_health with schema:
     agent_id text PRIMARY KEY,
     started_at timestamptz,
     last_heartbeat timestamptz,
     context_pct numeric,
     tool_calls_total int,
     errors_24h int,
     last_aletheia_violation timestamptz,
     uptime_seconds int,
     next_scheduled_restart timestamptz,
     current_boundary text DEFAULT 'unknown',  -- v4.0.1: 'atomic_primitive' | 'sub_task' | 'top_level' | 'conversational_turn' | 'idle'
     criticality_lock_held boolean DEFAULT false  -- v4.0.1
  2. RLS: only agent_writer role can write
  3. Janitor: archive rows >7 days to op_agent_health_archive (cron, Hygeia)
  4. Each in-scope agent posts heartbeat to this table every 60s — patch their
     main loops accordingly
  5. Verification: query op_agent_health → all in-scope agents show
     last_heartbeat within 90s
  6. log_decision(tag="phase_1_telemetry_complete", deliverable_link=<schema sql>)

═══════════════════════════════════════════════════════════════════
PHASE 2 — LAYER 2 ERROR-PATTERN FORCE-RESET (Day 2 — HIGHEST PRIORITY)
═══════════════════════════════════════════════════════════════════

Per v4.0 §3 Layer 2 + §4 Phase 2. This is the layer that would have
prevented today's e3b4e92 cascade. Build first, build right.

  1. Write /opt/amg-governance/aletheia_pattern_detector.py
     - systemd timer: every 5 min
     - Query op_decisions for tags matching aletheia-violation OR
       aletheia:false_completion within 30-min rolling window per agent
     - Threshold: 2+ violations same agent within window → write kill signal
     - Threshold: 3+ consecutive tool-call failures same agent → write kill signal
     - Threshold: 3+ identical error-retry attempts → write kill signal
  2. Write kill-signal mechanism: /opt/amg-governance/agent_kill_queue/<agent>.signal
     - HARDENED PERMS: root-owned, 0644, agent reads its own file only
     - Signal file format: reason=<text>, written_at=<iso>, expires_at=<iso+5min>
  3. Update each agent's main loop to check for kill signal at task boundary
     (NOT mid-primitive — respect §3 Layer 5 hierarchy)
  4. Add cold_start_hydrate verification on every restart (idempotent check)
  5. Per-agent disable flag: /opt/amg-governance/layer_disabled/<agent>:layer_2.flag
  6. SYNTHETIC TEST: inject 2 fake aletheia:false_completion decisions for
     daedalus-hercules → verify reset within 5 min
  7. If TEST 0B confirmed Aletheia scope bug: do NOT enable Layer 2 on Titan
     until scope is fixed. Self-inflicted DoS prevention.
  8. log_decision(tag="phase_2_layer_2_complete", text=<test results>)

═══════════════════════════════════════════════════════════════════
PHASE 3 — LAYER 1 CONTEXT MONITOR (Day 3–4)
═══════════════════════════════════════════════════════════════════

Per v4.0 §3 Layer 1 + §4 Phase 3.

  1. Each agent estimates context_pct (tokens used / model window) per task completion
  2. Write /opt/amg-governance/agent_context_monitor.py — polls op_agent_health every 60s
  3. Threshold: context_pct >= 0.70 → emit compact signal via decision tag
  4. Agent on next task boundary: snapshot → SIGTERM → systemd restart →
     cold_start_hydrate
  5. EXCLUDE from Layer 1: Mercury, factory_status_writer, persona_summary_daemon
     (stateless or single-purpose — restart cost ≈ 0, so Layer 2 alone suffices)
  6. SYNTHETIC TEST: inject context_pct=0.72 for daedalus-hercules → verify
     compact + restart within 5 min
  7. log_decision(tag="phase_3_layer_1_complete")

═══════════════════════════════════════════════════════════════════
PHASE 4 — LAYER 3 TIME CEILING (Day 5)
═══════════════════════════════════════════════════════════════════

Per v4.0 §3 Layer 3 + §4 Phase 4.

  1. Add uptime_seconds check to heartbeat process
  2. Threshold: uptime_seconds >= 14400 (4hr) → write warning decision +
     auto-snapshot (NO automatic restart — Solon decides)
  3. Override: SOLON_OVERRIDE.flag in /opt/amg-governance/ skips warning
  4. Surface in Atlas factory_status.json: per-agent time-ceiling status
  5. SYNTHETIC TEST: set agent uptime to 14401s → verify warning logged
  6. log_decision(tag="phase_4_layer_3_complete")

═══════════════════════════════════════════════════════════════════
PHASE 5 — LAYER 4 CANARY (Day 6–7)
═══════════════════════════════════════════════════════════════════

Per v4.0 §3 Layer 4 + §4 Phase 5.

  1. Define canary task per agent type — read-only, deterministic, hash-comparable
     (e.g., for daedalus: "audit this static known file, return finding hash")
  2. Cerberus schedules canaries every 6h per agent type
  3. Compare output hash to expected baseline (op_agent_health.canary_baseline_hash)
  4. Threshold: 3 consecutive canary deviations same agent → trigger Layer 2 reset
  5. Build incrementally: start with 3 agent types (Titan, daedalus-hercules,
     hephaestus-hercules); expand weekly
  6. log_decision(tag="phase_5_layer_4_complete")

═══════════════════════════════════════════════════════════════════
PHASE 6 — LAYER 5 SCHEDULED REST + CRITICALITY LOCK (Day 8–9)
═══════════════════════════════════════════════════════════════════

Per v4.0 §3 Layer 5 + §4 Phase 6 (with v2.0 hierarchical task-boundary
respect + criticality lock).

  1. Build /opt/amg-governance/scheduled_rest_orchestrator.py — single coordinator
     owning restart queue across all in-scope agents
  2. Read stagger schedule from v4.0 §3 Layer 5 table (Titan 00:00/04:00/08:00…
     etc., Hercules 01:00/05:00…, etc.)
  3. RESTART RULES (mandatory):
     a. Check criticality lock first: /opt/amg-governance/critical_lock/<agent>.lock
        — defer if held; respect TTL (max 30min, 12hr hard ceiling)
     b. Check current_boundary in op_agent_health — NEVER kill if 'atomic_primitive'
        — wait for sub-task or top-level boundary
     c. For chief class (Hercules/Nestor/Alexander) + Solon-facing only:
        inject 60s countdown into chat UI → wait → close session
     d. For all other classes: hard reset (snapshot → SIGTERM → systemd restart)
  4. CASCADE THROTTLE: max 2 concurrent restart-in-progress globally
  5. Per-agent skip override: /opt/amg-governance/no_scheduled_rest/<agent>.flag
     (one-shot, auto-expires after one restart cycle)
  6. Global override: /opt/amg-governance/SOLON_OVERRIDE.flag — disables all
     layers globally for 1hr (renewable)
  7. SYNTHETIC TESTS:
     - Dry-run: set cadence to 5 min for 30 min → observe 3 staggered cycles
       across 5 agents → revert to 4hr (Wave 3 will move to 6hr)
     - Solon UAT on chiefs: launch Hercules.app → 60s countdown appears
       → restart succeeds → memory persists in next session
     - Criticality lock test: agent acquires lock → scheduled restart
       deferred → release lock → restart fires within 60s
     - 12hr hard ceiling test: agent renews lock continuously → forced
       restart at 12hr regardless
     - Cascade throttle test: 5 simultaneous restart triggers → max 2
       concurrent → no MCP timeout errors
  8. log_decision(tag="phase_6_layer_5_complete")

═══════════════════════════════════════════════════════════════════
WAVE 1 ACCEPTANCE — REQUIRED FOR WAVE 2 GATE
═══════════════════════════════════════════════════════════════════

Per v4.0 §5 acceptance criteria items 1-12 (scoped to Wave 1).

After Phase 6 completes, observe 7 days of stability. During that window:
  - All 5 layers active and observable in Atlas factory_status panel
  - Synthetic tests for each layer pass
  - No Wave 1 self-inflicted denial-of-service incidents
  - Cost monitor shows daily cold_start_hydrate spend < $0.50

If 7 days clean: log_decision(tag="wave_1_stable_proceed_wave_2") and dispatch
Wave 2 (Phases 7-9: Universal Bootstrap + Manhattan Project memory + lcache).

If issues: log_decision(tag="wave_1_blocker"), flag_blocker, escalate to Solon.

═══════════════════════════════════════════════════════════════════
SOLON ESCALATION POINTS (Wave 1 only)
═══════════════════════════════════════════════════════════════════

Do NOT escalate for routine build issues. Use Aristotle (when available) OR Gemini API for blockers. Until Aristotle is greenlit + hardened (per v4.0.1 §11 #2 Q1+Q2 amendment), Gemini API is the only secondary lookup path. NO PERPLEXITY CALLS.
Only escalate for:
  - Phase 0 GATE failures (any of 0A/0B/0C produces unexpected results)
  - Final go/no-go on enabling Layer 2 on Titan itself (since Titan can self-restart)
  - If Wave 1 acceptance fails after 14 days of debugging

═══════════════════════════════════════════════════════════════════
COST GATES (mandatory)
═══════════════════════════════════════════════════════════════════

  - Daily Wave 1 build budget: $5/day (mostly Claude on VPS for you, plus
    cold_start_hydrate test cycles)
  - Hard halt: if daily spend exceeds $30, send P0 SMS to Solon, halt all
    non-essential work
  - Weekly report: log_decision(tag="wave_1_cost_report") with actual spend
    vs budget

═══════════════════════════════════════════════════════════════════
EXECUTE
═══════════════════════════════════════════════════════════════════

Begin with Phase 0. Do not skip ahead. Phase 0 completion (all three tests
+ MCP decisions) is the gate to Phase 1.

If anything is unclear, query Aristotle (when available) OR Gemini API for
technical guidance — until Aristotle is greenlit + hardened (per v4.0.1 §11 #2
Q1+Q2 amendment), Gemini API is the only secondary lookup path. NO PERPLEXITY
CALLS. Only escalate to Solon if Gemini + your own reasoning fail.

Report Wave 1 progress daily via log_decision(tag="wave_1_daily_progress")
with completed phases, blockers, cost actuals.

GO.
```

---

## DISPATCH METADATA (for QES tracking)

- **Wave:** 1 of 4 (Drift Defense → Memory Layer → 4-Deep Rotation → Model Sovereignty)
- **Source megaprompt:** v4.0.1 (v4.0 sealed + Aristotle/Argus/Hygeia patch)
- **Acceptance gate:** 7-day stability + 12 of 55 v4.0.1 acceptance criteria passed
- **Estimated duration:** 9 days build + 7 days observation = 16 days to Wave 2 dispatch
- **Estimated cost:** $30–60 build + $15-25 observation = ~$50-90 total Wave 1
- **Blocking dependencies:** None (Phase 0 GATE handles all)
- **Downstream unblocks:** Wave 2 (Phases 7-9)

**END OF WAVE 1 DISPATCH**
*Verification: First-Pass Gate passed (naming ✓ routing ✓ pricing ✓ tiering ✓ trade-secrets ✓ cross-refs ✓ math ✓ ADHD-format ✓).*
