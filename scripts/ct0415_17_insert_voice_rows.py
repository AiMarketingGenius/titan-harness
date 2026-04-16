#!/usr/bin/env python3
"""
titan-harness/scripts/ct0415_17_insert_voice_rows.py

Reads manifest.json produced by ct0415_17_voice_library_gen.py and upserts
one row per (agent_id, message_type, client_name) into public.agent_voice_library.

audio_url is constructed as:
  https://ops.aimarketinggenius.io/voices/<agent>/<message_type>.mp3

which the atlas-web Caddy route maps to /opt/titan-harness/services/atlas-web/voices/
where the mp3 files land after rsync.

Run:
  python3 ct0415_17_insert_voice_rows.py \
    --manifest ~/titan-harness/out/voice-library/manifest.json \
    --audio-base-url https://ops.aimarketinggenius.io/voices

Uses Supabase service-role key (not PAT) — reads from ~/.titan-env if not in env.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


AGENT_ROLES = {
    "alex":   "account manager",
    "maya":   "content lead",
    "jordan": "reputation manager",
    "sam":    "SEO strategist",
    "riley":  "strategic lead",
    "nadia":  "onboarding specialist",
    "lumina": "CRO expert",
}


def _load_env_from_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _supabase_upsert(url: str, key: str, rows: list[dict]) -> dict:
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/agent_voice_library?on_conflict=agent_id,message_type,client_name",
        data=body, method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"ok": True, "status": r.getcode(), "body": r.read().decode()[:2000]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode()[:2000]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--audio-base-url", required=True,
                   help="Public HTTPS base for the voices/ tree (no trailing slash)")
    p.add_argument("--supabase-url", default=None)
    p.add_argument("--service-key", default=None)
    args = p.parse_args()

    _load_env_from_file(Path.home() / ".titan-env")
    url = args.supabase_url or os.environ.get("SUPABASE_URL", "").strip()
    key = args.service_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        sys.stderr.write("ERR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required (env or ~/.titan-env)\n")
        return 2

    manifest = json.loads(args.manifest.read_text())
    client_name = manifest.get("client_name", "your business")

    rows = []
    for agent_id, agent in manifest.get("agents", {}).items():
        voice = agent.get("voice", "unknown")
        tts = agent.get("tts", "unknown")
        for message_type, f in agent.get("files", {}).items():
            transcript = f.get("transcript") or ""
            audio_url = f"{args.audio_base_url.rstrip('/')}/{agent_id}/{message_type}.mp3"
            row = {
                "agent_id": agent_id,
                "agent_role": AGENT_ROLES.get(agent_id, "agent"),
                "voice_profile": voice,
                "tts_engine": tts,
                "message_type": message_type,
                "transcript_text": transcript or f"(transcript pending for {agent_id} {message_type})",
                "client_name": client_name,
                "audio_url": audio_url,
                "audio_bytes": f.get("bytes"),
                "audio_duration_ms": f.get("duration_ms"),
                "status": "pending_regen" if f.get("pending") else "active",
                "pending_reason": f.get("pending"),
                "generated_by": "ct0415_17_voice_library_gen.py",
            }
            rows.append(row)

    print(f"[upsert] {len(rows)} rows to agent_voice_library@{url}")
    result = _supabase_upsert(url, key, rows)
    if result["ok"]:
        ret = json.loads(result["body"]) if result["body"].strip().startswith("[") else []
        print(f"[upsert] OK status={result['status']} rows_returned={len(ret)}")
        return 0
    else:
        print(f"[upsert] FAILED status={result['status']}: {result['body'][:500]}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
