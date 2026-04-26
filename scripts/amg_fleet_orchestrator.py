#!/usr/bin/env python3
"""
amg-fleet — direct-to-Ollama agent orchestrator.

Bypasses OpenClaw's broken agent runtime. Reads the AMG agent specs (TOML), maps
the AMG skill specs (YAML) to shell-callable tools, dispatches inference via
Ollama's /api/chat with native tool-calling, and runs N agents in parallel via
asyncio.

Usage:
    amg_fleet_orchestrator.py --agents achilles --task "Write 'hi' to /tmp/x.txt"
    amg_fleet_orchestrator.py --agents achilles,titan,odysseus,hector \
        --task "Create /tmp/test_{agent}.txt with '{agent} is live'"

The string '{agent}' inside --task is substituted per agent before dispatch.

Logs every run to MCP at memory.aimarketinggenius.io/mcp (best-effort, non-blocking).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time
import tomllib
import urllib.request
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
HOME = pathlib.Path.home()
AGENTS_DIR = HOME / ".openclaw" / "agents"
SKILLS_DIR = HOME / ".openclaw" / "skills" / "amg"
HANDS_FILE = SKILLS_DIR / "digital_hands.json"
OLLAMA_BASE_DEFAULT = "http://localhost:11434"
MCP_LOG_URL = "https://memory.aimarketinggenius.io/mcp/log_decision"
MAX_TOOL_ITERATIONS = 8  # cap loop so a runaway model can't pin Ollama forever
PER_AGENT_TIMEOUT_S = int(os.environ.get("AMG_FLEET_TIMEOUT_S", "180"))  # 32B models need >60s

# ─────────────────────────────────────────────────────────────────────────────
# Digital hands — per-agent skill→tool allowlists
# ─────────────────────────────────────────────────────────────────────────────
def _load_hands() -> dict:
    if not HANDS_FILE.exists():
        return {}
    try:
        return json.loads(HANDS_FILE.read_text())
    except Exception:
        return {}

_HANDS = _load_hands()


def _agent_default_key(agent: str) -> str | None:
    if agent.startswith("atlas_"):
        return None  # explicit per-agent only
    if agent.startswith("amg_") and agent.endswith("_builder"):
        return "_amg_builder_default"
    if agent.startswith("amg_") and agent.endswith("_researcher"):
        return "_amg_researcher_default"
    if agent.startswith("amg_"):
        return "_amg_avatar_default"
    return None


def allowed_tools_for(agent: str, cfg: dict) -> set[str] | None:
    """Resolve per-agent tool allowlist. Returns None to mean 'allow all' (full
    backward compat for legacy agents like 'achilles', 'titan' without atlas_
    prefix or 'main')."""
    overrides = (_HANDS.get("agent_hand_overrides") or {})
    skill_map = (_HANDS.get("skill_to_tools") or {})
    # 1) explicit per-agent override in digital_hands.json
    spec = overrides.get(agent)
    if not spec:
        # 2) per-class default for amg_*
        default_key = _agent_default_key(agent)
        spec = overrides.get(default_key) if default_key else None
    # 3) config.toml [hands] enabled = [...] (highest precedence if present)
    cfg_hands = (cfg.get("hands") or {}).get("enabled")
    if cfg_hands:
        skill_list = cfg_hands
    elif spec and spec.get("skills"):
        skill_list = spec["skills"]
    else:
        return None  # legacy / unscoped — allow all
    tools: set[str] = set()
    for sk in skill_list:
        for t in skill_map.get(sk, []):
            tools.add(t)
    if not tools:
        # empty allowlist — fall back to read-only safe default
        for t in skill_map.get("_default", ["read_file"]):
            tools.add(t)
    return tools

# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations — these are the shell-bound primitives that map to
# the YAML skill specs in ~/.openclaw/skills/amg/. Each returns a string the
# model sees on its next turn.
# ─────────────────────────────────────────────────────────────────────────────
def tool_write_file(path: str, content: str) -> str:
    pathlib.Path(path).write_text(content)
    return f"OK: wrote {len(content)} bytes to {path}"

def tool_read_file(path: str) -> str:
    p = pathlib.Path(path)
    if not p.exists():
        return f"ERROR: {path} not found"
    return p.read_text()

def tool_run_shell(command: str) -> str:
    # NOTE: prototype-grade — accepts arbitrary shell. Production needs allowlist.
    try:
        out = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=20,
        )
        return f"exit={out.returncode}\nstdout: {out.stdout[:1000]}\nstderr: {out.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out (20s)"

def tool_screenshot(output_path: str) -> str:
    r = subprocess.run(["screencapture", "-x", output_path], capture_output=True)
    if r.returncode == 0 and pathlib.Path(output_path).exists():
        size = pathlib.Path(output_path).stat().st_size
        return f"OK: screenshot saved to {output_path} ({size} bytes)"
    return f"ERROR: screencapture exit={r.returncode}"

def tool_edit_file(path: str, old: str, new: str) -> str:
    p = pathlib.Path(path)
    if not p.exists():
        return f"ERROR: {path} not found"
    txt = p.read_text()
    if old not in txt:
        return f"ERROR: pattern not found in {path}"
    bak = pathlib.Path(str(p) + ".bak.amgfleet")
    bak.write_text(txt)
    p.write_text(txt.replace(old, new))
    return f"OK: edited {path} (backup at {bak})"

def tool_git_op(operation: str, args: str = "") -> str:
    allowed = {"status", "diff", "log", "show", "add", "commit", "push", "pull", "branch", "checkout"}
    if operation not in allowed:
        return f"ERROR: git operation '{operation}' not allowed"
    cmd = ["git", operation] + (shlex.split(args) if args else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return f"exit={r.returncode}\nstdout: {r.stdout[:1000]}\nstderr: {r.stderr[:500]}"

def tool_curl_post(url: str, body: str = "{}") -> str:
    safe_hosts = (
        "n8n.aimarketinggenius.io",
        "memory.aimarketinggenius.io",
        "onnabpyamkcfbuxjnwtg.supabase.co",
        "api.aimarketinggenius.io",
    )
    if not any(host in url for host in safe_hosts):
        return f"ERROR: host in URL not in allowlist (allowed: {safe_hosts})"
    cmd = ["curl", "-sS", "-X", "POST", url, "-H", "Content-Type: application/json", "-d", body]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return f"exit={r.returncode}\nstdout: {r.stdout[:1500]}\nstderr: {r.stderr[:300]}"

def tool_browser_screenshot(url: str, output_path: str) -> str:
    # Best-effort Playwright via npx; falls back to ERROR if Playwright not installed.
    cmd = [
        "npx", "--yes", "playwright", "screenshot",
        "--viewport-size=1280,720", url, output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and pathlib.Path(output_path).exists():
        size = pathlib.Path(output_path).stat().st_size
        return f"OK: browser screenshot {output_path} ({size} bytes)"
    return f"ERROR: playwright exit={r.returncode}: {r.stderr[:300]}"

def tool_browser_navigate(url: str) -> str:
    return f"INFO: browser_navigate is a placeholder. Use tool_browser_screenshot for visible verification of {url}."

TOOL_IMPL = {
    "write_file": tool_write_file,
    "read_file": tool_read_file,
    "run_shell": tool_run_shell,
    "screenshot": tool_screenshot,
    "edit_file": tool_edit_file,
    "git_op": tool_git_op,
    "curl_post": tool_curl_post,
    "browser_screenshot": tool_browser_screenshot,
    "browser_navigate": tool_browser_navigate,
}

# Tool descriptors for Ollama (OpenAI-compatible function-calling schema)
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content. Returns OK on success.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Absolute path to the file."},
                    "content": {"type": "string", "description": "Full file content as a string."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at an absolute path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command. Use sparingly — prefer write_file/read_file for file ops.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Capture the current desktop to a PNG file at the given absolute path.",
            "parameters": {
                "type": "object",
                "properties": {"output_path": {"type": "string"}},
                "required": ["output_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace 'old' with 'new' in file at 'path'. Creates a .bak.amgfleet backup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old":  {"type": "string"},
                    "new":  {"type": "string"},
                },
                "required": ["path", "old", "new"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_op",
            "description": "Run an allowed git subcommand: status, diff, log, show, add, commit, push, pull, branch, checkout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "args":      {"type": "string"},
                },
                "required": ["operation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "curl_post",
            "description": "POST JSON to an allowlisted AMG endpoint (n8n, MCP, Supabase Edge Functions, atlas-api).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url":  {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Capture a screenshot of a URL via Playwright (1280×720). Useful for visual QA.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url":         {"type": "string"},
                    "output_path": {"type": "string"},
                },
                "required": ["url", "output_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate a Playwright browser to a URL (placeholder — use browser_screenshot for visible verification).",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
]


def filter_tool_specs(allowed: set[str] | None) -> list[dict]:
    if allowed is None:
        return TOOL_SPECS
    return [s for s in TOOL_SPECS if s["function"]["name"] in allowed]

# ─────────────────────────────────────────────────────────────────────────────
# Agent config loader
# ─────────────────────────────────────────────────────────────────────────────
def load_agent_config(name: str) -> dict[str, Any]:
    """Read ~/.openclaw/agents/<name>/config.toml. Falls back to sane defaults."""
    cfg_path = AGENTS_DIR / name / "config.toml"
    if not cfg_path.exists():
        return {
            "agent": {"name": name, "role": "generic", "primary_model": "qwen2.5-coder:7b", "fallback_model": "qwen2.5-coder:7b"},
            "rules": {},
        }
    return tomllib.loads(cfg_path.read_text())

# Ollama models that natively support tool/function calling. Anything outside
# this set will reject `tools=[...]` with HTTP 400 — we substitute when needed.
TOOL_CAPABLE_OLLAMA_MODELS = {
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "qwen2.5:32b",
    "qwen3:14b",
    "llama3.3:70b",
    "llama3.1:8b",
    "mistral:7b-instruct",
}
DEFAULT_TOOL_MODEL = "qwen2.5-coder:7b"

# Logical aliases (Hercules CT-0426 doctrine) → concrete Ollama tags.
# When a config.toml lists primary_model="vps_smart" etc., resolve to the
# actual model tag the orchestrator will hand to Ollama.
MODEL_ALIASES = {
    "mac_fast":      "qwen2.5-coder:7b",
    "vps_smart":     "qwen2.5:32b",
    "vps_reasoning": "deepseek-r1:32b",
    # api_* aliases are NOT Ollama; agents using them go through a different
    # dispatch path (not implemented here yet — falls through to default
    # tool-capable model so the local runtime still works for testing).
    "api_premium":       "qwen2.5-coder:7b",
    "api_premium_flash": "qwen2.5-coder:7b",
    "api_research":      "qwen2.5-coder:7b",
    "api_google":        "qwen2.5-coder:7b",
}


def _resolve_alias(name: str) -> str:
    return MODEL_ALIASES.get(name, name) if name else name


def resolve_model(cfg: dict, prefer_fallback: bool = True, need_tools: bool = True) -> str:
    """Return the Ollama model tag. Resolves Hercules-doctrine aliases
    (vps_smart, mac_fast, etc.) to concrete tags. If chosen tag isn't in the
    tool-capable set, substitute DEFAULT_TOOL_MODEL so Ollama doesn't 400.
    """
    a = cfg.get("agent", {})
    primary  = _resolve_alias(a.get("primary_model"))
    fallback = _resolve_alias(a.get("fallback_model"))
    chosen = (fallback if prefer_fallback else primary) or primary or "qwen2.5-coder:7b"
    if need_tools and chosen not in TOOL_CAPABLE_OLLAMA_MODELS:
        return DEFAULT_TOOL_MODEL
    return chosen

def system_prompt_for(cfg: dict) -> str:
    a = cfg.get("agent", {})
    rules = cfg.get("rules", {})
    rule_lines = [f"- {k.replace('_', ' ')}" for k, v in rules.items() if v is True]
    return (
        f"You are {a.get('name','agent')}, an AMG agent in role '{a.get('role','generic')}'. "
        "Use the provided tools (write_file, read_file, run_shell, screenshot) to complete the task. "
        "Prefer write_file/read_file over run_shell for file operations. "
        "When the task is done, return a short text summary and stop calling tools.\n"
        + ("\nRules:\n" + "\n".join(rule_lines) if rule_lines else "")
    )

# ─────────────────────────────────────────────────────────────────────────────
# Ollama dispatch (with tool-call loop)
# ─────────────────────────────────────────────────────────────────────────────
async def ollama_chat(messages: list[dict], model: str, base: str, tools: list[dict] | None = None) -> dict:
    """Single-turn request to Ollama /api/chat. Runs blocking urllib in a
    thread so asyncio.gather can fan out without GIL contention on I/O."""
    payload = json.dumps({
        "model":   model,
        "messages": messages,
        "tools":    tools if tools is not None else TOOL_SPECS,
        "stream":   False,
        "options":  {"temperature": 0.2, "num_ctx": 8192},
    }).encode()

    def _post() -> dict:
        req = urllib.request.Request(
            f"{base}/api/chat", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=PER_AGENT_TIMEOUT_S) as r:
            return json.loads(r.read())

    return await asyncio.to_thread(_post)

async def run_agent(agent: str, task: str, base: str) -> dict:
    """Run one agent end-to-end: load config → loop chat+tools until done."""
    t0 = time.time()
    cfg = load_agent_config(agent)
    model = resolve_model(cfg, prefer_fallback=True)
    sys_prompt = system_prompt_for(cfg)
    allowed = allowed_tools_for(agent, cfg)
    tool_specs = filter_tool_specs(allowed)
    if allowed is not None:
        sys_prompt += (
            f"\n\nDigital hands: you may ONLY call these tools: "
            f"{sorted(allowed)}. Other tools will be denied."
        )
    messages: list[dict] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": task},
    ]

    err: str | None = None
    last_text = ""
    tool_calls_made = 0
    tool_calls_denied = 0

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            resp = await ollama_chat(messages, model, base, tool_specs)
        except Exception as e:
            err = f"ollama_chat failed: {e!r}"
            break

        msg = resp.get("message") or {}
        last_text = msg.get("content", "") or last_text
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []

        # Fallback: smaller Ollama models (qwen2.5-coder etc.) often emit a JSON
        # tool-call envelope inside `content` instead of populating `tool_calls`.
        # Scan content for {"name": ..., "arguments": ...} blocks and synthesize
        # the structured calls so the loop below can execute them.
        if not tool_calls and last_text:
            for m in re.finditer(r"\{[^{}]*\"name\"\s*:\s*\"([a-zA-Z_]+)\"[^{}]*\"arguments\"\s*:\s*(\{(?:[^{}]|\{[^{}]*\})*\})", last_text):
                try:
                    name = m.group(1)
                    args = json.loads(m.group(2))
                    tool_calls.append({"function": {"name": name, "arguments": args}})
                except Exception:
                    continue

        if not tool_calls:
            break

        for tc in tool_calls:
            fn = (tc.get("function") or {}).get("name")
            args = (tc.get("function") or {}).get("arguments") or {}
            if isinstance(args, str):
                try: args = json.loads(args)
                except Exception: args = {}
            if allowed is not None and fn not in allowed:
                tool_result = f"DENIED: tool '{fn}' not in agent allowlist {sorted(allowed)}"
                tool_calls_denied += 1
            else:
                impl = TOOL_IMPL.get(fn)
                if not impl:
                    tool_result = f"ERROR: unknown tool '{fn}'"
                else:
                    try:
                        tool_result = impl(**args)
                    except Exception as e:
                        tool_result = f"ERROR: tool {fn} raised: {e!r}"
            messages.append({"role": "tool", "name": fn, "content": tool_result})
            tool_calls_made += 1

    latency_ms = int((time.time() - t0) * 1000)
    return {
        "agent":         agent,
        "model_used":    model,
        "tools_allowed": sorted(allowed) if allowed is not None else "all",
        "tools_denied":  tool_calls_denied,
        "latency_ms":    latency_ms,
        "tool_calls":    tool_calls_made,
        "result":        last_text or ("(no text — used tools only)" if tool_calls_made else "(empty)"),
        "success":       err is None,
        "error":         err,
    }

# ─────────────────────────────────────────────────────────────────────────────
# MCP best-effort logger
# ─────────────────────────────────────────────────────────────────────────────
async def mcp_log(agent: str, task: str, result: dict) -> None:
    payload = json.dumps({
        "agent":     agent,
        "task":      task,
        "result":    result,
        "timestamp": int(time.time()),
    }).encode()
    def _post() -> None:
        try:
            req = urllib.request.Request(
                MCP_LOG_URL, data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            pass  # non-blocking — MCP outage doesn't fail the run
    await asyncio.to_thread(_post)

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
async def main_async(args: argparse.Namespace) -> int:
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    if not agents:
        print("error: --agents must list at least one agent", file=sys.stderr)
        return 2

    # Per-agent task: substitute {agent} placeholder
    pairs = [(a, args.task.replace("{agent}", a)) for a in agents]

    t0 = time.time()
    results = await asyncio.gather(*[run_agent(a, t, args.ollama_base) for a, t in pairs])
    total_ms = int((time.time() - t0) * 1000)

    # Best-effort MCP log per agent (parallel)
    if not args.skip_mcp:
        await asyncio.gather(*[mcp_log(a, t, r) for (a, t), r in zip(pairs, results)])

    summary = {
        "total_latency_ms":   total_ms,
        "agent_count":        len(agents),
        "success_count":      sum(1 for r in results if r["success"]),
        "results":            results,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["success_count"] == len(agents) else 1

def main() -> int:
    p = argparse.ArgumentParser(description="amg-fleet — direct-to-Ollama agent orchestrator")
    p.add_argument("--agents", required=True, help="comma-separated agent names (achilles,titan,odysseus,hector)")
    p.add_argument("--task",   required=True, help="task prompt; '{agent}' is substituted per agent")
    p.add_argument("--ollama-base", default=OLLAMA_BASE_DEFAULT, help=f"Ollama base URL (default {OLLAMA_BASE_DEFAULT})")
    p.add_argument("--skip-mcp", action="store_true", help="skip MCP logging (offline / fast tests)")
    args = p.parse_args()
    return asyncio.run(main_async(args))

if __name__ == "__main__":
    sys.exit(main())
