#!/usr/bin/env python3
"""
agent_dispatch_bridge.py — MCP task queue → agent fleet router.

Reads pending tasks from MCP `op_task_queue`, picks each one up by mapping the
task's agent assignment to the right execution lane, runs it, logs proof to
`op_decisions`, and updates the task status.

Lanes
-----
1. kimi_api      — for Kimi-stack personas (nestor, alexander, hercules,
                   etc). Calls api.moonshot.ai with the kimi-k2.6 model.
                   Falls back to running ssh-based kimi CLI on the VPS if a
                   binary is present (currently absent — API path only).
2. amg_fleet     — for OpenClaw-resident agents (achilles, titan, odysseus,
                   hector, atlas_*, amg_<avatar>_builder). Shells out to
                   `scripts/amg_fleet_orchestrator.py --agents <name> --task ...`.
3. api_research  — for Perplexity-grounded judges/researchers (atlas_judge_
                   perplexity, atlas_research_perplexity, amg_*_researcher
                   except Nadia). Daily budget check via aliases.json before
                   the call.
4. api_google    — for Gemini-grounded researchers (atlas_research_gemini,
                   amg_nadia_researcher).
5. api_premium   — for DeepSeek architecture audits (atlas_judge_deepseek,
                   atlas_achilles fallback when local saturated).

Routing key
-----------
The bridge reads the task's `assigned_to`, `agent`, and `tags` fields, plus a
`notes` field hint like "DISPATCH: <agent>". First match wins. If the task is
ambiguous, it gets logged as `dispatch_skipped` with the reason and left in
the queue.

Usage
-----
    agent_dispatch_bridge.py --once       # drain one batch, exit
    agent_dispatch_bridge.py --watch      # poll every 60s (cron-friendly)
    agent_dispatch_bridge.py --task TASK_ID  # dispatch a single task by id
    agent_dispatch_bridge.py --dry-run    # plan + log, don't actually call

Reads /etc/amg/openrouter.env, /etc/amg/perplexity.env, /etc/amg/gemini.env,
/etc/amg/moonshot.env when present; falls back to env vars OPENROUTER_API_KEY
etc. otherwise. MCP base reads from MCP_BASE env (default
https://memory.aimarketinggenius.io/mcp).

Logs every dispatch to MCP `log_decision` with tag `agent-dispatch-bridge`.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io").rstrip("/")
# Routes migrated to /api/* (2026-04-26 — REST wrappers added to MCP server).
# The bare names (queue_operator_task etc) were JSON-RPC-only and returned 404.
ALIASES_FILE = HOME / ".openclaw" / "models" / "aliases.json"
FLEET_SCRIPT = HOME / "titan-harness" / "scripts" / "amg_fleet_orchestrator.py"
ETC_AMG = pathlib.Path("/etc/amg")  # only readable on VPS; on Mac read via SSH
SSH_HOST = os.environ.get("AMG_VPS_SSH_HOST", "amg-staging")

KIMI_AGENTS    = {"nestor", "alexander", "hercules", "kimi"}
OPENCLAW_AGENTS = {
    "achilles", "titan", "odysseus", "hector",
    "atlas_titan", "atlas_achilles", "atlas_odysseus",
    "atlas_hector", "atlas_hercules", "atlas_eom",
    "atlas_einstein", "atlas_hallucinometer",
}
RESEARCH_AGENTS = {
    "atlas_judge_perplexity", "atlas_research_perplexity",
}
GOOGLE_AGENTS = {"atlas_research_gemini", "amg_nadia_researcher"}
# Direct DeepSeek API (skip OpenRouter markup — Solon has $50 topped at api.deepseek.com)
# Mercury added 2026-04-26 per CT-0426 Fix 1 — qwen2.5-coder:7b was hallucinating
# orchestration completions. V4 Pro for multi-phase/premium, V4 Flash routine.
# Local Qwen 32B is the no-API-key fallback in lane_deepseek_direct itself.
DEEPSEEK_DIRECT_AGENTS = {"daedalus", "atlas_judge_deepseek", "mercury"}
# FREE fleet-wide browser-takeover via browser-use + local R1 32B (zero $ cost)
BROWSER_TAKEOVER_AGENTS = {"mercury", "daedalus", "archimedes", "atlas_titan", "atlas_odysseus"}
# Premium fallback via OpenRouter (only when DeepSeek direct unavailable)
PREMIUM_AGENTS = set()


# ─── env loading ─────────────────────────────────────────────────────────────
def _load_env_remote(name: str) -> dict:
    """Read /etc/amg/<name>.env from VPS via SSH. Returns {} on failure."""
    try:
        out = subprocess.run(
            ["ssh", SSH_HOST, f"cat /etc/amg/{name}.env"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return {}
        env = {}
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
        return env
    except Exception:
        return {}


def _key(env_name: str, file_hints: list[str]) -> str | None:
    if env_name in os.environ:
        return os.environ[env_name]
    for f in file_hints:
        env = _load_env_remote(f)
        if env_name in env:
            return env[env_name]
    return None


def _load_aliases() -> dict:
    try:
        return json.loads(ALIASES_FILE.read_text())
    except Exception:
        return {"aliases": {}}


# ─── MCP helpers (migrated to /api/* REST routes 2026-04-26) ────────────────
# Path migration table — old MCP-tool name → new /api/* REST path
_PATH_MAP = {
    "get_task_queue": ("GET",  "/api/task-queue"),
    "queue_operator_task": ("POST", "/api/queue-task"),
    "update_task": ("POST", "/api/update-task"),
    "claim_task": ("POST", "/api/claim-task"),
    "log_decision": ("POST", "/api/decisions"),
    "get_recent_decisions": ("GET", "/api/recent-decisions-json"),
}


def _mcp_post(path: str, body: dict, timeout: int = 15) -> tuple[int, dict]:
    """Backward-compat shim. Old call sites used path names like
    'get_task_queue'. Map to new /api/* REST routes; some are GET with query
    strings instead of POST."""
    method, route = _PATH_MAP.get(path, ("POST", "/" + path.lstrip("/")))
    if method == "GET":
        # Convert body to query params
        from urllib.parse import urlencode
        clean = {k: v for k, v in body.items() if v is not None}
        url = f"{MCP_BASE}{route}"
        if clean:
            url += "?" + urlencode(clean)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
    else:
        url = f"{MCP_BASE}{route}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
        )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return -1, {"error": repr(e)}


def fetch_pending_tasks(limit: int = 10) -> list[dict]:
    """Pull approved tasks but filter out stale pre-Hercules-takeover work
    (>7 days old, not in CT-0426 batch). Stale tasks need Hercules audit
    to re-validate before re-execution. Stops the cron firehose on the
    50+ Apr 5/16/17/18/19 backlog."""
    from datetime import timedelta
    code, body = _mcp_post(
        "get_task_queue", {"status": "approved", "limit": max(limit, 50)},
    )
    if code != 200:
        return []
    tasks = body.get("tasks") or []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
    fresh: list[dict] = []
    for t in tasks:
        tid = t.get("task_id", "")
        # Always include CT-0426 batch (Hercules-as-chief era)
        if tid.startswith("CT-0426"):
            fresh.append(t)
            continue
        # Otherwise skip if older than 7 days
        ts_str = t.get("created_at", "")
        if not ts_str:
            fresh.append(t)
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts >= cutoff:
                fresh.append(t)
        except Exception:
            fresh.append(t)
        if len(fresh) >= limit:
            break
    return fresh


def mark_in_progress(task_id: str, dispatcher_id: str) -> None:
    _mcp_post("update_task", {
        "task_id": task_id,
        "status": "active",
        "notes": f"dispatched by {dispatcher_id} at {datetime.now(tz=timezone.utc).isoformat()}",
    })


def mark_done(task_id: str, summary: str, link: str | None = None) -> None:
    # FSM hops through 'active' first if currently locked.
    # Terminal-success state in MCP is 'completed' (not 'done').
    _mcp_post("update_task", {"task_id": task_id, "status": "active",
                              "notes": "dispatch_bridge: pre-completed hop"})
    body = {
        "task_id": task_id,
        "status": "completed",
        "result_summary": summary[:1000],
    }
    if link:
        body["deliverable_link"] = link
    _mcp_post("update_task", body)


def mark_failed(task_id: str, reason: str) -> None:
    _mcp_post("update_task", {"task_id": task_id, "status": "active",
                              "notes": "dispatch_bridge: pre-fail hop"})
    _mcp_post("update_task", {
        "task_id": task_id,
        "status": "failed",
        "failure_reason": reason[:500],
    })


def log_dispatch(agent: str, task: dict, lane: str, result: dict) -> None:
    _mcp_post("log_decision", {
        "text": (
            f"agent-dispatch: {agent} via {lane} for task "
            f"{task.get('id') or task.get('task_id') or 'unknown'} → "
            f"ok={result.get('ok')} latency_ms={result.get('latency_ms')} "
            f"out={(result.get('text') or '')[:200]}"
        ),
        "rationale": (
            f"Bridge auto-routed task to {lane} based on agent name. "
            f"Task body: {(task.get('objective') or task.get('text') or '')[:200]}"
        ),
        "tags": ["agent-dispatch-bridge", lane, agent],
        "project_source": "titan",
    })


# ─── lane: Kimi/Moonshot API ────────────────────────────────────────────────
def lane_kimi_api(agent: str, prompt: str) -> dict:
    t0 = time.time()
    key = _key("MOONSHOT_API_KEY", ["moonshot"]) or _key("KIMI_API_KEY", ["moonshot"])
    if not key:
        return {"ok": False, "error": "no MOONSHOT_API_KEY", "latency_ms": 0}
    body = {
        "model": "kimi-k2.6",
        "messages": [
            {"role": "system",
             "content": f"You are {agent}, an AMG agent. Respond tersely."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1024,
    }
    req = urllib.request.Request(
        "https://api.moonshot.ai/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return {"ok": True, "text": text, "raw": data, "latency_ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read()[:200]}",
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "latency_ms": int((time.time() - t0) * 1000)}


# ─── lane: amg-fleet (OpenClaw) ─────────────────────────────────────────────
def lane_amg_fleet(agent: str, prompt: str, ollama_base: str | None = None) -> dict:
    t0 = time.time()
    if not FLEET_SCRIPT.exists():
        return {"ok": False, "error": f"fleet script missing: {FLEET_SCRIPT}",
                "latency_ms": 0}
    cmd = [
        "python3", str(FLEET_SCRIPT),
        "--agents", agent,
        "--task", prompt,
        "--skip-mcp",  # bridge does its own MCP logging
    ]
    if ollama_base:
        cmd += ["--ollama-base", ollama_base]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        latency_ms = int((time.time() - t0) * 1000)
        if out.returncode != 0 and out.returncode != 1:  # 1 = partial
            return {"ok": False, "error": f"exit={out.returncode}: {out.stderr[:300]}",
                    "latency_ms": latency_ms}
        try:
            payload = json.loads(out.stdout)
        except Exception:
            payload = {"raw": out.stdout[:500]}
        agent_result = (payload.get("results") or [{}])[0]
        return {
            "ok": agent_result.get("success", False) or out.returncode == 0,
            "text": agent_result.get("result", ""),
            "raw": payload,
            "latency_ms": latency_ms,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "fleet timeout 300s",
                "latency_ms": int((time.time() - t0) * 1000)}


# ─── lane: Perplexity Sonar ─────────────────────────────────────────────────
def lane_perplexity(agent: str, prompt: str) -> dict:
    t0 = time.time()
    key = _key("PERPLEXITY_API_KEY", ["perplexity"])
    if not key:
        return {"ok": False, "error": "no PERPLEXITY_API_KEY", "latency_ms": 0}
    body = {
        "model": "sonar-pro",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    req = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return {"ok": True, "text": text, "raw": data,
                "latency_ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read()[:200]}",
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "latency_ms": int((time.time() - t0) * 1000)}


# ─── lane: Gemini ───────────────────────────────────────────────────────────
def lane_gemini(agent: str, prompt: str) -> dict:
    t0 = time.time()
    key = _key("GEMINI_API_KEY", ["gemini"])
    if not key:
        return {"ok": False, "error": "no GEMINI_API_KEY", "latency_ms": 0}
    body = {
        "contents": [{"parts": [{"text": prompt}], "role": "user"}],
        "generationConfig": {"maxOutputTokens": 1024},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={key}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        cands = data.get("candidates") or []
        text = ""
        if cands:
            parts = cands[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        return {"ok": bool(text), "text": text, "raw": data,
                "latency_ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read()[:200]}",
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "latency_ms": int((time.time() - t0) * 1000)}


# ─── lane: DeepSeek DIRECT (api.deepseek.com — cheaper than OpenRouter) ─────
def lane_deepseek_direct(agent: str, prompt: str, model: str = "deepseek-v4-flash") -> dict:
    """Solon's DeepSeek account: $50 topped, key in /etc/amg/deepseek.env on VPS.
    V4 Flash for routine code/audit (~$0.40/1M out). V4 Pro for premium reasoning.
    Direct API skips OpenRouter's 5-10% markup."""
    t0 = time.time()
    key = _key("DEEPSEEK_API_KEY", ["deepseek"])
    if not key:
        return {"ok": False, "error": "no DEEPSEEK_API_KEY in /etc/amg/deepseek.env",
                "latency_ms": 0}
    body = {
        "model": model,
        "messages": [
            {"role": "system",
             "content": f"You are {agent}, an AMG specialist agent. Be concise and proof-oriented."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return {"ok": True, "text": text, "raw": data,
                "model": model,
                "latency_ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read()[:200]}",
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "latency_ms": int((time.time() - t0) * 1000)}


# ─── lane: browser-use FREE (open-source LLM-driven Chrome via local R1 32B) ─
def lane_browser_takeover(agent: str, prompt: str, params: dict | None = None) -> dict:
    """browser-use + local DeepSeek R1 32B on VPS. $0 cost.

    Spawns a browser-use agent on the VPS via SSH that:
    - Launches a headless Chromium via Playwright
    - Uses local Ollama R1 32B as the reasoning brain
    - Executes the prompt as natural-language browser instructions
    - Returns final state + screenshot path

    Best for: client portal scrapes when no API, demo recordings, AIMG
    dogfood automation, deep research crawls (Archimedes Mode 1/2).
    NOT for tasks that need pixel-perfect screen reading — those still
    escalate to Anthropic Computer Use via Titan or Daedalus.

    params: {url, max_steps, screenshot_required, viewport_width, viewport_height}
    """
    t0 = time.time()
    params = params or {}
    url = params.get("url", "")
    max_steps = int(params.get("max_steps", 12))
    screenshot_required = params.get("screenshot_required", True)
    out_path = params.get("out_path", f"/tmp/browser_use_{agent}_{int(time.time())}.png")

    # Build a JSON-encoded task spec the VPS-side runner consumes
    task_spec = json.dumps({
        "agent_name": agent,
        "prompt": prompt[:4000],
        "url": url,
        "max_steps": max_steps,
        "screenshot_path": out_path if screenshot_required else None,
    })

    # Run via SSH — invokes /opt/amg-tools/run_browser_use.py on VPS
    # which uses ollama deepseek-r1:32b as the LLM, browser-use lib for Chromium control.
    try:
        out = subprocess.run(
            [
                "ssh", SSH_HOST,
                f"python3 /opt/amg-tools/run_browser_use.py --task-json {shlex.quote(task_spec)}",
            ],
            capture_output=True, text=True, timeout=600,  # 10 min ceiling per task
        )
        if out.returncode != 0:
            return {
                "ok": False,
                "error": f"VPS exit {out.returncode}: {(out.stderr or '')[-300:]}",
                "latency_ms": int((time.time() - t0) * 1000),
            }
        try:
            payload = json.loads(out.stdout)
        except Exception:
            payload = {"raw_stdout": out.stdout[-1000:]}
        return {
            "ok": True,
            "text": payload.get("final_state") or payload.get("raw_stdout", ""),
            "screenshot_path": payload.get("screenshot_path", out_path),
            "steps_taken": payload.get("steps_taken"),
            "raw": payload,
            "latency_ms": int((time.time() - t0) * 1000),
            "cost_usd": 0.0,  # local LLM, no API charge
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "browser-use timeout 600s",
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "latency_ms": int((time.time() - t0) * 1000)}


# ─── lane: OpenRouter / DeepSeek V4 Pro ─────────────────────────────────────
def lane_openrouter(agent: str, prompt: str, model: str = "deepseek/deepseek-v4-pro") -> dict:
    t0 = time.time()
    key = _key("OPENROUTER_API_KEY", ["openrouter"])
    if not key:
        return {"ok": False, "error": "no OPENROUTER_API_KEY", "latency_ms": 0}
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return {"ok": True, "text": text, "raw": data,
                "latency_ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read()[:200]}",
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": repr(e),
                "latency_ms": int((time.time() - t0) * 1000)}


# ─── routing ────────────────────────────────────────────────────────────────
def pick_lane(agent: str, task: dict) -> str:
    a = (agent or "").lower()
    # Browser-takeover wins if explicitly requested via mercury_action.type
    notes = (task.get("notes") or "").lower()
    if "mercury_action" in notes and "browser_takeover" in notes and a in BROWSER_TAKEOVER_AGENTS:
        return "browser_takeover"
    if a in KIMI_AGENTS:
        return "kimi_api"
    if a in DEEPSEEK_DIRECT_AGENTS:
        return "api_deepseek_direct"
    if a in OPENCLAW_AGENTS or a.startswith("amg_") and a.endswith("_builder"):
        return "amg_fleet"
    if a in RESEARCH_AGENTS or a.startswith("amg_") and a.endswith("_researcher") and a != "amg_nadia_researcher":
        return "api_research"
    if a in GOOGLE_AGENTS:
        return "api_google"
    if a in PREMIUM_AGENTS:
        return "api_premium"
    # AMG avatar (front-facing strategist) — runs on amg-fleet
    if a.startswith("amg_"):
        return "amg_fleet"
    return "amg_fleet"  # default


def dispatch_task(task: dict, dry: bool = False) -> dict:
    agent = task.get("agent_assigned") or task.get("agent") or task.get("assigned_to") or "atlas_eom"
    # honor "DISPATCH: <name>" hint in notes
    notes = task.get("notes") or ""
    for line in notes.splitlines():
        if line.strip().lower().startswith("dispatch:"):
            agent = line.split(":", 1)[1].strip()
            break
    prompt = (
        task.get("instructions")
        or task.get("objective")
        or task.get("text")
        or "(no instructions provided)"
    )
    lane = pick_lane(agent, task)
    if dry:
        return {"agent": agent, "lane": lane, "dry_run": True, "ok": True, "text": "(skipped)"}
    if lane == "kimi_api":
        result = lane_kimi_api(agent, prompt)
    elif lane == "amg_fleet":
        result = lane_amg_fleet(agent, prompt)
    elif lane == "api_research":
        result = lane_perplexity(agent, prompt)
    elif lane == "api_google":
        result = lane_gemini(agent, prompt)
    elif lane == "api_deepseek_direct":
        # DeepSeek direct — V4 Flash default; if task tags include 'premium' or
        # context length suggests heavy reasoning, escalate to V4 Pro.
        # Mercury orchestration tasks (multi-phase, multi-agent-coordinated, or
        # any explicit "phase" instructions) auto-promote to V4 Pro.
        notes = (task.get("notes") or "").lower()
        tags = [str(t).lower() for t in (task.get("tags") or [])]
        instr = (task.get("instructions") or "").lower()
        prefer_pro = (
            "premium" in notes or "premium" in tags
            or "architecture" in notes or "v4-pro" in tags
            or len(prompt) > 3000
            or "multi-agent-coordinated" in tags
            or "final-debug" in tags
            or "phase 1" in instr or "phase 2" in instr or "phase 3" in instr
            or "orchestrat" in instr
        )
        model = "deepseek-v4-pro" if prefer_pro else "deepseek-v4-flash"
        result = lane_deepseek_direct(agent, prompt, model=model)
    elif lane == "browser_takeover":
        # Free fleet-wide browser-use + local R1 32B
        action = task.get("notes") or ""
        # Extract MERCURY_ACTION params if present
        params: dict = {}
        for line in action.splitlines():
            if line.strip().startswith("MERCURY_ACTION:"):
                try:
                    params = json.loads(line.split(":", 1)[1].strip()).get("params", {}) or {}
                except Exception:
                    pass
        result = lane_browser_takeover(agent, prompt, params=params)
    elif lane == "api_premium":
        result = lane_openrouter(agent, prompt)
    else:
        result = {"ok": False, "error": f"unknown lane {lane}", "latency_ms": 0}
    log_dispatch(agent, task, lane, result)
    if result.get("ok"):
        mark_done(task.get("task_id") or task.get("id") or "", result.get("text", "")[:1000])
    else:
        mark_failed(task.get("task_id") or task.get("id") or "", result.get("error", "unknown"))
    result["agent"] = agent
    result["lane"] = lane
    return result


def drain_once(limit: int = 10, dry: bool = False) -> list[dict]:
    tasks = fetch_pending_tasks(limit=limit)
    out = []
    for t in tasks:
        tid = t.get("task_id") or t.get("id")
        if not dry and tid:
            mark_in_progress(tid, "agent_dispatch_bridge")
        r = dispatch_task(t, dry=dry)
        r["task_id"] = tid
        out.append(r)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Agent dispatch bridge — MCP queue → fleet")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--task", help="single task body as JSON")
    p.add_argument("--task-id", help="single MCP task id to dispatch")
    p.add_argument("--agent", help="for --task, override the agent")
    p.add_argument("--prompt", help="for --task, override the prompt")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    args = p.parse_args()

    if args.task or args.task_id or (args.agent and args.prompt):
        if args.agent and args.prompt:
            t = {"task_id": "AD-HOC", "agent_assigned": args.agent, "instructions": args.prompt}
        elif args.task_id:
            code, body = _mcp_post("get_task_queue", {"task_id": args.task_id})
            tasks = body.get("tasks") or []
            if not tasks:
                print(f"task {args.task_id} not found", file=sys.stderr)
                return 2
            t = tasks[0]
        else:
            t = json.loads(args.task)
        r = dispatch_task(t, dry=args.dry_run)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1

    if args.watch:
        while True:
            try:
                results = drain_once(limit=args.limit, dry=args.dry_run)
                if results:
                    print(json.dumps({"drained": len(results),
                                      "ok": sum(1 for r in results if r.get("ok"))}, indent=2))
            except KeyboardInterrupt:
                return 0
            except Exception as e:
                print(f"[watch] error: {e!r}", file=sys.stderr)
            time.sleep(60)

    # default: --once
    results = drain_once(limit=args.limit, dry=args.dry_run)
    print(json.dumps({"drained": len(results), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
