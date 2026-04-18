# TLA Path 4 — n8n Idle Heartbeat + Hammerspoon Nudge

TLA v1.1 DELTA 8 implementation. Every 60s, n8n polls Supabase for:
- Last titan-authored MCP decision timestamp (idle threshold ≥10 min triggers fire)
- `operator_task_queue` rows where `status=pending AND approval=pre_approved`
- Kill-switch MCP tags (`tla-nudge-disabled` OR `tla-disabled`)

When idle ≥10 min AND queue non-empty AND no kill-switch (OR any urgent task bypasses idle gate),
n8n HMAC-signs a payload and POSTs to a Hammerspoon localhost endpoint on the Mac. Hammerspoon verifies the HMAC, checks Claude Code isn't actively receiving keystrokes (30s buffer), then types a sentinel phrase into the active Claude Code session.

CO-ARCHITECT parameters (dual-engine consensus 2026-04-18T18:28Z):
- Idle threshold: **10 min** (Grok) — Sonar proposed 12 min as fallback
- Dedupe window: **15 min** (both engines converged)
- Urgent-priority dedupe override: **true** (both engines converged)
- Keystroke race mitigation: **pre-nudge AXFocused + 30s keystroke buffer check, defer 2 min if active**
- Nudge phrase: `«MCP_QUEUE_POLL» poll MCP queue for pending tasks tagged today` (combined sentinel + instruction)

## Files

| File | Purpose |
|------|---------|
| `tla_nudge.lua` | Hammerspoon module — HTTP server on 127.0.0.1:41710, HMAC-verifies POST /nudge, injects keystrokes into Claude Code with race-condition pre-check |
| `n8n_idle_nudge_workflow.json` | n8n workflow — cron 60s → Supabase queries → fire-gate → HMAC sign → POST → log MCP |
| `bin/generate_hmac_key.sh` | Mac-side utility: generates 32-byte hex secret, stores in Keychain under `titan-tla-nudge`, prints for n8n env config |
| `bin/log_mcp_invocation.sh` | Mac-side utility called post-injection from `tla_nudge.lua` to write MCP op_decisions row |

## Activation (Solon — requires screenshots per UI-instruction rule)

**HARD LIMITS that must stay with Solon:**
1. **Hammerspoon install** — if not already present: `brew install --cask hammerspoon` (CLI autonomous) + grant Accessibility permission via System Settings (UI click — needs annotated screenshot pass on execution day; staged here, cannot automate).
2. **Keychain write** — running `bin/generate_hmac_key.sh` prompts Keychain unlock on first run (UI click — screenshot pass needed).
3. **n8n env var insertion** — `TLA_NUDGE_HMAC_SECRET` + `TLA_NUDGE_ENDPOINT` into n8n config (VPS-side; no UI but Solon-reviewable).

When Solon is at the Mac:
1. Install Hammerspoon (one-time). Grant Accessibility permission.
2. Run `bash scripts/tla-path-4/bin/generate_hmac_key.sh`. Paste the printed secret into VPS `/etc/amg/tla-nudge.env` as `TLA_NUDGE_HMAC_SECRET=<value>` (root:root 0600).
3. Add the following to `~/.hammerspoon/init.lua`:
   ```lua
   package.path = package.path .. ";/Users/solonzafiropoulos1/titan-harness/scripts/tla-path-4/?.lua"
   local tla_nudge = require("tla_nudge")
   tla_nudge.start()
   ```
4. Reload Hammerspoon (menu bar → Reload Config). Expect alert `TLA Path 4 nudge daemon listening on 127.0.0.1:41710`.
5. Import `n8n_idle_nudge_workflow.json` into the VPS n8n UI. Activate.
6. Validate with a manual nudge: `curl -X POST http://127.0.0.1:41710/nudge -H 'X-Titan-Ts: $(date +%s)' -H 'X-Titan-Sig: <hmac>' -d '{}'` — should inject the sentinel phrase into active Claude Code.

## Smoke test plan (post-activation)

1. Suppress Titan-authored MCP writes for 12 min (no activity).
2. Queue a synthetic pending task via `queue_operator_task` with `status=pending, approval=pre_approved`.
3. Observe: within ≤60s of the 12-min mark, Hammerspoon alert fires + sentinel phrase appears in Claude Code.
4. Titan's next turn parses `«MCP_QUEUE_POLL»` sentinel, runs `get_task_queue`, claims + executes.

Success Criterion 16 (DELTA 6) PASS = full loop within 90s of idle-threshold crossing.

## Kill-switches

- **Hammerspoon-side global abort:** `cmd+shift+escape` disables the nudge for this Hammerspoon session (re-enable via `hs.reload()`).
- **MCP tag kill-switch:** write an MCP decision with tag `tla-nudge-disabled` → n8n stops firing (check runs every 60s).
- **Global `tla-disabled` tag:** halts all four trigger paths (1/2/3/4).

## Kill by rotation

If HMAC secret is compromised: `bash bin/generate_hmac_key.sh --rotate` + update VPS `TLA_NUDGE_HMAC_SECRET` + n8n redeploy. Old secret becomes invalid immediately (HMAC mismatch → 401).

## Known limits v0.1

- Hammerspoon only — adapter interface (DELTA 3) not yet wired; future `cloud-mac-ssh` adapter will replace Lua module when cloud-Mac path activates.
- Single active Claude Code window assumption. Multiple windows = may nudge wrong one. Future: window-title or process-id scoping.
- AXFocused check sometimes reports stale under Mac fast-user-switching. Race mitigation covers the common case, not all edge cases.
