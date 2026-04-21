#!/bin/bash
# titan-harness/scripts/deploy_aimemoryguard.sh
#
# CT-0416-07 Gate 1 — one-shot deploy of aimemoryguard.com to Cloudflare Pages
# plus a VPS fallback-root refresh so the local Caddy mirror does not drift.
# Runs as soon as CLOUDFLARE_API_TOKEN_AIMG is available in the environment
# (or wrangler is already OAuth'd, i.e. ~/.wrangler exists).
#
# Three supported cred paths (script picks whichever is live):
#   Path A — wrangler OAuth: if `wrangler whoami` succeeds, use that
#            (Solon ran `wrangler login` once, Titan never touches passwords)
#   Path B — scoped API token: reads CLOUDFLARE_API_TOKEN_AIMG from env
#            or from /etc/amg/cloudflare.env (scope: Cloudflare Pages:Edit +
#            User Details:Read on account b68a11a14...)
#   Path C — existing CF_API_TOKEN that happens to have aimemoryguard scope
#            (fallback, usually fails because /etc/amg/cloudflare.env token is
#            for the ads@drseo.io account f4a3ae24..., not b68a11)
#
# Usage:
#   ./deploy_aimemoryguard.sh [--dry-run]
#
# Exit codes:
#   0 — deployed successfully (URL posted to stdout + Slack)
#   2 — no cred path available (one of the three above must exist)
#   3 — wrangler deploy failed
#   4 — deploy succeeded but post-deploy smoke test failed

set -euo pipefail

SITE_DIR="/opt/titan-harness/deploy/aimemoryguard-landing"
MIRROR_DIR="/opt/aimemoryguard-site"
PROJECT_NAME="aimemoryguard"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

if [ ! -d "$SITE_DIR" ]; then
  echo "ERR: $SITE_DIR missing" >&2
  exit 2
fi
if [ ! -f "$SITE_DIR/index.html" ]; then
  echo "ERR: $SITE_DIR/index.html missing" >&2
  exit 2
fi

# Resolve cred path
CRED_PATH=""

# Path A — wrangler OAuth
if command -v wrangler >/dev/null 2>&1; then
  if wrangler whoami 2>/dev/null | grep -q "@"; then
    CRED_PATH="A (wrangler OAuth)"
  fi
fi

# Path B — scoped API token
if [ -z "$CRED_PATH" ]; then
  if [ -z "${CLOUDFLARE_API_TOKEN_AIMG:-}" ] && [ -f /etc/amg/cloudflare.env ]; then
    # Source just this one var to avoid leaking other env
    TOKEN_LINE=$(grep -E '^CLOUDFLARE_API_TOKEN_AIMG=' /etc/amg/cloudflare.env 2>/dev/null || true)
    [ -n "$TOKEN_LINE" ] && export "$TOKEN_LINE"
  fi
  if [ -n "${CLOUDFLARE_API_TOKEN_AIMG:-}" ]; then
    export CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN_AIMG"
    CRED_PATH="B (CLOUDFLARE_API_TOKEN_AIMG)"
  fi
fi

# Path C — existing CF_API_TOKEN (least likely to work given account mismatch)
if [ -z "$CRED_PATH" ]; then
  if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
    CRED_PATH="C (pre-existing CLOUDFLARE_API_TOKEN)"
  elif [ -f /etc/amg/cloudflare.env ]; then
    TOKEN_LINE=$(grep -E '^CLOUDFLARE_API_TOKEN=' /etc/amg/cloudflare.env 2>/dev/null || true)
    if [ -n "$TOKEN_LINE" ]; then
      export "$TOKEN_LINE"
      CRED_PATH="C (pre-existing CLOUDFLARE_API_TOKEN)"
    fi
  fi
fi

if [ -z "$CRED_PATH" ]; then
  cat >&2 <<MSG
ERR: No Cloudflare cred path available. Pick one:
  A — Solon runs \`wrangler login\` once in Chrome (OAuth, no password autofill)
  B — Solon creates scoped token in CF dashboard (b68a11 account, Pages:Edit + User Details:Read),
      paste to this script via CLOUDFLARE_API_TOKEN_AIMG env or /etc/amg/cloudflare.env
  C — move aimemoryguard Pages project under ads@drseo.io CF account (reuses existing token)
MSG
  exit 2
fi

echo "[deploy] Using cred path: $CRED_PATH"
echo "[deploy] Site dir: $SITE_DIR"
echo "[deploy] Mirror:   $MIRROR_DIR/index.html"
echo "[deploy] Project: $PROJECT_NAME"

if [ "$DRY_RUN" = "1" ]; then
  echo "[deploy] DRY RUN — skipping actual wrangler invocation"
  exit 0
fi

# Ensure wrangler is available
if ! command -v wrangler >/dev/null 2>&1; then
  echo "[deploy] wrangler not on PATH — trying npx"
  WRANGLER="npx -y wrangler@latest"
else
  WRANGLER="wrangler"
fi

PREVIEW_CODE="n/a"
LIVE_CODE="n/a"
ORIGIN_CODE="n/a"

# Deploy
DEPLOY_OUT=$(cd "$SITE_DIR" && $WRANGLER pages deploy . --project-name="$PROJECT_NAME" --branch=main 2>&1)
echo "$DEPLOY_OUT"

# Extract deploy URL
DEPLOY_URL="$(printf '%s\n' "$DEPLOY_OUT" | grep -oE 'https://[a-z0-9-]+\.pages\.dev' | head -1 || true)"
LIVE_URL="https://aimemoryguard.com"

mkdir -p "$MIRROR_DIR"
install -m 0644 "$SITE_DIR/index.html" "$MIRROR_DIR/index.html"
echo "[sync] Mirrored landing page to $MIRROR_DIR/index.html"

echo ""
echo "[deploy] Success. Preview: $DEPLOY_URL"
echo "[deploy] Live:    $LIVE_URL"

# Smoke test
if command -v curl >/dev/null; then
  LIVE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$LIVE_URL" --max-time 10)
  if [ -n "$DEPLOY_URL" ]; then
    PREVIEW_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$DEPLOY_URL" --max-time 10)
  else
    PREVIEW_CODE="missing"
  fi
  ORIGIN_CODE=$(curl -ks --resolve aimemoryguard.com:443:127.0.0.1 -o /dev/null -w "%{http_code}" https://aimemoryguard.com --max-time 10)
  echo "[smoke] aimemoryguard.com HTTP $LIVE_CODE"
  echo "[smoke] pages.dev preview  HTTP $PREVIEW_CODE"
  echo "[smoke] VPS mirror         HTTP $ORIGIN_CODE"
  if [ "$PREVIEW_CODE" != "200" ]; then
    echo "[smoke] preview not 200 — investigate" >&2
    exit 4
  fi
  if [ "$ORIGIN_CODE" != "200" ]; then
    echo "[smoke] VPS mirror not 200 — investigate" >&2
    exit 4
  fi
fi

# Post to Slack if token available
if [ -n "${SLACK_BOT_TOKEN:-}" ] && [ -n "${CHANNEL_ID:-}" ]; then
  curl -s "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json; charset=utf-8" \
    --data "$(python3 -c "
import json
print(json.dumps({
  'channel': '$CHANNEL_ID',
  'text': ':rocket: *CT-0416-07 Gate 1 — aimemoryguard.com DEPLOYED*\n\n• Cred path: $CRED_PATH\n• Preview: $DEPLOY_URL\n• Live: $LIVE_URL\n• Mirror: $MIRROR_DIR/index.html\n• Smoke: preview HTTP $PREVIEW_CODE, live HTTP $LIVE_CODE, origin HTTP $ORIGIN_CODE',
}))")" >/dev/null 2>&1
fi

exit 0
