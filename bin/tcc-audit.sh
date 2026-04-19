#!/usr/bin/env bash
# bin/tcc-audit.sh — CT-0419-08 Layer A TCC pre-grant audit.
# Prints current observable TCC state for Titan-adjacent apps and opens
# System Settings panes sequentially for Solon to inspect/grant.
# Does NOT modify TCC.db (SIP-protected) and does NOT call `tccutil reset`
# unless explicitly invoked with --reset <category> <bundle>.

set -euo pipefail

cmd=${1:-report}

categories_panes=(
  "Accessibility|Privacy_Accessibility"
  "Full_Disk_Access|Privacy_AllFiles"
  "Automation|Privacy_Automation"
  "Developer_Tools|Privacy_DeveloperTool"
  "Input_Monitoring|Privacy_ListenEvent"
  "Files_and_Folders|Privacy_Files"
  "Speech_Recognition|Privacy_SpeechRecognition"
)

titan_apps=(
  "com.anthropic.claudefordesktop|Claude desktop app"
  "com.apple.Terminal|Terminal.app"
  "com.googlecode.iterm2|iTerm2"
  "com.mitchellh.ghostty|Ghostty"
  "org.hammerspoon.Hammerspoon|Hammerspoon"
  "com.microsoft.VSCode|VS Code"
)

cli_binaries=(
  "/bin/zsh"
  "/bin/bash"
  "/usr/bin/osascript"
  "/opt/homebrew/bin/node"
  "/usr/local/bin/node"
  "/opt/homebrew/bin/python3"
  "/usr/bin/python3"
)

report() {
  echo "═══════════════════════════════════════════════════════════════════"
  echo "CT-0419-08 TCC AUDIT — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "═══════════════════════════════════════════════════════════════════"
  echo
  echo "TCC.db direct read is unavailable (needs Full Disk Access for reader,"
  echo "chicken-and-egg). Audit is inferred from observable behavior + app"
  echo "running state."
  echo
  echo "── RUNNING APPS ───────────────────────────────────────────────────"
  for entry in "${titan_apps[@]}"; do
    bundle="${entry%%|*}"
    name="${entry#*|}"
    pid=$(pgrep -f "$bundle" 2>/dev/null | head -1 || true)
    if [ -n "$pid" ]; then
      printf "  %-38s RUNNING pid=%s\n" "$name" "$pid"
    else
      printf "  %-38s not running\n" "$name"
    fi
  done
  echo
  echo "── CLI BINARIES (exist) ───────────────────────────────────────────"
  for bin in "${cli_binaries[@]}"; do
    if [ -x "$bin" ]; then
      printf "  %-38s present\n" "$bin"
    fi
  done
  echo
  echo "── OBSERVABLE GRANTS (functional inference) ───────────────────────"
  # Hammerspoon: if accessibility is granted, hs.eventtap.keyStroke works;
  # we can check via a no-op AX query.
  hs_running=$(pgrep -xq Hammerspoon && echo yes || echo no)
  echo "  Hammerspoon running: $hs_running"
  if [ "$hs_running" = "yes" ]; then
    ax=$(osascript -e 'tell application "System Events" to get name of first process whose frontmost is true' 2>&1 || echo "fail")
    if [ "$ax" != "fail" ] && [ -n "$ax" ]; then
      echo "  Accessibility for osascript/System Events: ALLOWED (frontmost-query works)"
    else
      echo "  Accessibility for osascript/System Events: UNKNOWN/DENIED"
    fi
  fi
  # Check if the current process (Terminal/Ghostty) can read ~/Documents
  if ls "$HOME/Documents" >/dev/null 2>&1; then
    echo "  Current-shell Files & Folders access to Documents: ALLOWED"
  else
    echo "  Current-shell Files & Folders access to Documents: DENIED"
  fi
  # Full Disk Access check: can we read a known-FDA-protected path?
  if [ -r "$HOME/Library/Application Support/com.apple.TCC/TCC.db" ]; then
    echo "  Current-shell Full Disk Access: ALLOWED (can read user TCC.db)"
  else
    echo "  Current-shell Full Disk Access: DENIED or app not granted FDA"
  fi
  echo
  echo "── REQUIRED FOR TITAN AUTONOMY ────────────────────────────────────"
  cat <<'EOF'
  App/Binary                 Category                  Need    Why
  --------------------------------------------------------------------------
  Hammerspoon                Accessibility             YES     eventtap / AX read
  Hammerspoon                Input Monitoring          YES     keyStroke inject
  Terminal / iTerm / Ghostty Accessibility             YES     drives Claude CLI
  Terminal / iTerm / Ghostty Full Disk Access          YES     edits across $HOME
  Terminal / iTerm / Ghostty Automation → System Events YES    AX-driven prompts
  Claude (desktop, if used)  Files and Folders         YES     cross-app reads
  /bin/zsh (login shell)     Full Disk Access          YES     inherits to child procs
  /usr/bin/osascript         Accessibility             YES     UI scripting fallback

  EXPLICIT DENY (NEVER auto-grant via Layer B handler):
  - Camera, Microphone, Screen Recording
  - Contacts, Calendar, Reminders, Photos, Location, HomeKit
EOF
  echo
  echo "── NEXT STEP ──────────────────────────────────────────────────────"
  echo "  Run: bin/tcc-audit.sh open-settings"
  echo "  → opens each relevant System Settings pane sequentially for grant."
  echo "═══════════════════════════════════════════════════════════════════"
}

open_settings() {
  echo "Opening relevant Privacy & Security panes. Grant needed entries, then close."
  for entry in "${categories_panes[@]}"; do
    cat="${entry%%|*}"
    pane="${entry#*|}"
    echo "▶ $cat …"
    open "x-apple.systempreferences:com.apple.preference.security?$pane" 2>/dev/null || \
      open "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?$pane" 2>/dev/null || \
      echo "  could not open pane $pane"
    sleep 1.2
  done
  echo "Done. Review each pane; add Hammerspoon / Terminal / Ghostty / zsh where missing."
}

reset_category() {
  local category=${2:-}; local bundle=${3:-}
  if [ -z "$category" ] || [ -z "$bundle" ]; then
    echo "usage: $0 reset <category> <bundle_id>"
    echo "example: $0 reset Accessibility org.hammerspoon.Hammerspoon"
    exit 1
  fi
  echo "tccutil reset $category $bundle …"
  tccutil reset "$category" "$bundle"
}

case "$cmd" in
  report|"") report ;;
  open-settings|open) open_settings ;;
  reset) reset_category "$@" ;;
  *) echo "usage: $0 [report|open-settings|reset <cat> <bundle>]"; exit 1 ;;
esac
