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


def generate_digest() -> str:
    """Generate the weekly security digest."""
    events = load_events()
    f2b = count_fail2ban_bans()

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
📋 Sources: security-events.jsonl, fail2ban.log, suricata/fast.log, wazuh/alerts.json"""

    return digest


if __name__ == "__main__":
    digest = generate_digest()
    print(digest)

    # Write to file for n8n webhook pickup
    output = Path("/tmp/security-digest-latest.txt")
    output.write_text(digest)
    print(f"\nDigest written to {output}")
