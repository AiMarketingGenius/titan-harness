#!/usr/bin/env bash
# CT-0427-98 — deploy supervisor v2 + reviewer + restart 5 lanes + synthetic E2E.
set -euo pipefail

AGENTS_BUILDER=(codex hercules nestor alexander)
AGENT_REVIEWER=kimi_code
TEMPLATE_DIR=/opt/amg-titan/templates
LOG=/opt/amg-titan/migrations/CT-0427-98-supervisor-v2.log
SUPABASE_ENV=/etc/amg/supabase.env

note(){ printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
note '== CT-0427-98 DEPLOY START =='

# 1. Confirm the two new templates are in place.
for f in agent-supervisor-v2.sh reviewer-supervisor.sh; do
  if [ ! -f "${TEMPLATE_DIR}/${f}" ]; then
    note "FATAL: missing ${TEMPLATE_DIR}/${f}"
    exit 2
  fi
done
note "templates ready: agent-supervisor-v2.sh, reviewer-supervisor.sh"

# 2. Allow agents to read /etc/amg/supabase.env so the supervisor can write to MCP.
#    Group: amg_agents (created if missing) — gives supervisors read access without
#    exposing the env file world-readable.
if ! getent group amg_agents >/dev/null 2>&1; then
  groupadd amg_agents
  note "group amg_agents CREATED"
fi
chgrp amg_agents "${SUPABASE_ENV}"
chmod 0640 "${SUPABASE_ENV}"
note "${SUPABASE_ENV} chgrp amg_agents chmod 0640"

# 3. Deploy supervisor-v2 to 4 builders, reviewer to kimi_code; ensure group membership.
for AGENT in "${AGENTS_BUILDER[@]}"; do
  usermod -aG amg_agents "${AGENT}"
  install -m 0755 -o "${AGENT}" -g "${AGENT}" "${TEMPLATE_DIR}/agent-supervisor-v2.sh" "/home/${AGENT}/.claude/agent-supervisor.sh"
  note "${AGENT}: supervisor-v2 deployed + group amg_agents"
done
usermod -aG amg_agents "${AGENT_REVIEWER}"
install -m 0755 -o "${AGENT_REVIEWER}" -g "${AGENT_REVIEWER}" "${TEMPLATE_DIR}/reviewer-supervisor.sh" "/home/${AGENT_REVIEWER}/.claude/agent-supervisor.sh"
note "${AGENT_REVIEWER}: reviewer-supervisor deployed + group amg_agents"

# 4. Tear down + restart 5 tmux sessions so they pick up the new supervisor body.
for AGENT in "${AGENTS_BUILDER[@]}" "${AGENT_REVIEWER}"; do
  if sudo -u "${AGENT}" tmux has-session -t "${AGENT}-agent" 2>/dev/null; then
    sudo -u "${AGENT}" tmux kill-session -t "${AGENT}-agent" 2>/dev/null || true
  fi
  sudo -u "${AGENT}" tmux new-session -d -s "${AGENT}-agent" "bash /home/${AGENT}/.claude/agent-supervisor.sh ${AGENT}"
  note "${AGENT}: tmux restarted with new supervisor"
done

# 5. Wait for supervisors to print SUPERVISOR UP v2 / REVIEWER UP v2 before continuing.
sleep 4
PASS_BOOT=0; FAIL_BOOT=0
for AGENT in "${AGENTS_BUILDER[@]}"; do
  if grep -q "SUPERVISOR UP v2" "/home/${AGENT}/.claude/logs/${AGENT}-supervisor.log" 2>/dev/null; then
    note "${AGENT}: SUPERVISOR UP v2 detected"
    PASS_BOOT=$((PASS_BOOT+1))
  else
    note "${AGENT}: SUPERVISOR UP v2 NOT in log"
    FAIL_BOOT=$((FAIL_BOOT+1))
  fi
done
if grep -q "REVIEWER UP v2" "/home/${AGENT_REVIEWER}/.claude/logs/${AGENT_REVIEWER}-supervisor.log" 2>/dev/null; then
  note "${AGENT_REVIEWER}: REVIEWER UP v2 detected"
  PASS_BOOT=$((PASS_BOOT+1))
else
  note "${AGENT_REVIEWER}: REVIEWER UP v2 NOT in log"
  FAIL_BOOT=$((FAIL_BOOT+1))
fi
note "boot markers: PASS=${PASS_BOOT}/5 FAIL=${FAIL_BOOT}/5"

note '== CT-0427-98 DEPLOY END =='
exit "${FAIL_BOOT}"
