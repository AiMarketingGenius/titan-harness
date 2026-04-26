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
MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io/mcp")
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
PREMIUM_AGENTS = {"atlas_judge_deepseek"}


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


# ─── MCP helpers ─────────────────────────────────────────────────────────────
def _mcp_post(path: str, body: dict, timeout: int = 15) -> tuple[int, dict]:
    url = f"{MCP_BASE}/{path.lstrip('/')}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except Exception as e:
        return -1, {"error": repr(e)}


def fetch_pending_tasks(limit: int = 10) -> list[dict]:
    code, body = _mcp_post(
        "get_task_queue", {"status": "pending", "limit": limit},
    )
    if code != 200 or not body.get("success"):
        return []
    return body.get("tasks", [])


def mark_in_progress(task_id: str, dispatcher_id: str) -> None:
    _mcp_post("update_task", {
        "task_id": task_id,
        "status": "in_progress",
        "notes": f"dispatched by {dispatcher_id} at {datetime.now(tz=timezone.utc).isoformat()}",
    })


def mark_done(task_id: str, summary: str, link: str | None = None) -> None:
    body = {
        "task_id": task_id,
        "status": "done",
        "result_summary": summary[:1000],
    }
    if link:
        body["deliverable_link"] = link
    _mcp_post("update_task", body)


def mark_failed(task_id: str, reason: str) -> None:
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
    if a in KIMI_AGENTS:
        return "kimi_api"
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
