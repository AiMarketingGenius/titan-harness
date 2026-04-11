#!/usr/bin/env bash
# titan-harness/bin/worker-entrypoint.sh - Phase P9
#
# Container entrypoint shim:
#   1. Read Docker secrets from /run/secrets/ into env vars
#   2. Source policy-loader via titan-env.sh
#   3. Run harness-preflight.sh (CORE CONTRACT gate)
#   4. Exec the CMD
set -e

# ---- Load Docker secrets (fail silently if the file is absent) ----
for secret in supabase_service_role_key litellm_master_key anthropic_api_key perplexity_api_key slack_webhook_url; do
    f="/run/secrets/$secret"
    if [ -r "$f" ]; then
        upper=$(echo "$secret" | tr '[:lower:]' '[:upper:]')
        export "$upper"="$(cat "$f")"
    fi
done

# ---- Source policy loader (exports POLICY_CAPACITY_*, POLICY_MODEL_*, etc.) ----
if [ -f /opt/titan-harness/lib/titan-env.sh ]; then
    # shellcheck source=/dev/null
    . /opt/titan-harness/lib/titan-env.sh
fi

# ---- CORE CONTRACT: refuse to start if capacity/policy invalid ----
if [ -x /opt/titan-harness/bin/harness-preflight.sh ]; then
    /opt/titan-harness/bin/harness-preflight.sh || exit $?
fi

echo "[worker-entrypoint] instance=$TITAN_INSTANCE filter=$TITAN_WORKER_FILTER"

# ---- Exec the worker command ----
exec "$@"
