#!/usr/bin/env python3
"""titan_dep_watcher.py — Achilles dep + megaprompt arrival watcher.

Runs every 10 min via cron. Watches for:
  Achilles specs (auto-claim trigger):
    - /opt/amg-docs/architecture/WATCHDOG_VPS_v0_1.md (CT-56) → fires CT-57
    - /opt/amg-docs/architecture/CHIEF_BOOTSTRAP_RENDERER_v0_1.md (CT-65) → fires CT-66
    - /opt/amg-docs/architecture/CHIEF_DISPATCHER_SKELETON_v0_1.md (CT-67) → fires CT-68

  Megaprompt updates (informational log only):
    - /opt/amg-docs/megaprompts/*v5_0_2*
    - /opt/amg-docs/megaprompts/*v4_0_2_3*
    - /opt/amg-docs/megaprompts/*v4_0_3_2*

State at /var/lib/amg-titan/dep_watch_state.json prevents re-firing on detected deps.
Logs to /var/log/amg-titan-watch.log.

MCP HTTP API: localhost:3400 (POST /api/decisions, POST /api/queue-task).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

MCP_BASE = os.environ.get("MCP_BASE", "http://localhost:3000")
STATE_PATH = "/var/lib/amg-titan/dep_watch_state.json"
LOG_PATH = "/var/log/amg-titan-watch.log"

ACHILLES_DEPS = [
    {
        "spec_path": "/opt/amg-docs/architecture/WATCHDOG_VPS_v0_1.md",
        "spec_ct": "CT-0427-56",
        "build_ct": "CT-0427-57",
        "build_objective": "VPS Watchdog v0.1 build per Achilles WATCHDOG_VPS_v0_1.md",
        "tag_label": "watchdog_vps_v0_1",
    },
    {
        "spec_path": "/opt/amg-docs/architecture/CHIEF_BOOTSTRAP_RENDERER_v0_1.md",
        "spec_ct": "CT-0427-65",
        "build_ct": "CT-0427-66",
        "build_objective": "Chief Bootstrap Renderer Phase 2 build per Achilles CHIEF_BOOTSTRAP_RENDERER_v0_1.md",
        "tag_label": "chief_bootstrap_renderer_v0_1",
    },
    {
        "spec_path": "/opt/amg-docs/architecture/CHIEF_DISPATCHER_SKELETON_v0_1.md",
        "spec_ct": "CT-0427-67",
        "build_ct": "CT-0427-68",
        "build_objective": "Chief Dispatcher Skeleton Phase 3 build per Achilles CHIEF_DISPATCHER_SKELETON_v0_1.md",
        "tag_label": "chief_dispatcher_skeleton_v0_1",
    },
]

MEGAPROMPT_GLOBS = [
    "/opt/amg-docs/megaprompts/*v5_0_2*",
    "/opt/amg-docs/megaprompts/*v4_0_2_3*",
    "/opt/amg-docs/megaprompts/*v4_0_3_2*",
]


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except OSError:
        pass
    sys.stderr.write(line)


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"seen": {}}
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"seen": {}}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def file_fingerprint(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    st = os.stat(path)
    h = hashlib.sha1()
    h.update(f"{st.st_size}|{int(st.st_mtime)}".encode())
    return h.hexdigest()


def mcp_post(path: str, payload: dict) -> tuple[bool, str]:
    url = f"{MCP_BASE}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
        return True, body
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, str(e)


def log_decision(text: str, tags: list, rationale: str = "") -> None:
    ok, body = mcp_post("/api/decisions", {
        "text": text,
        "project_source": "titan",
        "rationale": rationale,
        "tags": tags,
    })
    log(f"log_decision tags={tags} ok={ok} resp={body[:200]}")


def queue_operator_task(objective: str, instructions: str, ac: str,
                        tags: list, priority: str = "urgent") -> None:
    ok, body = mcp_post("/api/queue-task", {
        "objective": objective,
        "instructions": instructions,
        "acceptance_criteria": ac,
        "priority": priority,
        "approval": "pre_approved",
        "assigned_to": "titan",
        "project_id": "EOM",
        "tags": tags,
    })
    log(f"queue_operator_task obj={objective[:60]!r} ok={ok} resp={body[:200]}")


def check_achilles_deps(state: dict) -> int:
    new_detections = 0
    seen = state.setdefault("seen", {})
    for dep in ACHILLES_DEPS:
        path = dep["spec_path"]
        fp = file_fingerprint(path)
        if fp is None:
            continue  # spec not yet filed
        if seen.get(path) == fp:
            continue  # already detected, no change
        # NEW detection (or content changed)
        is_first = path not in seen
        seen[path] = fp
        new_detections += 1
        spec_ct = dep["spec_ct"]
        build_ct = dep["build_ct"]
        label = dep["tag_label"]
        msg = (f"Achilles dep landed: {path} ({spec_ct}). "
               f"Triggering {build_ct} pickup. Watcher detection at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}.")
        log_decision(
            text=msg,
            tags=["ct_dep_release", spec_ct, build_ct, label, "titan_watcher"],
            rationale=f"Filesystem watcher detected {path} fingerprint {fp[:12]}. {'first_landing' if is_first else 'content_changed'}.",
        )
        if is_first:
            queue_operator_task(
                objective=f"WATCHER TRIGGER — claim and execute {build_ct} (Achilles spec {spec_ct} just landed)",
                instructions=(f"Achilles dep {dep['spec_path']} just landed (detected by titan_dep_watcher.py).\n"
                              f"Action: claim_task {build_ct} → read spec at {path} → implement per spec → file artifacts → log_decision tag {label}_complete.\n"
                              f"Original {build_ct} task in queue has full instructions; this trigger is a notification to come pick it up."),
                ac=f"{build_ct} flipped to completed with deliverable_link; spec read; implementation matches AC of {build_ct}.",
                tags=["watcher_trigger", spec_ct, build_ct, label, "auto_claim_signal"],
                priority="urgent",
            )
        log(f"✓ Achilles dep detected: {path} → {build_ct} signaled")
    return new_detections


def check_megaprompts(state: dict) -> int:
    new_detections = 0
    seen = state.setdefault("seen", {})
    for pattern in MEGAPROMPT_GLOBS:
        for path in glob.glob(pattern):
            fp = file_fingerprint(path)
            if fp is None:
                continue
            if seen.get(path) == fp:
                continue
            is_first = path not in seen
            seen[path] = fp
            new_detections += 1
            label = os.path.basename(path)
            msg = f"Megaprompt update detected: {path}. {'first_landing' if is_first else 'content_changed'}. Informational only — no auto-claim."
            log_decision(
                text=msg,
                tags=["megaprompt_update", label, "titan_watcher", "informational"],
                rationale=f"Filesystem watcher detected {path} fingerprint {fp[:12]}.",
            )
            log(f"✓ megaprompt update detected: {path} (informational)")
    return new_detections


def main(argv: list[str]) -> int:
    state = load_state()
    log("=== watcher run start ===")
    achilles_n = check_achilles_deps(state)
    mp_n = check_megaprompts(state)
    save_state(state)
    log(f"=== watcher run end (achilles_new={achilles_n}, megaprompt_new={mp_n}) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
