"""Mobile Command v2 session lifecycle module.

Implements the LIFECYCLE PROTOCOL v1 per Solon directive 2026-04-18 (MCP
decision tag `lifecycle-protocol-v1`):

- Rule 1: incremental heartbeat (crash protection, 15-min OR 3-tool-call OR
  post-commit whichever fires first)
- Rule 2: graceful shutdown (proactive MCP save + ok-to-close output)
- Rule 3: auto-resume (fresh session reads RESTART_HANDOFF + continues without prompt)

This module is the BACKEND helper that the mobile PWA surfaces via 4
endpoints (wired in Step 6.3 atlas_api.py mount):
- POST /api/mobile/claude/stop   → calls graceful_shutdown()
- POST /api/mobile/claude/start  → spawns session + runs auto_resume()
- POST /api/mobile/claude/reset  → graceful_shutdown() + fresh-spawn + auto_resume()
- GET  /api/mobile/claude/status → reads latest session-heartbeat from MCP

Session-spawn / session-kill / fresh-boot mechanics (actual subprocess control
of `claude` CLI) are SCOPED OUT of this module — returned as stubs that log to
MCP for operator-visible observability. A follow-up module (`lib/claude_cli_ctl.py`)
will implement actual process control after the architectural shape is proven.
This keeps Step 6.3 atomic: endpoints mount + protocol routines wire + MCP
source-of-truth-for-status, without coupling to the complex CLI-spawn subsystem.

MCP integration: calls the MCP memory server at the URL defined in
MCP_BASE_URL env var (default memory.aimarketinggenius.io). Uses httpx for
thin-wrapper HTTP calls to the MCP /decisions endpoint.

Dependencies: httpx (already a transitive dep of atlas_api.py via existing
lib/llm_client.py).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # tolerated for import-time; error at call if missing


MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "https://memory.aimarketinggenius.io").rstrip("/")
MCP_PROJECT_ID = os.environ.get("MCP_PROJECT_ID", "EOM")
MCP_TIMEOUT = 30


class MobileLifecycleError(Exception):
    """Base error for lifecycle operations."""


class MCPUnavailable(MobileLifecycleError):
    """MCP memory server unreachable — graceful degradation path needed."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HeartbeatPayload:
    active_step: str              # e.g. "6.3 atlas_api.py router mount"
    last_commit_hash: str         # short SHA, e.g. "2b711ae"
    tree_clean: bool              # from `git status`
    next_action: str              # 1-2 lines
    tokens_remaining: int | None  # best-effort estimate
    in_flight: str | None         # what's currently mid-execution

    def to_log_text(self) -> str:
        """Render as compact single-paragraph decision text."""
        lines = [
            f"HEARTBEAT {_now_iso()}",
            f"step: {self.active_step}",
            f"commit: {self.last_commit_hash}",
            f"tree: {'clean' if self.tree_clean else 'dirty'}",
            f"next: {self.next_action}",
        ]
        if self.tokens_remaining is not None:
            lines.append(f"tokens: {self.tokens_remaining}")
        if self.in_flight:
            lines.append(f"in_flight: {self.in_flight}")
        return " | ".join(lines)


@dataclass(frozen=True)
class ShutdownPayload:
    step_status: str    # "6.2 shipped, 6.3 pending"
    commit_hash: str
    next_action: str
    tokens_remaining: int | None

    def to_output_text(self) -> str:
        """Render as the EXACT spec-mandated operator-visible output per Rule 2."""
        lines = [
            "✅ MCP SAVED — safe to /compact, close, or power down.",
            f" Final state: {self.step_status}",
            f" Commit: {self.commit_hash}",
            f" Next action: {self.next_action}",
        ]
        if self.tokens_remaining is not None:
            lines.append(f" Tokens: {self.tokens_remaining} remaining")
        else:
            lines.append(" Tokens: (not measured)")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP HTTP thin-wrapper
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _require_httpx() -> None:
    if httpx is None:
        raise MobileLifecycleError("httpx package not installed — pip install httpx")


def _mcp_log_decision(text: str, tags: list[str]) -> dict[str, Any]:
    """Post a decision to the MCP memory server.

    Raises MCPUnavailable on network / 5xx errors.
    """
    _require_httpx()
    url = f"{MCP_BASE_URL}/api/decisions"
    payload = {
        "project_source": "titan",
        "text": text,
        "tags": tags,
    }
    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
            r = client.post(url, json=payload)
            if r.status_code >= 500:
                raise MCPUnavailable(f"MCP 5xx: {r.status_code}")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as exc:
        raise MCPUnavailable(f"MCP HTTP error: {exc}") from exc


def _mcp_get_recent_decisions(count: int = 10, tag_filter: str | None = None) -> list[dict[str, Any]]:
    """Fetch recent MCP decisions. Optionally filter by tag substring."""
    _require_httpx()
    url = f"{MCP_BASE_URL}/api/decisions/recent"
    params = {"count": count}
    if tag_filter:
        params["tag"] = tag_filter
    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json().get("decisions", [])
    except httpx.HTTPError as exc:
        raise MCPUnavailable(f"MCP HTTP error: {exc}") from exc


# ---------------------------------------------------------------------------
# Rule 1 — Heartbeat
# ---------------------------------------------------------------------------

def heartbeat(payload: HeartbeatPayload) -> dict[str, Any]:
    """Log a session-heartbeat decision to MCP.

    Fire this at whichever comes first:
    - Every 15 min of session elapsed time (caller must track its own timer)
    - Every 3 completed tool-call sequences
    - After any git commit

    Keep the payload COMPACT per Rule 1. If this fails, the session-heartbeat
    silently degrades — don't crash the caller just because MCP is flaky.
    """
    try:
        return _mcp_log_decision(
            text=payload.to_log_text(),
            tags=["session-heartbeat", f"step-{payload.active_step.split()[0]}"],
        )
    except MCPUnavailable as exc:
        # Log locally to a fallback file so the heartbeat isn't lost.
        _write_fallback_heartbeat(payload, reason=str(exc))
        return {"status": "mcp_unavailable", "fallback_written": True}


def _write_fallback_heartbeat(payload: HeartbeatPayload, reason: str) -> None:
    """When MCP is unreachable, spool heartbeats to a local file so they can
    be replayed on MCP recovery."""
    path = os.environ.get(
        "TITAN_HEARTBEAT_FALLBACK",
        "/var/log/titan-heartbeat-fallback.log",
    )
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps({
                    "ts": _now_iso(),
                    "reason": reason,
                    "payload": payload.to_log_text(),
                }) + "\n"
            )
    except OSError:
        # Last-resort silent fail — heartbeat is best-effort.
        pass


# ---------------------------------------------------------------------------
# Rule 2 — Graceful shutdown
# ---------------------------------------------------------------------------

def graceful_shutdown(payload: ShutdownPayload, trigger: str) -> dict[str, Any]:
    """Log a RESTART_HANDOFF decision to MCP + return operator-visible output.

    `trigger` is the shutdown cause — one of:
    - "operator_phrase" (Solon said done/sleep/stop/compact/etc.)
    - "token_ceiling" (crossed 75K remaining)
    - "step_complete_safe" (major step with safe-restart flag)
    - "mobile_stop_endpoint" (POST /api/mobile/claude/stop called)

    Returns dict with the EXACT output text Rule 2 mandates + MCP response.
    If MCP is unavailable, fallback-file writes the handoff payload.
    """
    decision_text = (
        f"RESTART_HANDOFF {_now_iso()} — trigger: {trigger}. "
        f"Final state: {payload.step_status}. "
        f"Commit: {payload.commit_hash}. "
        f"Next action: {payload.next_action}. "
        f"Tokens remaining: {payload.tokens_remaining if payload.tokens_remaining is not None else 'unmeasured'}."
    )
    tags = [
        "RESTART_HANDOFF",
        "safe-restart-eligible",
        f"shutdown-trigger-{trigger}",
        f"commit-{payload.commit_hash}",
    ]
    try:
        mcp_result = _mcp_log_decision(text=decision_text, tags=tags)
        mcp_ok = True
    except MCPUnavailable as exc:
        _write_fallback_heartbeat(
            HeartbeatPayload(
                active_step=payload.step_status,
                last_commit_hash=payload.commit_hash,
                tree_clean=True,
                next_action=payload.next_action,
                tokens_remaining=payload.tokens_remaining,
                in_flight=f"graceful_shutdown trigger={trigger}",
            ),
            reason=f"mcp_down_during_shutdown: {exc}",
        )
        mcp_result = {"error": str(exc)}
        mcp_ok = False

    return {
        "output": payload.to_output_text(),
        "trigger": trigger,
        "mcp_logged": mcp_ok,
        "mcp_result": mcp_result,
    }


# ---------------------------------------------------------------------------
# Rule 3 — Auto-resume helpers
# ---------------------------------------------------------------------------

def find_latest_handoff() -> dict[str, Any] | None:
    """Fetch the most recent RESTART_HANDOFF decision from MCP, if any.

    Returns the decision dict (with parsed tags, text, timestamp) or None if
    no handoff found in the recent window.
    """
    try:
        decisions = _mcp_get_recent_decisions(count=20)
    except MCPUnavailable:
        return None

    for dec in decisions:
        tags = dec.get("tags") or []
        if "RESTART_HANDOFF" in tags or "safe-restart-eligible" in tags:
            return dec
    return None


def latest_heartbeat() -> dict[str, Any] | None:
    """Fetch the most recent session-heartbeat decision from MCP.

    Used by the mobile status endpoint (GET /api/mobile/claude/status) to
    answer "where is Claude right now?"
    """
    try:
        decisions = _mcp_get_recent_decisions(count=10, tag_filter="session-heartbeat")
    except MCPUnavailable:
        return None

    if not decisions:
        return None
    return decisions[0]  # most-recent-first


# ---------------------------------------------------------------------------
# Mobile endpoint thin routines (delegated from atlas_api.py handlers)
# ---------------------------------------------------------------------------

def mobile_claude_status() -> dict[str, Any]:
    """GET /api/mobile/claude/status handler — reads MCP latest heartbeat.

    Response shape:
    {
        "status": "active" | "idle" | "unknown",
        "last_heartbeat": {ts, text, tags} | null,
        "last_handoff": {ts, text, tags} | null,
        "mcp_reachable": bool
    }
    """
    try:
        heartbeat_dec = latest_heartbeat()
        handoff_dec = find_latest_handoff()
        mcp_reachable = True
    except Exception:  # defensive; latest_heartbeat already swallows MCPUnavailable
        heartbeat_dec = None
        handoff_dec = None
        mcp_reachable = False

    now = _dt.datetime.now(_dt.timezone.utc)
    status = "unknown"
    if heartbeat_dec:
        ts_str = heartbeat_dec.get("created_at") or heartbeat_dec.get("ts")
        try:
            hb_time = _dt.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            age_seconds = (now - hb_time).total_seconds()
            # Heartbeat cadence = 15 min. Within 20 min = active; older = idle.
            if age_seconds < 20 * 60:
                status = "active"
            else:
                status = "idle"
        except (TypeError, ValueError):
            status = "unknown"

    return {
        "status": status,
        "last_heartbeat": heartbeat_dec,
        "last_handoff": handoff_dec,
        "mcp_reachable": mcp_reachable,
        "queried_at": now.isoformat(),
    }


def mobile_claude_stop(operator_id: str, reason: str = "mobile_stop_endpoint") -> dict[str, Any]:
    """POST /api/mobile/claude/stop handler — triggers Rule 2 graceful shutdown.

    This is a STUB at Step 6.3: logs the stop-request to MCP (so an operator
    watching the status endpoint sees the stop), but does NOT actually kill
    a running claude CLI process — that's follow-up Step 6.3-b (lib/claude_cli_ctl.py).

    The real CLI-kill mechanism will: find the in-flight claude process via
    systemd or pid-file, send SIGTERM, wait for orderly MCP-save, then log
    the RESTART_HANDOFF. Until that ships, this endpoint logs the intent
    + returns the expected shape.
    """
    payload = ShutdownPayload(
        step_status="mobile_stop_request_received",
        commit_hash="<unknown-stub>",
        next_action="await lib/claude_cli_ctl.py implementation for actual process control",
        tokens_remaining=None,
    )
    result = graceful_shutdown(payload, trigger=reason)
    return {
        "action": "stop_requested",
        "operator_id": operator_id,
        "stub_note": "process control not implemented yet — logged to MCP only",
        **result,
    }


def mobile_claude_start(operator_id: str) -> dict[str, Any]:
    """POST /api/mobile/claude/start handler — spawns a fresh claude session.

    STUB at Step 6.3: returns expected shape + MCP log, actual spawn in 6.3-b.
    """
    try:
        _mcp_log_decision(
            text=f"MOBILE_START requested by operator {operator_id} at {_now_iso()}. Stub handler — actual spawn pending lib/claude_cli_ctl.py.",
            tags=["mobile-start-request", f"operator-{operator_id}"],
        )
        mcp_ok = True
    except MCPUnavailable:
        mcp_ok = False

    return {
        "action": "start_requested",
        "operator_id": operator_id,
        "stub_note": "spawn not implemented yet — logged to MCP only",
        "mcp_logged": mcp_ok,
    }


def mobile_claude_reset(operator_id: str) -> dict[str, Any]:
    """POST /api/mobile/claude/reset handler — stop + fresh-spawn + auto-resume.

    STUB at Step 6.3: logs intent, returns expected shape.
    """
    stop_result = mobile_claude_stop(operator_id, reason="mobile_reset_stop_phase")
    start_result = mobile_claude_start(operator_id)
    return {
        "action": "reset_requested",
        "operator_id": operator_id,
        "stub_note": "reset not implemented yet — stop + start stubs logged to MCP",
        "stop_phase": stop_result,
        "start_phase": start_result,
    }


# ---------------------------------------------------------------------------
# Self-test (fast smoke — exercises payload rendering + fallback file path)
# ---------------------------------------------------------------------------

def _self_test() -> int:
    passed = 0
    failed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ok  {name}")
        else:
            failed += 1
            print(f"  FAIL {name}")

    # 1) HeartbeatPayload renders compact single-line
    hb = HeartbeatPayload(
        active_step="6.3 router mount",
        last_commit_hash="2b711ae",
        tree_clean=True,
        next_action="mount auth + lifecycle endpoints",
        tokens_remaining=140_000,
        in_flight="atlas_api.py edit",
    )
    line = hb.to_log_text()
    check("heartbeat renders as single line", "\n" not in line)
    check("heartbeat includes step", "step: 6.3 router mount" in line)
    check("heartbeat includes commit", "commit: 2b711ae" in line)
    check("heartbeat includes tree state", "tree: clean" in line)
    check("heartbeat includes tokens", "tokens: 140000" in line)

    # 2) ShutdownPayload renders exact Rule-2 output format
    sd = ShutdownPayload(
        step_status="6.2 shipped, 6.3 pending",
        commit_hash="2b711ae",
        next_action="atlas_api.py router mount",
        tokens_remaining=120_000,
    )
    out = sd.to_output_text()
    check("shutdown output starts with MCP SAVED banner", out.startswith("✅ MCP SAVED"))
    check("shutdown output contains Final state line", "Final state: 6.2 shipped, 6.3 pending" in out)
    check("shutdown output contains Commit line", "Commit: 2b711ae" in out)
    check("shutdown output contains Tokens line", "Tokens: 120000 remaining" in out)

    # 3) MCPUnavailable is a subclass of MobileLifecycleError
    check("MCPUnavailable inherits MobileLifecycleError",
          issubclass(MCPUnavailable, MobileLifecycleError))

    # 4) Fallback heartbeat path environment handling
    os.environ["TITAN_HEARTBEAT_FALLBACK"] = "/tmp/titan-heartbeat-test.log"
    try:
        os.remove("/tmp/titan-heartbeat-test.log")
    except FileNotFoundError:
        pass
    _write_fallback_heartbeat(hb, reason="self-test")
    check("fallback file created on write",
          os.path.exists("/tmp/titan-heartbeat-test.log"))
    with open("/tmp/titan-heartbeat-test.log") as f:
        fallback_line = f.read()
    check("fallback file contains reason", "self-test" in fallback_line)
    check("fallback file contains payload", "2b711ae" in fallback_line)
    os.remove("/tmp/titan-heartbeat-test.log")

    print()
    print(f"TOTAL: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
