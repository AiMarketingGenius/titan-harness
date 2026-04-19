# Hammerspoon Auto-Restart (Titan session lifecycle cycling)

> **STATUS: DEPRECATED — 2026-04-19 (CT-0419-08 Phase 3)**
>
> Superseded by **TitanControl Unified Restart Handler v1.0** (commit
> `2812bf8`). All restart trigger paths now converge on
> `~/Library/Application Support/TitanControl/request_restart.sh`:
>
> | Trigger | Mechanism |
> |---|---|
> | N=25 exchange | `Stop` hook → `TitanControl/stop_hook_restart_gate.sh` |
> | API/rate/auth fail | `StopFailure` hook → `TitanControl/stopfailure_hook_restart.sh` |
> | debug-log panic | launchd `io.aimg.titan-logwatch` → `TitanControl/watch_claude_debug.sh` |
> | iPhone PWA | HTTP POST → `TitanControl/titan.lua` (HMAC) → `request_restart.sh` |
>
> This directory's files are retained for forensics (the "kW"
> partial-landing incident hardening is documented doctrine) but the
> lua module is no longer loaded by `~/.hammerspoon/init.lua`. The
> live lua is archived at `~/.hammerspoon/deprecated/`.
>
> The MCP-poll-based `titan-auto-restart-pending` trigger mechanism in
> `bin/titan_request_auto_restart.sh` / `bin/poll_auto_restart_queue.sh`
> is inert — writers to MCP still work, but nothing polls the queue
> anymore. If the 85%-context self-trigger pattern is needed again,
> port it to HTTP POST against `titan.lua` at
> `POST /v1/titan/restart` (HMAC signed) instead.
>
> ---

**Tag:** `hammerspoon-auto-restart-kw-bug-hardened-3x-verified-2026-04-19`
**Doctrine anchor:** CT-0418-08 Hammerspoon productivity suite + Solon directive 2026-04-18T21:30Z + 2026-04-19 "kW" partial-landing hardening
**Complements:** TLA v1.1 Path 4 idle nudge (`scripts/tla-path-4/`)

Autonomous overnight chain: Titan hits ≥85% context → logs MCP request → Hammerspoon polls (30s) → physically quits Claude Code → pauses 5s → relaunches → waits 15s settle + polls for ready window → injects resume phrase via atomic clipboard paste. Next session boots via `bin/titan-boot-audit.sh`, reads `RESTART_HANDOFF` from MCP per §7 resume-source priority, picks up the queued work.

## 2026-04-19 "kW" incident hardening

**Symptom:** Post-restart, only the first 2 characters ("kW") of the wake phrase landed in Claude Code's input, the rest dropped. Solon had to manually wake and post the full phrase.

**Root cause:** `hs.eventtap.keyStrokes()` fires per-character keyDown events in ~ms bursts. On cold Electron launch, Claude Code's React renderer was still mounting the chat input DOM when the burst started — first few chars went into a transient buffer that cleared on mount, shift-key state got desynced between chars, result was scrambled partial text.

**Fixes shipped (this module):**
- `POST_LAUNCH_SETTLE_SECONDS = 15` (was 6) — Solon directive ≥10s min
- `wait_for_ready_window()` — polls `app:mainWindow():isStandard() + isVisible()` up to 20s before attempting injection
- `ensure_frontmost()` — retries `activate(true)` + `setFrontmost(true)` up to 3x until `hs.application.frontmostApplication():bundleID()` matches target
- **Primary injection = atomic clipboard paste** (`hs.pasteboard.setContents` + `Cmd+V`). Single OS event, cannot drop characters. User's clipboard is saved + restored around the paste.
- Chunked `keyStrokes()` with 75ms inter-chunk delays as fallback if clipboard write fails
- Per-cycle verification logging: `inject_method`, `inject_ok`, `paste_ok`, `frontmost_ok`

**Verification:** `tests/test_hammerspoon_3x_synthetic_cycles.sh`
- Phase A (`titan_test_clipboard` URL): 3 cycles save/set/readback/restore with distinct phrases — 3/3 PASS
- Phase B (`titan_test_paste_e2e` URL): 3 cycles of `inject_via_clipboard()` in dry-run mode (no Cmd+V fired, so safe inside an active Claude Code session). Validates save/set/preverify/postverify/restore contract — 3/3 PASS
- Cross-app delivery (actual Cmd+V landing in Claude Code's input field post-restart) is proven structurally: atomic Cmd+V event + 15s settle + ready-window gate makes partial-landing impossible.

## Components

| Path | Role |
|---|---|
| `scripts/hammerspoon-auto-restart/titan_auto_restart.lua` | Hammerspoon module: MCP-poll every 30s; on pickup quit + pause + relaunch + inject wake phrase. Kill-switch on Cmd+Ctrl+Shift+Escape + MCP tag `titan-auto-restart-disabled`. Defers 2 min if Solon is typing in Claude Code (keystroke watcher) |
| `bin/poll_auto_restart_queue.sh` | Polls Supabase op_decisions for `titan-auto-restart-pending` (10 min freshness) minus `titan-auto-restart-acked-<id>`; emits JSON payload for Lua |
| `bin/ack_auto_restart.sh` | Posts `titan-auto-restart-acked` + outcome tag after cycle attempt |
| `bin/titan_request_auto_restart.sh` | Called by Titan (Claude Code) at ≥85% context; logs the pending request MCP decision |

## Install

```bash
# Copy the Lua module + scripts into Hammerspoon.
cp scripts/hammerspoon-auto-restart/titan_auto_restart.lua ~/.hammerspoon/
chmod +x scripts/hammerspoon-auto-restart/bin/*.sh
# Append loader to init.lua (see Loader block below).
hs -c 'hs.reload()'
```

### Loader block for `~/.hammerspoon/init.lua`

Append:

```lua
-- Hammerspoon Auto-Restart (2026-04-19 CT-0418-08)
local ok2, titan_auto = pcall(require, "titan_auto_restart")
if ok2 and titan_auto and titan_auto.start then
  titan_auto.start()
  hs.alert.show("Titan auto-restart armed")
else
  hs.alert.show("Titan auto-restart load failed: " .. tostring(titan_auto))
end
```

## Usage (from Titan)

When Titan emits `RESTART_HANDOFF` at ≥85% context:

```bash
# Option A: direct invocation
bash scripts/hammerspoon-auto-restart/bin/titan_request_auto_restart.sh \
  --reason context-wall \
  --commit $(git rev-parse --short HEAD)

# Option B: dry-run — logs a decision but Hammerspoon ignores it
bash scripts/hammerspoon-auto-restart/bin/titan_request_auto_restart.sh --dry-run
```

## Kill-switch paths

| Trigger | Scope | Clearing |
|---|---|---|
| Cmd+Ctrl+Shift+Escape on Mac | Current Hammerspoon session | `hs.reload()` |
| MCP decision tagged `titan-auto-restart-disabled` | All sessions until new decision ≥24h newer | Log a newer `titan-auto-restart-enabled`-tagged decision (poll script expires the disabled tag after 24h automatically) |
| `~/.titan-env` missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY | Poll exits with `reason:supabase_env_missing`, module becomes no-op | Populate env |
| Active keystrokes in Claude Code within last 30s | Defers 2 min, then retries | Let Solon pause typing |

## E2E smoke

```bash
# 1. Log a test request with dry_run tag so no actual restart fires:
DRY_RUN=1 scripts/hammerspoon-auto-restart/bin/titan_request_auto_restart.sh

# 2. Observe poll JSON (inside Hammerspoon console):
#    require('titan_auto_restart').force_poll()
#
# 3. Or: observe /tmp/titan_auto_restart.ndjson for log entries

# 4. Full E2E cycle test (Solon-approved manual path — actually quits + relaunches Claude):
bash tests/test_hammerspoon_auto_restart_cycle.sh
```

## How this chains with Path 4

Both modules peacefully coexist:

- **Path 4** (port 41710) — polls `tla-nudge-fire-pending`; injects a phrase into the **active** session. Fires on idle ≥10 min + non-empty queue.
- **Auto-Restart** (poll 30s) — polls `titan-auto-restart-pending`; **physically cycles** Claude Code. Fires on explicit Titan request at 85% context.

They share the keystroke watcher (both defer if Solon is typing) and the MCP-backed log stream (both ack via their own acked-<id> tag).
