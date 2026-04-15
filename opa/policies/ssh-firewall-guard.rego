package amg.ssh

# Gate #4 v1.4 — ssh/firewall/host-mutation guard policy.
# DENY any matching command unless all input preconditions are satisfied.
#
# v1.4 deltas vs v1.2:
#   - Broadened scope regex: adds host-mutation commands that could produce
#     the same lockout-class blast radius (hostnamectl, usermod/passwd/groupmod,
#     sshd config/authorized_keys path writes, ssh-keygen/ssh-copy-id,
#     package mgmt pulling openssh/sudo/fail2ban).
#   - New required input: pre_proposal_hash must match one of
#     input.approved_hashes (pre-proposal gate #1 linkage).
#   - Explicit audit|enforce mode: in audit mode, allow-with-warn so v1.4
#     can soak for 24h without blocking work; in enforce, deny as v1.2.
#
# Callers must set input.mode to "audit" or "enforce". Default is "enforce"
# if omitted (fail-safe; no implicit audit).

scope_pattern := `^(ssh|sshd|systemctl\s+(start|stop|restart|reload|enable|disable)\s+(ssh|sshd|fail2ban|openssh[\w-]*)|iptables|ip6tables|ufw|fail2ban-client|hostnamectl|usermod|passwd|groupmod|ssh-keygen|ssh-copy-id|(cp|mv|cat|tee|sed|vi|vim|nano|dd|install|ln)\s+.*(\/etc\/ssh\/|\/etc\/sudoers|\/root\/\.ssh\/|authorized_keys)|(apt|apt-get|dpkg|yum|dnf|pacman|apk)\s+(install|remove|purge|autoremove|upgrade|-S|-R)\s+.*(openssh|\bssh\b|sudo|fail2ban))([^\w]|$)`

# Mode helpers ---------------------------------------------------------------
mode := input.mode
default mode := "enforce"

audit_mode if { mode == "audit" }
enforce_mode if { mode == "enforce" }

# Default deny in enforce mode ------------------------------------------------
default allow := false

# Non-scope commands are always allowed.
allow if {
    not cmd_in_scope
}

# Scope-matched commands allowed ONLY when ALL v1.4 preconditions satisfied.
allow if {
    cmd_in_scope
    enforce_mode
    input.baseline_sha256
    input.baseline_sha256 != ""
    input.baseline_age_sec <= 86400
    input.incident_id
    input.incident_id != ""
    input.escape_hatch_all_green == true
    input.chrony_synced == true
    input.pre_proposal_hash
    input.pre_proposal_hash != ""
    input.pre_proposal_hash == input.approved_hashes[_]
}

# Audit-mode: allow-with-warn. The call site is expected to log the warn decision.
allow if {
    cmd_in_scope
    audit_mode
}

cmd_in_scope if {
    regex.match(scope_pattern, input.cmd)
}

# Deny reasons ---------------------------------------------------------------
deny_reason := reason if {
    not allow
    cmd_in_scope
    enforce_mode
    reason := sprintf(
        "DENY v1.4 (enforce): scope cmd requires baseline(<24h)+incident_id+escape_hatch_green+chrony_synced+pre_proposal_hash in approved_hashes. Got baseline_sha=%v age=%v inc=%v esc=%v chrony=%v pph=%v",
        [
            input.baseline_sha256,
            input.baseline_age_sec,
            input.incident_id,
            input.escape_hatch_all_green,
            input.chrony_synced,
            input.pre_proposal_hash,
        ],
    )
}

# Warn reason for audit-mode logging (call site surfaces via decision log).
warn_reason := reason if {
    cmd_in_scope
    audit_mode
    reason := sprintf(
        "WARN v1.4 (audit): scope cmd allowed-with-warn. Would be DENIED in enforce unless all 6 preconditions present. cmd=%v",
        [input.cmd],
    )
}
