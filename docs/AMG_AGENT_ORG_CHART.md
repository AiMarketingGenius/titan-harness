# AMG Agent Org Chart

**Version:** 1.0
**Date:** 2026-04-26
**Total agents:** 33 (12 Atlas + 21 AMG subscriber-facing) + 1 Hercules-hands (Mercury)

This document is the operating reference for the agent army: who's who, what
they run on, where they live, and the rule that "Solon is never middleware."

---

## 1. Roster — by tier

### Tier 0 — Command (humans + Hercules)

| Name | Stack | Role |
|---|---|---|
| Solon | (CEO + Vision) | Final say on strategy, brand, money, public-facing content. **Never middleware.** |
| Achilles / Codex | `~/achilles-harness` | Principal builder + control tower (per CLAUDE.md §1) |
| Hercules | Kimi web (Moonshot) | Completion chief — directs Titan + the fleet |
| Titan | `~/titan-harness` (Claude Code) | Subordinate builder, infrastructure, harness work |

### Tier 1 — Atlas System (12 internal agents)

| Agent | Role | Primary model | Lane |
|---|---|---|---|
| `atlas_hercules` | Completion chief mirror | mac_fast | OpenClaw |
| `atlas_titan` | Heavy orchestration (40 lanes) | vps_smart | OpenClaw |
| `atlas_achilles` | Build captain (auto-commit) | vps_smart → api_premium | OpenClaw |
| `atlas_odysseus` | UX + planning | vps_smart | OpenClaw |
| `atlas_hector` | Brand voice | vps_smart | OpenClaw |
| `atlas_judge_perplexity` | Live-web judge | api_research | API |
| `atlas_judge_deepseek` | Code architecture judge | api_premium | API |
| `atlas_research_perplexity` | Deep research | api_research | API |
| `atlas_research_gemini` | SEO + trend research | api_google | API |
| `atlas_einstein` | Memory validation | vps_smart | OpenClaw → Einstein Edge |
| `atlas_hallucinometer` | Drift guard | vps_smart | OpenClaw |
| `atlas_eom` | Coordinator | vps_smart | OpenClaw |

### Tier 2 — AMG Subscriber System (21 agents = 7 avatars × 3 roles)

For each avatar `<a>` ∈ {alex, maya, jordan, sam, riley, nadia, lumina}:

| Agent | Role | Lane | Front-facing? |
|---|---|---|---|
| `amg_<a>` | Front-facing strategist | OpenClaw (vps_smart) | Yes (per-tenant RLS) |
| `amg_<a>_builder` | Local-VPS builder | OpenClaw (vps_smart) | No (writes for `amg_<a>`) |
| `amg_<a>_researcher` | Live-web researcher | API (Perplexity, except Nadia → Gemini) | No (returns to `amg_<a>`) |

### Tier 3 — Hercules-hands (1 agent)

| Agent | Role | Stack |
|---|---|---|
| `mercury` | Hercules' hands — credential retrieval, browser actions, file staging | OpenClaw (vps_smart) + Infisical CLI |

---

## 2. Communication flow

```
                ┌──────────────┐
                │    SOLON     │   never middleware
                │  (vision)    │
                └──────┬───────┘
                       │  directives only
                       ▼
                ┌──────────────┐         ┌──────────────┐
                │  HERCULES    │◄────────│  ACHILLES    │
                │   (Kimi)     │         │  (principal  │
                └──────┬───────┘         │   builder)   │
                       │                 └──────────────┘
              MCP op_task_queue
                       │
                       ▼
        ┌──────────────────────────────┐
        │  agent_dispatch_bridge.py    │  routes by agent name
        └──────┬───────────────────────┘
               │
   ┌───────────┴────────────┬─────────────────┬────────────────┐
   ▼                        ▼                 ▼                ▼
┌─────────┐          ┌─────────────┐    ┌──────────┐     ┌────────┐
│ Kimi API│          │  amg-fleet  │    │Perplexity│     │ Gemini │
│(Moonshot│          │ (OpenClaw + │    │ Sonar Pro│     │   2.5  │
│ k2.6)   │          │  Ollama)    │    │  api     │     │   Pro  │
└─────────┘          └─────────────┘    └──────────┘     └────────┘
nestor                achilles            judge_perplexity   research_gemini
alexander             titan                research_perplexity  amg_nadia_*
hercules              odysseus             amg_<x>_researcher
                      hector
                      atlas_*
                      amg_<x>
                      amg_<x>_builder
                      mercury
```

Logs: every dispatch posts a `log_decision` to MCP with tag
`agent-dispatch-bridge`. Heartbeat polls reach all 33 agents every 10 min and
flag any with no MCP activity for 3 polls (~30 min) as `dead`.

---

## 3. Escalation rules — when does each layer call up?

| Layer | Calls API when… | Calls human when… |
|---|---|---|
| **AMG avatar (front)** | Subscriber requests live-web data → routes through paired researcher | Never directly (escalation goes through Hercules) |
| **AMG builder** | `vps_smart` queue depth ≥ 10 sustained 5 min → API fallback (`api_premium_flash`); cost transparently shown to subscriber | Never; runs autonomous |
| **AMG researcher** | Always API by design; degrades to `vps_smart` summary if daily budget exceeded | Never |
| **Atlas judge** | Always API (architecture-critical) | When budget exceeds 80% of daily cap → Slack alert to Solon |
| **Atlas research** | Always API | When deep-research request from Hercules has ambiguity that can't be resolved from MCP context |
| **Atlas eom** | n8n webhook + heartbeat | When watchdog detects 3+ dead agents simultaneously |
| **Mercury** | Infisical CLI for credential retrieval (server-side) | When a credential rotation requires user-typed password (e.g., Stripe dashboard 2FA) |
| **Hercules** | Routes through bridge; chooses lane | When a ship-blocker is structural/legal/financial and outside Hard Limits |

---

## 4. The "Solon is never middleware" rule

**Hard rule.** Solon does not pipe tasks between agents. Period.

If you (a Titan, an Achilles, an avatar) need data or output from another agent:

1. Look it up in MCP first (`get_recent_decisions`, `search_memory`,
   `get_sprint_state`).
2. If MCP doesn't have it, queue a task in `op_task_queue` with
   `agent_assigned = <target>` and let the dispatch bridge route it.
3. Wait for the result via the task status update.

What this rule prevents:
- Solon being asked "can you ask Hercules whether…"
- Solon manually copying agent A's output into agent B's prompt
- Solon being the bottleneck for routine cross-agent coordination

What this rule allows (Solon stays in the loop on these):
- Strategy decisions (which campaign, which client, which price)
- Brand voice changes
- Money decisions (pricing tiers, recurring spend > $50/mo, refunds)
- Public-facing publication under his name
- Hard Limits per CLAUDE.md §15.1

---

## 5. Hard Limits (escalate to Solon, never auto-execute)

Per CLAUDE.md §15:

1. New credentials Solon-only can provision (verified absent from Drive +
   /etc/amg/ + Master Sheet).
2. Business decisions: pricing, contract terms, partnership scope.
3. Destructive ops with rollback >30 min.
4. Public-facing publications under Solon's name.
5. New recurring costs > $50/mo.
6. Supabase production schema changes (production data, prod project ref).
7. Greek codename locks for new processes (per CLAUDE.md §14, only after
   Solon "OK rename").

Everything else is autonomy land.

---

## 6. Files of record

| Path | Purpose |
|---|---|
| `scripts/agent_dispatch_bridge.py` | MCP queue → fleet router |
| `scripts/agent_heartbeat.py` | 10-min health poll, dead-agent detection |
| `scripts/amg_factory_cron.sh` | Cron installer for autonomous schedule |
| `scripts/amg_fleet_orchestrator.py` | Per-agent execution (Ollama + tool calls) |
| `scripts/monitor_and_scale.py` | n8n queue-depth fallback toggle |
| `scripts/amg_queue_depth_server.py` | VPS shim returning Bull queue depth |
| `scripts/einstein_call.py` | Einstein fact-check helper (signin → JWT) |
| `~/.openclaw/skills/amg/digital_hands.json` | Per-agent tool allowlist |
| `~/.openclaw/agents/<name>/config.toml` | Per-agent metadata + role |
| `~/.openclaw/models/aliases.json` | Logical-to-concrete model mapping |

---

*End of AMG Agent Org Chart v1.0.*
