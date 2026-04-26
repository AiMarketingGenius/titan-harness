"""
mcp_rest_client.py — thin client for the MCP server's REST endpoints.

All Hercules/Mercury bridges import from this module to avoid duplication
and to keep route name + payload shape changes in one place.

The MCP server at memory.aimarketinggenius.io exposes:
- POST /api/queue-task        (was: queue_operator_task)
- GET  /api/task-queue        (was: get_task_queue)
- POST /api/claim-task        (was: claim_task)
- POST /api/update-task       (existing)
- POST /api/decisions         (was: log_decision)
- GET  /api/recent-decisions  (was: get_recent_decisions)

The original tool names (queue_operator_task etc.) live behind /mcp JSON-RPC
with OAuth — those are for Claude Code / Cursor MCP clients. The /api routes
above are open and intended for Mac-side daemons + n8n + scripts.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

MCP_BASE = os.environ.get("MCP_BASE", "https://memory.aimarketinggenius.io")
DEFAULT_TIMEOUT = 20


def _post(path: str, body: dict, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, dict]:
    url = f"{MCP_BASE.rstrip('/')}/{path.lstrip('/')}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {"error": str(e)}
        return e.code, body
    except Exception as e:
        return -1, {"error": repr(e)}


def _get(path: str, params: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, dict]:
    url = f"{MCP_BASE.rstrip('/')}/{path.lstrip('/')}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {"error": str(e)}
        return e.code, body
    except Exception as e:
        return -1, {"error": repr(e)}


def queue_task(payload: dict) -> tuple[int, dict]:
    """POST /api/queue-task. Required: objective, instructions, acceptance_criteria."""
    return _post("/api/queue-task", payload)


def get_task_queue(
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    project_id: str | None = None,
    campaign_id: str | None = None,
    task_id: str | None = None,
    limit: int = 10,
    include_completed: bool = False,
) -> tuple[int, dict]:
    return _get("/api/task-queue", {
        "status": status, "priority": priority, "assigned_to": assigned_to,
        "project_id": project_id, "campaign_id": campaign_id, "task_id": task_id,
        "limit": limit,
        "include_completed": "true" if include_completed else None,
    })


def claim_task(operator_id: str, task_id: str | None = None) -> tuple[int, dict]:
    body = {"operator_id": operator_id}
    if task_id:
        body["task_id"] = task_id
    return _post("/api/claim-task", body)


def update_task(
    task_id: str,
    status: str | None = None,
    result_summary: str | None = None,
    failure_reason: str | None = None,
    notes: str | None = None,
    deliverable_link: str | None = None,
) -> tuple[int, dict]:
    body = {"task_id": task_id}
    if status:
        body["status"] = status
    if result_summary:
        body["result_summary"] = result_summary[:1500]
    if failure_reason:
        body["failure_reason"] = failure_reason[:500]
    if notes:
        body["notes"] = notes
    if deliverable_link:
        body["deliverable_link"] = deliverable_link
    return _post("/api/update-task", body)


def log_decision(
    text: str,
    rationale: str = "",
    tags: list[str] | None = None,
    project_source: str = "titan",
) -> tuple[int, dict]:
    return _post("/api/decisions", {
        "text": text[:1000],
        "rationale": rationale[:8000] if rationale else "",
        "tags": (tags or [])[:10],
        "project_source": project_source,
    })


def get_recent_decisions(count: int = 10, project_filter: str | None = None) -> tuple[int, dict]:
    """Returns structured JSON via /api/recent-decisions-json (added 2026-04-26
    for Mercury notifier). The older /api/recent-decisions returns markdown,
    which is harder to parse — avoid it for programmatic clients."""
    return _get("/api/recent-decisions-json", {"count": count, "project_filter": project_filter})


def health() -> tuple[int, dict]:
    return _get("/health")


def get_sprint_state(project_id: str = "EOM") -> tuple[int, dict]:
    """Wrapper for MCP sprint-state read. Used by hercules_daemon.py to
    hydrate context every poll cycle. Endpoint accepts either a JSON body
    or query string; we use query string for GET semantics."""
    return _get("/api/sprint-state", {"project_id": project_id})
