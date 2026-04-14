package amg.ssh_test

import data.amg.ssh

# --- positive cases (must allow) ---

test_non_scope_allowed if {
    ssh.allow with input as {
        "cmd": "ls -la /etc",
        "mode": "enforce",
    }
}

test_ssh_with_full_guards if {
    ssh.allow with input as {
        "cmd": "ssh -p 22 root@host 'uptime'",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 3600,
        "incident_id": "INC-2026-04-14-03",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
        "mode": "enforce",
    }
}

# --- negative cases (must deny) ---

test_deny_missing_baseline if {
    not ssh.allow with input as {
        "cmd": "ufw disable",
        "incident_id": "INC-1",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
    }
}

test_deny_stale_baseline if {
    not ssh.allow with input as {
        "cmd": "iptables -F",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 90000,
        "incident_id": "INC-1",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
    }
}

test_deny_missing_incident if {
    not ssh.allow with input as {
        "cmd": "fail2ban-client stop",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 100,
        "incident_id": "",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
    }
}

test_deny_escape_hatch_red if {
    not ssh.allow with input as {
        "cmd": "systemctl stop ssh",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 100,
        "incident_id": "INC-1",
        "escape_hatch_all_green": false,
        "chrony_synced": true,
    }
}

test_deny_chrony_not_synced if {
    not ssh.allow with input as {
        "cmd": "ssh user@host",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 100,
        "incident_id": "INC-1",
        "escape_hatch_all_green": true,
        "chrony_synced": false,
    }
}
