#!/usr/bin/env bash
# bin/titan-email-send.sh
# CT-0415-08 — CLI wrapper for Gmail SMTP autonomous send.
# Thin wrapper over lib/gmail_sender.py for shell-script consumers.
#
# Usage:
#   bin/titan-email-send.sh send --from-alias growyourbusiness --to solon@yahoo.com \
#     --subject "Subject" --body "Plain text body"
#
#   bin/titan-email-send.sh list-accounts
#   bin/titan-email-send.sh quota --from-alias growyourbusiness
#   bin/titan-email-send.sh selftest
#
# Env:
#   AMG_ENV_DIR   — override default /etc/amg for env-file discovery
#   MCP_ENDPOINT  — override default MCP audit-log endpoint
#
# Requires: at least one /etc/amg/gmail-<alias>.env file with
# GMAIL_ACCOUNT + GMAIL_APP_PASSWORD keys.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec python3 "$REPO_ROOT/lib/gmail_sender.py" "$@"
