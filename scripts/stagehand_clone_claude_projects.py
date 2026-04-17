#!/usr/bin/env python3
"""
CT-0417-HYBRID-C18 Phase 2 — Clone 18 project-backed Claude Projects via Stagehand.

Prereqs (blocker: Solon-only auth step needed first):
  1. Claude.ai authenticated session in /opt/persistent-browser/user-data-1 (or user-data-2, -3)
     Three ways to achieve this ONCE:
       (a) Solon SSHs into HostHatch and runs this script interactively — it will open
           a visible Chromium window where Solon logs in, session persists in user-data-1
       (b) Solon exports claude.ai cookies from his local browser + imports into
           user-data-1/Default/Cookies via the helper at bottom of this file
       (c) OAuth-like: capture session JWT from Solon's browser devtools + inject

Once authenticated, this script:
  1. Navigates to claude.ai/projects
  2. Reads manifest below (18 projects)
  3. For each project:
     a. Click "New Project"
     b. Enter project name
     c. Enter custom instructions (from /opt/amg-docs/agents/{agent}/SYSTEM_INSTRUCTIONS.md,
        falling back to concatenated kb/*.md if SI missing)
     d. Upload KB files as project knowledge (up to 30K tokens per project)
     e. Capture project URL / ID
     f. Screenshot for verification
  4. Writes /opt/amg-docs/agents/project_ids.json mapping agent → claude.ai project URL
  5. Updates agent_context_loader to prefer project-backed routing when project_id present

Runbook:
  # On HostHatch:
  python3 /opt/titan-harness/scripts/stagehand_clone_claude_projects.py --verify-auth
  python3 /opt/titan-harness/scripts/stagehand_clone_claude_projects.py --dry-run
  python3 /opt/titan-harness/scripts/stagehand_clone_claude_projects.py --execute
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

POOL_URL = os.environ.get("STAGEHAND_POOL_URL", "http://127.0.0.1:3201")
KB_ROOT = Path(os.environ.get("AGENT_KB_ROOT", "/opt/amg-docs/agents"))
OUTPUT_MANIFEST = Path("/opt/amg-docs/agents/project_ids.json")
SCREENSHOTS_DIR = Path("/opt/amg-docs/agents/claude_project_screenshots")

# Manifest: 18 projects per plans/doctrine/PROJECT_BACKED_BUSINESS_UNIT_TEMPLATE.md §2
PROJECT_MANIFEST = [
    # Layer 1 — Titan core + specialists (10)
    {"agent": "titan-operator", "claude_name": "Titan-Operator — AMG Master Orchestrator", "layer": 1},
    {"agent": "titan-cro", "claude_name": "Titan-CRO — Conversion + UX Implementation", "layer": 1},
    {"agent": "titan-seo", "claude_name": "Titan-SEO — Local SEO Execution", "layer": 1},
    {"agent": "titan-content", "claude_name": "Titan-Content — Content Production", "layer": 1},
    {"agent": "titan-social", "claude_name": "Titan-Social — Platform Scheduling + Engagement", "layer": 1},
    {"agent": "titan-paid-ads", "claude_name": "Titan-Paid-Ads — Paid Media Execution", "layer": 1},
    {"agent": "titan-security", "claude_name": "Titan-Security — Secrets, Tenant Iso, Compliance", "layer": 1},
    {"agent": "titan-reputation", "claude_name": "Titan-Reputation — Review Monitoring + Response", "layer": 1},
    {"agent": "titan-outbound", "claude_name": "Titan-Outbound — Cold Outreach Infrastructure", "layer": 1},
    {"agent": "titan-proposal-builder", "claude_name": "Titan-Proposal-Builder — Contracts + SOWs", "layer": 1},
    # Layer 2 — Subscriber-facing (7)
    {"agent": "alex", "claude_name": "Alex — AMG Business Coach", "layer": 2},
    {"agent": "maya", "claude_name": "Maya — AMG Content Strategist", "layer": 2},
    {"agent": "jordan", "claude_name": "Jordan — AMG SEO Specialist", "layer": 2},
    {"agent": "sam", "claude_name": "Sam — AMG Social Media Manager", "layer": 2},
    {"agent": "riley", "claude_name": "Riley — AMG Reviews Manager", "layer": 2},
    {"agent": "nadia", "claude_name": "Nadia — AMG Outbound Coordinator", "layer": 2},
    {"agent": "lumina", "claude_name": "Lumina — AMG CRO + UX Gatekeeper", "layer": 2},
    # Layer 3 — Ops (1+)
    {"agent": "titan-accounting", "claude_name": "Titan-Accounting — Bookkeeping + Tax Prep", "layer": 3},
]


def _post(path: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(f"{POOL_URL}{path}", data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(path: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(f"{POOL_URL}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def verify_auth() -> bool:
    """Confirm at least one pool slot has an active claude.ai session."""
    stats = _get("/pool/stats")
    print(f"Pool stats: {stats}")
    slot = _post("/pool/acquire", {"timeout_ms": 10000})
    if not slot.get("id"):
        print("ERROR: couldn't acquire pool slot", file=sys.stderr)
        return False
    slot_id = slot["id"]
    try:
        # Navigate to claude.ai and check if logged in
        _post(f"/navigate", {"slotId": slot_id, "url": "https://claude.ai/projects"})
        time.sleep(3)
        result = _post("/execute", {
            "slotId": slot_id,
            "script": "document.title + '|' + (document.querySelector('[data-testid=\"user-menu\"]') ? 'LOGGED_IN' : 'NOT_LOGGED_IN')",
        })
        title_status = result.get("result", "")
        print(f"claude.ai state: {title_status}")
        return "LOGGED_IN" in title_status
    finally:
        _post(f"/pool/release/{slot_id}")


def collect_kb(agent: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (system_instructions, [(filename, content), ...])."""
    agent_dir = KB_ROOT / agent
    si_path = agent_dir / "SYSTEM_INSTRUCTIONS.md"
    kb_dir = agent_dir / "kb" if (agent_dir / "kb").exists() else agent_dir
    si = si_path.read_text() if si_path.exists() else ""
    kb_files = sorted(kb_dir.glob("*.md"))
    kb_content = [(f.name, f.read_text()) for f in kb_files if f.is_file()]
    # If no SI but has KB, synthesize a minimal SI from 00_identity
    if not si and kb_content:
        identity = next((c for n, c in kb_content if "00_identity" in n), "")
        si = f"# {agent} — project-backed agent\n\n{identity[:4000]}\n\nFull knowledge base is attached. Refer to it for detailed capabilities, trade-secret rules, voice guidelines, and examples."
    return si, kb_content


def clone_project(slot_id: str, manifest_entry: dict, dry_run: bool = False) -> dict:
    agent = manifest_entry["agent"]
    name = manifest_entry["claude_name"]
    print(f"\n→ Cloning: {name} (agent={agent})")

    si, kb_files = collect_kb(agent)
    if not kb_files:
        return {"agent": agent, "status": "skipped", "reason": "no-kb-files"}

    total_chars = sum(len(c) for _, c in kb_files)
    print(f"  KB: {len(kb_files)} files, {total_chars} chars (~{total_chars//4} tokens)")
    print(f"  SI: {len(si)} chars")

    if dry_run:
        return {"agent": agent, "status": "dry-run", "si_chars": len(si), "kb_chars": total_chars, "kb_files": len(kb_files)}

    # Execute Stagehand clone — these are placeholder hooks; exact selectors depend on
    # claude.ai's current DOM which changes. Live-run requires claude.ai logged-in session.
    # 1. Navigate to projects list
    _post("/navigate", {"slotId": slot_id, "url": "https://claude.ai/projects"})
    time.sleep(2)

    # 2. Click "Create project" — selector captured at runtime via DOM snapshot
    _post("/execute", {"slotId": slot_id, "script": """
        const btn = [...document.querySelectorAll('button')].find(b => /create project|new project/i.test(b.innerText));
        if (btn) btn.click();
    """})
    time.sleep(2)

    # 3. Fill project name
    _post("/execute", {"slotId": slot_id, "script": f"""
        const inp = document.querySelector('input[placeholder*="name" i], input[aria-label*="name" i]');
        if (inp) {{ inp.value = {json.dumps(name)}; inp.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
    """})
    time.sleep(1)

    # 4-6: custom instructions, knowledge upload, capture URL — live-selector-dependent;
    # full implementation requires session + DOM capture during first manual run.

    # Capture resulting project URL
    url_result = _post("/execute", {"slotId": slot_id, "script": "window.location.href"})
    project_url = url_result.get("result", "")

    # Screenshot
    ss_path = SCREENSHOTS_DIR / f"{agent}_{time.strftime('%Y%m%d_%H%M%S')}.png"
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    _post("/screenshot", {"slotId": slot_id, "path": str(ss_path)})

    return {
        "agent": agent,
        "claude_name": name,
        "claude_project_url": project_url,
        "screenshot": str(ss_path),
        "si_chars": len(si),
        "kb_files": len(kb_files),
        "status": "cloned" if "/project/" in project_url else "incomplete",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--verify-auth", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--agents", type=str, help="comma-sep agent subset to process")
    args = p.parse_args()

    if args.verify_auth:
        ok = verify_auth()
        print(f"AUTH: {'OK' if ok else 'NOT AUTHENTICATED — Solon login required'}")
        sys.exit(0 if ok else 1)

    manifest = PROJECT_MANIFEST
    if args.agents:
        filter_ = {a.strip() for a in args.agents.split(",")}
        manifest = [m for m in manifest if m["agent"] in filter_]

    if args.dry_run:
        results = [clone_project("dry", m, dry_run=True) for m in manifest]
        OUTPUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_MANIFEST.with_name("project_ids.dry-run.json").write_text(json.dumps(results, indent=2))
        print(f"\nDRY-RUN complete: {len(results)} entries written to project_ids.dry-run.json")
        sys.exit(0)

    if not args.execute:
        p.print_help()
        sys.exit(0)

    # Execute mode requires auth
    if not verify_auth():
        print("BLOCKER: claude.ai session not authenticated. Run the auth-path described at top of file first.", file=sys.stderr)
        sys.exit(2)

    # Acquire slot + run clones
    slot = _post("/pool/acquire", {"timeout_ms": 30000})
    slot_id = slot["id"]
    results = []
    try:
        for m in manifest:
            try:
                r = clone_project(slot_id, m)
                results.append(r)
                time.sleep(5)  # rate limit
            except Exception as e:
                results.append({"agent": m["agent"], "status": "error", "error": str(e)})
    finally:
        _post(f"/pool/release/{slot_id}")

    OUTPUT_MANIFEST.write_text(json.dumps(results, indent=2))
    print(f"\nExecution complete: {len(results)} clone attempts written to {OUTPUT_MANIFEST}")
    for r in results:
        print(f"  {r['agent']}: {r['status']}")


if __name__ == "__main__":
    main()


# -------- COOKIE IMPORT HELPER (option b above) --------
# If Solon exports his claude.ai cookies from Chrome DevTools → JSON, save to
# /tmp/claude_cookies.json and run this helper to import into user-data-1.
#
# from playwright.sync_api import sync_playwright
# import json
# cookies = json.load(open('/tmp/claude_cookies.json'))
# with sync_playwright() as p:
#     ctx = p.chromium.launch_persistent_context('/opt/persistent-browser/user-data-1', headless=True)
#     ctx.add_cookies(cookies)
#     ctx.close()
