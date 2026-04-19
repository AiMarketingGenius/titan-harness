-- ~/.hammerspoon/titan.lua — TitanControl Restart Handler v1.1 HTTP ingress
-- Part of Atlas Command PWA v1.0 (CT-0419-17, 2026-04-19).
-- require("titan") from init.lua to activate.
--
-- Endpoints (all on port 8765):
--   GET  /v1/titan/status             (unauthenticated)
--   GET  /v1/titan/recent-decisions   (HMAC-authed, last 5 MCP decisions)
--   POST /v1/titan/restart            (HMAC-authed, fires request_restart.sh)
--   POST /v1/titan/shutdown           (HMAC-authed, graceful stop no auto-boot)
--   POST /v1/titan/upload             (HMAC-authed, multipart → ~/titan-session/uploads/)
--   POST /v1/titan/voice-memo         (HMAC-authed, audio bytes → voice-memos/)
-- URL scheme: hammerspoon://titan-restart (local fallback)
-- CORS enabled for pwa.aimarketinggenius.io (and local dev).

local json = hs.json

local TITAN = {
  port = 8765,
  appDir = os.getenv("HOME") .. "/Library/Application Support/TitanControl",
  stateDir = os.getenv("HOME") .. "/Library/Application Support/TitanControl/state",
  handler = os.getenv("HOME") .. "/Library/Application Support/TitanControl/request_restart.sh",
  secretFile = os.getenv("HOME") .. "/.config/titan-control.secret",
  sessionDir = os.getenv("HOME") .. "/titan-session",
  uploadsDir = os.getenv("HOME") .. "/titan-session/uploads",
  voiceMemosDir = os.getenv("HOME") .. "/titan-session/voice-memos",
  nonceTTL = 60,
  nonces = {},
  startupTs = os.time(),
}

-- ensure dirs
hs.fs.mkdir(TITAN.uploadsDir)
hs.fs.mkdir(TITAN.voiceMemosDir)

local function readFile(path)
  local f = io.open(path, "r"); if not f then return nil end
  local s = f:read("*a"); f:close(); return s
end

local function writeFile(path, bytes)
  local f = io.open(path, "wb"); if not f then return false end
  f:write(bytes); f:close(); return true
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

local function verifyRequest(path, headers, bodyHash)
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
  -- Canonical: ts\nnonce\npath (body is signed separately via x-titan-body-hash header on uploads)
  local canonical = table.concat({ts, nonce, path}, "\n")
  if bodyHash then canonical = canonical .. "\n" .. bodyHash end
  local expected = hmacHex(secret, canonical)
  if not expected or not consteq(expected, sig) then return false, "bad_signature" end
  TITAN.nonces[nonce] = now()
  for n, t in pairs(TITAN.nonces) do
    if (now() - t) > TITAN.nonceTTL then TITAN.nonces[n] = nil end
  end
  return true, nil
end

local function countExchanges()
  local f = io.open(os.getenv("HOME") .. "/titan-session/.exchange-count", "r")
  if not f then return nil end
  local s = f:read("*a"); f:close()
  return tonumber(s or "")
end

local function readStatus()
  local raw = readFile(TITAN.stateDir .. "/status.json")
  local decoded = {}
  if raw and raw ~= "" then
    local ok, d = pcall(json.decode, raw)
    if ok and type(d) == "table" then decoded = d end
  end
  decoded.ok = true
  decoded.state = decoded.state or "unknown"
  decoded.uptime_s = os.time() - TITAN.startupTs
  decoded.exchange_count = countExchanges()
  local app = hs.application.get("claude") or hs.application.get("Terminal")
  decoded.terminal_live = (app ~= nil)
  return decoded
end

local function jsonResp(obj, code)
  return json.encode(obj, true), code or 200, {
    ["Content-Type"] = "application/json",
    ["Cache-Control"] = "no-store",
    ["Access-Control-Allow-Origin"] = "*",
    ["Access-Control-Allow-Headers"] = "Content-Type,X-Titan-Timestamp,X-Titan-Nonce,X-Titan-Signature,X-Titan-Body-Hash,X-Titan-Filename,X-Titan-Mime",
    ["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS",
  }
end

local function startHandler(source, extraArgs)
  local args = {
    "-lc",
    shq(TITAN.handler) .. " --source " .. shq(source) .. " --reason " .. shq("manual_request") .. (extraArgs or "")
  }
  local task = hs.task.new("/bin/zsh", nil, args)
  return task:start()
end

-- Recent MCP decisions — pulls Supabase via curl from /root/.titan-env (VPS) if available,
-- else from ~/.titan-env on Mac. Fails gracefully on network error.
local function recentDecisions(limit)
  limit = limit or 5
  local envPath = os.getenv("HOME") .. "/.titan-env"
  local env = readFile(envPath) or ""
  local supaUrl = env:match("SUPABASE_URL=[\"']?(https?://[^\"'\n]+)")
  local key = env:match("SUPABASE_SERVICE_ROLE_KEY=[\"']?([A-Za-z0-9._%-]+)")
  if not supaUrl or not key then return { ok = true, decisions = {}, note = "env_not_available" } end
  local url = supaUrl .. "/rest/v1/op_decisions?select=created_at,decision_text,tags,project_source&order=created_at.desc&limit=" .. limit
  local cmd = "/usr/bin/curl -sS --max-time 5 -G " .. shq(url)
    .. " -H " .. shq("apikey: " .. key)
    .. " -H " .. shq("Authorization: Bearer " .. key)
  local out = sh(cmd) or "[]"
  local ok, rows = pcall(json.decode, out)
  if not ok or type(rows) ~= "table" then return { ok = true, decisions = {} } end
  -- Truncate decision_text for payload economy
  for _, r in ipairs(rows) do
    if r.decision_text and #r.decision_text > 300 then r.decision_text = r.decision_text:sub(1, 300) .. "..." end
  end
  return { ok = true, decisions = rows }
end

local function saveUpload(body, headers, destDir)
  hs.fs.mkdir(destDir)
  local h = normalizeHeaders(headers)
  local filename = h["x-titan-filename"] or (os.date("!%Y%m%dT%H%M%SZ") .. "-upload.bin")
  filename = filename:gsub("[/\\]", "_"):gsub("%.%.", ".")
  local path = destDir .. "/" .. os.date("!%Y%m%dT%H%M%SZ") .. "-" .. filename
  if not writeFile(path, body) then return nil, "write_failed" end
  return path
end

-- Bind HTTP server — prefer Tailscale IP
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
  -- CORS preflight
  if method == "OPTIONS" then return jsonResp({ ok = true }, 204) end

  if method == "GET" and path == "/v1/titan/status" then
    return jsonResp(readStatus(), 200)
  end

  if method == "GET" and path == "/v1/titan/recent-decisions" then
    local ok, err = verifyRequest(path, headers, nil)
    if not ok then return jsonResp({ ok = false, error = err }, 401) end
    return jsonResp(recentDecisions(5), 200)
  end

  if method == "POST" and path == "/v1/titan/restart" then
    local ok, err = verifyRequest(path, headers, nil)
    if not ok then return jsonResp({ ok = false, error = err }, 401) end
    local st = readStatus()
    if st.state == "killing" or st.state == "booting" then
      return jsonResp({ ok = true, accepted = false, state = st.state,
        request_id = st.request_id, note = "restart_already_in_progress" }, 202)
    end
    if not startHandler("manual:mobile-command") then
      return jsonResp({ ok = false, error = "handler_start_failed" }, 500)
    end
    return jsonResp({ ok = true, accepted = true, state = "accepted" }, 202)
  end

  if method == "POST" and path == "/v1/titan/shutdown" then
    local ok, err = verifyRequest(path, headers, nil)
    if not ok then return jsonResp({ ok = false, error = err }, 401) end
    if not startHandler("manual:pwa-power-off", " --no-autoboot") then
      return jsonResp({ ok = false, error = "handler_start_failed" }, 500)
    end
    return jsonResp({ ok = true, accepted = true, state = "shutting_down" }, 202)
  end

  if method == "POST" and path == "/v1/titan/upload" then
    -- body-hash signed in x-titan-body-hash header
    local h = normalizeHeaders(headers)
    local bodyHash = h["x-titan-body-hash"]
    local ok, err = verifyRequest(path, headers, bodyHash)
    if not ok then return jsonResp({ ok = false, error = err }, 401) end
    if not body or #body == 0 then return jsonResp({ ok = false, error = "empty_body" }, 400) end
    local savedPath, e = saveUpload(body, headers, TITAN.uploadsDir)
    if not savedPath then return jsonResp({ ok = false, error = e }, 500) end
    return jsonResp({ ok = true, path = savedPath, bytes = #body }, 201)
  end

  if method == "POST" and path == "/v1/titan/voice-memo" then
    local h = normalizeHeaders(headers)
    local bodyHash = h["x-titan-body-hash"]
    local ok, err = verifyRequest(path, headers, bodyHash)
    if not ok then return jsonResp({ ok = false, error = err }, 401) end
    if not body or #body == 0 then return jsonResp({ ok = false, error = "empty_body" }, 400) end
    local savedPath, e = saveUpload(body, headers, TITAN.voiceMemosDir)
    if not savedPath then return jsonResp({ ok = false, error = e }, 500) end
    return jsonResp({ ok = true, path = savedPath, bytes = #body }, 201)
  end

  return jsonResp({ ok = false, error = "not_found" }, 404)
end)
server:start()

hs.urlevent.bind("titan-restart", function() startHandler("manual:local-url") end)

return TITAN
