-- scripts/tla-path-4/tla_nudge.lua
--
-- TLA v1.1 Path 4 — Hammerspoon localhost HMAC-webhook handler for n8n-driven
-- idle-nudge keystroke injection into an active Claude Code session.
--
-- Per CO-ARCHITECT round 1 output 2026-04-18T18:28Z:
--   Idle threshold: 10 min (n8n-side)
--   Dedupe window: 15 min (n8n-side)
--   Urgent override: true (n8n-side)
--   Keystroke race mitigation: AXFocused + 30s keystroke-buffer check,
--     defer 2 min if Claude Code input is actively receiving keystrokes.
--   Nudge phrase: «MCP_QUEUE_POLL» poll MCP queue for pending tasks tagged today
--
-- This module is loaded by ~/.hammerspoon/init.lua via `require("tla_nudge")`.
-- See scripts/tla-path-4/README.md for installation.

local M = {}

-- ---------------------------------------------------------------------------
-- Configuration (reads from Keychain; fails closed if missing)
-- ---------------------------------------------------------------------------

local HMAC_SECRET = nil  -- lazy-loaded from Keychain
local LISTEN_PORT = 41710  -- localhost-only
local NUDGE_PHRASE = "«MCP_QUEUE_POLL» poll MCP queue for pending tasks tagged today"
local DEFER_SECONDS = 120
local KEYSTROKE_BUFFER_S = 30
local MCP_DECISION_LOG = "/tmp/tla_nudge_invocations.ndjson"
local MCP_LOG_HELPER = "/opt/titan-harness/scripts/tla-path-4/bin/log_mcp_invocation.sh"

-- ---------------------------------------------------------------------------
-- Recent-keystroke buffer (tracks when user last typed into Claude Code)
-- ---------------------------------------------------------------------------

local last_keystroke_ts = 0
local keystroke_watcher = nil

local function install_keystroke_watcher()
  if keystroke_watcher ~= nil then return end
  keystroke_watcher = hs.eventtap.new({hs.eventtap.event.types.keyDown}, function(event)
    local app = hs.application.frontmostApplication()
    if app and app:name() == "Claude Code" then
      last_keystroke_ts = hs.timer.secondsSinceEpoch()
    end
    return false  -- do not consume the event
  end)
  keystroke_watcher:start()
end

-- ---------------------------------------------------------------------------
-- HMAC verification (sha256, hex-encoded signature in X-Titan-Sig header)
-- ---------------------------------------------------------------------------

local function load_secret()
  if HMAC_SECRET ~= nil then return HMAC_SECRET end
  -- `security` CLI reads from macOS Keychain. Account name = "titan-tla-nudge".
  local out, status = hs.execute("/usr/bin/security find-generic-password -a 'titan-tla-nudge' -s 'titan-tla-nudge' -w 2>/dev/null", true)
  if not status or out == nil or out == "" then
    return nil
  end
  HMAC_SECRET = out:gsub("%s+$", "")
  return HMAC_SECRET
end

local function hex_hmac(key, msg)
  -- Hammerspoon's hs.hash does not expose HMAC directly; shell out to openssl.
  local cmd = string.format(
    "/usr/bin/printf '%%s' %q | /usr/bin/openssl dgst -sha256 -hmac %q -hex | awk '{print $2}'",
    msg, key
  )
  local out, ok = hs.execute(cmd, true)
  if not ok or out == nil then return nil end
  return out:gsub("%s+$", "")
end

local function constant_time_equal(a, b)
  if type(a) ~= "string" or type(b) ~= "string" then return false end
  if #a ~= #b then return false end
  local diff = 0
  for i = 1, #a do
    diff = diff | (string.byte(a, i) ~ string.byte(b, i))
  end
  return diff == 0
end

-- ---------------------------------------------------------------------------
-- Keystroke injection (with race-condition pre-check)
-- ---------------------------------------------------------------------------

local function inject_nudge(phrase)
  local now = hs.timer.secondsSinceEpoch()
  local app = hs.application.frontmostApplication()
  local app_name = app and app:name() or ""
  local active_recent = (now - last_keystroke_ts) < KEYSTROKE_BUFFER_S

  if app_name == "Claude Code" and active_recent then
    -- Solon is actively typing — defer
    hs.timer.doAfter(DEFER_SECONDS, function() inject_nudge(phrase) end)
    local entry = string.format('{"ts":"%s","action":"defer","reason":"active_keystrokes_within_30s","retry_at":"%s"}\n',
      os.date("!%Y-%m-%dT%H:%M:%SZ"), os.date("!%Y-%m-%dT%H:%M:%SZ", os.time() + DEFER_SECONDS))
    local f = io.open(MCP_DECISION_LOG, "a")
    if f then f:write(entry); f:close() end
    return {status = "deferred", defer_seconds = DEFER_SECONDS}
  end

  -- Find and focus the Claude Code window
  local cc = hs.application.find("Claude Code")
  if cc == nil then
    return {status = "failed", reason = "claude_code_not_running"}
  end
  cc:activate()
  hs.timer.usleep(300000)  -- 300ms focus settle

  -- Type the nudge phrase + enter
  hs.eventtap.keyStrokes(phrase)
  hs.timer.usleep(100000)
  hs.eventtap.keyStroke({}, "return")

  local entry = string.format('{"ts":"%s","action":"injected","phrase":%q,"app":%q}\n',
    os.date("!%Y-%m-%dT%H:%M:%SZ"), phrase, app_name)
  local f = io.open(MCP_DECISION_LOG, "a")
  if f then f:write(entry); f:close() end
  -- Fire MCP log helper in background (shells to VPS-stored Supabase creds)
  if hs.fs.attributes(MCP_LOG_HELPER) then
    hs.execute(string.format("bash %s 'path-4-nudge-injected' 'phrase-in:%s' &", MCP_LOG_HELPER, phrase), true)
  end
  return {status = "injected", phrase = phrase}
end

-- ---------------------------------------------------------------------------
-- HTTP server: localhost-only, HMAC-verified POST /nudge
-- ---------------------------------------------------------------------------

local server = nil

local function start_server()
  if server ~= nil then return end
  server = hs.httpserver.new(false, false)  -- no bonjour, no ssl
  server:setInterface("127.0.0.1")
  server:setPort(LISTEN_PORT)
  server:setCallback(function(method, path, headers, body)
    if method ~= "POST" or path ~= "/nudge" then
      return "Not Found", 404, {}
    end
    local secret = load_secret()
    if secret == nil then
      return '{"error":"hmac_secret_unavailable"}', 500, {["Content-Type"] = "application/json"}
    end
    local sig_header = headers["X-Titan-Sig"] or headers["x-titan-sig"] or ""
    local ts_header = headers["X-Titan-Ts"] or headers["x-titan-ts"] or ""
    local ts_n = tonumber(ts_header) or 0
    local now_n = hs.timer.secondsSinceEpoch()
    if math.abs(now_n - ts_n) > 60 then
      return '{"error":"timestamp_out_of_window"}', 401, {["Content-Type"] = "application/json"}
    end
    local canonical = ts_header .. "\n" .. (body or "")
    local expected = hex_hmac(secret, canonical)
    if expected == nil or not constant_time_equal(expected, sig_header) then
      return '{"error":"hmac_mismatch"}', 401, {["Content-Type"] = "application/json"}
    end
    -- Parse body: JSON { phrase: <optional override>, urgent: <bool> }
    local phrase = NUDGE_PHRASE
    if body and #body > 0 then
      local ok, parsed = pcall(hs.json.decode, body)
      if ok and type(parsed) == "table" and type(parsed.phrase) == "string" then
        phrase = parsed.phrase
      end
    end
    local result = inject_nudge(phrase)
    return hs.json.encode(result), 200, {["Content-Type"] = "application/json"}
  end)
  server:start()
  hs.alert.show("TLA Path 4 nudge daemon listening on 127.0.0.1:" .. LISTEN_PORT)
end

-- ---------------------------------------------------------------------------
-- Kill switch: Cmd+Shift+Escape aborts any in-progress defer timer and
-- disables the nudge for this session. Re-enable via hs.reload().
-- ---------------------------------------------------------------------------

local aborted = false

hs.hotkey.bind({"cmd", "shift"}, "escape", function()
  aborted = true
  hs.alert.show("TLA Path 4 nudge ABORTED for this Hammerspoon session")
end)

-- ---------------------------------------------------------------------------
-- Public API
-- ---------------------------------------------------------------------------

function M.start()
  install_keystroke_watcher()
  start_server()
end

function M.stop()
  if server ~= nil then server:stop(); server = nil end
  if keystroke_watcher ~= nil then keystroke_watcher:stop(); keystroke_watcher = nil end
end

function M.dry_run_inject()
  -- For local testing only — bypasses HMAC + server.
  return inject_nudge(NUDGE_PHRASE)
end

return M
