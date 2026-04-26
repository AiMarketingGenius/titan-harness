#!/usr/bin/env python3
"""
telnyx_send.py — outbound SMS via Telnyx API v2.

Used by mercury_mcp_notifier.telenix_send() for P0/P1/P2 routing per
CLAUDE.md §21 (quiet hours 11pm-7am EST, P0 only breaks quiet).

Credentials read from /etc/amg/telnyx.env on VPS (via SSH) or local env vars.
Solon's destination number + the AMG Telnyx FROM number both need to be
provisioned in /etc/amg/telnyx.env or pulled from Infisical by Mercury.

Required env keys (all in /etc/amg/telnyx.env):
    TELNYX_API_KEY      — Bearer token
    TELNYX_FROM_NUMBER  — E.164 (e.g., +14156671212) — the AMG Telnyx number
    TELNYX_SOLON_NUMBER — E.164 — Solon's iPhone

Usage:
    telnyx_send.py "ALERT: Cerberus P0 incident" --priority P0
    echo "Daily digest" | telnyx_send.py - --priority P2
    telnyx_send.py --to +14156675555 "custom recipient"
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
LOGFILE = HOME / ".openclaw" / "logs" / "telnyx_send.log"
SSH_HOST = os.environ.get("AMG_VPS_SSH_HOST", "amg-staging")


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _read_env_remote(name: str) -> dict:
    """Read /etc/amg/<name>.env via SSH. Returns {} on failure."""
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
            env[k.strip()] = v.strip().strip("'").strip('"')
        return env
    except Exception:
        return {}


def _get_creds() -> tuple[str, str, str]:
    """Returns (api_key, from_number, solon_number) from /etc/amg/telnyx.env."""
    env = _read_env_remote("telnyx")
    # also accept overrides from local env (for testing)
    api_key = os.environ.get("TELNYX_API_KEY") or env.get("TELNYX_API_KEY", "")
    from_num = os.environ.get("TELNYX_FROM_NUMBER") or env.get("TELNYX_FROM_NUMBER", "")
    solon_num = os.environ.get("TELNYX_SOLON_NUMBER") or env.get("TELNYX_SOLON_NUMBER", "")
    return api_key, from_num, solon_num


def send_sms(text: str, to: str | None = None, priority: str = "P2") -> dict:
    api_key, from_num, default_to = _get_creds()
    target = to or default_to
    if not api_key:
        return {"ok": False, "error": "TELNYX_API_KEY missing in /etc/amg/telnyx.env"}
    if not from_num:
        return {"ok": False, "error": "TELNYX_FROM_NUMBER missing"}
    if not target:
        return {"ok": False, "error": "no destination — set TELNYX_SOLON_NUMBER or pass --to"}
    # Truncate to single SMS segment if possible (160 chars), else allow multi-segment
    payload = {
        "from": from_num,
        "to": target,
        "text": text[:1600],  # Telnyx allows multi-segment up to ~10 SMS
        "type": "SMS",
    }
    req = urllib.request.Request(
        "https://api.telnyx.com/v2/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read() or b"{}")
        msg_id = (body.get("data") or {}).get("id", "unknown")
        _log(f"SENT priority={priority} to={target} msg_id={msg_id} text={text[:80]}")
        return {"ok": True, "message_id": msg_id, "to": target, "priority": priority}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:300]
        _log(f"FAIL priority={priority} HTTP {e.code} err={err}")
        return {"ok": False, "error": f"HTTP {e.code}: {err}"}
    except Exception as e:
        _log(f"FAIL priority={priority} err={e!r}")
        return {"ok": False, "error": repr(e)}


def main() -> int:
    p = argparse.ArgumentParser(description="Telnyx outbound SMS")
    p.add_argument("text", nargs="?", help="message text (or '-' for stdin)")
    p.add_argument("--to", help="destination E.164 (default: TELNYX_SOLON_NUMBER)")
    p.add_argument("--priority", default="P2", help="P0|P1|P2 (informational; quiet-hours guard upstream)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.text == "-" or not args.text:
        text = sys.stdin.read().strip()
    else:
        text = args.text

    if not text:
        sys.exit("no message text")

    if args.dry_run:
        api_key, from_num, target = _get_creds()
        target = args.to or target
        print(json.dumps({
            "dry_run": True, "to": target, "from": from_num,
            "priority": args.priority, "text": text,
            "api_key_present": bool(api_key),
        }, indent=2))
        return 0

    result = send_sms(text, to=args.to, priority=args.priority)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
