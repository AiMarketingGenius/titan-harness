#!/usr/bin/env python3
"""
build_amg_skills.py — generate stub YAML skill files for every skill referenced
in the AMG Agent Army agent configs. Idempotent: skips files that already exist.

Each stub registers the skill name with OpenClaw + amg-fleet so that agents can
reference the skill without a "skill not found" error at runtime. Real action
templates can be filled in incrementally.
"""
from __future__ import annotations

import pathlib

HOME = pathlib.Path.home()
SKILLS = HOME / ".openclaw" / "skills" / "amg"

# ─── All skills referenced by Atlas + AMG agents ────────────────────────────
SKILL_DEFS = {
    # Atlas system
    "amg_orchestrate":       "Dispatch sub-tasks to other Atlas agents in parallel",
    "amg_audit":             "Verify completion + grade outputs against rubric",
    "amg_batch":             "Group + sequence multi-step jobs for n8n",
    "amg_deploy":            "Push code to staging/prod via approved pipeline",
    "amg_git":               "Stage / commit / push using harness conventions",
    "amg_fact_check":        "Validate factual claims against live sources",
    "amg_citation_audit":    "Confirm citations resolve + are current",
    "amg_code_review":       "Static + architectural review for correctness + security",
    "amg_security_audit":    "OWASP top-10 + secret-leak + auth-flow audit",
    "amg_market_research":   "Long-form market + competitor + segment analysis",
    "amg_competitor_analysis": "Specific-competitor strategy + offer reverse-engineering",
    "amg_seo_research":      "Keyword + SERP-feature + intent research",
    "amg_keyword_trends":    "Search-trend deltas + seasonality + emerging terms",
    "amg_memory_check":      "Compare claim against MCP-stored decisions",
    "amg_contradiction_detect": "Detect internal inconsistencies in a thread",
    "amg_drift_detect":      "Score output for hallucination / drift",
    "amg_freshness_check":   "Confirm referenced data is within tolerable age",
    "amg_heartbeat":         "Emit periodic liveness signal to MCP",
    "amg_notify":            "Send Solon notification via Slack / Pushover",
    "amg_design":            "Information-architecture + layout proposal",
    "amg_mockup":            "Wireframe / static mockup generation",
    "amg_proposal":          "Client-facing proposal document",
    "amg_copy":              "Brand-voice copywriting",
    "amg_content":           "Long-form content (blog, email, ad)",
    "amg_voice_guide":       "Brand voice rules + tone reference",
    "amg_hands":             "File ops + shell + browser primitives",
    "amg_code":              "Read / write / edit code with backup",
    "amg_cli":               "Allowlisted shell command execution",
    "amg_browser":           "Playwright-driven browser navigation",
    "amg_file":              "File CRUD with backup",
    "amg_screenshot":        "Capture screen or browser viewport",
    "amg_file_edit":         "In-place edit with diff log",
    # AMG avatar skills
    "amg_voice_strategy":    "Voice clone strategy + script architecture",
    "amg_persona":           "Persona definition + voice/tone calibration",
    "amg_dialog_design":     "Conversational flow design",
    "amg_social_strategy":   "Social-platform strategy",
    "amg_calendar":          "Editorial / posting calendar",
    "amg_engagement_play":   "Comment / DM / reply engagement playbook",
    "amg_ads_strategy":      "Paid-ads strategy + budget pacing",
    "amg_creative_brief":    "Ad creative brief generation",
    "amg_audience_design":   "Targeting + audience segment design",
    "amg_email_strategy":    "Email program strategy",
    "amg_sequence_design":   "Drip / nurture sequence design",
    "amg_lifecycle":         "Customer lifecycle email mapping",
    "amg_content_strategy":  "Content pillar + topical strategy",
    "amg_editorial_calendar": "Long-form editorial calendar",
    "amg_topic_research":    "Topic-discovery + intent mapping",
    "amg_seo_strategy":      "SEO strategy + technical recommendations",
    "amg_serp_analysis":     "SERP feature + competitor SERP analysis",
    "amg_link_strategy":     "Backlink + internal-link strategy",
    "amg_design_strategy":   "Visual design strategy",
    "amg_brand_audit":       "Brand consistency + asset audit",
    "amg_visual_system":     "Design system + token spec",
    # Researcher tooling
    "amg_live_web":          "Live-web search via Perplexity / Google",
    "amg_competitor_spy":    "Competitor monitoring + change-detection",
    "amg_trend_analysis":    "Trend signals across SERP + social + news",
}

STUB_TEMPLATE = """name: {name}
description: "{desc}"
version: "0.1.0"
owner: amg
status: stub
actions:
  invoke:
    template: "echo 'skill {name} stub — fill in action template'"
    args:
      input: {{ type: string, required: false }}
notes:
  - "Stub registered so agents can reference this skill name."
  - "Replace 'invoke' template with real action(s) when wiring runtime."
"""


def main():
    SKILLS.mkdir(parents=True, exist_ok=True)
    created = []
    skipped = []
    # Files that already exist with real implementations — never overwrite
    PRESERVED = {
        "n8n_parallel.yml", "quality_gate.yml", "concurrency.yml",
        "code.yml", "hands.yml", "n8n.yml",
    }
    for name, desc in SKILL_DEFS.items():
        # Map skill_name -> filename without amg_ prefix
        fname = name.removeprefix("amg_") + ".yml"
        path = SKILLS / fname
        if fname in PRESERVED or path.exists():
            skipped.append(fname)
            continue
        path.write_text(STUB_TEMPLATE.format(name=name, desc=desc))
        created.append(fname)
    print(f"Skills dir: {SKILLS}")
    print(f"Created: {len(created)} stubs")
    for n in sorted(created):
        print(f"  + {n}")
    print(f"\nSkipped (already exist): {len(skipped)}")
    for n in sorted(skipped):
        print(f"  = {n}")


if __name__ == "__main__":
    main()
