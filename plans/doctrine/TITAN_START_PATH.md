# Titan Start Path — Mac + VPS (CT-0417-27 T3-prep)

**Purpose:** document exactly how Titan boots on both machines so the remote-restart endpoint (CT-0417-27 T3) can target the correct process without touching atlas-api — Mobile Command depends on atlas-api staying up.

---

## 1. Mac start path (existing infrastructure — reuse)

### Components

| File | Role |
|---|---|
| `~/Library/LaunchAgents/com.amg.titan-autorestart.plist` | launchd agent, watches the flag file, fires `titan-restart-launch.sh` on touch |
| `~/.claude/titan-restart.flag` | touch this file to trigger a restart |
| `bin/titan-restart-capture.sh` | helper that captures current session state, then touches the flag |
| `bin/titan-restart-launch.sh` | idempotent launcher — reads flag, debounces 30 s, logs, opens new Claude Code session in Terminal/iTerm |
| `bin/install-titan-autorestart.sh` | one-shot installer for the plist |

### Restart mechanics (how to kick it from atlas-api)

```bash
# 1. Run flush (saves session state, writes MCP heartbeat)
~/titan-harness/bin/titan-restart-capture.sh

# 2. Touch the flag — launchd observes, fires launch script
touch ~/.claude/titan-restart.flag
```

**What restarts:** the Claude Code CLI session (Titan's brain).
**What does NOT restart:** atlas-api service, any other background process.

### Debounce + daily cap

Built-in to `titan-restart-launch.sh`:
- 30-second debounce between launches (prevents flag-storm from re-launching rapidly)
- Daily cap of 50 launches (configurable via `TITAN_RESTART_DAILY_CAP` env var)

The T3 restart endpoint's per-IP rate limit (3 / 5 min) is a *first* line of defense; the launcher's debounce is second; the daily cap is third.

### Log + state paths

```
~/.claude/titan-restart.log            ← human-readable launch log
~/.claude/titan-restart.last-launch-ts ← unix ts of last launch
~/.claude/titan-restart.daily/         ← per-day count files
~/.claude/titan-resume-state.json      ← state captured by capture.sh for the next session's boot
```

---

## 2. VPS start path

### Active services

```
atlas-api.service       loaded active   running   ← /api/* endpoints; CANNOT restart from T3
titan-agent.service     loaded failed   failed    ← Titan's autonomous loop (currently down)
titan-autowake.service  loaded inactive dead      ← auto-wake monitor (oneshot)
```

### titan-agent.service internals

```ini
[Service]
Type=forking
User=root
WorkingDirectory=/opt/amg-titan
EnvironmentFile=/opt/amg-titan/.env
ExecStart=/usr/bin/tmux new-session -d -s titan-agent '/usr/bin/python3 /opt/amg-titan/titan_agent.py'
ExecStop=/usr/bin/tmux send-keys -t titan-agent C-c
ExecStopPost=/usr/bin/tmux kill-session -t titan-agent
Restart=on-failure
RestartSec=10
```

The VPS Titan runtime lives at `/opt/amg-titan/titan_agent.py` inside a tmux session named `titan-agent`. Restart = `systemctl restart titan-agent`.

### Restart mechanics (how to kick it from atlas-api)

```bash
# From inside atlas-api (running as root on VPS already), restart just the titan-agent service:
systemctl restart titan-agent.service
# → ExecStop sends Ctrl-C into the tmux session
# → ExecStopPost kills the tmux session
# → ExecStart opens a fresh tmux session running titan_agent.py
# → RestartSec=10 means the unit respects a 10s window between retries
```

**What restarts:** titan-agent Python process + its tmux session.
**What does NOT restart:** atlas-api (different unit), any other service.

---

## 3. Restart endpoint — proposed design (Task 3)

### 3.1 Endpoint: `POST /api/titan/session/restart`

Request:
```json
{
  "reason": "Why the restart was triggered (logged to MCP)",
  "target": "mac" | "vps" | "both"    // defaults to "both"
}
```

Headers:
```
Authorization: Bearer <TITAN_RESTART_TOKEN>
```

Response:
```json
{
  "status": "ok",
  "targets_restarted": ["mac", "vps"],
  "mac": {
    "flag_touched": true,
    "launchd_label": "com.amg.titan-autorestart",
    "expected_new_session_within": "30s"
  },
  "vps": {
    "systemctl_exit": 0,
    "old_session_uptime_sec": 18432,
    "new_session_started_at": "2026-04-17T18:23:14Z",
    "mcp_handshake": true
  },
  "reason": "Solon requested from phone"
}
```

### 3.2 Auth mechanism (per Solon direction)

- **Bearer token** stored in `/etc/amg/titan-restart.env` on VPS (600 perms, root-owned)
- **Token rotation** via `POST /api/titan/session/rotate-token` (requires current token; writes new one + logs rotation to MCP)
- **Rate limit:** 3 restarts per 5-min window per IP, enforced at the endpoint
- **Slack fallback:** `/titan-restart` slash-command hits `POST /api/titan/session/restart` with `X-Slack-Signature` + `X-Slack-Request-Timestamp` HMAC verification (using `SLACK_SIGNING_SECRET` env var)
- **MCP logging:** every restart writes `log_decision` with source IP, user-agent, reason, target
- **Token delivery:** after first token generation, Titan prints it once to stderr with instructions to save to password manager; the token never lands in git or MCP memory

### 3.3 Restart flow (full path)

```
POST /api/titan/session/restart
  ↓  (auth check, rate limit, MCP log of incoming request)
atlas-api handler
  ├── target=mac  → ssh-tunnel to Mac control socket OR (if atlas-api is on Mac) local flag-touch
  │                  → ~/titan-harness/bin/titan-restart-capture.sh   (flush state)
  │                  → touch ~/.claude/titan-restart.flag              (launchd fires)
  │                  → wait up to 30s for new-session-ts to advance
  │                  → return confirmation
  ├── target=vps  → systemctl restart titan-agent.service
  │                  → wait up to 15s for service to reach "active" state
  │                  → probe MCP handshake via get_sprint_state
  │                  → return confirmation
  └── response bundled + final MCP log written
```

Critical: **atlas-api itself never restarts through this endpoint.** Circular dependency kills Mobile Command if atlas-api goes down.

---

## 4. Effort-level toggle (Task 4)

### 4.1 Endpoint: `POST /api/titan/session/effort`

```json
{"level": "medium" | "high" | "max", "reason": "optional"}
```

Behavior:
1. Write level to `~/.claude/effort.conf` on Mac AND `/etc/amg/titan-effort.conf` on VPS (atomic via rename-from-tempfile).
2. Call the restart endpoint (§3) with target="both" and reason prefixed with "effort toggle → {level}".
3. Return both the new level + the restart response.

### 4.2 Effort → model-variant mapping

Claude Code exposes model selection via the `ANTHROPIC_MODEL` env var. Titan's launcher reads `~/.claude/effort.conf` before `exec claude`:

```bash
# Inside bin/titan-restart-launch.sh, before opening the new Claude Code session:
EFFORT_CONF="$HOME/.claude/effort.conf"
if [ -f "$EFFORT_CONF" ]; then
  EFFORT="$(cat "$EFFORT_CONF" | tr -d '[:space:]')"
  case "$EFFORT" in
    medium) export ANTHROPIC_MODEL="claude-sonnet-4-6" ;;
    high)   export ANTHROPIC_MODEL="claude-opus-4-6"   ;;
    max)    export ANTHROPIC_MODEL="claude-opus-4-6"; export CLAUDE_THINKING_BUDGET="high" ;;
    *)      ;;  # default — Claude Code uses its configured default
  esac
fi
```

**Research note:** Claude Code's runtime thinking-budget toggle is not a first-class config flag today. The practical mechanism is model-variant swap (Sonnet for medium / Opus for high / Opus + extended-thinking for max). Confirmed via Claude Code docs 2026-04-17. If future Claude Code versions expose a first-class `--effort max` CLI flag, `bin/titan-restart-launch.sh` picks it up with a one-line change.

---

## 5. Remote Control panel (Mobile Command UI)

The 3-button segmented control (Medium / High / Max) lives on `ops.aimarketinggenius.io/titan` under the new "Remote Control" panel (same tab as the folder-lock status from CT-0417-27 T1 §7).

Tapping a button:
1. Toast: "Restarting Titan at {level}…"
2. POST `/api/titan/session/effort` with the level
3. Poll `/api/titan/session/status` every 2s until `new_session_ready` is true
4. Toast: "Titan restarted at {level}. MCP handshake green."
5. If handshake fails in 30s → red error + "tap to see restart log"

---

## 6. Security posture

- Every endpoint under `/api/titan/session/*` requires the bearer token OR a valid Slack HMAC header
- Token stored ONLY in `/etc/amg/titan-restart.env` (VPS, 600 perms, root) — not in git, not in MCP, not in Mac keychain
- First-token-generation flow prints the token once to stderr (Solon copies to password manager), then purges from stderr buffer
- Every call logs source IP + user-agent + reason to MCP decisions
- Token rotation is an endpoint, not a ceremony — Solon rotates from phone anytime
- Rate limit: 3 calls per 5 minutes per IP
- No destructive ops accessible via these endpoints (restart is the only mutation; no DB writes, no file deletes, no key rotations)

---

## 7. What this doc deliberately does NOT do

- Does not commit the token to any file tracked in git
- Does not deploy the endpoints (Task 3 / 4 write code; deploy happens via atlas-api restart which itself only happens on a scheduled maintenance window, not from this endpoint)
- Does not promise zero-downtime for the VPS Titan session restart — there's a ~10-15s window where titan-agent is not servicing autonomous tasks. Mobile Command + atlas-api stay up.
