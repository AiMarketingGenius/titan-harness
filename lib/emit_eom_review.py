"""emit_eom_review.py — emit an EOM review-needed event to MCP.

Usage (Titan):
    python3 lib/emit_eom_review.py \
        --owner titan \
        --task-id CT-0421-06 \
        --objective "Deploy closed-loop notifier" \
        --scope "lib/emit_eom_review.py, eom_notifier.lua, n8n workflow" \
        --criteria "n8n detects event; Hammerspoon injects packet into claude.ai tab" \
        --proof "test_eom_dry_run.json written to ~/achilles-session/eom-reviews/" \
        --risks "n8n Supabase credentials; Safari tab focus race" \
        --decision "Review send path — approve or add constraints before Titan ships"

Usage (Achilles shorthand):
    python3 lib/emit_eom_review.py --owner achilles --task-id <id> --objective "..." \
        --decision "..."

All other fields default to safe placeholders.

Secret redaction: bearer tokens, service keys, raw credentials are stripped
from all string fields before the event is written. This is enforced at write
time, not left to callers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Secret redaction — scrub before any field lands in MCP
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),  # JWT
    re.compile(r"sk[-_][a-zA-Z0-9\-]{20,}"),  # OpenAI/Anthropic style
    re.compile(r"sbp_[a-zA-Z0-9]{40,}"),       # Supabase service key prefix
    re.compile(r"[a-f0-9]{40,64}"),             # raw hex tokens (sha256+)
]

def _redact(s: str) -> str:
    if not isinstance(s, str):
        return s
    for pat in _SECRET_PATTERNS:
        s = pat.sub("[REDACTED]", s)
    return s

def redact_packet(packet: dict) -> dict:
    return {k: _redact(v) if isinstance(v, str) else v for k, v in packet.items()}

# ---------------------------------------------------------------------------
# Supabase env loading
# ---------------------------------------------------------------------------

def _load_env() -> tuple[str, str]:
    def load_file(path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v

    load_file(os.path.expanduser("~/.titan-env"))
    load_file(os.path.expanduser("~/.env"))

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return url, key

# ---------------------------------------------------------------------------
# Core emit
# ---------------------------------------------------------------------------

def emit_eom_review(
    *,
    owner: str,
    task_id: str,
    objective: str,
    scope: str = "see task",
    acceptance_criteria: str = "see task",
    proof: str = "see task",
    open_risks: str = "none listed",
    required_decision: str = "review and approve or add constraints",
    ttl_hours: int = 4,
) -> dict:
    """Write an EOM review-needed event to MCP op_decisions."""
    url, key = _load_env()
    if not url or not key:
        print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(2)

    packet_id = str(uuid.uuid4())[:8]
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build the compact review packet text (what EOM will see)
    packet_text = (
        f"EOM REVIEW REQUEST — {ts}\n"
        f"owner={owner} task_id={task_id} packet_id={packet_id}\n"
        f"expires_at={expires_at} (4h TTL — stale after this)\n\n"
        f"OBJECTIVE\n{objective}\n\n"
        f"SCOPE\n{scope}\n\n"
        f"ACCEPTANCE CRITERIA\n{acceptance_criteria}\n\n"
        f"PROOF\n{proof}\n\n"
        f"OPEN RISKS\n{open_risks}\n\n"
        f"REQUIRED DECISION\n{required_decision}"
    )

    raw_payload = {
        "owner": owner,
        "task_id": task_id,
        "objective": objective,
        "scope": scope,
        "acceptance_criteria": acceptance_criteria,
        "proof": proof,
        "open_risks": open_risks,
        "required_decision": required_decision,
        "packet_text": packet_text,
        "expires_at": expires_at,
    }
    clean = redact_packet(raw_payload)

    decision_text = (
        f"EOM REVIEW NEEDED owner={owner} task_id={task_id} packet_id={packet_id} "
        f"expires_at={expires_at} | "
        f"objective: {clean['objective'][:120]} | "
        f"decision: {clean['required_decision'][:120]} | "
        f"packet_id={packet_id}"
    )

    body = json.dumps({
        "decision_text": decision_text,
        "tags": [
            "eom_review_needed",
            f"eom_packet_id-{packet_id}",
            f"owner-{owner}",
            f"task-{task_id}",
        ],
        "project_source": owner,
        "decision_type": "review_request",
    }).encode()

    req = urllib.request.Request(
        f"{url}/rest/v1/op_decisions",
        data=body,
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())

    row = result[0] if isinstance(result, list) else result
    row_id = row.get("id", "unknown")

    # Also write compact packet to local artifacts dir for Achilles visibility
    artifacts_dir = os.path.expanduser("~/achilles-session/eom-reviews")
    os.makedirs(artifacts_dir, exist_ok=True)
    artifact_path = os.path.join(artifacts_dir, f"eom_review_{packet_id}.json")
    with open(artifact_path, "w") as f:
        json.dump({
            "mcp_id": row_id,
            "packet_id": packet_id,
            "owner": owner,
            "task_id": task_id,
            "expires_at": expires_at,
            "status": "pending",
            "emitted_at": ts,
            "packet_text": clean["packet_text"],
        }, f, indent=2)

    print(f"ok: mcp_id={row_id} packet_id={packet_id} artifact={artifact_path}")
    return {"mcp_id": row_id, "packet_id": packet_id, "artifact": artifact_path}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Emit EOM review-needed event to MCP")
    p.add_argument("--owner", required=True, choices=["titan", "achilles", "eom"])
    p.add_argument("--task-id", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--scope", default="see task")
    p.add_argument("--criteria", default="see task", dest="acceptance_criteria")
    p.add_argument("--proof", default="see task")
    p.add_argument("--risks", default="none listed", dest="open_risks")
    p.add_argument("--decision", default="review and approve or add constraints",
                   dest="required_decision")
    p.add_argument("--ttl-hours", type=int, default=4)
    args = p.parse_args()

    emit_eom_review(
        owner=args.owner,
        task_id=args.task_id,
        objective=args.objective,
        scope=args.scope,
        acceptance_criteria=args.acceptance_criteria,
        proof=args.proof,
        open_risks=args.open_risks,
        required_decision=args.required_decision,
        ttl_hours=args.ttl_hours,
    )


if __name__ == "__main__":
    main()
