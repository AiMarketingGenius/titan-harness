#!/usr/bin/env python3
"""titan_harness_sync.py — autonomous /opt/amg-docs sync (CT-0427-71 step 3).

Runs every 5 min via cron. rsyncs new/changed Markdown from
/opt/titan-harness/docs/{architecture,megaprompts,runbooks,audits}/*.md
to /opt/amg-docs/{architecture,megaprompts,runbooks,audits}/.

VPS-side titan-harness mirror is updated via the existing post-receive
hook (Mac → VPS push on commit). This script promotes those harness-mirror
files to the canonical /opt/amg-docs/ paths consumed by other agents.

Idempotent: sha1-fingerprint state at /var/lib/amg-titan/harness_sync_state.json
ensures no re-fire on unchanged files.

Logs to /var/log/amg-titan-watch.log (shared with dep watcher).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time

STATE_PATH = "/var/lib/amg-titan/harness_sync_state.json"
LOG_PATH = "/var/log/amg-titan-watch.log"

# (source_dir, dest_dir) pairs
SYNC_PAIRS = [
    ("/opt/titan-harness/docs/architecture", "/opt/amg-docs/architecture"),
    ("/opt/titan-harness/docs/megaprompts", "/opt/amg-docs/megaprompts"),
    ("/opt/titan-harness/docs/runbooks", "/opt/amg-docs/runbooks"),
    ("/opt/titan-harness/docs/audits", "/opt/amg-docs/audits"),
]


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] [harness-sync] {msg}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except OSError:
        pass
    sys.stderr.write(line)


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"synced": {}}
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"synced": {}}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def file_sha1(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def sync_one(src_dir: str, dst_dir: str, state: dict) -> tuple[int, int]:
    """Sync .md files src→dst. Returns (synced_count, skipped_count)."""
    if not os.path.isdir(src_dir):
        return 0, 0
    os.makedirs(dst_dir, exist_ok=True)
    synced = 0
    skipped = 0
    for fname in os.listdir(src_dir):
        if not fname.endswith(".md") and not fname.endswith(".yaml") and not fname.endswith(".yml") and not fname.endswith(".json"):
            continue
        src = os.path.join(src_dir, fname)
        dst = os.path.join(dst_dir, fname)
        if not os.path.isfile(src):
            continue

        src_sha = file_sha1(src)
        dst_sha = file_sha1(dst)
        seen_sha = state["synced"].get(src)

        # Skip if src hasn't changed AND dst matches (already synced this version)
        if src_sha == seen_sha and src_sha == dst_sha:
            skipped += 1
            continue

        # Copy with metadata preserved
        try:
            shutil.copy2(src, dst)
            state["synced"][src] = src_sha
            synced += 1
            log(f"sync {fname}: {src_sha[:12]} → {dst}")
        except OSError as e:
            log(f"FAIL sync {src} → {dst}: {e}")

    return synced, skipped


def main(argv: list[str]) -> int:
    log("=== harness-sync run start ===")
    state = load_state()
    total_synced = 0
    total_skipped = 0
    for src, dst in SYNC_PAIRS:
        s, k = sync_one(src, dst, state)
        total_synced += s
        total_skipped += k
    save_state(state)
    log(f"=== harness-sync run end (synced={total_synced}, skipped={total_skipped}) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
