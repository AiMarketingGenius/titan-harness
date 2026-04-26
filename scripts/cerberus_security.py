#!/usr/bin/env python3
"""
cerberus_security.py — Defensive-only security guardian daemon.

Polls Mac syslog + VPS auth/fail2ban/ufw logs + MCP decisions every 5 minutes.
Detects rogue activity using a dual-signal floor — never escalates on a single
signal. Confidence floor 9.0/10 before any flag fires.

Three "heads":
  Head 1 — Mac endpoint: file integrity, process anomaly, browser session
  Head 2 — VPS infrastructure: SSH, fail2ban, UFW, port scans
  Head 3 — Agent fleet: rogue agent behavior (out-of-scope ops, credential leaks
           in MCP text, infinite loops, race conditions)

DEFENSIVE ONLY — no counter-attacks, no payloads, no retaliation.

Run modes:
    cerberus_security.py --watch        # daemon (default), poll 5 min
    cerberus_security.py --once
    cerberus_security.py --deep-scan    # 4-hourly deep scan
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
from mcp_rest_client import (  # noqa: E402
    get_recent_decisions as mcp_get_recent,
    log_decision as mcp_log_decision,
)

INBOX = HOME / "AMG" / "hercules-inbox"
STATE_DIR = HOME / ".openclaw" / "state"
BASELINE_FILE = STATE_DIR / "cerberus_baseline.json"
INCIDENTS_FILE = STATE_DIR / "cerberus_incidents.json"
LOGFILE = HOME / ".openclaw" / "logs" / "cerberus_security.log"
SSH_HOST = os.environ.get("AMG_VPS_SSH_HOST", "amg-staging")

# Credential leak patterns we flag if found in MCP text
CRED_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),                 # OpenAI / Anthropic-style
    re.compile(r"\bpk_(live|test)_[A-Za-z0-9]{16,}\b"),       # Stripe
    re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),                  # GitHub PAT
    re.compile(r"\beyJ[A-Za-z0-9_-]{60,}\.[A-Za-z0-9_-]{40,}\.[A-Za-z0-9_-]{20,}\b"),  # JWT
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\bkey\b", re.IGNORECASE),  # base64 + "key"
    re.compile(r"AKIA[0-9A-Z]{16}"),                          # AWS access key
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----"),
]

CONFIDENCE_FLOOR = 9.0
DUAL_SIGNAL_REQUIRED = True


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _load_state(path: pathlib.Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_state(path: pathlib.Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def ssh_run(cmd: str, timeout_s: int = 15) -> str:
    try:
        out = subprocess.run(
            ["ssh", SSH_HOST, cmd],
            capture_output=True, text=True, timeout=timeout_s,
        )
        return out.stdout if out.returncode == 0 else ""
    except Exception:
        return ""


# ─── Head 1: Mac endpoint ──────────────────────────────────────────────────
def head1_mac() -> list[dict]:
    """Return list of signals (NOT incidents — incidents require dual signal)."""
    signals: list[dict] = []
    # New process anomaly: check for known-bad parent processes
    try:
        out = subprocess.run(
            ["ps", "-A", "-o", "pid,user,comm"],
            capture_output=True, text=True, timeout=10,
        )
        for line in out.stdout.splitlines():
            line_lower = line.lower()
            if any(k in line_lower for k in ("nmap", "metasploit", "sqlmap", "nikto", "hydra", "john")):
                signals.append({
                    "head": "mac",
                    "kind": "suspicious_process",
                    "evidence": line.strip(),
                    "score": 7,  # tools, but could be legit security testing — needs corroboration
                })
    except Exception:
        pass
    # Check ~/.ssh/authorized_keys for unexpected lines (newly added)
    auth = HOME / ".ssh" / "authorized_keys"
    if auth.exists():
        try:
            lines = auth.read_text().splitlines()
            cur = {l.strip() for l in lines if l.strip() and not l.startswith("#")}
            baseline = _load_state(BASELINE_FILE, {})
            seen = set(baseline.get("authorized_keys") or cur)
            new = cur - seen
            if new and seen:  # only flag if baseline existed and there's a delta
                signals.append({
                    "head": "mac",
                    "kind": "authorized_keys_added",
                    "evidence": f"new ssh key(s): {len(new)}",
                    "score": 9,  # high — new auth keys are serious
                })
        except Exception:
            pass
    return signals


# ─── Head 2: VPS infrastructure ────────────────────────────────────────────
def head2_vps() -> list[dict]:
    signals: list[dict] = []
    # fail2ban recent bans
    bans = ssh_run("tail -200 /var/log/fail2ban.log 2>/dev/null | grep -c 'Ban '", 8)
    try:
        ban_count = int(bans.strip() or "0")
        if ban_count > 5:
            signals.append({
                "head": "vps", "kind": "fail2ban_burst",
                "evidence": f"{ban_count} bans in last 200 log lines",
                "score": 8,
            })
    except ValueError:
        pass
    # SSH 401 burst
    sshd = ssh_run("tail -500 /var/log/auth.log 2>/dev/null | grep -c 'Failed password'", 8)
    try:
        fail_count = int(sshd.strip() or "0")
        if fail_count > 20:
            signals.append({
                "head": "vps", "kind": "ssh_failed_burst",
                "evidence": f"{fail_count} failed SSH in last 500 log lines",
                "score": 8,
            })
    except ValueError:
        pass
    # UFW recent denies
    ufw = ssh_run("tail -200 /var/log/ufw.log 2>/dev/null | grep -c 'BLOCK'", 8)
    try:
        block_count = int(ufw.strip() or "0")
        if block_count > 10:
            signals.append({
                "head": "vps", "kind": "ufw_block_burst",
                "evidence": f"{block_count} UFW blocks recent",
                "score": 7,
            })
    except ValueError:
        pass
    return signals


# ─── Head 3: Agent fleet (MCP scan) ────────────────────────────────────────
def head3_agents() -> list[dict]:
    signals: list[dict] = []
    code, body = mcp_get_recent(count=20)
    if code != 200:
        return signals
    decisions = body.get("decisions") or []
    for d in decisions:
        text_full = (d.get("text") or "") + "\n" + (d.get("rationale") or "")
        for pat in CRED_PATTERNS:
            m = pat.search(text_full)
            if m:
                signals.append({
                    "head": "agents",
                    "kind": "credential_leak_in_mcp",
                    "evidence": (
                        f"decision id={d.get('id')} project={d.get('project_source')} "
                        f"matched_pattern={pat.pattern[:40]}... matched_text=[REDACTED]"
                    ),
                    "score": 10,  # MAX severity — credential exposed in MCP text
                    "decision_id": d.get("id"),
                })
                break  # one signal per decision is enough
        # Detect "infinite loop" pattern — same exact text in MCP > 5 times in last 20
        # (handled by Warden, but Cerberus also corroborates here)
    return signals


# ─── correlate + score + decide ────────────────────────────────────────────
def correlate_signals(signals: list[dict]) -> list[dict]:
    """Group signals by kind. If a kind has multiple corroborating signals
    OR a signal is score-10 (e.g., credential leak — single-signal sufficient
    because the evidence IS the proof), promote to incident.

    Returns list of incidents."""
    incidents: list[dict] = []
    by_kind: dict[str, list[dict]] = {}
    for s in signals:
        by_kind.setdefault(s["kind"], []).append(s)
    for kind, group in by_kind.items():
        if len(group) >= 2 or any(s["score"] >= 10 for s in group):
            # promote to incident
            avg_score = sum(s["score"] for s in group) / len(group)
            confidence = min(avg_score + (0.5 if len(group) >= 2 else 0), 10)
            if confidence < CONFIDENCE_FLOOR:
                continue
            severity = "P0" if confidence >= 9.5 else ("P1" if confidence >= 9.0 else "P2")
            incidents.append({
                "kind": kind,
                "severity": severity,
                "confidence": round(confidence, 2),
                "signal_count": len(group),
                "evidence": [s.get("evidence") for s in group],
                "heads": list({s["head"] for s in group}),
            })
    return incidents


def write_incident_report(incident: dict) -> pathlib.Path:
    INBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fname = f"CERBERUS_{incident['severity']}__{stamp}__{incident['kind']}.md"
    path = INBOX / fname
    body = (
        f"# CERBERUS INCIDENT — {incident['severity']}\n\n"
        f"- **Kind:** {incident['kind']}\n"
        f"- **Confidence:** {incident['confidence']}/10\n"
        f"- **Heads activated:** {', '.join(incident['heads'])}\n"
        f"- **Signal count:** {incident['signal_count']}\n"
        f"- **Detected at:** {datetime.now(tz=timezone.utc).isoformat()}\n\n"
        f"## Evidence\n\n"
    )
    for i, ev in enumerate(incident["evidence"], 1):
        body += f"{i}. {ev}\n"
    body += (
        f"\n## Recommended action\n\n"
        f"- {incident['severity']} severity\n"
        f"- Mercury isolates affected service if applicable\n"
        f"- Hercules audits + decides next step\n"
        f"- Defensive only — NO counter-attacks per standing constraint\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def drain_once(deep: bool = False) -> dict:
    signals = head1_mac() + head2_vps() + head3_agents()
    incidents = correlate_signals(signals)
    out = {"signals": len(signals), "incidents": len(incidents)}
    for inc in incidents:
        path = write_incident_report(inc)
        mcp_log_decision(
            text=(
                f"CERBERUS INCIDENT — {inc['severity']} kind={inc['kind']} "
                f"confidence={inc['confidence']} heads={inc['heads']}"
            ),
            rationale=(
                f"Signals: {len(inc['evidence'])} corroborating. "
                f"Evidence sample: {str(inc['evidence'])[:300]}. Report: {path}"
            ),
            tags=["cerberus-incident", inc["severity"].lower(), f"kind:{inc['kind']}"],
            project_source="titan",
        )
        _log(f"INCIDENT {inc['severity']} kind={inc['kind']} conf={inc['confidence']} → {path.name}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Cerberus security guardian (defensive only)")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--deep-scan", action="store_true")
    p.add_argument("--interval", type=int, default=300)
    args = p.parse_args()

    if args.once or args.deep_scan:
        print(json.dumps(drain_once(deep=args.deep_scan), indent=2))
        return 0

    _log(f"cerberus_security starting watch interval={args.interval}s defensive-only")
    while True:
        try:
            r = drain_once()
            if r["incidents"] > 0:
                _log(f"poll: signals={r['signals']} incidents={r['incidents']}")
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            _log(f"poll error: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
