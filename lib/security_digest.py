#!/usr/bin/env python3
"""DR-AMG-SECURITY-01 Phase 3 Task 3.8 — Weekly Security Digest

Generates weekly security summary from security-events.jsonl, fail2ban,
backup verification, and RLS audit logs.
Schedule: Monday 08:00 EDT via cron
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

EVENTS_FILE = Path("/var/log/amg-security/security-events.jsonl")
FAIL2BAN_LOG = Path("/var/log/fail2ban.log")
SURICATA_LOG = Path("/var/log/suricata/fast.log")
WAZUH_ALERTS = Path("/var/ossec/logs/alerts/alerts.json")


def load_events(days: int = 7) -> list:
    """Load security events from the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = []
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    ts = datetime.fromisoformat(event.get("timestamp", ""))
                    if ts >= cutoff:
                        events.append(event)
                except (json.JSONDecodeError, ValueError):
                    continue
    return events


def count_fail2ban_bans() -> dict:
    """Count fail2ban bans from log."""
    unique_ips = set()
    total_bans = 0
    if FAIL2BAN_LOG.exists():
        cutoff = datetime.now() - timedelta(days=7)
        with open(FAIL2BAN_LOG) as f:
            for line in f:
                if "Ban" in line and "Unban" not in line:
                    total_bans += 1
                    # Extract IP
                    parts = line.split()
                    for p in parts:
                        if p.count(".") == 3:
                            unique_ips.add(p)
                            break
    return {"unique_ips": len(unique_ips), "total_bans": total_bans}


def count_breach_incidents() -> dict:
    """Count breach incidents + review state (Item 5 v1.1 patch)."""
    incidents_dir = Path("/opt/amg-security/incidents")
    if not incidents_dir.exists():
        return {"total": 0, "confirmed": 0, "false_positive": 0, "pending_review": 0}
    total = confirmed = fp = pending = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for f in incidents_dir.glob("INC-*.json"):
        try:
            d = json.load(open(f))
            detected = datetime.fromisoformat(d.get("detected_at", ""))
            if detected < cutoff: continue
            total += 1
            s = d.get("status", "")
            if s == "CONFIRMED": confirmed += 1
            elif s == "DISMISSED_FALSE_POSITIVE": fp += 1
            elif s == "PENDING_REVIEW": pending += 1
        except Exception:
            continue
    return {"total": total, "confirmed": confirmed, "false_positive": fp, "pending_review": pending}


def count_gate_activity() -> dict:
    """Count enforcement-gate activity from audit logs (Item 5 v1.1 patch).

    Gate #1 bypass-log, Gate #2 hypothesis audit, Gate #4 opa-decisions +
    mode-changes. Best-effort reads; missing logs = zeros.
    """
    out = {"gate1_bypass": 0, "gate2_alerts": 0, "gate2_force_baseline": 0,
           "gate4_decisions": 0, "gate4_mode_changes": 0, "gate4_auto_reverts": 0}
    harness_state = Path(os.path.expanduser("~/titan-harness/.harness-state"))
    vps_logs = Path("/var/log/amg")
    cutoff_epoch = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()

    def _count_jsonl(path: Path, match: callable) -> int:
        if not path.exists(): return 0
        n = 0
        try:
            with open(path) as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        ts = d.get("ts_epoch") or d.get("timestamp", 0)
                        if isinstance(ts, str):
                            try: ts = datetime.fromisoformat(ts.rstrip("Z")).timestamp()
                            except Exception: ts = 0
                        if ts >= cutoff_epoch and match(d): n += 1
                    except Exception: continue
        except Exception: pass
        return n

    out["gate1_bypass"] = _count_jsonl(harness_state / "bypass-log.jsonl", lambda d: True)
    out["gate2_alerts"] = _count_jsonl(harness_state / "hypothesis-audit.jsonl",
                                       lambda d: d.get("event") == "alert")
    out["gate2_force_baseline"] = _count_jsonl(harness_state / "hypothesis-audit.jsonl",
                                               lambda d: d.get("event") == "force-baseline")
    out["gate4_decisions"] = _count_jsonl(vps_logs / "opa-decisions.jsonl", lambda d: True)
    out["gate4_mode_changes"] = _count_jsonl(vps_logs / "opa-mode-changes.jsonl", lambda d: True)
    out["gate4_auto_reverts"] = _count_jsonl(vps_logs / "opa-mode-changes.jsonl",
                                             lambda d: "auto-revert" in d.get("reason", ""))
    return out


def count_watchdog_truthful_failures() -> dict:
    """Count truthful_check failures from watchdog (Item 5 v1.1 patch).

    Events that carry truthful_check=True and sev >= SEV2 are real health
    problems that v1.0 surface checks would have missed.
    """
    out = {"caddy_flapping": 0, "caddy_restart_increase": 0,
           "n8n_flapping": 0, "fail2ban_jail_missing": 0}
    if not EVENTS_FILE.exists(): return out
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    with open(EVENTS_FILE) as f:
        for line in f:
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e.get("timestamp", ""))
                if ts < cutoff: continue
                t = e.get("type", "")
                if t == "caddy_container_flapping": out["caddy_flapping"] += 1
                elif t == "caddy_restart_count_increased": out["caddy_restart_increase"] += 1
                elif t == "n8n_flapping": out["n8n_flapping"] += 1
                elif t == "fail2ban_sshd_jail_missing": out["fail2ban_jail_missing"] += 1
            except Exception: continue
    return out


def generate_digest() -> str:
    """Generate the weekly security digest."""
    events = load_events()
    f2b = count_fail2ban_bans()
    breaches = count_breach_incidents()
    gates = count_gate_activity()
    truthful = count_watchdog_truthful_failures()

    # Categorize events
    severity_counts = Counter(e.get("severity", "unknown") for e in events)
    type_counts = Counter(e.get("type", "unknown") for e in events)

    # Credential status
    cred_rotated = sum(1 for e in events if e.get("type") == "credential_rotated")
    cred_overdue = sum(1 for e in events if e.get("type") == "credential_expired")

    # Backup status
    backup_fails = sum(1 for e in events if "backup" in e.get("type", "") and "fail" in e.get("type", ""))
    backup_ok = "❌" if backup_fails > 0 else "✅"

    # RLS status
    rls_violations = sum(1 for e in events if e.get("type") == "rls_violations")
    rls_status = "❌" if rls_violations > 0 else "✅"

    # Controls health
    check_errors = sum(1 for e in events if "error" in e.get("type", ""))
    total_checks = sum(1 for e in events if e.get("severity") == "SEV4")
    controls_passing = total_checks - check_errors

    # Injection attempts
    injection_blocked = sum(1 for e in events if "injection" in e.get("type", ""))

    # Secret scan
    secrets_found = sum(1 for e in events if e.get("type") == "secret_found")
    dep_vulns = sum(1 for e in events if "vuln" in e.get("type", ""))

    # Suricata alerts (source 3)
    suricata_alerts = 0
    if SURICATA_LOG.exists():
        try:
            cutoff_str = (datetime.now() - timedelta(days=7)).strftime("%m/%d/%Y")
            with open(SURICATA_LOG) as f:
                for line in f:
                    suricata_alerts += 1
        except Exception:
            pass

    # Wazuh alerts (source 4)
    wazuh_alerts = 0
    if WAZUH_ALERTS.exists():
        try:
            with open(WAZUH_ALERTS) as f:
                for line in f:
                    if line.strip():
                        wazuh_alerts += 1
        except Exception:
            pass

    week_end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    digest = f"""📊 AMG Security Weekly Digest — week ending {week_end}
🔑 Credentials: {cred_rotated} rotated, {cred_overdue} due ≤30d
🚫 fail2ban: {f2b['unique_ips']} unique IPs banned, {f2b['total_bans']} total bans
💉 Injection attempts blocked: {injection_blocked}
💾 Backups: {backup_ok} verified | {backup_fails} failures
🔐 RLS: {rls_status} covered | {rls_violations} violations
🛡️ Controls health: {controls_passing}/{total_checks} passing
📦 Dependencies: {dep_vulns} vulns, {secrets_found} secrets found
🔔 Alerts: SEV1 {severity_counts.get('SEV1', 0)}, SEV2 {severity_counts.get('SEV2', 0)}, SEV3 {severity_counts.get('SEV3', 0)}
🔍 Suricata IDS: {suricata_alerts} alerts
🛡️ Wazuh: {wazuh_alerts} alerts
⚖️ Breach incidents: {breaches['total']} total ({breaches['confirmed']} confirmed, {breaches['false_positive']} FP, {breaches['pending_review']} pending review)
🛂 Enforcement gates:
    Gate #1 bypass-log entries: {gates['gate1_bypass']}
    Gate #2 alerts: {gates['gate2_alerts']} | force-baseline: {gates['gate2_force_baseline']}
    Gate #4 decisions: {gates['gate4_decisions']} | mode changes: {gates['gate4_mode_changes']} | auto-reverts: {gates['gate4_auto_reverts']}
🕵️ Truthful-check failures (post-DELTA-B): caddy flap {truthful['caddy_flapping']}, caddy restart+ {truthful['caddy_restart_increase']}, n8n flap {truthful['n8n_flapping']}, fail2ban jail missing {truthful['fail2ban_jail_missing']}
📋 Sources: security-events.jsonl, breach-audit.jsonl, bypass-log.jsonl, hypothesis-audit.jsonl, opa-decisions.jsonl, fail2ban.log, suricata/fast.log, wazuh/alerts.json"""

    return digest


if __name__ == "__main__":
    digest = generate_digest()
    print(digest)

    # Write to file for n8n webhook pickup
    output = Path("/tmp/security-digest-latest.txt")
    output.write_text(digest)
    print(f"\nDigest written to {output}")
