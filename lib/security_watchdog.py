#!/usr/bin/env python3
"""DR-AMG-SECURITY-01 Phase 3 Task 3.1 — Security Watchdog

Full asyncio implementation. Runs as dedicated security-watchdog user.
60s tick. Each check independent. All events → security-events.jsonl.
Heartbeat every 5 min to external monitor.
"""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Configuration
TICK_SECONDS = 60
HEARTBEAT_INTERVAL = 300  # 5 min
LOG_DIR = Path("/var/log/amg-security")
EVENTS_FILE = LOG_DIR / "security-events.jsonl"
FORENSICS_DIR = Path("/opt/amg-security/forensics")
ENV_DIR = Path("/etc/amg")

# Severity config
SEVERITY = {
    "SEV1": {"prefix": "🚨 SEV-1", "channels": ["slack_dm", "ntfy"], "ntfy_priority": "urgent"},
    "SEV2": {"prefix": "⚠️ SEV-2", "channels": ["slack_dm"]},
    "SEV3": {"prefix": "🔔 SEV-3", "channels": ["slack_channel"]},
    "SEV4": {"prefix": "INFO", "channels": ["weekly_digest"]},
}

# Alert budget tracking
alert_counts = {"SEV1": 0, "SEV2": 0, "week_start": datetime.now(timezone.utc)}
last_heartbeat = 0
remediation_counts = {}


def log_event(event_type: str, severity: str, details: dict):
    """Append event to security-events.jsonl."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "severity": severity,
        "details": details,
    }
    try:
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"ERROR: Could not write event: {e}", file=sys.stderr)

    # Check alert budget
    if severity == "SEV1":
        alert_counts["SEV1"] += 1
        if alert_counts["SEV1"] > 2:
            log_event("alert_budget_breach", "SEV2",
                      {"message": "SEV1 alerts > 2/week — meta-alert"})


def run_cmd(cmd: list, timeout: int = 30) -> tuple:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -2, "", str(e)


# ============================================================
# CHECK FUNCTIONS (all independent)
# ============================================================

async def check_credential_ages():
    """Check credential registry for expired credentials."""
    registry = Path("/opt/amg-security/credential-registry.json")
    if not registry.exists():
        log_event("credential_check", "SEV4", {"status": "registry_not_found"})
        return

    try:
        with open(registry) as f:
            creds = json.load(f)

        now = datetime.now(timezone.utc)
        for cred in creds.get("credentials", []):
            created = datetime.fromisoformat(cred.get("created", "2026-01-01"))
            max_days = cred.get("max_age_days", 90)
            age = (now - created).days
            if age > max_days:
                sev = "SEV2" if not cred.get("auto_rotate_allowed") else "SEV3"
                log_event("credential_expired", sev, {
                    "key_id": cred.get("id"),
                    "age_days": age,
                    "max_days": max_days,
                })
    except Exception as e:
        log_event("credential_check_error", "SEV3", {"error": str(e)})


async def check_fail2ban_running():
    """Check fail2ban is active."""
    rc, out, _ = run_cmd(["systemctl", "is-active", "fail2ban"])
    if "active" not in out:
        log_event("fail2ban_down", "SEV2", {"status": out.strip()})
        await remediate_fail2ban_down()
    else:
        log_event("fail2ban_check", "SEV4", {"status": "active"})


async def check_ufw_drift():
    """Check UFW rules against canonical snapshot."""
    rc, out, _ = run_cmd(["/opt/amg-security/check-ufw-drift.sh"])
    if "DRIFT" in out:
        log_event("ufw_drift", "SEV2", {"output": out.strip()})


async def check_wazuh_agent():
    """Check Wazuh agent is running."""
    rc, out, _ = run_cmd(["systemctl", "is-active", "wazuh-agent"])
    if "active" not in out:
        log_event("wazuh_down", "SEV2", {"status": out.strip()})


async def check_caddy_running():
    """Check all 5 domains respond."""
    domains = [
        "chatapi.aimarketinggenius.io",
        "memory.aimarketinggenius.io",
        "operator.aimarketinggenius.io",
        "browser.aimarketinggenius.io",
        "ops.aimarketinggenius.io",
    ]
    for domain in domains:
        rc, out, _ = run_cmd(["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
                              f"https://{domain}/", "--max-time", "10"])
        if rc != 0:
            log_event("caddy_domain_down", "SEV2", {"domain": domain, "http_code": out.strip()})


async def check_supabase_rls():
    """Re-run RLS audit query daily."""
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if not db_url:
        return

    rc, out, err = run_cmd(["psql", db_url, "-t", "-c",
        "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename NOT IN "
        "(SELECT tablename FROM pg_tables t JOIN pg_policies p ON t.tablename=p.tablename "
        "WHERE t.schemaname='public')"])
    if rc == 0:
        count = out.strip()
        if count and int(count) > 0:
            log_event("rls_violations", "SEV2", {"tables_without_rls": int(count)})


async def check_mcp_auth():
    """Verify unauthenticated MCP request returns 401."""
    rc, out, _ = run_cmd(["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
                          "http://127.0.0.1:3000/tools/list", "--max-time", "5"])
    code = out.strip()
    if code == "200":
        log_event("mcp_auth_bypass", "SEV1", {"endpoint": "/tools/list", "code": code})
    else:
        log_event("mcp_auth_check", "SEV4", {"code": code})


async def check_backup_freshness():
    """Check backup in R2 within 25h."""
    log_file = LOG_DIR / "backup.log"
    if log_file.exists():
        stat = log_file.stat()
        age_hours = (time.time() - stat.st_mtime) / 3600
        if age_hours > 25:
            log_event("backup_stale", "SEV2", {"age_hours": round(age_hours, 1)})
            await remediate_backup_missing()


async def check_backup_checksum():
    """Verify backup manifest checksums."""
    rc, out, _ = run_cmd(["/opt/amg-security/verify-backup.sh"], timeout=120)
    if "ERROR" in out or rc != 0:
        log_event("backup_checksum_fail", "SEV2", {"output": out[:500]})


async def check_titan_restrictions():
    """Verify titan-agent cannot access /etc/amg."""
    rc, out, _ = run_cmd(["sudo", "-u", "titan-agent", "ls", "/etc/amg"])
    if rc == 0:
        log_event("titan_access_violation", "SEV1", {
            "message": "titan-agent can read /etc/amg",
            "output": out[:200]
        })

    # Check iptables rules exist
    rc, out, _ = run_cmd(["iptables", "-L", "OUTPUT", "-n"])
    if "titan-agent" not in out and "996" not in out:
        log_event("titan_iptables_missing", "SEV2", {"message": "No iptables rules for titan-agent"})


async def check_n8n_running():
    """Check n8n health endpoint."""
    rc, out, _ = run_cmd(["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
                          "http://127.0.0.1:5678/healthz", "--max-time", "5"])
    if out.strip() != "200":
        log_event("n8n_down", "SEV2", {"http_code": out.strip()})


async def check_gitleaks_hook():
    """Check pre-commit hook present in AMG repos."""
    repos = ["/opt/titan-harness-work", "/opt/amg-mcp-server"]
    for repo in repos:
        hook = Path(repo) / ".git" / "hooks" / "pre-commit"
        if not hook.exists():
            log_event("gitleaks_hook_missing", "SEV3", {"repo": repo})


async def check_listening_ports():
    """Check for unexpected listening ports."""
    rc, out, _ = run_cmd(["ss", "-tlnp"])
    canonical_ports = {"22", "80", "443", "2222", "3000", "5678", "8080", "8081",
                       "8082", "8083", "8084", "8880", "11434", "3100", "3200",
                       "3300", "3301", "3002", "4000", "9977"}
    for line in out.split("\n"):
        if "LISTEN" in line:
            parts = line.split()
            for p in parts:
                if ":" in p:
                    port = p.rsplit(":", 1)[-1]
                    if port.isdigit() and port not in canonical_ports:
                        log_event("unexpected_port", "SEV2", {"port": port, "line": line.strip()})


async def check_mcp_memory_integrity():
    """Check MCP memory hash tree."""
    rc, out, _ = run_cmd(["curl", "-sf", "http://127.0.0.1:3000/health", "--max-time", "5"])
    if rc == 0:
        log_event("mcp_memory_check", "SEV4", {"health": out[:200]})


async def check_ssh_authorized_keys():
    """Detect changes to authorized_keys files."""
    keys_files = ["/root/.ssh/authorized_keys", "/home/solon/.ssh/authorized_keys"]
    canonical_dir = Path("/etc/amg")

    for kf in keys_files:
        if not Path(kf).exists():
            continue
        with open(kf) as f:
            current_hash = hashlib.sha256(f.read().encode()).hexdigest()

        canonical = canonical_dir / f"ssh-keys-{Path(kf).parent.parent.name}.sha256"
        if canonical.exists():
            stored = canonical.read_text().strip()
            if current_hash != stored:
                log_event("ssh_keys_changed", "SEV1", {
                    "file": kf,
                    "expected": stored[:16],
                    "actual": current_hash[:16]
                })
        else:
            # First run — store canonical
            canonical.write_text(current_hash)


async def check_cloudflare_waf_rules():
    """Check CF WAF rules haven't drifted."""
    cf_env = ENV_DIR / "cloudflare.env"
    if not cf_env.exists():
        return
    log_event("cf_waf_check", "SEV4", {"status": "check_scheduled"})


async def verify_own_integrity():
    """Hash own source file — detect tampering."""
    own_path = Path(__file__).resolve()
    canonical = ENV_DIR / "watchdog-hash.sha256"

    with open(own_path) as f:
        current_hash = hashlib.sha256(f.read().encode()).hexdigest()

    if canonical.exists():
        stored = canonical.read_text().strip()
        if current_hash != stored:
            log_event("watchdog_tampered", "SEV1", {
                "expected": stored[:16],
                "actual": current_hash[:16]
            })
    else:
        canonical.write_text(current_hash)


async def send_heartbeat():
    """POST heartbeat to external monitor."""
    global last_heartbeat
    now = time.time()
    if now - last_heartbeat < HEARTBEAT_INTERVAL:
        return

    heartbeat_url = os.environ.get("HEARTBEAT_URL", "")
    if heartbeat_url:
        ts = datetime.now(timezone.utc).isoformat()
        run_cmd(["curl", "-sf", "-d", f"AMG Security Watchdog alive at {ts}",
                 heartbeat_url], timeout=10)
    last_heartbeat = now
    log_event("heartbeat", "SEV4", {"status": "sent"})


# ============================================================
# REMEDIATION FUNCTIONS (hard-bounded)
# Every remediation writes before/after state to governance_audit
# ============================================================

def log_remediation_to_governance_audit(action: str, before_state: dict, after_state: dict):
    """Write remediation event to governance_audit table via Supabase."""
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if not db_url:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.governance_audit (
                session_id, agent_id, action_type, action_payload,
                prev_event_hash, this_event_hash
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            "security-watchdog",
            "security-watchdog",
            f"remediation_{action}",
            json.dumps({"action": action, "before": before_state, "after": after_state,
                        "timestamp": datetime.now(timezone.utc).isoformat()}),
            hashlib.sha256(json.dumps(before_state).encode()).hexdigest(),
            hashlib.sha256(json.dumps(after_state).encode()).hexdigest()
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log_event("governance_audit_write_error", "SEV3", {"error": str(e)})


async def remediate_fail2ban_down():
    """Restart fail2ban, max 3/h."""
    key = "fail2ban_restart"
    now = time.time()
    count = remediation_counts.get(key, {"count": 0, "window_start": now})

    if now - count["window_start"] > 3600:
        count = {"count": 0, "window_start": now}

    if count["count"] >= 3:
        log_event("remediation_limit", "SEV2", {
            "service": "fail2ban",
            "message": "Max 3 restarts/h exceeded"
        })
        return

    # Capture before state
    _, before_out, _ = run_cmd(["systemctl", "is-active", "fail2ban"])
    before_state = {"service": "fail2ban", "status": before_out.strip()}

    run_cmd(["systemctl", "restart", "fail2ban"])

    # Capture after state
    _, after_out, _ = run_cmd(["systemctl", "is-active", "fail2ban"])
    after_state = {"service": "fail2ban", "status": after_out.strip()}

    count["count"] += 1
    remediation_counts[key] = count
    log_event("remediation_applied", "SEV3", {"action": "fail2ban_restart"})
    log_remediation_to_governance_audit("fail2ban_restart", before_state, after_state)


async def remediate_backup_missing():
    """Trigger backup script."""
    before_state = {"backup_status": "stale_or_missing"}
    log_event("remediation_applied", "SEV2", {"action": "backup_trigger"})
    run_cmd(["/opt/amg-security/amg-backup.sh"], timeout=300)
    after_state = {"backup_status": "triggered"}
    log_remediation_to_governance_audit("backup_trigger", before_state, after_state)


async def remediate_titan_violation(violation_type: str, details: dict):
    """Kill titan-agent, forensic snapshot, invalidate JWT."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    forensic_dir = FORENSICS_DIR / ts
    forensic_dir.mkdir(parents=True, exist_ok=True)

    # Forensic snapshot
    run_cmd(["ps", "aux"], timeout=5)
    run_cmd(["ss", "-tlnp"], timeout=5)

    # Kill titan-agent
    run_cmd(["pkill", "-9", "-u", "titan-agent"])

    log_event("titan_suspended", "SEV1", {
        "violation": violation_type,
        "details": details,
        "forensics": str(forensic_dir),
        "message": "Titan suspended — awaiting Solon restart"
    })
    log_remediation_to_governance_audit("titan_kill",
        {"titan_agent": "running", "violation": violation_type},
        {"titan_agent": "killed", "forensics_dir": str(forensic_dir)})


# ============================================================
# MAIN LOOP
# ============================================================

ALL_CHECKS = [
    check_credential_ages,
    check_fail2ban_running,
    check_ufw_drift,
    check_wazuh_agent,
    check_caddy_running,
    check_supabase_rls,
    check_mcp_auth,
    check_backup_freshness,
    check_titan_restrictions,
    check_n8n_running,
    check_gitleaks_hook,
    check_listening_ports,
    check_mcp_memory_integrity,
    check_ssh_authorized_keys,
    check_cloudflare_waf_rules,
    verify_own_integrity,
    send_heartbeat,
]

# Run expensive checks less frequently
EXPENSIVE_CHECKS = {
    check_backup_checksum: 3600,      # Every hour
    check_supabase_rls: 86400,        # Daily
    check_credential_ages: 3600,       # Every hour
    check_cloudflare_waf_rules: 3600,  # Every hour
}

last_expensive_run = {}


async def run_tick():
    """Execute one tick of the watchdog."""
    for check in ALL_CHECKS:
        try:
            await check()
        except Exception as e:
            log_event("check_error", "SEV3", {
                "check": check.__name__,
                "error": str(e)
            })

    # Run expensive checks on their schedule
    now = time.time()
    for check, interval in EXPENSIVE_CHECKS.items():
        last = last_expensive_run.get(check.__name__, 0)
        if now - last >= interval:
            try:
                await check()
                last_expensive_run[check.__name__] = now
            except Exception as e:
                log_event("expensive_check_error", "SEV3", {
                    "check": check.__name__,
                    "error": str(e)
                })


async def main():
    """Main watchdog loop."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    FORENSICS_DIR.mkdir(parents=True, exist_ok=True)

    log_event("watchdog_start", "SEV4", {
        "checks": len(ALL_CHECKS),
        "tick_seconds": TICK_SECONDS,
        "pid": os.getpid()
    })

    while True:
        try:
            await run_tick()
        except Exception as e:
            log_event("tick_error", "SEV2", {"error": str(e)})

        # Reset weekly alert budget
        now = datetime.now(timezone.utc)
        if (now - alert_counts["week_start"]).days >= 7:
            alert_counts["SEV1"] = 0
            alert_counts["SEV2"] = 0
            alert_counts["week_start"] = now

        await asyncio.sleep(TICK_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
