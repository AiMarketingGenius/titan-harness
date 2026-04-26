#!/usr/bin/env bash
# amg_factory_cron.sh — install/uninstall cron jobs for AMG factory autonomy.
#
# Installs:
#   *  every 10 min   : agent_heartbeat.py (--report on every 6th run = hourly)
#   *  every 5 min    : agent_dispatch_bridge.py --once (drain pending tasks)
#   *  every 60 sec   : monitor_and_scale.py --once (queue-depth fallback toggle)
#   *  hourly :07     : credential_audit.sh (placeholder — Mercury does this once it lands)
#   *  hourly :13     : einstein_drift_scan.sh (placeholder)
#   *  hourly :19     : git_audit.sh (placeholder — checks ESCALATE.md)
#   *  daily 06:00    : backlog_review.py (placeholder — surfaces stale tasks)
#   *  daily 06:30    : brand_audit.py (placeholder — Lumina-side asset audit)
#   *  daily 23:50    : daily heartbeat report → MCP
#
# Usage
#   amg_factory_cron.sh install
#   amg_factory_cron.sh uninstall
#   amg_factory_cron.sh status
#
# Logs: /var/log/amg_cron.log if root, otherwise ~/.openclaw/logs/amg_cron.log

set -u

HOME_DIR="${HOME}"
TITAN="${HOME_DIR}/titan-harness/scripts"
LOG_DIR_ROOT="/var/log"
LOG_DIR_USER="${HOME_DIR}/.openclaw/logs"
if [ -w "$LOG_DIR_ROOT" ] 2>/dev/null; then
    LOG="${LOG_DIR_ROOT}/amg_cron.log"
else
    mkdir -p "$LOG_DIR_USER"
    LOG="${LOG_DIR_USER}/amg_cron.log"
fi
PYTHON="$(command -v python3)"
BASH="$(command -v bash)"
BEGIN_TAG="# === AMG-FACTORY-CRON BEGIN ==="
END_TAG="# === AMG-FACTORY-CRON END ==="

fragment() {
    cat <<EOF
$BEGIN_TAG
# Installed by scripts/amg_factory_cron.sh on $(date -Iseconds)
*/5  * * * * $PYTHON $TITAN/agent_dispatch_bridge.py --once >> $LOG 2>&1
*/10 * * * * $PYTHON $TITAN/agent_heartbeat.py >> $LOG 2>&1
*    * * * * $PYTHON $TITAN/monitor_and_scale.py --once >> $LOG 2>&1
7    * * * * $BASH   $TITAN/cron_credential_audit.sh    >> $LOG 2>&1
13   * * * * $BASH   $TITAN/cron_einstein_drift_scan.sh >> $LOG 2>&1
19   * * * * $BASH   $TITAN/cron_git_audit.sh           >> $LOG 2>&1
0    6 * * * $PYTHON $TITAN/cron_backlog_review.py      >> $LOG 2>&1
30   6 * * * $PYTHON $TITAN/cron_brand_audit.py         >> $LOG 2>&1
50   23 * * * $PYTHON $TITAN/agent_heartbeat.py --report >> $LOG 2>&1
$END_TAG
EOF
}

current_tab() {
    crontab -l 2>/dev/null || true
}

filtered_tab() {
    current_tab | awk -v B="$BEGIN_TAG" -v E="$END_TAG" '
        $0 == B {skip=1; next}
        $0 == E {skip=0; next}
        skip {next}
        {print}
    '
}

write_placeholders() {
    for f in cron_credential_audit.sh cron_einstein_drift_scan.sh cron_git_audit.sh; do
        path="$TITAN/$f"
        if [ ! -f "$path" ]; then
            cat > "$path" <<'PLACEHOLDER'
#!/usr/bin/env bash
# Placeholder — fleshed out once Mercury (Hercules' hands) lands.
echo "[$(date -Iseconds)] $0 placeholder ran (no-op)"
PLACEHOLDER
            chmod +x "$path"
        fi
    done
    for f in cron_backlog_review.py cron_brand_audit.py; do
        path="$TITAN/$f"
        if [ ! -f "$path" ]; then
            cat > "$path" <<'PLACEHOLDER'
#!/usr/bin/env python3
import datetime, sys
print(f"[{datetime.datetime.now().isoformat()}] {sys.argv[0]} placeholder ran (no-op)")
PLACEHOLDER
            chmod +x "$path"
        fi
    done
}

cmd_install() {
    write_placeholders
    {
        filtered_tab
        fragment
    } | crontab -
    echo "[install] crontab updated. Log: $LOG"
    crontab -l | grep -A20 "$BEGIN_TAG" | head -20
}

cmd_uninstall() {
    filtered_tab | crontab -
    echo "[uninstall] AMG factory cron block removed."
}

cmd_status() {
    echo "[status] crontab block:"
    current_tab | awk -v B="$BEGIN_TAG" -v E="$END_TAG" '
        $0 == B {p=1}
        p {print}
        $0 == E {exit}
    '
    echo ""
    echo "[status] log path: $LOG"
    if [ -f "$LOG" ]; then
        echo "[status] last 5 log lines:"
        tail -5 "$LOG"
    fi
}

case "${1:-help}" in
    install)   cmd_install ;;
    uninstall) cmd_uninstall ;;
    status)    cmd_status ;;
    help|*)
        cat <<EOF
Usage: $0 {install|uninstall|status}

  install    Add the AMG factory cron block (idempotent).
  uninstall  Remove the AMG factory cron block.
  status     Show installed block + log tail.

Cron entries (when installed):
  */5  * * * * agent_dispatch_bridge.py --once
  */10 * * * * agent_heartbeat.py
  *    * * * * monitor_and_scale.py --once
  7    * * * * cron_credential_audit.sh
  13   * * * * cron_einstein_drift_scan.sh
  19   * * * * cron_git_audit.sh
  0    6 * * * cron_backlog_review.py
  30   6 * * * cron_brand_audit.py
  50   23 * * * agent_heartbeat.py --report

Logs: $LOG
EOF
        ;;
esac
