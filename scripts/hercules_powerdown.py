#!/usr/bin/env python3
"""
hercules_powerdown.py — log a conversation snapshot from a Hercules web-tab
session so it survives the next restart.

Solves Solon's pain: when he says "power down" to Hercules-in-tab and starts
a new tab later, the new Hercules has factory state (bootstrap brief) but
zero memory of the actual conversation. This script bridges that gap by
persisting the snapshot to MCP, where the bootstrap brief picks it up on
next regen.

Workflow:
  1. Solon says "power down" to Hercules in the Kimi tab.
  2. Hercules responds with a SNAPSHOT block (see prompt template in
     ~/AMG/HERCULES_BOOTSTRAP.md "Powerdown protocol" section).
  3. Solon copies the snapshot text.
  4. Solon runs:
       pbpaste | python3 ~/titan-harness/scripts/hercules_powerdown.py
     OR clicks Hammerspoon shortcut Cmd+Opt+H (if installed).
  5. Snapshot logs to MCP tagged hercules-conversation-snapshot + archives to
     ~/AMG/hercules-conversation-archive/<TS>__snapshot.md
  6. Bootstrap brief next regen (within 5 min) shows the snapshot under
     "## Last conversation snapshot" — new Hercules sees it on paste.

Usage:
    pbpaste | python3 hercules_powerdown.py            # from clipboard
    python3 hercules_powerdown.py --text "<snapshot>"  # explicit
    python3 hercules_powerdown.py --file path.md       # from file
    python3 hercules_powerdown.py --interactive        # paste then Ctrl-D
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
from mcp_rest_client import log_decision as mcp_log_decision  # noqa: E402

ARCHIVE_DIR = HOME / "AMG" / "hercules-conversation-archive"
LOGFILE = HOME / ".openclaw" / "logs" / "hercules_powerdown.log"
MIN_SNAPSHOT_BYTES = 50  # reject obvious empty/test pastes


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def _read_snapshot(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.file:
        return pathlib.Path(args.file).expanduser().read_text(encoding="utf-8")
    if args.interactive:
        print("Paste snapshot then Ctrl-D:", file=sys.stderr)
        return sys.stdin.read()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("ERROR: no snapshot provided. Use --text, --file, --interactive, or pipe via stdin.", file=sys.stderr)
    return ""


def _extract_snapshot_block(raw: str) -> tuple[str, str]:
    """If the raw text contains a 'SNAPSHOT:' marker, extract the block.
    Otherwise treat the whole input as the snapshot. Returns (snapshot_text, summary_first_line)."""
    text = raw.strip()
    marker = "SNAPSHOT:"
    if marker in text:
        idx = text.index(marker)
        text = text[idx + len(marker):].strip()
    # Strip trailing instructions to Solon (the "Run: pbpaste | ..." line)
    for cutoff in ("Run:", "RUN:", "Powered down.", "POWERED DOWN."):
        if cutoff in text:
            text = text.split(cutoff)[0].strip()
            break
    # First non-empty line as summary
    summary = ""
    for line in text.splitlines():
        line = line.strip().lstrip("#").lstrip("*").lstrip("-").strip()
        if line:
            summary = line[:200]
            break
    return text, summary


def _archive_snapshot(text: str) -> pathlib.Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = ARCHIVE_DIR / f"{stamp}__hercules_snapshot.md"
    body = (
        f"# Hercules Conversation Snapshot — {stamp}\n\n"
        f"**Source:** hercules_powerdown.py CLI\n"
        f"**Logged at:** {datetime.now(tz=timezone.utc).isoformat()}\n\n"
        f"---\n\n{text}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description="Log a Hercules conversation snapshot to MCP")
    p.add_argument("--text", help="snapshot text directly")
    p.add_argument("--file", help="read snapshot from file")
    p.add_argument("--interactive", action="store_true", help="paste then Ctrl-D")
    p.add_argument("--quiet", action="store_true", help="no stdout (Hammerspoon-friendly)")
    args = p.parse_args()

    raw = _read_snapshot(args)
    if not raw or len(raw.strip()) < MIN_SNAPSHOT_BYTES:
        msg = f"snapshot too short ({len(raw.strip())}B < {MIN_SNAPSHOT_BYTES}B); refusing to log empty paste"
        _log(f"REJECT {msg}")
        if not args.quiet:
            print(f"ERROR: {msg}", file=sys.stderr)
        return 1

    snapshot, summary = _extract_snapshot_block(raw)

    archive_path = _archive_snapshot(snapshot)
    _log(f"archived snapshot to {archive_path} ({len(snapshot)}B)")

    # Log to MCP — this is what the bootstrap brief picks up on next regen
    text_for_mcp = (
        f"Hercules conversation snapshot (powerdown @ "
        f"{datetime.now(tz=timezone.utc).isoformat()}): {summary}"
    )[:1000]
    rationale_for_mcp = (
        f"Solon-driven Hercules powerdown. Full snapshot archived at {archive_path}. "
        f"Bootstrap brief will surface this on next regen so a new Hercules tab "
        f"resumes the conversation context.\n\n--- snapshot ---\n{snapshot[:6000]}"
    )
    try:
        code, body = mcp_log_decision(
            text=text_for_mcp,
            rationale=rationale_for_mcp,
            tags=["hercules-conversation-snapshot", "session-end", "powerdown",
                  "hercules-resume-context"],
            project_source="titan",
        )
        if code != 200:
            _log(f"MCP log_decision failed: code={code} body={str(body)[:200]}")
            if not args.quiet:
                print(f"WARN: MCP returned {code}; archive saved at {archive_path}", file=sys.stderr)
            return 2
    except Exception as e:
        _log(f"MCP log_decision exception: {e!r}")
        if not args.quiet:
            print(f"WARN: MCP exception {e!r}; archive saved at {archive_path}", file=sys.stderr)
        return 2

    # Trigger immediate bootstrap brief regen so the snapshot appears in the
    # paste-block before Solon opens his next tab
    try:
        import subprocess
        subprocess.Popen(
            ["python3", str(HOME / "titan-harness" / "scripts" / "hercules_bootstrap_brief.py"), "--once"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass

    if not args.quiet:
        print(f"OK: snapshot logged to MCP + archived at {archive_path}")
        print(f"     Summary: {summary}")
        print(f"     Bootstrap brief regenerating in background.")
    _log(f"OK powerdown logged ({len(snapshot)}B) summary='{summary}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
