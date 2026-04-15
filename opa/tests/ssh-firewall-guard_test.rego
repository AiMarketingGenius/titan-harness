package amg.ssh_test

import data.amg.ssh

# v1.4 test suite.
# Keeps all v1.2 cases green + adds: pre_proposal_hash requirement,
# audit-mode behavior, broadened scope regex.

# ---------------------------------------------------------------------------
# v1.2 regression: non-scope commands always allowed
# ---------------------------------------------------------------------------

test_non_scope_allowed if {
    ssh.allow with input as {
        "cmd": "ls -la /etc",
        "mode": "enforce",
    }
}

# ---------------------------------------------------------------------------
# v1.4 positive: full guards present (enforce) — must allow
# ---------------------------------------------------------------------------

test_ssh_with_full_v14_guards if {
    ssh.allow with input as {
        "cmd": "ssh -p 22 root@host 'uptime'",
        "mode": "enforce",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 3600,
        "incident_id": "INC-2026-04-15-01",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
        "pre_proposal_hash": "sha256:f00ba7",
        "approved_hashes": ["sha256:f00ba7", "sha256:deadbe"],
    }
}

# ---------------------------------------------------------------------------
# v1.4 negative: missing pre_proposal_hash — must deny
# ---------------------------------------------------------------------------

test_deny_missing_pre_proposal_hash if {
    not ssh.allow with input as {
        "cmd": "ufw disable",
        "mode": "enforce",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 100,
        "incident_id": "INC-1",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
        "approved_hashes": ["sha256:f00ba7"],
    }
}

# ---------------------------------------------------------------------------
# v1.4 negative: pre_proposal_hash present but not in approved_hashes — must deny
# ---------------------------------------------------------------------------

test_deny_wrong_pre_proposal_hash if {
    not ssh.allow with input as {
        "cmd": "iptables -F",
        "mode": "enforce",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 100,
        "incident_id": "INC-1",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
        "pre_proposal_hash": "sha256:rogue",
        "approved_hashes": ["sha256:f00ba7", "sha256:deadbe"],
    }
}

# ---------------------------------------------------------------------------
# v1.2 regression: stale baseline — must deny
# ---------------------------------------------------------------------------

test_deny_stale_baseline if {
    not ssh.allow with input as {
        "cmd": "iptables -F",
        "mode": "enforce",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 90000,
        "incident_id": "INC-1",
        "escape_hatch_all_green": true,
        "chrony_synced": true,
        "pre_proposal_hash": "sha256:f00ba7",
        "approved_hashes": ["sha256:f00ba7"],
    }
}

# ---------------------------------------------------------------------------
# v1.2 regression: escape hatch red — must deny
# ---------------------------------------------------------------------------

test_deny_escape_hatch_red if {
    not ssh.allow with input as {
        "cmd": "systemctl stop ssh",
        "mode": "enforce",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 100,
        "incident_id": "INC-1",
        "escape_hatch_all_green": false,
        "chrony_synced": true,
        "pre_proposal_hash": "sha256:f00ba7",
        "approved_hashes": ["sha256:f00ba7"],
    }
}

# ---------------------------------------------------------------------------
# v1.2 regression: chrony not synced — must deny
# ---------------------------------------------------------------------------

test_deny_chrony_not_synced if {
    not ssh.allow with input as {
        "cmd": "ssh user@host",
        "mode": "enforce",
        "baseline_sha256": "abcd",
        "baseline_age_sec": 100,
        "incident_id": "INC-1",
        "escape_hatch_all_green": true,
        "chrony_synced": false,
        "pre_proposal_hash": "sha256:f00ba7",
        "approved_hashes": ["sha256:f00ba7"],
    }
}

# ---------------------------------------------------------------------------
# v1.4 audit mode: scope cmd allowed-with-warn even with zero guards
# ---------------------------------------------------------------------------

test_audit_mode_allows_scope_cmd_without_guards if {
    ssh.allow with input as {
        "cmd": "iptables -F",
        "mode": "audit",
    }
}

# ---------------------------------------------------------------------------
# v1.4 audit mode emits warn_reason
# ---------------------------------------------------------------------------

test_audit_mode_emits_warn if {
    ssh.warn_reason with input as {
        "cmd": "ufw disable",
        "mode": "audit",
    }
}

# ---------------------------------------------------------------------------
# v1.4 new scope: hostnamectl denied in enforce without guards
# ---------------------------------------------------------------------------

test_hostnamectl_in_scope_denied_enforce if {
    not ssh.allow with input as {
        "cmd": "hostnamectl set-hostname new-host",
        "mode": "enforce",
    }
}

# ---------------------------------------------------------------------------
# v1.4 new scope: authorized_keys write denied in enforce without guards
# ---------------------------------------------------------------------------

test_authorized_keys_write_denied if {
    not ssh.allow with input as {
        "cmd": "tee -a /root/.ssh/authorized_keys",
        "mode": "enforce",
    }
}

# ---------------------------------------------------------------------------
# v1.4 new scope: ssh-keygen denied in enforce without guards
# ---------------------------------------------------------------------------

test_sshkeygen_denied_without_guards if {
    not ssh.allow with input as {
        "cmd": "ssh-keygen -R old.host",
        "mode": "enforce",
    }
}

# ---------------------------------------------------------------------------
# v1.4 new scope: apt install openssh-server denied in enforce without guards
# ---------------------------------------------------------------------------

test_apt_ssh_package_denied_without_guards if {
    not ssh.allow with input as {
        "cmd": "apt install openssh-server",
        "mode": "enforce",
    }
}

# ---------------------------------------------------------------------------
# v1.4: default mode is enforce (no implicit audit fallback)
# ---------------------------------------------------------------------------

test_default_mode_is_enforce if {
    not ssh.allow with input as {
        "cmd": "ufw disable",
    }
}
