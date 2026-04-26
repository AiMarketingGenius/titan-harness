#!/usr/bin/env python3
"""
mercury_folder_sync.py — ~/AMG/shared-with-hercules/ → MCP indexer daemon.

Watches ~/AMG/shared-with-hercules/ for new or modified files and posts a
summary entry to MCP via `log_decision` so Hercules (and any other agent
querying MCP) can find the file content via `search_memory`.

For each file:
    - hashes content (sha256)
    - skips if hash matches the last logged version (no duplicate posts)
    - logs to MCP with tag `hercules-shared-file` + filename + size + first 50KB
      of text content (binary files are noted by mime, not embedded)
    - records the file's hash in ~/.openclaw/state/folder_sync_hashes.json

Solon's flow: drop a doc/script/PDF into ~/AMG/shared-with-hercules/, Mercury
indexes it within 60s, Hercules can then ask "summarize the latest file
Solon shared" via MCP search.

Run modes:
    mercury_folder_sync.py --watch        # daemon (default), poll 60s
    mercury_folder_sync.py --once         # one pass
    mercury_folder_sync.py --interval 60  # custom interval
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import pathlib
import sys
import time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
from mcp_rest_client import log_decision as mcp_log_decision  # noqa: E402

SHARED = HOME / "AMG" / "shared-with-hercules"
STATE_DIR = HOME / ".openclaw" / "state"
HASH_FILE = STATE_DIR / "folder_sync_hashes.json"
LOGFILE = HOME / ".openclaw" / "logs" / "mercury_folder_sync.log"
MAX_TEXT_BYTES = 50 * 1024  # 50KB cap per file embedding
TEXT_EXTS = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv", ".html", ".css", ".js", ".ts", ".tsx", ".py", ".sh", ".sql", ".log"}


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _load_hashes() -> dict:
    if not HASH_FILE.exists():
        return {}
    try:
        return json.loads(HASH_FILE.read_text())
    except Exception:
        return {}


def _save_hashes(d: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    HASH_FILE.write_text(json.dumps(d, indent=2))


def file_sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_text(p: pathlib.Path) -> bool:
    if p.suffix.lower() in TEXT_EXTS:
        return True
    mime, _ = mimetypes.guess_type(str(p))
    return bool(mime and mime.startswith("text/"))


def index_file(p: pathlib.Path) -> dict:
    digest = file_sha256(p)
    size = p.stat().st_size
    rel = p.relative_to(SHARED) if p.is_relative_to(SHARED) else p.name
    body = {
        "ok": True,
        "path": str(p),
        "rel": str(rel),
        "size": size,
        "sha256": digest,
        "modified": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
    }
    if is_text(p):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_BYTES]
            body["content"] = text
            body["content_bytes_logged"] = len(text)
        except Exception as e:
            body["content_error"] = repr(e)
    else:
        mime, _ = mimetypes.guess_type(str(p))
        body["mime"] = mime or "application/octet-stream"
        body["content_NOT_LOGGED"] = "binary file — fetch via path"
    return body


def post_to_mcp(meta: dict) -> tuple[bool, str]:
    text_content = meta.get("content") or ""
    summary = (
        f"Hercules shared-folder file indexed: {meta['rel']} "
        f"size={meta['size']}B sha256={meta['sha256'][:12]} modified={meta['modified']}"
    )
    rationale = (
        f"mercury_folder_sync.py picked up file at {meta['path']}. "
        f"First {meta.get('content_bytes_logged', 0)}B of text follows when applicable. "
        f"Hercules + agents can search this via MCP search_memory tag=hercules-shared-file."
        + (("\n\n---\n" + text_content[:8000]) if text_content else "")
    )
    code, body = mcp_log_decision(
        text=summary[:500],
        rationale=rationale[:8000],
        tags=[
            "hercules-shared-file",
            f"file:{pathlib.PurePath(meta['rel']).name[:80]}",
            f"sha:{meta['sha256'][:12]}",
        ],
        project_source="titan",
    )
    if code == 200:
        return True, "logged"
    return False, f"MCP code={code} body={str(body)[:200]}"


def drain_once() -> dict:
    SHARED.mkdir(parents=True, exist_ok=True)
    hashes = _load_hashes()
    out = {"scanned": 0, "indexed": 0, "skipped": 0, "errors": 0}
    for p in SHARED.rglob("*"):
        if not p.is_file() or p.name.startswith("."):
            continue
        out["scanned"] += 1
        try:
            digest = file_sha256(p)
        except Exception as e:
            _log(f"hash error {p}: {e!r}")
            out["errors"] += 1
            continue
        rel = str(p.relative_to(SHARED))
        if hashes.get(rel) == digest:
            out["skipped"] += 1
            continue
        meta = index_file(p)
        ok, msg = post_to_mcp(meta)
        if ok:
            hashes[rel] = digest
            out["indexed"] += 1
            _log(f"INDEXED {rel} sha={digest[:12]}")
        else:
            out["errors"] += 1
            _log(f"INDEX FAIL {rel}: {msg}")
    _save_hashes(hashes)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Mercury folder sync — shared-with-hercules → MCP")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=60)
    args = p.parse_args()

    if args.once or not args.watch:
        print(json.dumps(drain_once(), indent=2))
        return 0

    _log(f"mercury_folder_sync starting watch interval={args.interval}s shared={SHARED}")
    while True:
        try:
            results = drain_once()
            if results["indexed"] > 0:
                _log(f"poll: scanned={results['scanned']} indexed={results['indexed']} skipped={results['skipped']}")
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            _log(f"poll error: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
