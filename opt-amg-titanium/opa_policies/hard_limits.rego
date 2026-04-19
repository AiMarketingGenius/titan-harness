package amg.titanium

import rego.v1

# Hard limits from CLAUDE.md §15 — never gated past without Solon approval.
# OPA deny rules fire when a staged change touches these surfaces without
# an explicit Solon-approval-marker commit tag.

# Credentials rotation — any .env / keys / secrets path change
deny contains msg if {
    some f
    input.files[_] = f
    regex.match(`\.env|(^|/)secrets/|credentials|\.age$|private_key|service_role\.key`, f)
    not input.solon_approved
    msg := sprintf("hard-limit: credentials file change without Solon approval: %s", [f])
}

# Financial files — pricing, invoicing, payments
deny contains msg if {
    some f
    input.files[_] = f
    regex.match(`pricing|paddle|stripe|invoice|billing|PRICING_`, f)
    not contains(f, "opt-amg-titanium")
    not input.solon_approved
    msg := sprintf("hard-limit: financial-surface change without Solon approval: %s", [f])
}

# External comms — email templates, Slack broadcast scripts
deny contains msg if {
    some f
    input.files[_] = f
    regex.match(`marketing_engine|broadcast|email_sender|outbound_`, f)
    not input.solon_approved
    msg := sprintf("hard-limit: external-comms change without Solon approval: %s", [f])
}

# Destructive ops — migration DROP, TRUNCATE, DELETE FROM without WHERE.
# File-content check is populated by pre-proposal-gate.sh when it loads
# staged diffs; when unpopulated, this rule is a no-op.
deny contains msg if {
    some f
    input.files[_] = f
    endswith(f, ".sql")
    contains(lower(file_content_if_loaded(f)), "drop table")
    not input.solon_approved
    msg := sprintf("hard-limit: destructive SQL (DROP TABLE) without Solon approval: %s", [f])
}

# Naming locks — Greek codename doctrine changes
deny contains msg if {
    some f
    input.files[_] = f
    regex.match(`DOCTRINE_GREEK_CODENAMES|greek_codenames`, f)
    not input.solon_approved
    msg := sprintf("hard-limit: Greek codename doctrine change without Solon approval: %s", [f])
}

# Helper — returns empty string when not populated (denies do not fire).
file_content_if_loaded(_) := "" if {
    true
}
