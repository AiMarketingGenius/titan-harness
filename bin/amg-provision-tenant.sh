#!/usr/bin/env bash
# amg-provision-tenant — CLI wrapper for lib/tenant_provisioning.py
#
# Sources /etc/amg/supabase.env if present to populate SUPABASE_DB_URL, then
# invokes the Python module. All args forward transparently.
#
# Examples:
#   amg-provision-tenant --slug revere-chamber-demo \
#                        --name "Revere Chamber (Demo)" \
#                        --subdomain revere-chamber-demo \
#                        --plan-tier chamber-founding
set -euo pipefail

if [[ -f /etc/amg/supabase.env ]]; then
    # shellcheck disable=SC1091
    . /etc/amg/supabase.env
fi

: "${SUPABASE_DB_URL:?SUPABASE_DB_URL not set (expected /etc/amg/supabase.env or environment)}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

exec python3 -m lib.tenant_provisioning "$@"
