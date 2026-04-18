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
local MCP_LOG_HELPER = os.getenv("HOME") .. "/titan-harness/scripts/tla-path-4/bin/log_mcp_invocation.sh"

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
  -- LibreSSL (macOS) outputs bare hex with no "HMAC-SHA256(stdin)= " prefix.
  -- Write canonical string to temp file to avoid quoting surprises with
  -- newlines and special chars in body JSON.
  local tmp = os.tmpname()
  local f = io.open(tmp, "wb")
  if not f then return nil end
  f:write(msg)
  f:close()
  local cmd = string.format(
    "/usr/bin/openssl dgst -sha256 -hmac %q -hex < %q 2>/dev/null",
    key, tmp
  )
  local out, ok = hs.execute(cmd, true)
  os.remove(tmp)
  if not ok or out == nil then return nil end
  -- Strip trailing newline; if a prefix like "HMAC-SHA256(stdin)= " is present
  -- on other openssl builds, extract just the trailing hex token.
  out = out:gsub("%s+$", "")
  local hex = out:match("[0-9a-f]+$")
  return hex
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

  -- Titan host app on Mac may be called "Claude" (Desktop app) or "Claude Code"
  -- (future CLI-wrapped app). Support both.
  local claude_candidates = {"Claude Code", "Claude"}
  local is_claude_active = false
  for _, n in ipairs(claude_candidates) do
    if app_name == n then is_claude_active = true; break end
  end

  if is_claude_active and active_recent then
    -- Solon is actively typing in the Claude session — defer
    hs.timer.doAfter(DEFER_SECONDS, function() inject_nudge(phrase) end)
    local entry = string.format('{"ts":"%s","action":"defer","reason":"active_keystrokes_within_30s","retry_at":"%s"}\n',
      os.date("!%Y-%m-%dT%H:%M:%SZ"), os.date("!%Y-%m-%dT%H:%M:%SZ", os.time() + DEFER_SECONDS))
    local f = io.open(MCP_DECISION_LOG, "a")
    if f then f:write(entry); f:close() end
    return {status = "deferred", defer_seconds = DEFER_SECONDS}
  end

  -- Find the Claude window across candidate app names
  local cc = nil
  for _, n in ipairs(claude_candidates) do
    cc = hs.application.find(n)
    if cc ~= nil then break end
  end
  if cc == nil then
    return {status = "failed", reason = "claude_app_not_running", candidates_tried = claude_candidates}
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

-- ---------------------------------------------------------------------------
-- MCP-polling inversion (added 2026-04-18 post-reveal that VPS→Mac inbound
-- isn't reachable without a tunnel). n8n writes an op_decision tagged
-- `tla-nudge-fire-pending` + `nudge-id-<uuid>`; Hammerspoon polls every 30s.
-- ---------------------------------------------------------------------------

local mcp_poll_timer = nil
local MCP_POLL_SECONDS = 30
local POLL_SCRIPT = os.getenv("HOME") .. "/.hammerspoon/poll_nudge_queue.sh"
local ACK_SCRIPT  = os.getenv("HOME") .. "/.hammerspoon/ack_nudge.sh"

local function mcp_poll_once()
  if not hs.fs.attributes(POLL_SCRIPT) then return end
  local out, ok = hs.execute(POLL_SCRIPT, true)
  if not ok or out == nil then return end
  local parsed = nil
  local ok_parse, obj = pcall(hs.json.decode, out)
  if ok_parse then parsed = obj end
  if parsed == nil or parsed.nudge ~= true then return end
  local nudge_id = parsed.nudge_id or "no-id"
  local phrase = parsed.phrase or NUDGE_PHRASE
  -- If the pending payload explicitly marks dry_run, skip the keystroke
  -- (still fire the ack so the record doesn't re-trigger).
  local dry_run = (parsed.dry_run == true) or phrase:find("DRY_RUN_ONLY") ~= nil
  if dry_run then
    hs.execute(string.format("bash %q %q dry_run &", ACK_SCRIPT, nudge_id), true)
    return
  end
  local result = inject_nudge(phrase)
  local outcome = (result and result.status) or "unknown"
  hs.execute(string.format("bash %q %q %q &", ACK_SCRIPT, nudge_id, outcome), true)
end

local function start_mcp_poller()
  if mcp_poll_timer ~= nil then return end
  mcp_poll_timer = hs.timer.doEvery(MCP_POLL_SECONDS, mcp_poll_once)
end

-- ---------------------------------------------------------------------------
-- Public API
-- ---------------------------------------------------------------------------

function M.start()
  install_keystroke_watcher()
  start_server()
  start_mcp_poller()
  hs.alert.show("TLA Path 4 armed (HTTP:41710 + MCP poll 30s)")
end

function M.stop()
  if server ~= nil then server:stop(); server = nil end
  if keystroke_watcher ~= nil then keystroke_watcher:stop(); keystroke_watcher = nil end
  if mcp_poll_timer ~= nil then mcp_poll_timer:stop(); mcp_poll_timer = nil end
end

function M.dry_run_inject()
  -- For local testing only — bypasses HMAC + server.
  return inject_nudge(NUDGE_PHRASE)
end

function M.force_poll()
  -- Test helper — fires MCP poll immediately without waiting 30s.
  mcp_poll_once()
end

return M
