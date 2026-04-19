-- ~/.hammerspoon/titan.lua — TitanControl Restart Handler v1.0 HTTP ingress
-- require("titan") from init.lua to activate.
--
-- Provides port 8765 HTTP server for iPhone Mobile Command PWA restart:
--   GET  /v1/titan/status     (unauthenticated, read-only)
--   POST /v1/titan/restart    (HMAC-authenticated, triggers request_restart.sh)
--
-- Also binds hammerspoon://titan-restart URL scheme as a local fallback.
--
-- Coexists with existing titan_auto_restart.lua (85%-context auto-cycle) and
-- tla_nudge.lua (TLA Path 4 idle-nudge). Different trigger mechanisms, same
-- restart handler endpoint (request_restart.sh).

local json = hs.json

local TITAN = {
  port = 8765,
  appDir = os.getenv("HOME") .. "/Library/Application Support/TitanControl",
  stateDir = os.getenv("HOME") .. "/Library/Application Support/TitanControl/state",
  handler = os.getenv("HOME") .. "/Library/Application Support/TitanControl/request_restart.sh",
  secretFile = os.getenv("HOME") .. "/.config/titan-control.secret",
  nonceTTL = 60,
  nonces = {},
}

local function readFile(path)
  local f = io.open(path, "r"); if not f then return nil end
  local s = f:read("*a"); f:close(); return s
end

local function sh(cmd)
  local p = io.popen(cmd .. " 2>/dev/null"); if not p then return nil end
  local out = p:read("*a"); p:close()
  if out then out = out:gsub("%s+$", "") end; return out
end

local function shq(s) s = tostring(s or ""); return "'" .. s:gsub("'", [['"'"']]) .. "'" end
local function now() return os.time() end

local function normalizeHeaders(headers)
  local out = {}; for k,v in pairs(headers or {}) do out[string.lower(k)] = v end; return out
end

local function consteq(a, b)
  if not a or not b or #a ~= #b then return false end
  local diff = 0
  for i = 1, #a do
    local xa = string.byte(a, i); local xb = string.byte(b, i)
    diff = bit32.bor(diff, bit32.bxor(xa, xb))
  end
  return diff == 0
end

local function hmacHex(secret, msg)
  local cmd = "/bin/printf %s " .. shq(msg)
    .. " | /usr/bin/openssl dgst -sha256 -hmac " .. shq(secret)
    .. " -binary | /usr/bin/xxd -p -c 256"
  return sh("/bin/zsh -lc " .. shq(cmd))
end

local function verifyRequest(path, headers)
  local h = normalizeHeaders(headers)
  local ts, nonce, sig = h["x-titan-timestamp"], h["x-titan-nonce"], h["x-titan-signature"]
  local secret = readFile(TITAN.secretFile)
  if not secret then return false, "missing_server_secret" end
  secret = secret:gsub("%s+$", "")
  if not ts or not nonce or not sig then return false, "missing_auth_headers" end
  local tsNum = tonumber(ts)
  if not tsNum or math.abs(now() - tsNum) > TITAN.nonceTTL then return false, "stale_timestamp" end
  if TITAN.nonces[nonce] and (now() - TITAN.nonces[nonce]) < TITAN.nonceTTL then
    return false, "replayed_nonce"
  end
  local canonical = table.concat({ts, nonce, path}, "\n")
  local expected = hmacHex(secret, canonical)
  if not expected or not consteq(expected, sig) then return false, "bad_signature" end
  TITAN.nonces[nonce] = now()
  for n, t in pairs(TITAN.nonces) do
    if (now() - t) > TITAN.nonceTTL then TITAN.nonces[n] = nil end
  end
  return true, nil
end

local function readStatus()
  local raw = readFile(TITAN.stateDir .. "/status.json")
  if not raw or raw == "" then return { ok = true, state = "unknown" } end
  local decoded = json.decode(raw)
  if type(decoded) ~= "table" then return { ok = true, state = "unknown" } end
  decoded.ok = true
  local app = hs.application.get("claude") or hs.application.get("Terminal")
  decoded.terminal_live = (app ~= nil)
  return decoded
end

local function jsonResp(obj, code)
  return json.encode(obj, true), code, {
    ["Content-Type"] = "application/json",
    ["Cache-Control"] = "no-store",
  }
end

local function startHandler(source)
  local task = hs.task.new("/bin/zsh", nil, {
    "-lc",
    shq(TITAN.handler) .. " --source " .. shq(source) .. " --reason " .. shq("manual_request")
  })
  return task:start()
end

-- Bind HTTP server — prefer Tailscale IP, fall back to all-interfaces with warning
local ts_ip = sh("/usr/local/bin/tailscale ip -4") or sh("/opt/homebrew/bin/tailscale ip -4")
if ts_ip then ts_ip = ts_ip:match("(%d+%.%d+%.%d+%.%d+)") end

local server = hs.httpserver.new(false, false)
server:setPort(TITAN.port)
if ts_ip then
  server:setInterface(ts_ip)
  hs.logger.new("titan"):i("Bound to Tailscale IP: " .. ts_ip)
else
  hs.logger.new("titan"):w("Tailscale IP not found — binding all interfaces; ensure firewall/ACL covers port 8765!")
end

server:setCallback(function(method, path, headers, body)
  if method == "GET" and path == "/v1/titan/status" then
    return jsonResp(readStatus(), 200)
  end

  if method == "POST" and path == "/v1/titan/restart" then
    local ok, err = verifyRequest(path, headers)
    if not ok then return jsonResp({ ok = false, error = err }, 401) end

    local st = readStatus()
    if st.state == "killing" or st.state == "booting" then
      return jsonResp({
        ok = true, accepted = false, state = st.state,
        request_id = st.request_id, note = "restart_already_in_progress"
      }, 202)
    end

    if not startHandler("manual:mobile-command") then
      return jsonResp({ ok = false, error = "handler_start_failed" }, 500)
    end
    return jsonResp({ ok = true, accepted = true, state = "accepted" }, 202)
  end

  return jsonResp({ ok = false, error = "not_found" }, 404)
end)
server:start()

-- Local fallback: hammerspoon://titan-restart
hs.urlevent.bind("titan-restart", function()
  startHandler("manual:local-url")
end)

return TITAN
