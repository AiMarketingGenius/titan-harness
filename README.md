# titan-harness — cross-instance Claude Code enforcement

Deployable harness that installs 4 Claude Code hooks on any machine
running Claude Code. Hooks write to shared Supabase tables so every
instance shares a single source of truth.

## Install
```bash
git clone ssh://root@170.205.37.148/opt/titan-harness.git ~/titan-harness
bash ~/titan-harness/install.sh --instance $(hostname -s)
```

## Hooks installed
- SessionStart — prints NEXT_TASK + last 3 handovers from Supabase
- PreToolUse — blocks Write/Edit without ACTIVE_TASK_ID; logs to tool_log
- PostToolUse — logs to tool_log
- SessionEnd — appends to HANDOVER.md locally + inserts session_handover row

## Shared backend (already live)
- Supabase: `session_handover`, `session_next_task`, `tool_log`, `titan_audit_log`
- n8n: Titan Heartbeat Watchdog (5min), QES canary, operator alerts
- Slack: #amg-admin alerts

## Env file precedence
1. `$HOME/.titan-env` (per-user)
2. `/opt/amg-titan/.env` (VPS)
3. `$HOME/.config/titan/env`

Required vars: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TITAN_INSTANCE`
