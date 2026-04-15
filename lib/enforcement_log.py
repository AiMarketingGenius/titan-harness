"""
titan-harness/lib/enforcement_log.py

Gate #4 v1.4 — MCP log_decision helper for enforcement-gate trips.

Every policy decision (allow, deny, warn) emitted by the OPA guard OR by
the review_gate.py / escape-hatch / pre-proposal gate chain flows through
this module so the event lands in MCP with project_source='EOM' and
tag='enforcement_gate'. Downstream EOM can query decisions by tag to build
an audit timeline without tailing per-host log files.

Public API:
    log_gate_trip(event_type, cmd, decision, mode, details=None) -> bool
    log_mode_change(from_mode, to_mode, actor, reason) -> bool

Both are best-effort. Failure is printed to stderr and returned as False.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT", "http://memory.aimarketinggenius.io")
MCP_PROJECT_SOURCE = "EOM"
DEFAULT_TAG = "enforcement_gate"
POLICY_VERSION = "v1.4"
_TIMEOUT_SEC = 10

ALLOWED_EVENT_TYPES = {"allow", "deny", "warn", "mode_change", "preflight_block"}
ALLOWED_DECISIONS = {"auto-continue", "escalate", "allowed", "denied", "warned"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _post_decision(payload: dict[str, Any]) -> bool:
    try:
        body = json.dumps({"action": "log_decision", "data": payload}).encode("utf-8")
        req = urllib.request.Request(
            f"{MCP_ENDPOINT}/log_decision",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=_TIMEOUT_SEC)  # noqa: S310 — MCP is trusted
        return True
    except Exception as exc:  # pragma: no cover — best-effort
        print(f"[enforcement_log] WARNING: MCP log failed (non-fatal): {exc}", file=sys.stderr)
        return False


def log_gate_trip(
    event_type: str,
    cmd: str,
    decision: str,
    mode: str,
    details: Optional[dict[str, Any]] = None,
) -> bool:
    """
    Log a Gate #4 OPA policy decision to MCP.

    event_type  — "allow" | "deny" | "warn" | "preflight_block"
    cmd         — the command that triggered the scope match (truncate safely)
    decision    — short human-readable summary (e.g. "allowed", "denied", "warned")
    mode        — "audit" | "enforce" | "reverting" | "auto-reverted"
    details     — optional dict with policy inputs (baseline_sha, incident_id,
                  pre_proposal_hash, escape_hatch_all_green, chrony_synced, etc.)

    Returns True on successful MCP post, False otherwise.
    """
    if event_type not in ALLOWED_EVENT_TYPES:
        print(
            f"[enforcement_log] rejected unknown event_type={event_type!r}; "
            f"allowed: {sorted(ALLOWED_EVENT_TYPES)}",
            file=sys.stderr,
        )
        return False

    # Truncate cmd so a single pathological log line can't blow MCP row size.
    safe_cmd = (cmd or "")[:500]

    payload = {
        "project_source": MCP_PROJECT_SOURCE,
        "tags": [DEFAULT_TAG, f"policy_{POLICY_VERSION}", event_type],
        "text": (
            f"enforcement_gate {event_type} in {mode} mode: "
            f"{decision} for cmd={safe_cmd!r}"
        ),
        "rationale": json.dumps(
            {
                "policy_version": POLICY_VERSION,
                "event_type": event_type,
                "mode": mode,
                "decision": decision,
                "cmd": safe_cmd,
                "details": details or {},
                "ts_utc": _now_iso(),
            }
        ),
    }
    return _post_decision(payload)


def log_mode_change(from_mode: str, to_mode: str, actor: str, reason: str) -> bool:
    """
    Log a mode transition (audit↔enforce, or enforce→auto-reverted) to MCP.

    actor  — the identity that triggered the change ("titan", "solon",
             "auto-revert-tick", "install-gate4-opa.sh")
    reason — short free-text reason / incident ID / ack nonce
    """
    payload = {
        "project_source": MCP_PROJECT_SOURCE,
        "tags": [DEFAULT_TAG, f"policy_{POLICY_VERSION}", "mode_change"],
        "text": f"enforcement_gate mode_change: {from_mode} -> {to_mode} by {actor}",
        "rationale": json.dumps(
            {
                "policy_version": POLICY_VERSION,
                "event_type": "mode_change",
                "from_mode": from_mode,
                "to_mode": to_mode,
                "actor": actor,
                "reason": reason,
                "ts_utc": _now_iso(),
            }
        ),
    }
    return _post_decision(payload)


def main() -> int:
    """
    CLI entrypoint: `python3 lib/enforcement_log.py <event_type> <cmd> <decision> <mode> [details_json]`

    Designed to be called from shell hooks (opa-guard.sh, pre-proposal-gate.sh,
    harness-conflict-check.sh) without requiring a Python import path.
    """
    import argparse

    ap = argparse.ArgumentParser(description="MCP logger for Gate #4 v1.4 enforcement trips")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("trip", help="log a gate trip (allow/deny/warn/preflight_block)")
    t.add_argument("--event-type", required=True, choices=sorted(ALLOWED_EVENT_TYPES - {"mode_change"}))
    t.add_argument("--cmd", required=True)
    t.add_argument("--decision", required=True)
    t.add_argument("--mode", required=True)
    t.add_argument("--details-json", default=None, help="optional JSON blob")

    m = sub.add_parser("mode-change", help="log a mode transition")
    m.add_argument("--from-mode", required=True)
    m.add_argument("--to-mode", required=True)
    m.add_argument("--actor", required=True)
    m.add_argument("--reason", required=True)

    args = ap.parse_args()

    if args.cmd == "trip":
        details = None
        if args.details_json:
            try:
                details = json.loads(args.details_json)
            except json.JSONDecodeError as exc:
                print(f"[enforcement_log] bad --details-json: {exc}", file=sys.stderr)
                return 2
        ok = log_gate_trip(args.event_type, args.cmd, args.decision, args.mode, details)
        return 0 if ok else 1

    if args.cmd == "mode-change":
        ok = log_mode_change(args.from_mode, args.to_mode, args.actor, args.reason)
        return 0 if ok else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
