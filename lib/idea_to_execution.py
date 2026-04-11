"""
titan-harness/lib/idea_to_execution.py - Sections 3-5 of IDEA_TO_EXECUTION_PIPELINE

End-to-end orchestrator. Watches ideas / session_next_task / dr_plan tasks and
drives each through: DR → prompt/spec war room → phased execution → per-phase
QA → auto-advance or solon-override flag.

Public API:
    run_once(dry_run: bool = False) -> dict
        single poll + process cycle (cron-friendly)

    run_daemon(interval_s: int = 120, dry_run: bool = False)
        long-running poll loop (systemd-friendly)

CORE CONTRACT: harness-preflight + check-capacity + POLICY_CAPACITY_* limits.
"""
from __future__ import annotations

import os
import sys
import re
import json
import time
import hashlib
import datetime
import subprocess
import uuid
from urllib import request, error
from typing import Optional, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from capacity import check_capacity
    import idea_to_dr
    import context_builder
    import model_router
    import llm_client
except Exception as e:
    print(f"[idea_to_execution] import warning: {e}", file=sys.stderr)
    idea_to_dr = None  # type: ignore
    context_builder = None  # type: ignore
    model_router = None  # type: ignore
    llm_client = None  # type: ignore
    def check_capacity(timeout: float = 5.0) -> int:
        return 0


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PLANS_DIR = os.environ.get("TITAN_PLANS_DIR", "/opt/titan-harness/plans")
PROMPTS_DIR = os.path.join(PLANS_DIR, "prompts")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "") or os.environ.get("SLACK_WEBHOOK_CHANNEL", "")
HARNESS_PREFLIGHT = "/opt/titan-harness/bin/harness-preflight.sh"
CHECK_CAPACITY = "/opt/titan-harness/bin/check-capacity.sh"

# Disabled projects (opt-out) — override via env
_DISABLED_PROJECTS = set((os.environ.get("IDEA_TO_EXEC_DISABLED_PROJECTS") or "").split(","))
_DISABLED_PROJECTS.discard("")


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
            headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        req = request.Request(SUPABASE_URL + "/rest/v1/" + path,
                              data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=15) as r:
            if r.status == 204:
                return None
            return json.loads(r.read())
    except Exception as e:
        print(f"[idea_to_execution] supa error on {path}: {e}", file=sys.stderr)
        return None


def _preflight_ok() -> bool:
    """Run harness-preflight. Returns True on success, False otherwise."""
    try:
        r = subprocess.run([HARNESS_PREFLIGHT], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _slack(text: str) -> None:
    if not SLACK_WEBHOOK:
        return
    try:
        body = json.dumps({"text": text}).encode()
        req = request.Request(SLACK_WEBHOOK, data=body,
                              headers={"Content-Type": "application/json"},
                              method="POST")
        request.urlopen(req, timeout=5).read()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Section 1 — Idea intake (pull candidate work)
# ---------------------------------------------------------------------------
def _pending_ideas() -> list[dict]:
    """Return ideas that need a DR plan."""
    rows = _supa("ideas?status=in.(approved,promoted)&promoted_to_task_id=is.null"
                 "&select=*&order=created_at.asc&limit=5") or []
    out = []
    for r in rows:
        out.append({
            "id": r.get("id"),
            "title": r.get("idea_title") or (r.get("idea_text") or "")[:80],
            "text": r.get("idea_text") or "",
            "source": "ideas",
            "project_id": r.get("project_id") or "EOM",
        })
    return out


def _pending_session_tasks() -> list[dict]:
    """session_next_task rows whose body has a task_type in the allowed set."""
    rows = _supa("session_next_task?select=*&order=ts.asc&limit=5") or []
    allowed = {"plan", "blueprint", "performance", "infra", "mp1", "mp2", "atlas"}
    out = []
    for r in rows:
        body = r.get("body") or {}
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                body = {}
        task_type = (body.get("task_type") or "").lower()
        if task_type not in allowed:
            continue
        # Skip if already linked to a task
        if body.get("linked_task_id"):
            continue
        out.append({
            "id": r.get("id"),
            "title": r.get("summary") or body.get("title") or task_type,
            "text": r.get("body") if isinstance(r.get("body"), str) else json.dumps(body),
            "source": "session_next_task",
            "project_id": body.get("project_id", "EOM"),
            "task_type_hint": task_type,
        })
    return out


def _pending_dr_plans_for_grading() -> list[dict]:
    """DR plans that completed but haven't been phase-split yet."""
    rows = _supa("idea_to_exec_runs?status=eq.dr_complete&select=*&limit=5") or []
    return rows


def _running_phase_batches() -> list[dict]:
    """Idea runs mid-execution that need their next phase processed."""
    rows = _supa("idea_to_exec_runs?status=eq.executing&select=*&limit=5") or []
    return rows


# ---------------------------------------------------------------------------
# Section 3 — Prompt / Spec extraction from DR plan
# ---------------------------------------------------------------------------
def _extract_phases(dr_markdown: str) -> list[dict]:
    """Extract numbered phases from DR markdown using a tightened multi-pattern
    parser. Prefers explicit `### Phase N: <name>` headers (primary target after
    the DR prompt was updated to mandate that format). Falls back to
    `phase_number:/phase_name:` field pairs or labeled numbered lists.

    Guards against false positives:
      - phase_name must be 3-80 chars, not end in bare colon, not be a common
        scope-section header, and not equal to a generic meta-field label.
      - phases are deduped by number and sorted.
    """
    phases: list[dict] = []

    # Pattern 1 (PRIMARY): "### Phase N: name" or "## Phase N - name"
    # Accepts 2-4 hash markers and several dash variants.
    pat1 = re.compile(
        r"^#{2,4}\s+Phase\s+(\d+)\s*[:\-\u2013\u2014]\s+(.+?)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    for m in pat1.finditer(dr_markdown):
        phases.append({
            "phase_number": int(m.group(1)),
            "phase_name": m.group(2).strip().strip(":").strip()[:80],
            "task_type": "phase",
        })

    # Pattern 2 (SECONDARY): "**phase_number**: N" paired with "**phase_name**: name"
    # Perplexity often returns structured field lists like this.
    if not phases:
        pat2_block = re.compile(
            r"\*\*phase_number\*\*\s*:\s*(\d+).*?"
            r"\*\*phase_name\*\*\s*:\s*([^\n\r*]+)",
            re.DOTALL | re.IGNORECASE,
        )
        for m in pat2_block.finditer(dr_markdown):
            phases.append({
                "phase_number": int(m.group(1)),
                "phase_name": m.group(2).strip().strip(":").strip()[:80],
                "task_type": "phase",
            })

    # Pattern 3 (TERTIARY): explicit "Phase N" inside a bold label
    # e.g. "1. **Phase 1: Build substrate**" — common when model inlines title
    if not phases:
        pat3 = re.compile(
            r"\*\*\s*Phase\s+(\d+)\s*[:\-\u2013\u2014]\s+([^*]+?)\*\*",
            re.IGNORECASE,
        )
        for m in pat3.finditer(dr_markdown):
            phases.append({
                "phase_number": int(m.group(1)),
                "phase_name": m.group(2).strip().strip(":").strip()[:80],
                "task_type": "phase",
            })

    # Guard: drop items whose name is empty, looks like a meta-field label,
    # or is just a fragment ending in a colon with < 3 meaningful chars.
    _bad_names = {
        "", "phase_number", "phase_name", "task_type", "depends_on",
        "inputs", "outputs", "acceptance_criteria", "root cause",
        "resume", "rollback path", "scope", "goals", "risks",
    }
    cleaned: list[dict] = []
    for p in phases:
        nm = (p.get("phase_name") or "").strip()
        if not nm or nm.lower() in _bad_names:
            continue
        if len(nm) < 3:
            continue
        p["phase_name"] = nm
        cleaned.append(p)
    phases = cleaned

    # Infer task_type from name keywords
    for p in phases:
        name = p["phase_name"].lower()
        if "plan" in name or "design" in name:
            p["task_type"] = "plan"
        elif "architect" in name:
            p["task_type"] = "architecture"
        elif "spec" in name:
            p["task_type"] = "spec"
        elif "synthesis" in name or "synth" in name or "compute" in name or "hash" in name:
            p["task_type"] = "synthesis"
        elif "research" in name or "discover" in name:
            p["task_type"] = "research"
        elif "review" in name or "audit" in name or "verify" in name:
            p["task_type"] = "review"
        elif "write" in name or "persist" in name or "save" in name:
            p["task_type"] = "transform"

    # Dedup by number and sort
    seen = {}
    for p in phases:
        seen[p["phase_number"]] = p
    return [seen[k] for k in sorted(seen.keys())]


def _write_phase_artifacts(run_row: dict, phases: list[dict]) -> list[dict]:
    """Write PROMPT_ and SPEC_ files for each phase. Returns artifact rows."""
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    slug = run_row.get("slug", "idea")
    run_id = run_row.get("id")
    artifacts = []
    for p in phases:
        num = p["phase_number"]
        name = p["phase_name"]
        task_type = p["task_type"]
        prompt_path = os.path.join(PROMPTS_DIR, f"PROMPT_{slug}_p{num:02d}.md")
        spec_path = os.path.join(PROMPTS_DIR, f"SPEC_{slug}_p{num:02d}.md")

        # Write a minimal A-seed; the grading loop will iterate via war_room
        prompt_body = (
            f"# Phase {num} Prompt — {name}\n\n"
            f"**Idea slug:** {slug}\n"
            f"**Task type:** {task_type}\n"
            f"**Run id:** {run_id}\n\n"
            "## Objective\n"
            f"Execute phase {num} ({name}) of the idea. Follow the matching SPEC file "
            "for acceptance criteria.\n\n"
            "## Inputs\n- (from DR plan)\n\n"
            "## Outputs\n- (from DR plan)\n\n"
            "## Capacity CORE CONTRACT\n"
            "- Pass harness-preflight.sh + check-capacity.sh before any heavy work\n"
            "- Respect POLICY_CAPACITY_* ceilings\n"
        )
        spec_body = (
            f"# Phase {num} Spec — {name}\n\n"
            f"**Idea slug:** {slug}\n"
            f"**Task type:** {task_type}\n"
            f"**Run id:** {run_id}\n\n"
            "## Acceptance Criteria\n"
            "- (filled by war-room on first iteration)\n\n"
            "## Rollback path\n"
            "- (filled by war-room)\n"
        )
        open(prompt_path, "w").write(prompt_body)
        open(spec_path, "w").write(spec_body)

        art = _supa("idea_to_exec_phase_artifacts", "POST", {
            "run_id": run_id,
            "phase_number": num,
            "phase_name": name,
            "prompt_path": prompt_path,
            "spec_path": spec_path,
            "grade": None,
        })
        if isinstance(art, list) and art:
            artifacts.append(art[0])
    return artifacts


# ---------------------------------------------------------------------------
# Section 3 — Grade prompt/spec via war_room
# ---------------------------------------------------------------------------
def _grade_via_warroom(text: str, phase: str, project_id: str) -> tuple[str, str]:
    """Grade Titan output via the WarRoom class (imported directly, no subprocess).
    Returns (grade, summary). Uses existing war_room policy + A-grade floor.
    """
    try:
        import war_room as _wr
        room = _wr.WarRoom()
        if not room.policy.get("enabled", False):
            return "ERROR", "war_room.enabled=false"
        session = room.grade(
            titan_output=text,
            phase=phase,
            trigger_source="plan_finalization",
            project_id=project_id,
        )
        rounds = getattr(session, "rounds", []) or []
        if rounds:
            final_grade = rounds[-1].grade_result.grade
        else:
            final_grade = "ERROR"
        return str(final_grade).upper()[:1] if final_grade else "ERROR", str(session)[-2000:]
    except Exception as e:
        import traceback
        return "ERROR", f"{e}\n{traceback.format_exc()[-800:]}"


# ---------------------------------------------------------------------------
# Section 4 — Execute one phase (calls gateway, grades result)
# ---------------------------------------------------------------------------
def _execute_phase(run_row: dict, artifact: dict) -> dict:
    """Execute a single phase end-to-end. Returns {status, grade, mp_runs_id}."""
    run_id = run_row.get("id")
    phase_num = artifact.get("phase_number")
    phase_name = artifact.get("phase_name")
    project_id = run_row.get("project_id", "EOM")
    slug = run_row.get("slug", "idea")

    # Capacity preflight
    if not _preflight_ok():
        return {"status": "deferred", "grade": None, "error": "harness-preflight failed"}
    if check_capacity() == 2:
        return {"status": "deferred", "grade": None, "error": "capacity hard block"}

    # Create the mp_runs row
    mp_row = _supa("mp_runs", "POST", {
        "project_id": project_id,
        "megaprompt": "idea_to_exec",
        "phase_number": phase_num,
        "phase_name": phase_name[:80],
        "status": "running",
        "script_path": artifact.get("prompt_path"),
        "notes": f"idea_to_exec run_id={run_id} slug={slug}",
    })
    mp_runs_id = None
    if isinstance(mp_row, list) and mp_row:
        mp_runs_id = mp_row[0].get("id")

    # Read the prompt file
    prompt_path = artifact.get("prompt_path")
    prompt_text = ""
    if prompt_path and os.path.exists(prompt_path):
        prompt_text = open(prompt_path).read()

    # Resolve model via router
    model = "claude-sonnet-4-6"
    if model_router:
        try:
            model = model_router.resolve_model("phase", {"task_type": "phase"})
        except Exception:
            pass

    # Execute: single-LLM call (caller can migrate to pipeline later)
    if not llm_client:
        return {"status": "failed", "grade": None, "error": "llm_client unavailable"}

    try:
        output = llm_client.complete(
            f"You are executing phase {phase_num} ({phase_name}) of an automated harness pipeline.\n\n"
            f"Follow this prompt and produce a concise deliverable:\n\n{prompt_text}",
            model_group=model,
            max_tokens=2000,
        )
    except Exception as e:
        _supa(f"mp_runs?id=eq.{mp_runs_id}", "PATCH", {
            "status": "failed",
            "notes": f"phase exec error: {str(e)[:500]}",
        })
        return {"status": "failed", "grade": None, "error": str(e)}

    # QA grade via war_room (subprocess to use existing A-grade floor)
    grade, raw = _grade_via_warroom(output, f"idea_to_exec_p{phase_num}", project_id)

    new_status = "complete" if grade == "A" else "blocked"
    _supa(f"mp_runs?id=eq.{mp_runs_id}", "PATCH", {
        "status": new_status,
        "war_room_triggered": True,
        "war_room_grade": grade,
        "notes": f"phase exec complete, grade={grade}",
    })
    _supa(f"idea_to_exec_phase_artifacts?id=eq.{artifact.get('id')}", "PATCH", {
        "grade": grade,
        "mp_runs_id": mp_runs_id,
    })

    if grade == "A":
        _slack(f":white_check_mark: *idea_to_exec* phase {phase_num} ({phase_name}) A-graded for `{slug}`")
    else:
        _slack(f":warning: *idea_to_exec* phase {phase_num} ({phase_name}) flagged *needs_solon_override* for `{slug}` (grade={grade})")

    return {"status": new_status, "grade": grade, "mp_runs_id": mp_runs_id, "output": output[:500]}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def run_once(dry_run: bool = False) -> dict:
    """Single poll + process cycle. Safe to run from cron every 2 min."""
    stats = {"preflight": False, "capacity": "ok", "processed": 0, "deferred": 0, "errors": 0, "events": []}

    # Preflight
    if not _preflight_ok():
        stats["events"].append("harness-preflight failed — abort")
        return stats
    stats["preflight"] = True

    cap = check_capacity()
    if cap == 2:
        stats["capacity"] = "hard_block"
        stats["events"].append("capacity hard block — skip tick")
        return stats
    if cap == 1:
        stats["capacity"] = "soft_block"

    # Section 1: New ideas → DR
    for idea in _pending_ideas() + _pending_session_tasks():
        if idea.get("project_id") in _DISABLED_PROJECTS:
            stats["events"].append(f"skip {idea.get('id')} — project disabled")
            continue
        if dry_run:
            stats["events"].append(f"[dry] would run DR for {idea.get('source')}:{idea.get('id')}")
            stats["processed"] += 1
            continue
        if idea_to_dr is None:
            stats["errors"] += 1
            stats["events"].append("idea_to_dr module unavailable")
            continue
        result = idea_to_dr.run_dr(idea, project_id=idea.get("project_id", "EOM"))
        if result.get("plan_path"):
            _slack(f":page_facing_up: *idea_to_exec* DR complete: `{os.path.basename(result['plan_path'])}` grade={result.get('grade')}")
            stats["processed"] += 1
            stats["events"].append(f"DR complete: {result['plan_path']}")
        else:
            stats["errors"] += 1
            stats["events"].append(f"DR failed for {idea.get('id')}: {result.get('error')}")

    # Section 3: Completed DRs → prompt/spec war room → mark executing
    for run_row in _pending_dr_plans_for_grading():
        plan_path = run_row.get("plan_path")
        if not plan_path or not os.path.exists(plan_path):
            continue
        if dry_run:
            stats["events"].append(f"[dry] would phase-split {plan_path}")
            stats["processed"] += 1
            continue
        try:
            dr_md = open(plan_path).read()
        except Exception:
            continue
        phases = _extract_phases(dr_md)
        if not phases:
            _supa(f"idea_to_exec_runs?id=eq.{run_row['id']}", "PATCH", {
                "status": "needs_solon_override",
                "notes": "no phases extracted from DR markdown",
            })
            stats["errors"] += 1
            continue
        artifacts = _write_phase_artifacts(run_row, phases)
        _supa(f"idea_to_exec_runs?id=eq.{run_row['id']}", "PATCH", {
            "status": "executing",
            "phase_count": len(phases),
        })
        stats["processed"] += 1
        stats["events"].append(f"split {len(phases)} phases for run {run_row['id']}")

    # Section 4: Executing runs → process next pending phase
    for run_row in _running_phase_batches():
        if dry_run:
            stats["events"].append(f"[dry] would exec next phase for {run_row['id']}")
            stats["processed"] += 1
            continue
        # Find the next phase without a grade
        arts = _supa(
            f"idea_to_exec_phase_artifacts?run_id=eq.{run_row['id']}&grade=is.null&order=phase_number.asc&limit=1"
        ) or []
        if not arts:
            # All phases done — mark run complete
            _supa(f"idea_to_exec_runs?id=eq.{run_row['id']}", "PATCH", {
                "status": "complete",
                "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            _slack(f":tada: *idea_to_exec* run complete for `{run_row.get('slug')}`")
            stats["processed"] += 1
            continue
        result = _execute_phase(run_row, arts[0])
        if result.get("grade") == "A":
            stats["processed"] += 1
        elif result.get("status") == "deferred":
            stats["deferred"] += 1
        else:
            stats["errors"] += 1
            # Stop auto-advance on this run until Solon override
            _supa(f"idea_to_exec_runs?id=eq.{run_row['id']}", "PATCH", {
                "status": "needs_solon_override",
                "notes": f"phase {arts[0].get('phase_number')} blocked: {result.get('error','below A')}",
            })
        stats["events"].append(f"phase {arts[0].get('phase_number')} of {run_row['id']}: grade={result.get('grade')}")

    return stats


def run_daemon(interval_s: int = 120, dry_run: bool = False) -> None:
    print(f"[idea_to_execution] daemon starting: interval={interval_s}s dry_run={dry_run}")
    while True:
        try:
            stats = run_once(dry_run=dry_run)
            if stats.get("processed") or stats.get("errors"):
                print(f"[idea_to_execution] {datetime.datetime.now().isoformat()}: {json.dumps(stats)}", flush=True)
        except Exception as e:
            print(f"[idea_to_execution] tick error: {e}", flush=True)
        time.sleep(interval_s)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="single poll cycle")
    p.add_argument("--daemon", action="store_true", help="long-running loop")
    p.add_argument("--interval", type=int, default=120)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.daemon:
        run_daemon(interval_s=args.interval, dry_run=args.dry_run)
    else:
        stats = run_once(dry_run=args.dry_run)
        print(json.dumps(stats, indent=2, default=str))
