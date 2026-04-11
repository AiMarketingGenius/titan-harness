# DOCTRINE — Routing Automations (Harness vs Computer vs Deep Research)

**Status:** CANONICAL — governs where work gets routed in Solon OS / AMG Atlas
**Established:** 2026-04-12 (Solon autonomy directive)
**Enforcement:** applied automatically to every new PLAN_* / BATCH_* / DOCTRINE_* / COMPUTER_TASKS_* file. Titan marks each step with its engine. MCP `log_decision` for every delegation.

---

## 1. The three engines

AMG has three distinct execution engines available. Each is best at specific work types. This doctrine defines the routing rules so Titan doesn't have to ask Solon every time.

### Engine 1 — Titan harness (`~/titan-harness`)

**Runs on:** Mac Claude Code session + VPS `/opt/titan-harness` + VPS systemd services
**Strengths:** Python, bash, SQL, git, file system, LiteLLM gateway, MCP memory, war-room grading, capacity-gated execution, Hercules Triangle auto-mirror, cron jobs, systemd daemons
**Weaknesses:** can't drive a real browser with JS rendering, can't do heavy interactive web QA, no direct visual inspection

### Engine 2 — Perplexity Computer (52K credits available)

**Runs on:** Perplexity's hosted Chrome agent with full browser + DOM access + network + file upload
**Strengths:** browser/DOM interaction, form filling, KYC document screenshots, site compliance audits, visual QA, cross-browser testing, interactive SaaS dashboard navigation, Lovable/Supabase UI interaction, Loom asset capture, DOM/CSS live tweaks
**Weaknesses:** not integrated with MCP memory server, credit cost (~5-15K per task), no direct write access to `~/titan-harness` repo, no git commit ability
**Task budget:** spend ~40K of 52K credits on the initial task bundle (`plans/COMPUTER_TASKS_2026-04-12.md`), reserve ~12K for iteration

### Engine 3 — Perplexity Deep Research

**Runs on:** Perplexity's Deep Research mode (longer-horizon multi-source research)
**Strengths:** market analysis, competitive pricing research, vendor comparisons, industry benchmark gathering, cross-source fact validation, long-form intelligence briefs with citations
**Weaknesses:** expensive per query, slow, not suited for code or file operations, output is text only

---

## 2. Routing decision tree

For any given step inside a plan, Titan picks the engine by asking these questions in order:

### Step A — Does the step involve real browser / DOM / JS rendering / visual inspection / file upload to a web form?

**YES** → **Route to Engine 2 (Perplexity Computer)**

Examples:
- "Audit the Lovable SPA at aimarketinggenius.io and flag compliance gaps"
- "Walk through PaymentCloud application and screenshot every form field"
- "Tweak the Atlas UI CSS live in DevTools and report the winning direction"
- "Capture screenshots of the 3 hero flows on os.aimarketinggenius.io"
- "Fill out and screenshot the merchant stack KYC forms"

Output: add to `plans/COMPUTER_TASKS_*.md` with the exact prompt Solon pastes into Computer.

### Step B — Does the step need external market / pricing / competitive / vendor research that Titan can't answer from its existing corpus?

**YES** → **Route to Engine 3 (Perplexity Deep Research)**

Examples:
- "What are competitors charging for AI-powered reputation management in 2026?"
- "Find the best streaming TTS vendors with sub-100ms first-byte latency and custom voice cloning"
- "Research merchant processors with the highest approval rates for adult-adjacent verticals"
- "Compare 5 voice-first UX patterns for AI assistants in the enterprise SaaS space"

Output: add to a `plans/RESEARCH_*.md` file with the exact Deep Research query, expected deliverable format, and how the result will feed back into downstream work.

### Step C — Is the step pure infra / code / SQL / harness wiring / file editing?

**YES** → **Route to Engine 1 (Titan harness)**

Examples:
- "Write `bin/titan-night-grind.sh` with cron entries"
- "Add a `scheduler:` block to `policy.yaml`"
- "Edit `CORE_CONTRACT.md` §8 to encode the Never-stop rule"
- "Commit + push + mirror the Greek codename doctrine"
- "Run `log_decision` via MCP to record the autonomy decision"
- "Apply `sql/006_payment_link_tests.sql` migration"

Output: Titan just does it in the current session via Bash/Edit/Write tools.

### Step D — Hybrid / ambiguous steps

Some steps touch multiple engines. Break them down:
- "Run MP-1 Phase 2 Perplexity harvester" → Engine 1 harness (runs a Python script) that internally hits perplexity.ai via browser-emulated cookie auth (which is NOT Perplexity Computer — it's curl-based from the harness)
- "Generate a Loom demo script" → Engine 1 for writing the markdown, Engine 2 for capturing the visual assets, Engine 3 for researching competitor Loom styles if needed
- "Design a new pricing tier" → Engine 3 for market research + Engine 1 for the pricing engine code + Engine 2 for testing the pricing calculator UI

Titan decomposes hybrid steps in the plan file and marks each sub-step with its engine tag: `[engine: harness]`, `[engine: computer]`, `[engine: deep-research]`.

---

## 3. Mandatory marking in every new plan file

Every new `PLAN_*.md`, `BATCH_*.md`, `DOCTRINE_*.md`, or `COMPUTER_TASKS_*.md` file that Titan creates MUST include, for each actionable step:

1. A routing tag: `[engine: harness]` / `[engine: computer]` / `[engine: deep-research]`
2. A rationale line explaining why that engine (one sentence)
3. An MCP `log_decision` call at the time the plan is committed, recording which steps were routed to which engine

Format example:

```
### Step 3 — Audit the AMG Lovable SPA for compliance gaps [engine: computer]

Rationale: Lovable SPA blocked WebFetch (RADAR item O7); Computer has real
browser + JS rendering needed to walk through the site.

Delegation logged: MCP decision id __________ (populated after log_decision call)
```

---

## 4. MCP logging requirement

Every delegation decision is logged via MCP `log_decision` at the time the plan is committed:

```
log_decision(
  text: "Routed <step description> to <engine name> per DOCTRINE_ROUTING_AUTOMATIONS §2",
  rationale: "<the one-sentence rationale from the plan file>",
  project_source: "EOM",
  tags: ["routing_decision", "<engine-name>", "<plan-file-name>"]
)
```

Aristotle audits routing decisions periodically via `search_memory("routing_decision")` when Slack path is live. Until then, Solon can inspect by running `get_recent_decisions` with a tag filter.

---

## 5. Default routing per work type (fast reference)

| Work type | Default engine | Notes |
|---|---|---|
| Browser / DOM / DevTools / visual QA | Computer | `plans/COMPUTER_TASKS_*.md` |
| KYC form walkthroughs / screenshot capture | Computer | Never submit forms — reconnaissance only |
| Site compliance audit (public web) | Computer | Chrome MCP acceptable alternative for simple pages |
| Atlas skin polish / UI CSS tweaks | Computer | Live DOM edits, Solon approves, Titan transcribes to repo |
| Loom demo asset capture | Computer | Requires polished skin first |
| Competitor pricing / vendor benchmarks | Deep Research | Single query → intelligence brief |
| Market sizing / industry trends | Deep Research | Citations + confidence tier |
| Technical vendor comparison (Deepgram vs Whisper vs AssemblyAI) | Deep Research | Usually needs 2-3 follow-up Deep Research passes |
| Python / bash / SQL / git / file edits | Harness | Titan in-session |
| War-room grading | Harness (with Slack Aristotle fallback → Titan self-grade per §12) | Future: add Grok via §C6 conflict resolution |
| Cron jobs / systemd services | Harness | Solon approves cron install, Titan writes the script |
| MCP memory operations | Harness | `log_decision`, `update_sprint_state`, etc. |
| Supabase migrations | Harness | Titan writes SQL, Solon applies in Supabase SQL Editor |
| Harvester runs (MP-1 Phase 1-5) | Harness | Not Computer — the harvester is a Python script that reads cookies from secrets dir |

---

## 6. Grading block (Titan self-grade, PENDING_ARISTOTLE)

| # | Dimension | Score /10 | Notes |
|---|---|---|---|
| 1 | Correctness | 9.5 | 3 engines accurately characterized; routing rules match each engine's real strengths |
| 2 | Completeness | 9.4 | 4-step decision tree + mandatory marking rule + MCP logging + fast reference table + hybrid step handling |
| 3 | Honest scope | 9.5 | Clear about what each engine can't do |
| 4 | Rollback availability | 9.4 | Routing decisions logged to MCP, so Solon can audit and Titan can re-route |
| 5 | Fit with harness patterns | 9.5 | Reuses MCP logging, DOCTRINE_* convention, §12 compliance |
| 6 | Actionability | 9.5 | Titan can apply this to the next plan file created |
| 7 | Risk coverage | 9.3 | Covers the "hybrid step" ambiguity; minor gap on "what if Computer credits run out" |
| 8 | Evidence quality | 9.4 | References specific RADAR items, existing Computer task file, engine characterizations |
| 9 | Internal consistency | 9.5 | Decision tree maps cleanly to the fast reference table |
| 10 | Ship-ready for production | 9.4 | Can be applied immediately |
| **Overall** | | **9.44/10 A** | **PENDING_ARISTOTLE** |

---

## 7. Change log

| Date | Change |
|---|---|
| 2026-04-12 | Initial doctrine per Solon autonomy directive. |
