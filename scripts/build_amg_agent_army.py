#!/usr/bin/env python3
"""
build_amg_agent_army.py — one-shot scaffolder for the AMG Agent Army.

Creates 33 agents:
  - 12 Atlas system agents (atlas_*)
  - 21 AMG subscriber agents (amg_<avatar>{,_builder,_researcher})

Each agent gets:
  - ~/.openclaw/agents/<name>/config.toml
  - ~/.openclaw/agents/<name>/system_prompt.md (role stub)
  - ~/.openclaw/agents/<name>/knowledge_base/ (empty; populate via Claude project export)
  - ~/.openclaw/agents/<name>/workspace/

Idempotent: re-running overwrites configs but leaves workspaces / knowledge_base intact.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import datetime, timezone

HOME = pathlib.Path.home()
AGENTS = HOME / ".openclaw" / "agents"
SKILLS = HOME / ".openclaw" / "skills" / "amg"
MODELS = HOME / ".openclaw" / "models"

# ─── Atlas System (12) ───────────────────────────────────────────────────────
ATLAS_AGENTS = [
    {
        "name": "atlas_hercules",
        "role": "completion_chief",
        "primary_model": "mac_fast",
        "skills": ["amg_orchestrate", "amg_audit"],
        "max_parallel_lanes": 8,
        "system_prompt": (
            "You are Hercules, completion chief for AMG Atlas. You verify that "
            "every agent ships finished work; you enforce the war-room A-grade "
            "floor (9.4) and route incomplete work back to the originating agent. "
            "You do not build — you audit, sign off, and unblock."
        ),
    },
    {
        "name": "atlas_titan",
        "role": "heavy_orchestration",
        "primary_model": "vps_smart",
        "skills": ["amg_orchestrate", "amg_n8n_route", "amg_batch"],
        "max_parallel_lanes": 40,
        "system_prompt": (
            "You are Atlas-Titan, heavy orchestration. You fan tasks out to up to "
            "40 parallel lanes via amg-fleet + n8n. You pick the right agent for "
            "the job, batch overnight work for free-tier, and route to API "
            "fallback only when local lanes saturate (queue depth >= 10)."
        ),
    },
    {
        "name": "atlas_achilles",
        "role": "build_captain",
        "primary_model": "vps_smart",
        "fallback_model": "api_premium",
        "skills": ["amg_code", "amg_deploy", "amg_git"],
        "max_parallel_lanes": 20,
        "auto_commit": True,
        "system_prompt": (
            "You are Atlas-Achilles, principal builder. You ship code, commit "
            "with descriptive messages, and run the test/lint gates before "
            "claiming a task done. Trade-secret scanner + Lumina gate must pass "
            "before any client-facing artifact lands."
        ),
    },
    {
        "name": "atlas_odysseus",
        "role": "ux_planning",
        "primary_model": "vps_smart",
        "skills": ["amg_design", "amg_mockup", "amg_proposal"],
        "max_parallel_lanes": 6,
        "system_prompt": (
            "You are Atlas-Odysseus, UX + planning. You draft proposals, mockups, "
            "and information architecture. You bring options A/B/C with named "
            "tradeoffs, never one option presented as the only choice."
        ),
    },
    {
        "name": "atlas_hector",
        "role": "brand_voice",
        "primary_model": "vps_smart",
        "skills": ["amg_copy", "amg_content", "amg_voice_guide"],
        "max_parallel_lanes": 6,
        "system_prompt": (
            "You are Atlas-Hector, brand + voice. You write client-facing copy "
            "in the brand voice loaded from knowledge_base/voice_corpus/. You "
            "never use placeholder copy; you pull from real samples."
        ),
    },
    {
        "name": "atlas_judge_perplexity",
        "role": "live_web_judge",
        "primary_model": "api_research",
        "skills": ["amg_fact_check", "amg_citation_audit"],
        "cost_per_task_usd": 0.50,
        "daily_budget_usd": 20.00,
        "system_prompt": (
            "You are Atlas-Judge-Perplexity, live-web fact-checker. You audit "
            "research outputs for citation quality, currency, and factual "
            "accuracy against live web sources. You return PASS / FAIL / "
            "NEEDS_REVISION with specific findings."
        ),
    },
    {
        "name": "atlas_judge_deepseek",
        "role": "code_architecture_judge",
        "primary_model": "api_premium",
        "skills": ["amg_code_review", "amg_security_audit"],
        "cost_per_task_usd": 1.00,
        "daily_budget_usd": 20.00,
        "system_prompt": (
            "You are Atlas-Judge-DeepSeek, code + architecture auditor. You "
            "review for: security (OWASP top 10), correctness, maintainability, "
            "and fit with existing codebase patterns. You return PASS / FAIL / "
            "NEEDS_REVISION with line-numbered findings."
        ),
    },
    {
        "name": "atlas_research_perplexity",
        "role": "deep_research",
        "primary_model": "api_research",
        "skills": ["amg_market_research", "amg_competitor_analysis"],
        "cost_per_task_usd": 1.00,
        "daily_budget_usd": 10.00,
        "system_prompt": (
            "You are Atlas-Research-Perplexity, deep researcher. You produce "
            "long-form market + competitor reports backed by current citations. "
            "You distinguish primary sources from aggregators."
        ),
    },
    {
        "name": "atlas_research_gemini",
        "role": "seo_trend_research",
        "primary_model": "api_google",
        "skills": ["amg_seo_research", "amg_keyword_trends"],
        "cost_per_task_usd": 0.50,
        "daily_budget_usd": 10.00,
        "system_prompt": (
            "You are Atlas-Research-Gemini, SEO + trend specialist. You query "
            "for keyword data, search-trend deltas, and SERP feature changes. "
            "You output structured tables ready for downstream agents."
        ),
    },
    {
        "name": "atlas_einstein",
        "role": "memory_validation",
        "primary_model": "vps_smart",
        "skills": ["amg_memory_check", "amg_contradiction_detect"],
        "mcp_endpoint": "https://memory.aimarketinggenius.io/mcp",
        "system_prompt": (
            "You are Atlas-Einstein, memory + contradiction validator. You "
            "compare incoming claims against MCP-stored decisions + "
            "knowledge_base entries. If a claim contradicts memory, you flag it "
            "with the specific decision ID + timestamp of conflict."
        ),
    },
    {
        "name": "atlas_hallucinometer",
        "role": "drift_guard",
        "primary_model": "vps_smart",
        "skills": ["amg_drift_detect", "amg_freshness_check"],
        "system_prompt": (
            "You are Atlas-Hallucinometer, drift + freshness guard. You score "
            "outputs on a 0-1 hallucination index based on: (a) presence of "
            "specific dates / numbers / names, (b) traceability to source, "
            "(c) age of supporting data."
        ),
    },
    {
        "name": "atlas_eom",
        "role": "coordinator",
        "primary_model": "vps_smart",
        "skills": ["amg_n8n_route", "amg_heartbeat", "amg_notify"],
        "system_prompt": (
            "You are Atlas-EOM, coordinator. You manage the heartbeat cadence, "
            "queue-depth monitoring, and Solon notifications. You are the "
            "n8n-side bridge between agents and human escalation."
        ),
    },
]

# ─── AMG Subscriber System (21) ──────────────────────────────────────────────
AMG_AVATARS = [
    {"name": "alex",   "role": "voice_clone_strategist",
     "skills": ["amg_voice_strategy", "amg_persona", "amg_dialog_design"]},
    {"name": "maya",   "role": "social_strategist",
     "skills": ["amg_social_strategy", "amg_calendar", "amg_engagement_play"]},
    {"name": "jordan", "role": "ads_strategist",
     "skills": ["amg_ads_strategy", "amg_creative_brief", "amg_audience_design"]},
    {"name": "sam",    "role": "email_strategist",
     "skills": ["amg_email_strategy", "amg_sequence_design", "amg_lifecycle"]},
    {"name": "riley",  "role": "content_strategist",
     "skills": ["amg_content_strategy", "amg_editorial_calendar", "amg_topic_research"]},
    {"name": "nadia",  "role": "seo_strategist",
     "skills": ["amg_seo_strategy", "amg_serp_analysis", "amg_link_strategy"],
     "researcher_model_override": "api_google"},  # Nadia's researcher uses Gemini per directive
    {"name": "lumina", "role": "design_strategist",
     "skills": ["amg_design_strategy", "amg_brand_audit", "amg_visual_system"]},
]

# ─── Builders / Helpers ──────────────────────────────────────────────────────
def toml_kv(key, value):
    if isinstance(value, bool):
        return f"{key} = {str(value).lower()}"
    if isinstance(value, (int, float)):
        return f"{key} = {value}"
    if isinstance(value, list):
        items = ", ".join(f'"{v}"' for v in value)
        return f"{key} = [{items}]"
    return f'{key} = "{value}"'


def build_atlas_config(spec):
    name = spec["name"]
    lines = ["[agent]"]
    lines.append(toml_kv("name", name))
    lines.append(toml_kv("role", spec["role"]))
    lines.append(toml_kv("scope", "atlas_internal"))
    lines.append(toml_kv("primary_model", spec["primary_model"]))
    if "fallback_model" in spec:
        lines.append(toml_kv("fallback_model", spec["fallback_model"]))
    lines.append(toml_kv("max_parallel_lanes", spec.get("max_parallel_lanes", 4)))
    if spec.get("auto_commit"):
        lines.append(toml_kv("auto_commit", True))
    if spec.get("mcp_endpoint"):
        lines.append("")
        lines.append("[mcp]")
        lines.append(toml_kv("endpoint", spec["mcp_endpoint"]))
        lines.append(toml_kv("bootstrap_on_start", True))
    lines.append("")
    lines.append("[skills]")
    lines.append(toml_kv("enabled", spec["skills"]))
    if "cost_per_task_usd" in spec or "daily_budget_usd" in spec:
        lines.append("")
        lines.append("[cost_control]")
        if "cost_per_task_usd" in spec:
            lines.append(toml_kv("cost_per_task_usd", spec["cost_per_task_usd"]))
        if "daily_budget_usd" in spec:
            lines.append(toml_kv("daily_budget_usd", spec["daily_budget_usd"]))
        lines.append(toml_kv("max_tokens_per_task", 8000))
        lines.append(toml_kv("fallback_to_local_on_budget_exceeded", True))
        lines.append(toml_kv("alert_solon_at_80_percent", True))
    lines.append("")
    lines.append("[knowledge]")
    lines.append('source_dir = "knowledge_base/"')
    lines.append("auto_embed = true")
    lines.append('mcp_table = "mem_embeddings"')
    lines.append("query_limit = 5")
    lines.append("client_isolation = true")
    return "\n".join(lines) + "\n"


def build_amg_avatar_config(avatar):
    name = f"amg_{avatar['name']}"
    role = f"{avatar['name']}_strategist"
    lines = [
        "[agent]",
        toml_kv("name", name),
        toml_kv("role", role),
        toml_kv("scope", "amg_subscriber_facing"),
        toml_kv("client_scope", "per_subscriber"),
        toml_kv("tenant_isolation", "client_id"),
        toml_kv("primary_model", "vps_smart"),
        "",
        "[skills]",
        toml_kv("enabled", avatar["skills"]),
        "",
        "[knowledge]",
        'source_dir = "knowledge_base/"',
        "auto_embed = true",
        'mcp_table = "mem_embeddings"',
        "query_limit = 5",
        "client_isolation = true",
    ]
    return "\n".join(lines) + "\n"


def build_amg_builder_config(avatar):
    name = f"amg_{avatar['name']}_builder"
    role = f"{avatar['name']}_builder"
    parent = f"amg_{avatar['name']}"
    lines = [
        "[agent]",
        toml_kv("name", name),
        toml_kv("role", role),
        toml_kv("scope", "amg_subscriber_facing"),
        toml_kv("client_scope", "per_subscriber"),
        toml_kv("primary_model", "vps_smart"),
        toml_kv("parent_avatar", parent),
        "",
        "[skills]",
        toml_kv("enabled", ["amg_code", "amg_hands", "amg_deploy"]),
        "",
        "[knowledge]",
        'source_dir = "knowledge_base/"',
        "auto_embed = true",
        'mcp_table = "mem_embeddings"',
        "query_limit = 5",
        "client_isolation = true",
    ]
    return "\n".join(lines) + "\n"


def build_amg_researcher_config(avatar):
    name = f"amg_{avatar['name']}_researcher"
    role = f"{avatar['name']}_researcher"
    parent = f"amg_{avatar['name']}"
    model = avatar.get("researcher_model_override", "api_research")
    lines = [
        "[agent]",
        toml_kv("name", name),
        toml_kv("role", role),
        toml_kv("scope", "amg_subscriber_facing"),
        toml_kv("client_scope", "per_subscriber"),
        toml_kv("primary_model", model),
        toml_kv("parent_avatar", parent),
        "",
        "[cost_control]",
        toml_kv("cost_per_task_usd", 0.50),
        toml_kv("daily_budget_usd", 5.00),
        toml_kv("max_tokens_per_task", 4000),
        toml_kv("fallback_to_local_on_budget_exceeded", True),
        "",
        "[skills]",
        toml_kv("enabled", ["amg_live_web", "amg_competitor_spy", "amg_trend_analysis"]),
        "",
        "[knowledge]",
        'source_dir = "knowledge_base/"',
        "auto_embed = true",
        'mcp_table = "mem_embeddings"',
        "query_limit = 5",
        "client_isolation = true",
    ]
    return "\n".join(lines) + "\n"


def write_agent_dir(name, config_text, system_prompt_text):
    base = AGENTS / name
    (base / "knowledge_base").mkdir(parents=True, exist_ok=True)
    (base / "workspace").mkdir(parents=True, exist_ok=True)
    (base / "agent").mkdir(parents=True, exist_ok=True)
    (base / "config.toml").write_text(config_text)
    (base / "system_prompt.md").write_text(system_prompt_text + "\n")
    placeholder = base / "knowledge_base" / ".placeholder"
    if not placeholder.exists():
        placeholder.write_text(
            "# Populate via Claude project export OR direct file drop.\n"
            "# Files in this directory are auto-embedded into mem_embeddings\n"
            "# with client_id isolation per RLS.\n"
        )


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    AGENTS.mkdir(parents=True, exist_ok=True)
    SKILLS.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    created = []
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    # Atlas
    for spec in ATLAS_AGENTS:
        cfg = build_atlas_config(spec)
        sp = (
            f"# {spec['name']} — system prompt\n\n"
            f"**Role:** {spec['role']}\n"
            f"**Scope:** Atlas internal (not client-facing)\n"
            f"**Created:** {timestamp}\n\n"
            f"## Identity\n\n{spec['system_prompt']}\n"
        )
        write_agent_dir(spec["name"], cfg, sp)
        created.append(spec["name"])

    # AMG: 7 avatars × 3 = 21
    for avatar in AMG_AVATARS:
        # avatar (front-facing strategist)
        cfg = build_amg_avatar_config(avatar)
        sp = (
            f"# amg_{avatar['name']} — system prompt\n\n"
            f"**Role:** {avatar['name']}_strategist\n"
            f"**Scope:** AMG subscriber-facing (per-tenant, RLS-isolated)\n"
            f"**Created:** {timestamp}\n\n"
            "## Identity\n\nFront-facing strategist persona. Plans the avatar's "
            "domain (voice / social / ads / email / content / SEO / design). "
            "Hands deep work to the paired builder + researcher.\n"
        )
        write_agent_dir(f"amg_{avatar['name']}", cfg, sp)
        created.append(f"amg_{avatar['name']}")

        # builder (local)
        cfg = build_amg_builder_config(avatar)
        sp = (
            f"# amg_{avatar['name']}_builder — system prompt\n\n"
            f"**Role:** {avatar['name']}_builder\n"
            f"**Scope:** AMG subscriber-facing (per-tenant)\n"
            f"**Parent:** amg_{avatar['name']}\n"
            f"**Created:** {timestamp}\n\n"
            "## Identity\n\nLocal-VPS builder for the paired avatar. Runs free "
            "(Qwen 32B local) on the async batch queue. No API spend.\n"
        )
        write_agent_dir(f"amg_{avatar['name']}_builder", cfg, sp)
        created.append(f"amg_{avatar['name']}_builder")

        # researcher (API)
        cfg = build_amg_researcher_config(avatar)
        model = avatar.get("researcher_model_override", "api_research")
        sp = (
            f"# amg_{avatar['name']}_researcher — system prompt\n\n"
            f"**Role:** {avatar['name']}_researcher\n"
            f"**Scope:** AMG subscriber-facing (per-tenant)\n"
            f"**Parent:** amg_{avatar['name']}\n"
            f"**Model:** {model} (paid, $0.50/task, $5/day budget)\n"
            f"**Created:** {timestamp}\n\n"
            "## Identity\n\nLive-web researcher for the paired avatar. Routes to "
            f"{model}; falls back to local if daily budget exceeded.\n"
        )
        write_agent_dir(f"amg_{avatar['name']}_researcher", cfg, sp)
        created.append(f"amg_{avatar['name']}_researcher")

    print(f"Created {len(created)} agents:")
    for n in created:
        print(f"  - {n}")

    # Write a manifest snapshot
    manifest = AGENTS / "_AMG_AGENT_ARMY_MANIFEST.json"
    manifest.write_text(json.dumps({
        "created_at": timestamp,
        "atlas_count": len(ATLAS_AGENTS),
        "amg_count": len(AMG_AVATARS) * 3,
        "total": len(created),
        "agents": created,
    }, indent=2))
    print(f"\nManifest: {manifest}")


if __name__ == "__main__":
    main()
