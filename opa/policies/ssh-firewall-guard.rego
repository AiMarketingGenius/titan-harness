package amg.ssh

# Gate #4 v1.2 — ssh/firewall guard policy.
# DENY any matching command unless all input preconditions are satisfied.

# Scope: commands that could cause a lockout or invisible access change.
scope_pattern := "^(ssh|sshd|systemctl\\s+(start|stop|restart|reload|enable|disable)\\s+(ssh|sshd|fail2ban)|iptables|ip6tables|ufw|fail2ban-client)(\\s|$)"

# Default deny.
default allow := false

allow if {
    not cmd_in_scope
}

allow if {
    cmd_in_scope
    input.baseline_sha256
    input.baseline_sha256 != ""
    input.baseline_age_sec <= 86400
    input.incident_id
    input.incident_id != ""
    input.escape_hatch_all_green == true
    input.chrony_synced == true
}

cmd_in_scope if {
    regex.match(scope_pattern, input.cmd)
}

deny_reason := reason if {
    not allow
    cmd_in_scope
    reason := sprintf(
        "DENY: SSH-scope cmd requires baseline(<24h) + incident_id + escape_hatch_green + chrony_synced. Got baseline_sha=%v age=%v inc=%v esc=%v chrony=%v",
        [
            input.baseline_sha256,
            input.baseline_age_sec,
            input.incident_id,
            input.escape_hatch_all_green,
            input.chrony_synced,
        ],
    )
}
