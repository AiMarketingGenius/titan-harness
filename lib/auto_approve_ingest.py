#!/usr/bin/env python3
"""
auto_approve_ingest.py — ship Hammerspoon auto-approve events to MCP.

Reads one-line-JSON files dropped by ~/.hammerspoon/auto_approve_claude_prompts.lua
into ~/titan-harness/logs/auto_approve_queue/ and calls log_decision via MCP REST.
Idempotent; deletes queue files only on successful log_decision insert.

CT-0419-08 Layer 3 sidecar. Runs via launchd (io.aimg.auto-approve-ingest, 5min).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HOME = Path(os.environ.get("HOME", "/Users/solonzafiropoulos1"))
QUEUE = HOME / "titan-harness" / "logs" / "auto_approve_queue"
LOG = HOME / "titan-harness" / "logs" / "auto_approve_ingest.log"
MCP_URL = os.environ.get("AMG_MCP_URL", "https://memory.aimarketinggenius.io/rpc/log_decision")
SUPA_KEY_FILE = Path("/etc/amg/supabase_service_role.key")
ENV_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("AMG_SUPABASE_KEY")


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")


def _from_env_file(path: Path, var: str) -> str | None:
    if not path.exists():
        return None
    try:
        for line in path.read_text().splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            if k.strip() == var:
                return v.strip().strip("'\"")
    except Exception:
        return None
    return None


def load_key() -> str | None:
    if ENV_KEY:
        return ENV_KEY
    for candidate in (HOME / ".titan-env", Path("/opt/amg-titan/.env"), HOME / ".config/titan/env"):
        for var in ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY"):
            v = _from_env_file(candidate, var)
            if v:
                return v
    if SUPA_KEY_FILE.exists():
        try:
            return SUPA_KEY_FILE.read_text().strip()
        except PermissionError:
            return None
    return None


def load_url() -> str:
    override = os.environ.get("AMG_MCP_URL")
    if override:
        return override
    for candidate in (HOME / ".titan-env", Path("/opt/amg-titan/.env"), HOME / ".config/titan/env"):
        v = _from_env_file(candidate, "SUPABASE_URL")
        if v:
            return v.rstrip("/") + "/rest/v1/op_decisions"
    return MCP_URL


def post_decision(event: dict, key: str, url: str) -> bool:
    kind = event.get("kind") or event.get("event") or "unknown"
    target = event.get("target", "unknown")
    action = event.get("action", "unknown")
    is_tcc = str(event.get("event", "")).startswith("tcc")
    body = {
        "project_source": "titan",
        "decision_text": (
            f"[{'tcc-' if is_tcc else ''}auto-approve] kind={kind} "
            f"target={target} action={action} app={event.get('app')} "
            f"category={event.get('category')} ts={event.get('ts')}"
        ),
        "rationale": "CT-0419-08 Hammerspoon auto-approve event",
        "tags": [
            "tcc-auto-approve" if is_tcc else "auto-approve",
            "claude-code-dialog" if not is_tcc else "tcc-dialog",
            f"kind:{kind}",
            f"action:{action}",
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        log(f"http_err {e.code} target={target}")
        return False
    except Exception as e:
        log(f"post_err {type(e).__name__}:{e} target={target}")
        return False


def main() -> int:
    if not QUEUE.exists():
        return 0
    key = load_key()
    url = load_url()
    files = sorted(QUEUE.glob("*.json"))
    if not files:
        return 0
    if not key:
        log(f"no_key queue_size={len(files)}; retry on next invocation")
        return 0
    ok, fail = 0, 0
    for p in files:
        try:
            event = json.loads(p.read_text())
        except Exception as e:
            log(f"parse_err {p.name} {e}")
            p.unlink(missing_ok=True)
            continue
        if post_decision(event, key, url):
            p.unlink(missing_ok=True)
            ok += 1
        else:
            fail += 1
    log(f"drained ok={ok} fail={fail} url={url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
