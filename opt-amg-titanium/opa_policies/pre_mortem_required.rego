package amg.titanium

import rego.v1

# Production-bound changes require a PRE_MORTEM_*.md in the same changeset.

production_paths := {
    "deploy/", "sql/", "TitanControl/",
    "bin/deploy-", "scripts/deploy_",
    "opt-amg-titanium/",
    "portal/", "site/", "marketing/",
    "revere-", "chamber-",
    "hooks/", ".git/hooks/",
    "CLAUDE.md", "CORE_CONTRACT.md", "policy.yaml",
}

touches_production if {
    some f
    input.files[_] = f
    prefix := production_paths[_]
    startswith(f, prefix)
}

has_pre_mortem if {
    some f
    input.files[_] = f
    regex.match(`^(.*/)?PRE_MORTEM_.*\.md$`, f)
}

deny contains msg if {
    input.production_bound == 1
    touches_production
    not has_pre_mortem
    not input.skip_pre_mortem
    msg := "pre-mortem required: production-bound commit has no PRE_MORTEM_*.md file (see /opt/amg-titanium/PRE_MORTEM_TEMPLATE.md)"
}
