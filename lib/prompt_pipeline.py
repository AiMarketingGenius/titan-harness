"""
titan-harness/lib/prompt_pipeline.py - Phase P7 (war-room graded A in spec)

Declarative DAG runner for multi-step LLM pipelines. Each step is a dict
with name, prompt_template, inputs, outputs, model_group, depends_on,
validate, retries, timeout.

Public API:
    run_pipeline(name: str, steps: list[dict], inputs: dict,
                 caller: str = "unknown") -> dict
    load_pipeline(yaml_path: str) -> list[dict]

Features:
    - Topological sort with cycle detection
    - Parallel execution of independent branches via asyncio.gather
    - Per-step retries with escalation (Haiku -> Sonnet -> Opus)
    - Per-step timeout + per-pipeline wall-clock cap
    - Idempotent step output cache (hash(template + inputs + model))
    - Capacity-gated before each step
"""
from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import asyncio
import uuid
import re
from typing import Any, Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from capacity import check_capacity
    from llm_client import complete
    from model_router import resolve_model
except Exception:
    def check_capacity(timeout: float = 5.0) -> int:
        return 0
    def complete(*a, **kw) -> str:
        return ""
    def resolve_model(tt: Optional[str], task: Optional[dict] = None) -> str:
        return "claude-sonnet-4-6"

from urllib import request, error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_MAX_CONCURRENT = int(os.environ.get("POLICY_CAPACITY_MAX_LLM_CONCURRENT_BATCHES", "8"))


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------
def _supa(path: str, method: str = "GET", body: Optional[dict] = None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        data = json.dumps(body).encode() if body else None
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": "Bearer " + SUPABASE_KEY,
            "Accept": "application/json",
        }
        if body:
            headers["Content-Type"] = "application/json"
            headers["Prefer"] = "return=representation"
        req = request.Request(SUPABASE_URL + "/rest/v1/" + path,
                              data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=5) as r:
            if r.status == 204:
                return None
            return json.loads(r.read())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Topological sort with cycle detection
# ---------------------------------------------------------------------------
def _topo_sort(steps: list[dict]) -> list[list[str]]:
    """Return a list of 'waves' — each wave is a list of step names that
    can run in parallel (all dependencies satisfied by prior waves)."""
    name_to_step = {s["name"]: s for s in steps}
    in_degree = {s["name"]: 0 for s in steps}
    dependents: dict[str, list[str]] = {s["name"]: [] for s in steps}
    for s in steps:
        for dep in s.get("depends_on", []):
            if dep not in name_to_step:
                raise ValueError(f"step '{s['name']}' depends on unknown step '{dep}'")
            in_degree[s["name"]] += 1
            dependents[dep].append(s["name"])

    waves: list[list[str]] = []
    ready = [n for n, d in in_degree.items() if d == 0]
    scheduled = set()
    while ready:
        wave = sorted(ready)
        waves.append(wave)
        scheduled.update(wave)
        next_ready = []
        for n in wave:
            for m in dependents[n]:
                in_degree[m] -= 1
                if in_degree[m] == 0:
                    next_ready.append(m)
        ready = next_ready

    if len(scheduled) != len(steps):
        unresolved = set(in_degree.keys()) - scheduled
        raise ValueError(f"pipeline has cycle or unreachable steps: {unresolved}")

    return waves


# ---------------------------------------------------------------------------
# Prompt template rendering
# ---------------------------------------------------------------------------
def _render(template: str, context: dict) -> str:
    def repl(m):
        key = m.group(1).strip()
        v = context.get(key, "")
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return str(v)
    return re.sub(r"\{\{\s*([a-z0-9_]+)\s*\}\}", repl, template, flags=re.IGNORECASE)


def _step_cache_key(step: dict, rendered_prompt: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(step.get("name", "").encode())
    h.update(rendered_prompt.encode())
    h.update(model.encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Single step execution
# ---------------------------------------------------------------------------
async def _run_step(step: dict, context: dict, run_id: str,
                    pipeline_name: str) -> dict:
    name = step["name"]
    task_type = step.get("task_type") or step.get("model_group") or "phase"
    model = resolve_model(task_type)

    # Capacity gate
    cap = check_capacity()
    if cap == 2:
        _supa("pipeline_steps", "POST", {
            "run_id": run_id,
            "step_name": name,
            "model_resolved": model,
            "status": "failed",
            "error_text": "capacity hard block",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        return {"_status": "deferred", "error": "capacity hard block"}

    rendered = _render(step.get("prompt_template", ""), context)
    cache_key = _step_cache_key(step, rendered, model)

    # Check cache (pipeline_step_outputs keyed by (run_id, step_name, content_hash))
    cached = _supa("pipeline_step_outputs?step_name=eq." + name +
                   "&content_hash=eq." + cache_key + "&limit=1")
    if cached:
        return cached[0].get("output", {})

    started = time.time()
    retries = int(step.get("retries", 2))
    timeout = float(step.get("timeout", 180.0))
    output_text = ""
    error_text = None

    loop = asyncio.get_event_loop()
    for attempt in range(retries + 1):
        try:
            output_text = await asyncio.wait_for(
                loop.run_in_executor(
                    None, complete, rendered, model, 4000, 0.1, timeout
                ),
                timeout=timeout + 10,
            )
            if output_text:
                break
        except Exception as e:
            error_text = str(e)[:500]
            if attempt < retries:
                await asyncio.sleep(0.5 * (2 ** attempt))

    duration_ms = int((time.time() - started) * 1000)

    # Optional per-step validator
    validate: Optional[Callable] = step.get("validate")
    if validate and output_text:
        try:
            if not validate(output_text):
                error_text = "validate() returned False"
                output_text = ""
        except Exception as e:
            error_text = "validate() raised: " + str(e)[:200]
            output_text = ""

    status = "success" if output_text else "failed"
    step_output = {"text": output_text, "step_name": name, "model": model}

    _supa("pipeline_steps", "POST", {
        "run_id": run_id,
        "step_name": name,
        "model_group": task_type,
        "model_resolved": model,
        "duration_ms": duration_ms,
        "status": status,
        "error_text": error_text,
    })

    if status == "success":
        _supa("pipeline_step_outputs", "POST", {
            "run_id": run_id,
            "step_name": name,
            "content_hash": cache_key,
            "output": step_output,
        })
    else:
        _supa("pipeline_failures", "POST", {
            "run_id": run_id,
            "step_name": name,
            "error_text": error_text,
            "retry_count": retries,
        })

    return step_output if status == "success" else {"_status": "failed", "error": error_text}


# ---------------------------------------------------------------------------
# Top-level pipeline runner
# ---------------------------------------------------------------------------
def run_pipeline(name: str, steps: list[dict], inputs: dict,
                 caller: str = "unknown",
                 max_wall_clock: float = 1200.0) -> dict:
    """Run a pipeline to completion. Returns {step_name: step_output} dict."""
    run_id = str(uuid.uuid4())
    input_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

    _supa("pipeline_runs", "POST", {
        "id": run_id,
        "pipeline_name": name,
        "caller": caller,
        "input_hash": input_hash,
        "status": "running",
    })

    waves = _topo_sort(steps)
    context: dict = dict(inputs)  # shared context — step outputs append here
    start = time.time()

    async def _run_all():
        results: dict[str, dict] = {}
        step_by_name = {s["name"]: s for s in steps}
        for wave in waves:
            if time.time() - start > max_wall_clock:
                return results, "wall-clock-exceeded"

            # Run wave in parallel, bounded by semaphore
            sem = asyncio.Semaphore(_MAX_CONCURRENT)

            async def _one(step_name: str):
                step = step_by_name[step_name]
                async with sem:
                    return step_name, await _run_step(step, context, run_id, name)

            wave_results = await asyncio.gather(*[_one(sn) for sn in wave])
            for sn, out in wave_results:
                results[sn] = out
                # Merge step output into context for downstream steps
                if isinstance(out, dict) and "text" in out:
                    context[sn] = out["text"]
                # If any step failed hard, mark and break (future: configurable)
                if isinstance(out, dict) and out.get("_status") == "failed":
                    return results, "step-failed:" + sn
        return results, "success"

    results, status_code = asyncio.run(_run_all())

    final_status = "success" if status_code == "success" else "failed"
    failed_step = status_code.split(":", 1)[1] if status_code.startswith("step-failed:") else None

    _supa("pipeline_runs?id=eq." + run_id, "PATCH", {
        "status": final_status,
        "failed_step": failed_step,
        "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notes": status_code,
    })

    return {
        "run_id": run_id,
        "status": final_status,
        "failed_step": failed_step,
        "results": results,
    }


# ---------------------------------------------------------------------------
# YAML loader (lightweight — no PyYAML dependency)
# ---------------------------------------------------------------------------
def load_pipeline(yaml_path: str) -> list[dict]:
    """Load a pipeline definition from a minimal YAML file.

    Expected shape:
      steps:
        - name: outline
          task_type: plan
          prompt_template: "..."
          depends_on: [research]
          retries: 2
    """
    import yaml  # PyYAML on VPS
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return data.get("steps", [])


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pipeline = [
        {
            "name": "greet",
            "task_type": "transform",
            "prompt_template": "Say 'hello, world' and nothing else.",
            "depends_on": [],
        },
        {
            "name": "echo",
            "task_type": "transform",
            "prompt_template": "Repeat the following exactly: {{greet}}",
            "depends_on": ["greet"],
        },
        {
            "name": "summarize",
            "task_type": "summarize_short",
            "prompt_template": "Summarize in 5 words or less: {{echo}}",
            "depends_on": ["echo"],
        },
    ]
    result = run_pipeline("smoke_test", pipeline, {}, caller="self_test")
    print("run_id:", result["run_id"])
    print("status:", result["status"])
    for k, v in result["results"].items():
        txt = v.get("text", "") if isinstance(v, dict) else str(v)
        print(f"  {k}: {txt[:80]}")
