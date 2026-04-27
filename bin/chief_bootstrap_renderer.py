#!/usr/bin/env python3
"""chief_bootstrap_renderer.py — Phase 2 build (CT-0427-66).

Renders deterministic boot prompts for Hercules / Nestor / Alexander from MCP
state. No strategy decisions; pure assembly. Per CHIEF_BOOTSTRAP_RENDERER_v0_1.md.

Usage:
    chief_bootstrap_renderer.py <chief>          # render fresh bootstrap
    chief_bootstrap_renderer.py <chief> --refresh # refresh-only mini block

Outputs:
    /opt/amg-docs/chiefs/<chief>/boot_prompt.txt
    /opt/amg-docs/chiefs/<chief>/boot_prompt.degraded.txt
    /opt/amg-governance/lcache/<chief>.md  (touched, not rewritten if absent)
    /opt/amg-governance/shift_state/<chief>.json  (contract template)

Degraded mode: when get_bootstrap_context OR search_memory unavailable, prepend
a DEGRADED CONTEXT warning and render from recent decisions + lcache only
(per spec §6).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

MCP_BASE = os.environ.get("MCP_BASE", "http://localhost:3000")
CHIEFS_ROOT = os.environ.get("CHIEFS_ROOT", "/opt/amg-docs/chiefs")
LCACHE_ROOT = os.environ.get("LCACHE_ROOT", "/opt/amg-governance/lcache")
SHIFT_STATE_ROOT = os.environ.get("SHIFT_STATE_ROOT", "/opt/amg-governance/shift_state")

CHIEF_PROFILES = {
    "hercules": {
        "lane": "Architecture, doctrine, queue honesty, risk gates, cross-team orchestration",
        "kb_namespaces": ["kb:hercules:eom", "kb:hercules:doctrine"],
        "owner_tag": "owner:hercules",
        "builders": ["iolaus", "cadmus", "themis", "nike"],
    },
    "nestor": {
        "lane": "Product, UX, demos, client-safe presentation, Atlas onboarding",
        "kb_namespaces": ["kb:nestor:lumina-cro"],
        "owner_tag": "owner:nestor",
        "builders": ["ariadne", "calypso", "demeter", "pallas"],
    },
    "alexander": {
        "lane": "Content, SEO, voice/chat, brand language, offer positioning, newsletters",
        "kb_namespaces": [
            "kb:alexander:seo-content", "kb:alexander:hormozi", "kb:alexander:welby",
            "kb:alexander:koray", "kb:alexander:reputation", "kb:alexander:paid-ads",
            "kb:alexander:outbound",
        ],
        "owner_tag": "owner:alexander",
        "builders": ["calliope", "pythia", "orpheus", "clio"],
    },
}


def http_get(path: str) -> tuple[bool, str | dict]:
    req = urllib.request.Request(f"{MCP_BASE}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            ct = r.headers.get("Content-Type", "")
            if "json" in ct:
                try:
                    return True, json.loads(body)
                except json.JSONDecodeError:
                    return True, body
            return True, body
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, str(e)


def get_bootstrap() -> tuple[bool, str]:
    ok, body = http_get("/api/bootstrap?project_id=EOM&scope=both")
    if not ok or not isinstance(body, str) or not body.strip():
        return False, str(body)
    return True, body


def get_recent_decisions(count: int = 25) -> tuple[bool, list[dict]]:
    ok, body = http_get(f"/api/recent-decisions-json?count={count}")
    if not ok or not isinstance(body, dict):
        return False, []
    if not body.get("success"):
        return False, []
    return True, body.get("decisions", [])


def filter_decisions_by_owner(decisions: list[dict], chief: str) -> list[dict]:
    owner = f"owner:{chief}"
    chief_tag = f"chief:{chief}"
    out = []
    for d in decisions:
        tags = d.get("tags") or []
        if owner in tags or chief_tag in tags or chief in tags:
            out.append(d)
        elif d.get("project_source") == chief.upper() or d.get("project_source") == chief:
            out.append(d)
    return out


def read_lcache(chief: str) -> str:
    path = os.path.join(LCACHE_ROOT, f"{chief}.md")
    if not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def touch_lcache(chief: str) -> None:
    """Ensure lcache file exists (don't overwrite if present)."""
    os.makedirs(LCACHE_ROOT, exist_ok=True)
    path = os.path.join(LCACHE_ROOT, f"{chief}.md")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(f"# {chief} lcache\n\n_initialized {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}_\n\n")


def write_shift_state(chief: str) -> str:
    os.makedirs(SHIFT_STATE_ROOT, exist_ok=True)
    path = os.path.join(SHIFT_STATE_ROOT, f"{chief}.json")
    state = {
        "agent": chief,
        "active_letter": "auto",
        "lock_holder": None,
        "last_heartbeat": None,
        "handoff": None,
        "_template_initialized": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
    return path


def render_prompt(chief: str, bootstrap_ok: bool, bootstrap_text: str,
                  decisions_ok: bool, decisions: list[dict],
                  lcache: str, search_ok: bool) -> str:
    profile = CHIEF_PROFILES[chief]
    chief_decisions = filter_decisions_by_owner(decisions, chief)
    degraded = (not bootstrap_ok) or (not search_ok)

    lines = []
    if degraded:
        missing = []
        if not bootstrap_ok:
            missing.append("get_bootstrap_context")
        if not search_ok:
            missing.append("search_memory")
        lines.append("=" * 70)
        lines.append("⚠️  DEGRADED CONTEXT — full memory parity NOT claimed.")
        lines.append(f"⚠️  Missing routes: {', '.join(missing)}")
        lines.append("⚠️  Render from recent decisions + lcache only.")
        lines.append("⚠️  On boot, MUST log_decision tag bootstrap_degraded:" + chief)
        lines.append("=" * 70)
        lines.append("")

    lines.append(f"# {chief.upper()} BOOTSTRAP — {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    lines.append("")
    lines.append("## 1. Identity + Lane")
    lines.append(f"You are **{chief.capitalize()}**, AMG chief.")
    lines.append(f"Lane: {profile['lane']}")
    lines.append(f"KB namespaces: {', '.join(profile['kb_namespaces'])}")
    lines.append(f"Builders under your dispatch (planned): {', '.join(profile['builders'])}")
    lines.append("")

    lines.append("## 2. Top 3 Live Priorities (filtered to owner-scoped recent decisions)")
    if chief_decisions:
        for d in chief_decisions[:3]:
            ts = (d.get("created_at") or "")[:19]
            text = (d.get("text") or "")[:200]
            lines.append(f"- ({ts}) {text}")
    else:
        lines.append("- (no owner-scoped decisions in recent window)")
    lines.append("")

    lines.append("## 3. Blockers Relevant To You")
    blockers = [d for d in chief_decisions if any(t in (d.get("tags") or []) for t in ("blocker", "watchdog-blocker"))]
    if blockers:
        for b in blockers[:5]:
            text = (b.get("text") or "")[:200]
            lines.append(f"- {text}")
    else:
        lines.append("- (none in recent window)")
    lines.append("")

    lines.append("## 4. Last Verified Handoff")
    if lcache.strip():
        lines.append(lcache.strip()[:1000])
    else:
        lines.append("(no lcache entries — first boot or fresh state)")
    lines.append("")

    if not degraded:
        lines.append("## 5. Standing Rules + Sprint State (from /api/bootstrap)")
        lines.append(bootstrap_text.strip()[:5000])
        lines.append("")

    lines.append("## 6. Mandatory On-Boot Action")
    if degraded:
        lines.append(f"- log_decision(text=\"bootstrap_degraded:{chief} — missing routes: {', '.join([r for r in ['get_bootstrap_context', 'search_memory'] if not (bootstrap_ok if r == 'get_bootstrap_context' else search_ok)])}\", "
                     f"tags=[\"bootstrap_degraded\", \"{chief}\"], project_source=\"{chief}\")")
    lines.append("- Acknowledge sprint state above before claiming any task.")
    lines.append("- Use queue tools tagged `owner:" + chief + "` for all dispatch work.")
    lines.append("")

    lines.append("## 7. Excluded From This Prompt (per spec §5)")
    lines.append("- Raw secrets")
    lines.append("- Other chiefs' backlogs")
    lines.append("- Speculative route status")
    lines.append("")

    return "\n".join(lines)


def render_degraded_template(chief: str) -> str:
    """Static template for fully-offline degraded mode (both routes down)."""
    profile = CHIEF_PROFILES[chief]
    return f"""\
======================================================================
⚠️  DEGRADED CONTEXT (BOTH BOOTSTRAP AND SEARCH UNAVAILABLE)
⚠️  Render from local lcache only.
⚠️  MUST log_decision bootstrap_degraded:{chief} on resume.
======================================================================

# {chief.upper()} BOOTSTRAP (degraded, lcache-only)

## 1. Identity + Lane
You are {chief.capitalize()}, AMG chief.
Lane: {profile['lane']}
Builders under dispatch (planned): {', '.join(profile['builders'])}

## 2. Standing Rules
- All Solon/EOM/Hercules-Triangle rules per CLAUDE.md still apply.
- No claim of full memory parity.
- Surface degraded-mode warning in every response until routes restore.

## 3. Lcache (last continuity buffer)
[lcache content inserted at render time]

## 4. Mandatory On-Boot Action
- log_decision(text="bootstrap_degraded:{chief} — both routes down",
               tags=["bootstrap_degraded", "{chief}", "lcache_only"],
               project_source="{chief}")
"""


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: chief_bootstrap_renderer.py <hercules|nestor|alexander> [--refresh]",
              file=sys.stderr)
        return 2
    chief = argv[0].lower()
    if chief not in CHIEF_PROFILES:
        print(f"unknown chief: {chief}. Must be one of {list(CHIEF_PROFILES)}", file=sys.stderr)
        return 2

    refresh_only = "--refresh" in argv

    bootstrap_ok, bootstrap_text = get_bootstrap()
    decisions_ok, decisions = get_recent_decisions(50)
    # search_memory has no no-auth GET path → mark unavailable (degraded)
    search_ok = False
    lcache = read_lcache(chief)

    prompt = render_prompt(
        chief=chief,
        bootstrap_ok=bootstrap_ok,
        bootstrap_text=bootstrap_text if bootstrap_ok else "",
        decisions_ok=decisions_ok,
        decisions=decisions,
        lcache=lcache,
        search_ok=search_ok,
    )

    chief_dir = os.path.join(CHIEFS_ROOT, chief)
    os.makedirs(chief_dir, exist_ok=True)

    boot_path = os.path.join(chief_dir, "boot_prompt.txt")
    with open(boot_path, "w") as f:
        f.write(prompt)

    degraded_path = os.path.join(chief_dir, "boot_prompt.degraded.txt")
    if not os.path.exists(degraded_path):
        with open(degraded_path, "w") as f:
            f.write(render_degraded_template(chief))

    touch_lcache(chief)
    shift_path = write_shift_state(chief)

    print(f"chief: {chief}")
    print(f"bootstrap_ok: {bootstrap_ok}")
    print(f"decisions_ok: {decisions_ok} (count={len(decisions)})")
    print(f"search_ok: {search_ok} (degraded marker)")
    print(f"degraded: {(not bootstrap_ok) or (not search_ok)}")
    print(f"boot_prompt: {boot_path} ({os.path.getsize(boot_path)} bytes)")
    print(f"degraded_template: {degraded_path}")
    print(f"shift_state: {shift_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
