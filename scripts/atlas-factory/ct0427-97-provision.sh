#!/usr/bin/env bash
# CT-0427-97 — provision 5 builder users + wake infra on VPS.
# Idempotent: re-runs without harm.
set -euo pipefail

AGENTS=(codex hercules nestor alexander kimi_code)
TEMPLATE_DIR=/opt/amg-titan/templates
LOG=/opt/amg-titan/migrations/CT-0427-97-linux-wake.log
mkdir -p /opt/amg-titan/migrations /opt/amg-titan/templates

note(){ printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
note '== CT-0427-97 PROVISIONING START =='

# 1. Stage canonical templates
for f in agent-wake.path.template agent-wake.service.template nudge-template.sh baseline-supervisor.sh; do
  if [ ! -f "${TEMPLATE_DIR}/${f}" ]; then
    note "FATAL: missing template ${TEMPLATE_DIR}/${f}"
    exit 2
  fi
done
note "templates verified: 4/4 in ${TEMPLATE_DIR}"

for AGENT in "${AGENTS[@]}"; do
  note "--- agent: ${AGENT} ---"

  # 2. Create user
  if id "${AGENT}" >/dev/null 2>&1; then
    note "user ${AGENT} already exists"
  else
    useradd --create-home --shell /bin/bash --comment "Atlas builder ${AGENT}" "${AGENT}"
    note "user ${AGENT} CREATED"
  fi
  HOMEDIR="/home/${AGENT}"
  CLAUDE_DIR="${HOMEDIR}/.claude"
  LOG_DIR="${CLAUDE_DIR}/logs"

  install -d -m 0755 -o "${AGENT}" -g "${AGENT}" "${HOMEDIR}" "${CLAUDE_DIR}" "${LOG_DIR}"
  note "dirs: ${CLAUDE_DIR} + logs/ provisioned"

  # 3. Render nudge script
  NUDGE="${CLAUDE_DIR}/nudge-${AGENT}.sh"
  sed "s/AGENT_NAME/${AGENT}/g" "${TEMPLATE_DIR}/nudge-template.sh" > "${NUDGE}"
  chmod 0755 "${NUDGE}"
  chown "${AGENT}:${AGENT}" "${NUDGE}"
  note "nudge: ${NUDGE} (mode 0755 owner ${AGENT})"

  # 4. Render baseline supervisor (CT-98 replaces with v2 later)
  SUPER="${CLAUDE_DIR}/agent-supervisor.sh"
  if [ -f "${SUPER}" ] && grep -q 'SUPERVISOR UP v2' "${SUPER}" 2>/dev/null; then
    note "supervisor: v2 already deployed; skipping baseline overwrite"
  else
    cp "${TEMPLATE_DIR}/baseline-supervisor.sh" "${SUPER}"
    chmod 0755 "${SUPER}"
    chown "${AGENT}:${AGENT}" "${SUPER}"
    note "supervisor: ${SUPER} (baseline v1)"
  fi

  # 5. Render systemd path + service units (root-owned, /etc/systemd/system)
  PATH_UNIT="/etc/systemd/system/${AGENT}-wake.path"
  SVC_UNIT="/etc/systemd/system/${AGENT}-wake.service"
  sed "s/AGENT_NAME/${AGENT}/g" "${TEMPLATE_DIR}/agent-wake.path.template"    > "${PATH_UNIT}"
  sed "s/AGENT_NAME/${AGENT}/g" "${TEMPLATE_DIR}/agent-wake.service.template" > "${SVC_UNIT}"
  chmod 0644 "${PATH_UNIT}" "${SVC_UNIT}"
  note "systemd: ${PATH_UNIT} + ${SVC_UNIT}"

  # 6. Append tmux auto-recreate guard to .bashrc (only once)
  BASHRC="${HOMEDIR}/.bashrc"
  touch "${BASHRC}"; chown "${AGENT}:${AGENT}" "${BASHRC}"
  if ! grep -q "atlas-factory tmux guard ${AGENT}" "${BASHRC}"; then
    cat >> "${BASHRC}" <<BASH_EOF

# atlas-factory tmux guard ${AGENT}
if [ -z "\${TMUX:-}" ] && [ -t 1 ]; then
  if ! tmux has-session -t ${AGENT}-agent 2>/dev/null; then
    tmux new-session -d -s ${AGENT}-agent "bash \${HOME}/.claude/agent-supervisor.sh ${AGENT}"
  fi
fi
BASH_EOF
    note "bashrc: tmux guard added for ${AGENT}"
  else
    note "bashrc: tmux guard already present"
  fi
done

# 7. systemd reload + enable + start
note "== systemctl daemon-reload =="
systemctl daemon-reload
for AGENT in "${AGENTS[@]}"; do
  systemctl enable --now "${AGENT}-wake.path" >/dev/null 2>&1 || true
  STATE="$(systemctl is-active "${AGENT}-wake.path" 2>&1 || true)"
  note "${AGENT}-wake.path is-active=${STATE}"
done

# 8. Start tmux sessions per agent (idempotent)
for AGENT in "${AGENTS[@]}"; do
  if sudo -u "${AGENT}" tmux has-session -t "${AGENT}-agent" 2>/dev/null; then
    note "tmux ${AGENT}-agent already running"
  else
    sudo -u "${AGENT}" tmux new-session -d -s "${AGENT}-agent" "bash /home/${AGENT}/.claude/agent-supervisor.sh ${AGENT}"
    note "tmux ${AGENT}-agent CREATED"
  fi
done

# 9. Per-agent flag-drop smoke
note "== smoke tests =="
PASS=0; FAIL=0
for AGENT in "${AGENTS[@]}"; do
  TEST_ID="CT-0427-97-SMOKE-$(date -u +%H%M%S)-${AGENT}"
  FLAG="/home/${AGENT}/.claude/${AGENT}-wake.flag"
  echo "${TEST_ID}" | sudo tee "${FLAG}" >/dev/null
  chown "${AGENT}:${AGENT}" "${FLAG}"
  sleep 4
  if [ ! -f "${FLAG}" ] && grep -q "${TEST_ID}" "/home/${AGENT}/.claude/logs/${AGENT}-supervisor.log" 2>/dev/null; then
    note "smoke ${AGENT}: PASS (flag consumed + supervisor log entry found)"
    PASS=$((PASS+1))
  else
    REM=""; [ -f "${FLAG}" ] && REM="flag still present "
    LOG_HIT="$(grep -c "${TEST_ID}" "/home/${AGENT}/.claude/logs/${AGENT}-supervisor.log" 2>/dev/null || echo 0)"
    note "smoke ${AGENT}: FAIL (${REM}log_hits=${LOG_HIT})"
    FAIL=$((FAIL+1))
  fi
done

note "== smoke summary: PASS=${PASS}/5 FAIL=${FAIL}/5 =="
note "== CT-0427-97 PROVISIONING END =="
exit $FAIL
