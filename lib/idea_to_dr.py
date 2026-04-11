"""
titan-harness/lib/idea_to_dr.py - Section 2 of IDEA_TO_EXECUTION_PIPELINE

Converts a raw idea into an A-graded Design Review plan via Perplexity (sonar-pro).
Saves the plan as plans/PLAN_<YYYY-MM-DD>_<slug>.md.

Public API:
    run_dr(idea: dict, project_id: str = "EOM") -> dict
        idea = {
            "id": str,            # idempotency source (ideas.id or session_next_task.id)
            "title": str,
            "text": str,
            "source": str,        # "ideas" | "session_next_task" | "lock_it" | "manual"
        }
        returns {"plan_path": str, "slug": str, "grade": "A"|..., "run_row": dict}
"""
from __future__ import annotations

import os
import sys
import re
import json
import hashlib
import datetime
import uuid
import time
from urllib import request, error
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from capacity import check_capacity
    import context_builder
except Exception:
    def check_capacity(timeout: float = 5.0) -> int:
        return 0
    context_builder = None  # type: ignore

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
PLANS_DIR = os.environ.get("TITAN_PLANS_DIR", "/opt/titan-harness/plans")


def _slugify(text: str, max_len: int = 50) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:max_len] or "idea"


def _idempotency_key(source: str, source_id: str, slug: str) -> str:
    h = hashlib.sha256()
    h.update(f"{source}:{source_id}:{slug}".encode())
    return h.hexdigest()[:32]


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
            headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        req = request.Request(SUPABASE_URL + "/rest/v1/" + path,
                              data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=15) as r:
            if r.status == 204:
                return None
            return json.loads(r.read())
    except error.HTTPError as e:
        # 409 = idempotent conflict (expected on re-runs); stay silent
        if e.code in (409,):
            return None
        print(f"[idea_to_dr] supa http {e.code} on {path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[idea_to_dr] supa error: {e}", file=sys.stderr)
        return None


def _llm_call(messages: list[dict], model: str = "sonar-pro",
              max_tokens: int = 4000, timeout: int = 240) -> tuple[int, dict]:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode()
    req = request.Request(
        LITELLM_BASE_URL + "/v1/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + LITELLM_MASTER_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


DR_SYSTEM_PROMPT = (
    "You are a senior staff engineer evaluating a raw idea for inclusion in "
    "an automated AI-agent harness (capacity-gated, war-room A-grade floor, "
    "substrate-first sequencing). Produce a design review in markdown."
)


def _build_dr_user_message(idea: dict, context: str) -> str:
    return f"""Produce a design review for this idea. Target A-grade (9.4+/10) on your native scale.

# Idea
Title: {idea.get('title', '<none>')}
Source: {idea.get('source', '<unknown>')}
Raw text:
{idea.get('text', '')}

# Harness context (injected from context_builder)
{context}

# Required DR structure

## 1. Scope & goals
What this idea does, what it does NOT do.

## 2. Phases
Render EACH phase as a level-3 markdown header in the EXACT form:

    ### Phase <N>: <short-slug-name>

(e.g. `### Phase 1: hash-compute`). This format is REQUIRED — the orchestrator
parses these headers with a strict regex. Do NOT use numbered lists, do NOT put
phase_number inside a bold label, do NOT skip the colon.

Under each phase header, provide the following fields as a bullet list:
    - task_type: (plan | architecture | spec | synthesis | phase | transform | classify | research | review)
    - depends_on: [list of prior phase numbers or empty list]
    - inputs: (named)
    - outputs: (named)
    - acceptance_criteria: (bullet list)
3. **Risks & mitigations** — top 5 risks with proposed mitigations.
4. **Acceptance criteria** — how to prove the whole thing is done.
5. **Rollback path** — what happens if this idea fails in production.
6. **Honest scope cuts** — what is explicitly deferred as follow-on sub-phases.

If the idea is underspecified, list the top 3 clarifying questions and grade as B (not A).

Return the DR as markdown. Do not wrap in code fences."""


def run_dr(idea: dict, project_id: str = "EOM") -> dict:
    """Generate an A-graded DR plan for the given idea. Returns {plan_path, slug, grade, run_row}."""
    if check_capacity() == 2:
        return {"error": "capacity hard block", "plan_path": None}

    title = idea.get("title") or (idea.get("text") or "")[:80]
    slug = _slugify(title)
    source_id = str(idea.get("id", uuid.uuid4()))
    source = idea.get("source", "manual")
    idkey = _idempotency_key(source, source_id, slug)

    # Upsert the audit row
    run_row = _supa("idea_to_exec_runs", "POST", {
        "idempotency_key": idkey,
        "source": source,
        "idea_id": source_id if source == "ideas" else None,
        "project_id": project_id,
        "title": title,
        "slug": slug,
        "status": "dr_running",
    })
    run_id = (run_row[0]["id"] if isinstance(run_row, list) and run_row else None)

    # Build context
    context_text = ""
    if context_builder:
        try:
            context_text, _ = context_builder.build_context(
                {"id": source_id, "task_type": "plan", "project": project_id,
                 "prompt": title + "\n\n" + (idea.get("text") or "")[:500]},
                caller="idea_to_dr",
                max_tokens=4000,
            )
        except Exception:
            context_text = ""

    # Call Perplexity sonar-pro through the gateway
    messages = [
        {"role": "system", "content": DR_SYSTEM_PROMPT},
        {"role": "user", "content": _build_dr_user_message(idea, context_text)},
    ]
    status, resp = _llm_call(messages, model="sonar-pro", max_tokens=4000)

    if status != 200:
        _supa(f"idea_to_exec_runs?id=eq.{run_id}", "PATCH", {
            "status": "failed",
            "notes": f"DR call http {status}: {str(resp)[:300]}",
        })
        return {"error": f"http {status}", "plan_path": None, "run_id": run_id}

    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = resp.get("usage", {}) or {}

    # Write the plan file
    os.makedirs(PLANS_DIR, exist_ok=True)
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    plan_path = os.path.join(PLANS_DIR, f"PLAN_{today}_{slug}.md")

    header = (
        f"# DR Plan: {title}\n\n"
        f"**Source:** {source}\n"
        f"**Source ID:** {source_id}\n"
        f"**Project:** {project_id}\n"
        f"**Generated:** {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
        f"**Model:** sonar-pro (via LiteLLM gateway)\n"
        f"**Tokens in/out:** {usage.get('prompt_tokens', '?')} / {usage.get('completion_tokens', '?')}\n"
        f"**Run id:** {run_id}\n\n"
        "---\n\n"
    )
    open(plan_path, "w").write(header + content)

    # Best-effort grade from the DR content itself (the model was asked to self-grade)
    grade = "A"
    if re.search(r"\bgrade\s*[:=]\s*B\b", content, re.IGNORECASE):
        grade = "B"

    # Update the audit row
    _supa(f"idea_to_exec_runs?id=eq.{run_id}", "PATCH", {
        "status": "dr_complete" if grade == "A" else "needs_solon_override",
        "plan_path": plan_path,
        "notes": f"DR generated at {plan_path}, grade={grade}",
    })

    # Insert / update the dr_plan task row for the rest of the pipeline
    task_body = {
        "idempotency_key": idkey,
        "task_type": "dr_plan",
        "status": "completed" if grade == "A" else "revision_needed",
        "summary": f"DR plan for: {title}",
        "handler_type": "titan_auto",
        "urgency": "normal",
        "routing": "idea_to_execution",
        "deliverable": plan_path,
        "deliverable_content": content[:60000],
        "agent_id": "titan",
    }
    task_row = _supa("tasks?on_conflict=idempotency_key", "POST", task_body)
    task_id = None
    if isinstance(task_row, list) and task_row:
        task_id = task_row[0].get("id")

    if run_id and task_id:
        _supa(f"idea_to_exec_runs?id=eq.{run_id}", "PATCH", {"task_id": task_id})

    # Flip source ideas row to 'promoted' so the orchestrator stops re-picking it
    if source == "ideas" and source_id:
        _supa(f"ideas?id=eq.{source_id}", "PATCH", {
            "status": "promoted",
            "promoted_to_task_id": task_id,
        })

    return {
        "plan_path": plan_path,
        "slug": slug,
        "grade": grade,
        "run_id": run_id,
        "task_id": task_id,
        "content": content,
        "status": "dr_complete" if grade == "A" else "needs_solon_override",
    }


if __name__ == "__main__":
    # Self-test with a tiny synthetic idea
    result = run_dr({
        "id": "smoke-test-" + str(int(time.time())),
        "title": "Smoke test for idea_to_dr",
        "text": ("Build a 2-phase pipeline that (a) computes the SHA256 of a "
                 "string and (b) writes the hash to a file. Trivial test case."),
        "source": "manual",
    }, project_id="EOM")
    print("result:", json.dumps({k: v for k, v in result.items() if k != "content"}, indent=2))
    if result.get("content"):
        print("--- first 400 chars of DR ---")
        print(result["content"][:400])
