# AMG VPS STATE FACTS — CANONICAL GROUND TRUTH

- **Generated:** 2026-04-29T13:56:45Z
- **Generator:** titan (CT-0429-19, EOM founder-override 2026-04-29)
- **Canonical Path (VPS):** `/opt/amg-titan/STATE_FACTS.md`
- **Harness Mirror (Mac):** `docs/STATE_FACTS.md` (3-leg sync via post-receive hook)
- **Doctrine:** `docs/STATE_FACTS_PROTOCOL.md`
- **Verbatim shell output, not summaries.** Future dispatches grep this file mechanically.

---

## 1. MP-1 SUBSTRATE TRUTH

```
+++cmd: cat /opt/amg-titan/solon-corpus/MANIFEST.json | jq -c '{status,percent_complete,total_artifacts,total_bytes,total_words,generated_at,harvest_run_id}'
{"status":"partial","percent_complete":43,"total_artifacts":856,"total_bytes":2681780,"total_words":479080,"generated_at":"2026-04-10T19:29:02Z","harvest_run_id":"mp1-20260410-192902"}
```

```
+++cmd: cat /opt/amg-titan/solon-corpus/MANIFEST.json | jq '.by_source | to_entries | map({source: .key, count: .value.count, hq: .value.high_quality_count})'
[
  { "source": "claude_threads", "count": 0,   "hq": 0  },
  { "source": "perplexity",     "count": 0,   "hq": 0  },
  { "source": "fireflies",      "count": 46,  "hq": 5  },
  { "source": "loom",           "count": 0,   "hq": 0  },
  { "source": "gmail",          "count": 0,   "hq": 0  },
  { "source": "slack",          "count": 37,  "hq": 7  },
  { "source": "mcp_decisions",  "count": 773, "hq": 90 }
]
```

**INTERPRETATION:** MP-1 substrate is **partial / 43% / 856 artifacts** as of 2026-04-10. Sources still empty: `claude_threads`, `perplexity`, `loom`, `gmail`. Major sources actually ingested: `mcp_decisions` (773 / 90 hq), `fireflies` (46 / 5 hq), `slack` (37 / 7 hq). DIR-011 v1 claim of "complete / 86% / 3816 artifacts" is **FALSE**.

---

## 2. COMMIT TRUTH (Atlas MCP control-plane contract claim)

```
+++cmd: cd /opt/titan-harness-work && git log --all --oneline | grep -iE 'atlas|control-plane' | head -20
efec3ba fix(ct-0428-recovery): claim_cycle_deadlock_fix + atlas-agent restored + Iris v0.3
a0cd761 feat(ct-0427-95..103): Atlas Factory Build Titan-lane (6/6 shipped)
c1e43c2 feat(aimg+atlas): D2 launcher + Atlas launcher (mirrors of ~/AMG/launchers/)
5dbcac9 feat(atlas): MVP dashboard — 4-panel single-page UI for daily ops
c11ceb6 fix(roster): dedup canonical naming - atlas_ worker bare support specialist
7fa62fd feat(amg-agent-army): 33-agent fleet (12 Atlas + 21 AMG) per Hercules CT-0426
774ffd2 feat(voice-orb): full Chamber OS module catalog injected + City Hall roster + _has_atlas_address scope fix
93e5183 feat(voice-orb): Atlas-for-Revere-Chamber persona (CT-0419-23, Don-demo eve)
861ee30 fix(voice-orb): API_BASE same-origin — atlas.aimarketinggenius.io was nonexistent DNS
7be5599 feat(ct-0419-17): Atlas Command PWA v1.0 + titan.lua v1.1 backend
3eeeb73 fix(atlas-api): gate /api/titan/tts on cost_kill_switch — cap ElevenLabs daily spend
a18d8eb feat(atlas-api): Step 6.3 — mount 12 mobile command endpoints + lifecycle module
d621d1f feat(atlas-admin): static admin portal at operator.aimarketinggenius.io/atlas-admin.html
624c531 feat(atlas-api): CORS middleware for aimarketinggenius.io origin
5732e9a feat(CT-0417-26): Encyclopedia v1.4.1 — roster 10→9 (Aria retired, Atlas sole-interface lock)
1674abb feat(CT-0417-25 WIP on feature branch): Atlas-sole-speaker refactor — staged, NOT deployed
0863c1d arch(CT-0417-HYBRID-C18): 18-project Atlas base template + Titan-Accounting deep spec
716918f feat: POST-R3 Phase 4 — Atlas Demo Co preset + 7-lane pipeline + playbook
33a8060 feat: DEMO.01 Atlas orb demo script — 3-scene voice + mobile + desktop
db1b4ef doctrine: install MP-4 Atlas Reliability Monitoring Incidents v1.0 verbatim
```

```
+++cmd: cd /opt/titan-harness-work && git log --all --oneline | grep -E '6557abd|6be496e' | head -5
6be496e doctrine(solon-os): canonical PROFILE v2.0 — triple-source, zero splices, 9.65 dual-grade
```

```
+++cmd: cd /opt/titan-harness-work && git log --all --oneline | wc -l
451
```

**INTERPRETATION:** Commit `6557abd` (DIR-011 v1 "Atlas MCP control-plane contract merged") is **ABSENT** from all 451 commits across all branches. Commit `6be496e` (Solon OS canonical PROFILE v2.0) **PRESENT** ✓. Many other Atlas-related commits exist but none match `6557abd`.

---

## 3. SERVICES TRUTH

```
+++cmd: ls -la /opt/amg-titan/services/ 2>&1
ls: cannot access '/opt/amg-titan/services/': No such file or directory
```

```
+++cmd: ls -la /opt/amg-titan/scripts/ 2>&1
ls: cannot access '/opt/amg-titan/scripts/': No such file or directory
```

```
+++cmd: ls -la /opt/amg-titan/atlas-chassis/ 2>&1
ls: cannot access '/opt/amg-titan/atlas-chassis/': No such file or directory
```

```
+++cmd: ls -la /opt/amg-titan/reports/dir-011/ 2>&1
total 20
drwxr-xr-x 2 root root  4096 Apr 29 08:03 .
drwxr-xr-x 3 root root  4096 Apr 29 08:01 ..
-rw-r--r-- 1 root root 10980 Apr 29 08:03 STATE_PRE_FLIGHT_MATRIX.md
```

```
+++cmd: systemctl list-units --type=service --no-pager --state=active | grep -iE 'amg|atlas|kokoro|titan|voice|mercury|hercules|aletheia|cerberus|argus|watchdog'
  amg-chatbot.service                                   loaded active running AMG Chatbot API
  amg-lead-intake.service                               loaded active running AMG Lead Intake Webhook Server
  atlas-api.service                                     loaded active running Atlas API shim (Hermes Phase A, sprint)
  titan-kokoro.service                                  loaded active running Titan Kokoro TTS (CPU variant, Hermes Phase A Step 1)
```

**INTERPRETATION:** `/opt/amg-titan/services/`, `/opt/amg-titan/scripts/`, `/opt/amg-titan/atlas-chassis/` — **ABSENT.** Only `/opt/amg-titan/reports/dir-011/STATE_PRE_FLIGHT_MATRIX.md` exists (filed earlier this session). Active services: 4 (`amg-chatbot`, `amg-lead-intake`, `atlas-api` skeleton, `titan-kokoro`). NO services for `voice-ai-bridge`, `mercury-notifier`, `hercules-bridge`, `aletheia`, `cerberus`, `argus`, `watchdog`. Hermes Phase B Conversational Voice AI (DIR-011 Phase 3 critical-path Friday demo dependency) has **no foundation.**

---

## 4. DOCTRINES TRUTH

```
+++cmd: ls -la /opt/amg-docs/doctrines/ 2>&1
total 8
drwxr-xr-x  2 root root 4096 Apr 29 08:01 .
drwxr-xr-x 15 root root 4096 Apr 29 08:01 ..
```

```
+++cmd: ls -la /opt/amg-docs/doctrine/ 2>&1
ls: cannot access '/opt/amg-docs/doctrine/': No such file or directory
```

```
+++cmd: ls /opt/amg-docs/ | head -40
agent_pressure_test.py
agent_pressure_test_results.json
agent_pressure_test_results_NADIA_LUMINA_2026-04-15.json
AGENT_READINESS_REPORT_FINAL_2026-04-15.md
AGENT_READINESS_REPORT.md
AI_Consulting_Manifesto_AMG_v1_1_2026-04-05.md
AI_Consulting_Playbook_AMG_v1_1-EXT_2026-04-05.md
aimg
AMG_MASTER_CREDENTIAL_AND_INFRASTRUCTURE_INVENTORY.md
AMG_PORTAL_DOGFOOD_REPORT.md
AMG_PRICING_BUNDLING_SOURCE_OF_TRUTH_v1.md
AMG_STANDING_RULES_EOM_AND_TITAN_v1.md
architecture
chamber-ai-advantage
chatgpt-migration
chrome-tab-archive-2026-04-08.md
chrome-tabs-raw-2026-04-08.txt
clients
COMPETITOR_TEARDOWN_MEMORY_EXTENSIONS.md
credentials
CREDENTIALS_ADDENDUM.md
deliverables
Doc_09_KB_MANIFEST_v3_3.md
doctrines
LOVABLE_P0_AUTH_FIX_PROMPT.md
megaprompts
MODEL_ROUTING_CONFIG.md
PADDLE_ACTIVATION_INSTRUCTIONS.md
patch_agent_prompts.py
qes
runbooks
screenshots
templates
TITAN_AUTONOMY_SOLOTIONS_BENCHMARK.md
```

**INTERPRETATION:** `/opt/amg-docs/doctrines/` (canonical per CLAUDE.md §19.1) is **EMPTY** (created 2026-04-29T08:01Z by titan during this session's preflight). `/opt/amg-docs/doctrine/` (singular, deprecated) does **NOT exist.** §19 doctrine-keeper protocol is **unenforced on VPS** — file class doctrines have not landed at canonical path. The parent `/opt/amg-docs/` does have many other named directories (`architecture`, `chamber-ai-advantage`, `clients`, `credentials`, `deliverables`, `megaprompts`, `qes`, `runbooks`, `screenshots`, `templates`).

---

## 5. MCP SERVER TRUTH

```
+++cmd: systemctl is-active amg-mcp-server.service
inactive
```

```
+++cmd: systemctl status amg-mcp-server.service --no-pager | head -10
Unit amg-mcp-server.service could not be found.
```

```
+++cmd: curl -fsS -m 5 https://memory.aimarketinggenius.io/health | head -5
{"status":"ok","server":"amg-operator-memory","version":"1.3.0","timestamp":"2026-04-29T13:56:45.705Z"}
```

**INTERPRETATION:** Systemd unit `amg-mcp-server.service` does **NOT exist**. However, the LIVE MCP endpoint at `memory.aimarketinggenius.io/health` returns `{"status":"ok","server":"amg-operator-memory","version":"1.3.0"}` — so the MCP server IS running, **under a different process supervisor** (Docker / PM2 / launchd / unrelated systemd unit name — to be confirmed). DIR-011 Phase 8 (Sentry observability) targets `amg-mcp-server` by that exact unit name; that target is **invalid** until the supervisor relationship is documented.

---

## 6. AGENT FLEET TRUTH

```
+++cmd: ps aux | grep -iE 'atlas-agent|iris|warden|sentinel|harmonia|metis|mercury|hercules|aletheia|cerberus|judge' | grep -v grep | head -20
(no output — zero matches)
```

```
+++cmd: ls /opt/amg-titan/agent-configs/ 2>&1
ls: cannot access '/opt/amg-titan/agent-configs/': No such file or directory
```

```
+++cmd: ls /opt/amg-personas/ | head -20
agents
agents_backup_pre_merge
config
deploy_personas.py
FALLBACK_LADDER.md
holding
loader
merge_patches.sh
MODEL_TIER_POLICY.md
monitoring
PERPLEXITY_INDEPENDENT_GRADE_v1.md
PERPLEXITY_REGRADE_v1.1.md
PERPLEXITY_REVIEW_v1.md
PROJECT_AGENT_MAP.md
projects
ROLLBACK_RUNBOOK.md
run_live_tests.sh
SLAs.md
TASK_ENVELOPE_SCHEMA.md
test-results-v1.1-FULL.json
```

**INTERPRETATION:** No fleet agent processes are running on the VPS (`atlas-agent`, `iris`, `warden`, `sentinel`, `harmonia`, `metis`, `mercury`, `hercules`, `aletheia`, `cerberus`, `judge`). MCP `get_recent_decisions` separately confirms `atlas-agent` heartbeats from `host=MacBookPro.lan` and `iris` heartbeats from `host=Dr` — the live fleet runs on **Mac**, not VPS. `/opt/amg-titan/agent-configs/` **ABSENT.** Persona infrastructure exists at `/opt/amg-personas/` (configs, loader, deploy script, fallback ladder, SLAs) — that is a **persona / model-tier routing layer**, not a running-agent registry. DIR-011 Phase 4 ("33-agent factory orchestration online") has no running fleet on VPS to register.

---

## 7. FACTORY INFRA TRUTH

```
+++cmd: systemctl is-active caddy
inactive
```

```
+++cmd: curl -sI -m 5 https://memory.aimarketinggenius.io/chamber-preview/ | head -5
HTTP/2 200
accept-ranges: bytes
alt-svc: h3=":443"; ma=2592000
content-type: text/html; charset=utf-8
etag: "di5bki58r08hjvt"
```

```
+++cmd: curl -sI -m 5 https://aimemoryguard.com | head -5
HTTP/2 200
date: Wed, 29 Apr 2026 13:56:45 GMT
content-type: text/html; charset=utf-8
access-control-allow-origin: *
cache-control: public, max-age=0, must-revalidate
```

```
+++cmd: cd /opt/titan-harness-work && git log --oneline -5
c053127 feat(dir-009-phase3): agent_config sync script (3B) + 3A schema halt + 3C deferred
7f46f38 feat(dir-009): bin/phase-grade-hook.sh + lib/phase_gate.py — interim grader
9044561 feat(dir-009-phase2): Chamber static mockup hosted (CT-0428-44)
3d8ce98 feat(dir-009-phase1): CT-0428-40 universal queue-requery hooks
c9c7b64 docs(ct-0428-20): file SOLON_CLICK_AUTOMATION_AUDIT_v1 + queue Gmail App Pwd autopatch
```

```
+++cmd: ls /opt/titan-harness-work/plans/dir-009/ 2>&1
ls: cannot access '/opt/titan-harness-work/plans/dir-009/': No such file or directory
```

**INTERPRETATION:** `caddy` service is **inactive**, yet `chamber-preview` and `aimemoryguard.com` both return HTTP 200 — reverse-proxy duty is being served by **a different fronting layer** (likely Cloudflare-edge + container-direct, to be confirmed). DIR-009 actual ship state = **Phase 3 latest** (`c053127` agent_config sync 3B + 3A schema halt + 3C deferred). DIR-011 v1 dispatch claims dependency on DIR-009 Phase 7C (atlas-chassis), Phase 8 (Solon OS substrate API skeleton), and Phase 13 (5-endpoint multi-instance) — those phases have **NOT shipped.** `plans/dir-009/` directory does not exist in the harness-work tree.

---

## 8. KNOWN POLLUTED ASSERTIONS FROM DIR-011 v1 (audit-confirmed FALSE)

| Assertion | Source section | Verdict |
|---|---|---|
| "MP-1 substrate complete / 86% / 3816 artifacts" | §1 | **FALSE** — partial / 43% / 856 |
| "Commit 6557abd merged (Atlas MCP control-plane contract)" | §2 | **FALSE** — commit absent across all 451 commits |
| "/opt/amg-titan/services/voice-ai-bridge/ skeleton + Echo Plan filed" | §3 | **FALSE** — services/ does not exist |
| "/opt/amg-titan/atlas-chassis/ shipped (DIR-009 Phase 7C)" | §3 | **FALSE** — atlas-chassis/ does not exist; DIR-009 only at Phase 3 |
| "/opt/amg-titan/scripts/judges/ houses sonar-replica + reasoning-judge" | §3 | **FALSE** — scripts/ does not exist |
| "/opt/amg-docs/doctrines/ populated with filed doctrines" | §4 | **FALSE** — empty (created during this session's preflight) |
| "amg-mcp-server.service active" | §5 | **FALSE** — systemd unit not found (server alive under different supervisor) |
| "DIR-009 Phases 4–23 done" | §7 | **FALSE** — only Phase 3 done; 4–23 unshipped |
| "Sonar-Pro-Mirror Judge multi-instance deployment (DIR-009 Phase 13)" | §6 | **FALSE** — no judge processes on VPS |

## 9. CONFIRMED LIVE (verified 2026-04-29)

| Asset | Verification |
|---|---|
| Solon OS substrate commit `6be496e` PROFILE v2.0 | git log present ✓ |
| `titan-kokoro.service` (Kokoro TTS, Hermes Phase A Step 1) | systemctl active ✓ |
| `atlas-api.service` (Hermes Phase A skeleton) | systemctl active ✓ |
| `amg-chatbot.service` | systemctl active ✓ |
| `amg-lead-intake.service` | systemctl active ✓ |
| `chamber-preview` (DIR-009 Phase 2 hosted static) | HTTP 200 ✓ |
| `aimemoryguard.com` (AIMG production landing) | HTTP 200 ✓ |
| MCP server endpoint `memory.aimarketinggenius.io/health` v1.3.0 | `{"status":"ok"}` ✓ |
| MCP `op_decisions` heartbeats — atlas-agent on `MacBookPro.lan`, iris on `Dr` | running on **Mac**, not VPS |
| `/opt/amg-personas/` (persona / model-tier routing) | populated ✓ |
| `/opt/titan-harness-work/scripts/hercules_mcp_bridge.py` | file exists (no service) |
| `/opt/titan-harness-work/scripts/mercury_mcp_notifier.py` | file exists (no service) |
| `/opt/amg-titan/solon-os-substrate/{00_audit … 07_validation}/` | dirs exist; `06_api` empty |
| Latest harness commit `c053127` (DIR-009 Phase 3) | git log present ✓ |
| Total commits across all branches | 451 |

---

## Tag

`state_facts_md_v1_canonical_live`
