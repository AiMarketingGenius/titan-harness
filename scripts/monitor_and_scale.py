#!/usr/bin/env python3
"""
monitor_and_scale.py — n8n queue depth monitor with API-fallback auto-toggle.

Polls https://n8n.aimarketinggenius.io/webhook/queue-depth every 60 seconds.

Behavior:
  - depth > 20 sustained 5 min  → enable API fallback + alert Solon + queue
                                  overnight batch for low-priority tasks
  - depth < 5  sustained 10 min → disable API fallback (save $)
  - depth 5-20                  → no change (steady-state)

State file: ~/.openclaw/scale_state.json
  {
    "api_fallback_enabled": bool,
    "last_change_at":       isoformat,
    "consecutive_high":     int,  # how many consecutive 60s polls above 20
    "consecutive_low":      int,
    "history":              [list of recent (ts, depth) pairs, capped]
  }
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
STATE_FILE = HOME / ".openclaw" / "scale_state.json"
QUEUE_URL = "https://n8n.aimarketinggenius.io/webhook/queue-depth"
ALERT_WEBHOOK_ENV = "SLACK_ALERT_WEBHOOK"  # optional; degrade gracefully if unset
POLL_INTERVAL_S = 60
HIGH_THRESHOLD = 20
LOW_THRESHOLD = 5
HIGH_SUSTAIN_MIN = 5   # → 5 consecutive polls
LOW_SUSTAIN_MIN = 10   # → 10 consecutive polls
HISTORY_CAP = 60       # last 60 polls = 1 hour of data

DEFAULT_STATE = {
    "api_fallback_enabled": False,
    "last_change_at":       None,
    "consecutive_high":     0,
    "consecutive_low":      0,
    "history":              [],
}


def load_state() -> dict:
    if not STATE_FILE.exists():
        return DEFAULT_STATE.copy()
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return DEFAULT_STATE.copy()


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_queue_depth() -> int | None:
    try:
        with urllib.request.urlopen(QUEUE_URL, timeout=5) as r:
            data = json.loads(r.read())
            return int(data.get("depth", 0))
    except Exception as e:
        print(f"[monitor] queue fetch failed: {e!r}", file=sys.stderr)
        return None


def alert_solon(message: str) -> None:
    webhook = os.environ.get(ALERT_WEBHOOK_ENV)
    if not webhook:
        print(f"[monitor] ALERT (no webhook set): {message}")
        return
    try:
        body = json.dumps({"text": f"[amg-monitor] {message}"}).encode()
        req = urllib.request.Request(
            webhook, data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print(f"[monitor] alert post failed: {e!r}", file=sys.stderr)


def queue_overnight_batch() -> None:
    """Best-effort: tell n8n to defer low-priority tasks to overnight queue."""
    try:
        body = json.dumps({"action": "shift_to_overnight"}).encode()
        req = urllib.request.Request(
            "https://n8n.aimarketinggenius.io/webhook/scale-action",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
        print("[monitor] queued overnight-batch shift")
    except Exception as e:
        print(f"[monitor] overnight batch shift failed: {e!r}")


def toggle_api_fallback(enable: bool, state: dict) -> None:
    state["api_fallback_enabled"] = enable
    state["last_change_at"] = datetime.now(tz=timezone.utc).isoformat()
    save_state(state)
    msg = (
        f"API fallback {'ENABLED' if enable else 'disabled'} "
        f"(queue trigger; threshold {HIGH_THRESHOLD if enable else LOW_THRESHOLD})"
    )
    alert_solon(msg)
    print(f"[monitor] {msg}")
    if enable:
        queue_overnight_batch()


def step(state: dict) -> dict:
    depth = fetch_queue_depth()
    now = datetime.now(tz=timezone.utc).isoformat()
    if depth is None:
        return state  # transient; no state change
    state["history"].append([now, depth])
    state["history"] = state["history"][-HISTORY_CAP:]

    if depth > HIGH_THRESHOLD:
        state["consecutive_high"] += 1
        state["consecutive_low"] = 0
    elif depth < LOW_THRESHOLD:
        state["consecutive_low"] += 1
        state["consecutive_high"] = 0
    else:
        state["consecutive_high"] = 0
        state["consecutive_low"] = 0

    if state["consecutive_high"] >= HIGH_SUSTAIN_MIN and not state["api_fallback_enabled"]:
        toggle_api_fallback(True, state)
    elif state["consecutive_low"] >= LOW_SUSTAIN_MIN and state["api_fallback_enabled"]:
        toggle_api_fallback(False, state)

    save_state(state)
    print(f"[monitor] depth={depth} fb={state['api_fallback_enabled']} "
          f"high_streak={state['consecutive_high']} low_streak={state['consecutive_low']}")
    return state


def main():
    if "--once" in sys.argv:
        state = load_state()
        step(state)
        return 0
    state = load_state()
    print(f"[monitor] started; polling {QUEUE_URL} every {POLL_INTERVAL_S}s")
    while True:
        try:
            state = step(state)
        except KeyboardInterrupt:
            print("[monitor] stopped via KeyboardInterrupt")
            return 0
        except Exception as e:
            print(f"[monitor] step failed: {e!r}")
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
