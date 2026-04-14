#!/usr/bin/env bash
# bin/install-gate1-hooks.sh
# Idempotent installer for Gate #1 v1.1 hooks.
#
#  - Appends a chained call to bin/pre-proposal-gate.sh into .git/hooks/pre-commit
#    (Layer 3 after git-secrets + harness integrity)
#  - Appends bin/post-commit-bypass-logger.sh into .git/hooks/post-commit
#    (runs first, before auto-mirror)
#  - Optionally deploys hooks/git/pre-receive to VPS bare repo via ssh
#  - Optionally creates the override secret if missing on VPS
#
# Usage:
#   bin/install-gate1-hooks.sh                    # local hooks only
#   bin/install-gate1-hooks.sh --vps              # + deploy to VPS pre-receive
#   bin/install-gate1-hooks.sh --vps --rotate-secret   # also rotate the override secret

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DO_VPS=0
ROTATE_SECRET=0

for arg in "$@"; do
  case "$arg" in
    --vps) DO_VPS=1 ;;
    --rotate-secret) ROTATE_SECRET=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

MARKER_PRE="# <GATE-1> pre-proposal-gate v1.1"
MARKER_POST="# <GATE-1> post-commit-bypass-logger v1.1"
PRE_HOOK="$REPO/.git/hooks/pre-commit"
POST_HOOK="$REPO/.git/hooks/post-commit"

# --- Local pre-commit wiring ---
if [[ -f "$PRE_HOOK" ]]; then
  if grep -qF "$MARKER_PRE" "$PRE_HOOK"; then
    echo "[install-gate1] pre-commit already wired"
  else
    cat >> "$PRE_HOOK" <<'EOH'

# <GATE-1> pre-proposal-gate v1.1
bash "$HOME/titan-harness/bin/pre-proposal-gate.sh" pre-commit || exit 1
EOH
    echo "[install-gate1] pre-commit chained"
  fi
else
  echo "[install-gate1] WARN: $PRE_HOOK missing" >&2
fi

# --- Local post-commit wiring ---
if [[ -f "$POST_HOOK" ]]; then
  if grep -qF "$MARKER_POST" "$POST_HOOK"; then
    echo "[install-gate1] post-commit already wired"
  else
    # Insert AFTER the shebang/set line, BEFORE auto-mirror
    tmp="$(mktemp)"
    awk -v marker="$MARKER_POST" '
      NR==1 || NR==2 || /^set -/ { print; next }
      !printed { print ""; print marker; print "bash \"$HOME/titan-harness/bin/post-commit-bypass-logger.sh\" 2>/dev/null || true"; print ""; printed=1 }
      { print }
    ' "$POST_HOOK" > "$tmp"
    mv "$tmp" "$POST_HOOK"
    chmod +x "$POST_HOOK"
    echo "[install-gate1] post-commit wired (bypass logger runs before auto-mirror)"
  fi
fi

# --- VPS pre-receive deployment ---
if (( DO_VPS == 1 )); then
  VPS_HOST="${AMG_VPS_HOST:-root@170.205.37.148}"
  VPS_PORT="${AMG_VPS_PORT:-2222}"
  VPS_KEY="${AMG_VPS_KEY:-$HOME/.ssh/id_ed25519_amg}"
  SSH_OPTS=(-4 -p "$VPS_PORT" -i "$VPS_KEY" -o StrictHostKeyChecking=accept-new)

  echo "[install-gate1] deploying pre-receive to $VPS_HOST:$VPS_PORT"
  scp -P "$VPS_PORT" -i "$VPS_KEY" -o StrictHostKeyChecking=accept-new \
      "$REPO/hooks/git/pre-receive" "$VPS_HOST":/opt/titan-harness.git/hooks/pre-receive
  ssh "${SSH_OPTS[@]}" "$VPS_HOST" \
      'chmod +x /opt/titan-harness.git/hooks/pre-receive && echo "[install-gate1] VPS pre-receive installed"'

  if (( ROTATE_SECRET == 1 )); then
    SECRET="$(openssl rand -hex 32)"
    ssh "${SSH_OPTS[@]}" "$VPS_HOST" bash -s -- "$SECRET" <<'REMOTE'
set -euo pipefail
s="$1"
mkdir -p /etc/amg
umask 077
echo -n "$s" > /etc/amg/gate-override.secret
chown root:root /etc/amg/gate-override.secret
chmod 0400 /etc/amg/gate-override.secret
mkdir -p /var/log/amg
touch /var/log/amg/gate-overrides.jsonl
chmod 0600 /var/log/amg/gate-overrides.jsonl
echo "[install-gate1] override secret rotated on VPS"
REMOTE
    echo "[install-gate1] override secret rotated — copy locally:"
    echo "    export GIT_GATE_OVERRIDE='$SECRET'"
    echo "    (store in ~/.ssh/amg-gate-override or 1Password; NEVER commit)"
  fi
fi

echo "[install-gate1] done. Smoke-test:"
echo "    touch /tmp/fake-sshd_config && git add /tmp/fake-sshd_config 2>/dev/null"
echo "    (better: touch bin/ssh-fake.sh, git add, try to commit without trailer → gate blocks)"
