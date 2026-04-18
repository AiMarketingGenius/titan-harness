#!/usr/bin/env bash
# install.sh — deploy Memory Vault Portal to VPS at memory.aimarketinggenius.io/memoryvault/
#
# Installs:
#   /opt/amg-memory-vault-portal/public/   (static site)
#   n8n-caddy Caddyfile: adds @memoryvault handle
#   Configures SUPABASE_URL + SUPABASE_ANON_KEY in public/config.js from /etc/amg/aimg-supabase.env
#
# Does NOT change DNS — vault is served at existing cert-covered domain.
# For memoryvault.aimemoryguard.com subdomain, add DNS A record separately.

set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-/opt/titan-harness}"
SRC="$HARNESS_DIR/services/memory-vault-portal/public"
DEST="/opt/amg-memory-vault-portal/public"
AIMG_ENV="/etc/amg/aimg-supabase.env"

echo "[install] deploying static site to $DEST"
install -d -m 0755 /opt/amg-memory-vault-portal
install -d -m 0755 "$DEST"
for f in index.html styles.css app.js config.js; do
  install -m 0644 "$SRC/$f" "$DEST/$f"
done

echo "[install] populating config.js from $AIMG_ENV"
if [[ ! -f "$AIMG_ENV" ]]; then
  echo "[install] ERROR: $AIMG_ENV not found. Populate AIMG_SUPABASE_URL + AIMG_SUPABASE_ANON_KEY first." >&2
  exit 2
fi

SB_URL=$(grep -hE '^AIMG_SUPABASE_URL=' "$AIMG_ENV" | head -1 | cut -d= -f2- | tr -d '"')
SB_KEY=$(grep -hE '^AIMG_SUPABASE_ANON_KEY=' "$AIMG_ENV" | head -1 | cut -d= -f2- | tr -d '"')

if [[ -z "$SB_URL" || -z "$SB_KEY" ]]; then
  echo "[install] ERROR: AIMG_SUPABASE_URL or ANON_KEY missing in $AIMG_ENV" >&2
  exit 2
fi

DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 - <<PY
import re
p = '$DEST/config.js'
with open(p) as f: c = f.read()
c = c.replace('REPLACED_AT_DEPLOY_TIME', '|||SENTINEL_MULTI|||')
# replace each sentinel in order with [url, key, timestamp]
reps = [r'''$SB_URL''', r'''$SB_KEY''', r'''$DEPLOYED_AT''']
out = []
parts = c.split('|||SENTINEL_MULTI|||')
for i, part in enumerate(parts):
    out.append(part)
    if i < len(reps):
        out.append(reps[i])
with open(p, 'w') as f: f.write(''.join(out))
print('config.js populated')
PY

chmod 0644 "$DEST/config.js"

echo "[install] wiring Caddy /memoryvault path on memory.aimarketinggenius.io"

CADDYFILE="/opt/amg-n8n/caddy/Caddyfile"
if [[ ! -f "$CADDYFILE" ]]; then
  # Find it via docker-compose volume
  CADDYFILE=$(docker inspect n8n-caddy-1 2>/dev/null | grep -oE '"/[^"]+/Caddyfile"' | head -1 | tr -d '"' | sed 's|^/host_mnt||')
fi
if [[ -z "$CADDYFILE" || ! -f "$CADDYFILE" ]]; then
  # Fallback: find any Caddyfile in /opt/n8n* or /opt/amg-n8n
  CADDYFILE=$(find /opt/n8n* /opt/amg-n8n 2>/dev/null -name Caddyfile | head -1)
fi
if [[ -z "$CADDYFILE" || ! -f "$CADDYFILE" ]]; then
  echo "[install] WARN: n8n-caddy Caddyfile not found on host. Skipping Caddy edit; portal is still on disk at $DEST."
  echo "[install] Manual step: add a @memoryvault path handle to memory.aimarketinggenius.io serving $DEST."
else
  echo "[install] editing $CADDYFILE"
  if grep -q 'path /memoryvault' "$CADDYFILE"; then
    echo "[install] Caddy block already present; skipping insert."
  else
    # Insert @memoryvault path block before the default handle of memory.aimarketinggenius.io
    python3 - <<PY
import re
p = "$CADDYFILE"
with open(p) as f: c = f.read()

block = '''    # Memory Vault Portal (AMG AI Memory Guard consumer surface)
    @memoryvault path /memoryvault /memoryvault/*
    handle @memoryvault {
        uri strip_prefix /memoryvault
        root * /opt/amg-memory-vault-portal/public
        file_server
        try_files {path} /index.html
    }

'''
# Insert before the MCP default-handle inside memory.aimarketinggenius.io block.
# We look for "# Existing MCP ingest" comment as anchor.
anchor = "# Existing MCP ingest"
if anchor in c:
    c = c.replace(anchor, block + anchor, 1)
    with open(p, "w") as f: f.write(c)
    print("inserted @memoryvault block")
else:
    print("anchor not found; skipping (manual edit required)")
PY
  fi

  echo "[install] reloading caddy"
  docker exec n8n-caddy-1 caddy reload --config /etc/caddy/Caddyfile 2>&1 || echo "[install] WARN: caddy reload failed (may need restart)"
fi

echo
echo "[install] Vault Portal deployed."
echo "[install] Test: curl -sSLI https://memory.aimarketinggenius.io/memoryvault/ | head -3"
echo "[install] Browser: https://memory.aimarketinggenius.io/memoryvault/"
