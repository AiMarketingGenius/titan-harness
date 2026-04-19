-- auto_approve_claude_prompts.lua — CT-0419-08 Layer 3 defense-in-depth
-- Observes Terminal/iTerm/Ghostty/Warp/Alacritty/Tabby for Claude Code
-- permission prompts. If the detected target (edit/write path or bash cmd)
-- matches the ~/.claude/settings.json permissions.allow list, auto-selects
-- "1. Yes" after a 2s debounce. Non-whitelisted prompts are NEVER auto-clicked.
--
-- Triggered AFTER Layers 1+2 fail (settings.json bypassPermissions + CLI flag);
-- this is last-resort so most sessions will log zero events.

local M = {}

local json = require("hs.json")

-- tuneables
local SETTINGS_PATH    = os.getenv("HOME") .. "/.claude/settings.json"
local LOG_DIR          = os.getenv("HOME") .. "/titan-harness/logs"
local LOG_PATH         = LOG_DIR .. "/auto_approve.log"
local QUEUE_DIR        = os.getenv("HOME") .. "/titan-harness/logs/auto_approve_queue"
local DEBOUNCE_SEC     = 2.0
local POLL_INTERVAL    = 0.8
local TAIL_CHARS       = 3000
local TERMINAL_APPS    = { Terminal=true, iTerm2=true, iTerm=true, Ghostty=true, Warp=true, Alacritty=true, Tabby=true }

-- TCC (macOS privacy dialog) configuration — CT-0419-08 Layer B
-- Requesting-app allowlist: only auto-Allow when one of these apps triggered the dialog.
local TCC_ALLOW_APPS = {
  ["Claude"] = true, ["claude"] = true, ["claude.app"] = true,
  ["Terminal"] = true, ["iTerm2"] = true, ["iTerm"] = true, ["Ghostty"] = true,
  ["Warp"] = true, ["Alacritty"] = true, ["Tabby"] = true,
  ["Hammerspoon"] = true,
  ["node"] = true, ["python3"] = true, ["python"] = true,
  ["osascript"] = true, ["zsh"] = true, ["bash"] = true, ["sh"] = true,
  ["Visual Studio Code"] = true, ["Code"] = true,
  ["git"] = true, ["gh"] = true,
}

-- Explicit DENY categories — NEVER auto-approve these regardless of requesting app.
-- Humans must grant sensitive hardware / personal-data access.
local TCC_DENY_CATEGORIES = {
  ["Camera"] = true,
  ["Microphone"] = true,
  ["Screen Recording"] = true,
  ["Screen & System Audio Recording"] = true,
  ["Contacts"] = true,
  ["Calendar"] = true, ["Calendars"] = true,
  ["Reminders"] = true,
  ["Photos"] = true,
  ["Location Services"] = true, ["Location"] = true,
  ["HomeKit"] = true,
  ["Speech Recognition"] = true,
  ["Bluetooth"] = true,
  ["Media Library"] = true,
  ["Music"] = true, ["Apple Music"] = true,
  ["Health"] = true,
}

-- System apps that host TCC dialogs
local TCC_HOST_APPS = {
  ["UserNotificationCenter"] = true,
  ["tccd"] = true,
  ["System Settings"] = true,
  ["System Preferences"] = true,
  ["coreservicesd"] = true,
  ["CoreLocationAgent"] = true,
  ["universalAccessAuthWarn"] = true,
}

-- state
local timer            = nil
local lastSig          = nil
local lastSeenAt       = 0
local lastActionSig    = nil
local lastActionAt     = 0
local tccSeenWindowIds = {}  -- dedupe: window_id -> ts of last action

hs.fs.mkdir(LOG_DIR)
hs.fs.mkdir(QUEUE_DIR)

local function nowSec()
  return hs.timer.absoluteTime() / 1e9
end

local function isoNow()
  return os.date("!%Y-%m-%dT%H:%M:%SZ")
end

local function writeLog(line)
  local f = io.open(LOG_PATH, "a")
  if f then f:write(isoNow() .. " " .. line .. "\n"); f:close() end
end

local function queueMcp(event)
  -- Write one-line JSON to queue dir; sidecar ingester (lib/auto_approve_ingest.py)
  -- ships to MCP via log_decision. Decoupled from Hammerspoon → MCP auth concerns.
  local fname = string.format("%s/%d-%d.json", QUEUE_DIR, os.time(), math.random(100000, 999999))
  local f = io.open(fname, "w")
  if f then f:write(json.encode(event)); f:close() end
end

local function loadAllow()
  local f = io.open(SETTINGS_PATH, "r")
  if not f then return {} end
  local content = f:read("*a")
  f:close()
  local ok, data = pcall(json.decode, content)
  if not ok or not data then return {} end
  return (data.permissions or {}).allow or {}
end

local function globToPattern(glob)
  -- Convert Claude allowlist glob to Lua pattern. Supports **, *, literal.
  local p = glob
  p = p:gsub("([%^%$%(%)%%%+%-%?%[%]])", "%%%1")   -- escape Lua specials except * and .
  p = p:gsub("%%%*%%%*", ".*")                      -- ** → anything
  p = p:gsub("%%%*", "[^/]*")                       -- *  → anything-except-slash
  return "^" .. p .. "$"
end

local function pathMatches(path, allow)
  if not path then return false end
  path = path:gsub("^%s+", ""):gsub("%s+$", "")
  for _, rule in ipairs(allow) do
    local glob = rule:match("^Edit%((.+)%)$") or rule:match("^Write%((.+)%)$")
    if glob then
      if glob == "*" then return true end
      local ok, match = pcall(function() return path:match(globToPattern(glob)) end)
      if ok and match then return true end
    end
  end
  return false
end

local function bashMatches(cmd, allow)
  if not cmd then return false end
  local head = cmd:match("^(%S+)")
  if not head then return false end
  for _, rule in ipairs(allow) do
    local bp = rule:match("^Bash%((.+)%)$")
    if bp then
      if bp == "*" then return true end
      local prefix = bp:match("^(%S+)")
      if prefix == head then return true end
    end
  end
  return false
end

local function getFrontTerminalText()
  local app = hs.application.frontmostApplication()
  if not app then return nil, nil end
  local name = app:name()
  if not TERMINAL_APPS[name] then return nil, name end
  local axApp = hs.axuielement.applicationElement(app)
  if not axApp then return nil, name end
  local focused = axApp.AXFocusedWindow
  if not focused then return nil, name end

  local collected = {}
  local function walk(el, depth)
    if depth > 7 or not el then return end
    local ok_role, role = pcall(function() return el.AXRole end)
    if ok_role and (role == "AXTextArea" or role == "AXStaticText") then
      local ok_val, val = pcall(function() return el.AXValue end)
      if ok_val and type(val) == "string" and #val > 0 then
        table.insert(collected, val)
      end
    end
    local ok_kids, kids = pcall(function() return el.AXChildren end)
    if ok_kids and kids then
      for _, c in ipairs(kids) do walk(c, depth + 1) end
    end
  end
  pcall(walk, focused, 0)
  if #collected == 0 then return nil, name end
  local joined = table.concat(collected, "\n")
  if #joined > TAIL_CHARS then joined = joined:sub(-TAIL_CHARS) end
  return joined, name
end

-- Pattern detector: returns { kind, target } or nil
-- Claude Code CLI TUI prompts typically end with numbered options "❯ 1. Yes ..."
local function detectPrompt(content)
  if not content then return nil end
  -- Must have the tell-tale numbered-yes option near the tail
  if not content:find("1%.%s*Yes") and not content:find("❯%s*1") and not content:find("Allow Claude") then
    return nil
  end

  -- Edit pattern
  local p = content:match("[Ee]dit%s+([^\n]+%.[%w]+)[^\n]*\n[^\n]*Yes")
      or content:match("make this edit to%s+([^\n?]+)")
      or content:match("Allow Claude to edit%s+([^\n?]+)")
  if p then
    p = p:gsub("^%s+", ""):gsub("%s+$", ""):gsub("%?+$", "")
    return { kind = "edit", target = p }
  end

  -- Write pattern
  p = content:match("[Ww]rite%s+([^\n]+%.[%w]+)[^\n]*\n[^\n]*Yes")
      or content:match("write this file to%s+([^\n?]+)")
      or content:match("create%s+([^\n?]+%.[%w]+)[^\n]*Yes")
  if p then
    p = p:gsub("^%s+", ""):gsub("%s+$", ""):gsub("%?+$", "")
    return { kind = "write", target = p }
  end

  -- Bash pattern
  p = content:match("run this command%?[^\n]*\n%s*([^\n]+)")
      or content:match("Allow Claude to run%s+([^\n?]+)")
  if p then
    p = p:gsub("^%s+", ""):gsub("%s+$", "")
    return { kind = "bash", target = p }
  end
  return nil
end

-- ─── TCC dialog handling (Layer B) ────────────────────────────────────────
-- Parse TCC window title to extract (requesting_app, category)
local function parseTccTitle(title)
  if not title or title == "" then return nil, nil end
  local app = title:match("^[\"']?([^\"']+)[\"']?%s+[Ww]ould like")
           or title:match("^[\"']?([^\"']+)[\"']?%s+wants")
           or title:match("^[\"']?([^\"']+)[\"']?%s+requests")
           or title:match("^[\"']?([^\"']+)[\"']?%s+is trying")
  local category = title:match("access to%s+[\"']?([^\"']+)[\"']?")
                or title:match("access%s+[\"']?([^\"']+)[\"']?%s+data")
                or title:match("control%s+[\"']?([^\"']+)[\"']?")
                or title:match("would like to access%s+the%s+([%w%s&]+)")
  if app then
    app = app:gsub("%.app$", "")
  end
  return app, category
end

local function findButtonInWindow(axWin, labels)
  if not axWin then return nil end
  local function walk(el, depth)
    if depth > 8 or not el then return nil end
    local ok_role, role = pcall(function() return el.AXRole end)
    if ok_role and role == "AXButton" then
      local ok_t, t = pcall(function() return el.AXTitle end)
      if ok_t and t then
        for _, lbl in ipairs(labels) do
          if t == lbl then return el end
        end
      end
    end
    local ok_k, kids = pcall(function() return el.AXChildren end)
    if ok_k and kids then
      for _, k in ipairs(kids) do
        local f = walk(k, depth + 1)
        if f then return f end
      end
    end
    return nil
  end
  return walk(axWin, 0)
end

local function handleTccWindow(win, hostAppName)
  if not win then return end
  local wid
  local ok_id = pcall(function() wid = win:id() end)
  if not ok_id or not wid then return end

  -- Dedupe: skip if we've already acted on this window recently
  local now = nowSec()
  if tccSeenWindowIds[wid] and (now - tccSeenWindowIds[wid]) < 10 then
    return
  end

  local title = ""
  pcall(function() title = win:title() or "" end)
  if title == "" then return end

  local app, category = parseTccTitle(title)
  if not app then return end

  -- Normalize app key
  local appKey = app
  local appBase = app:match("^([^%s]+)")

  if not (TCC_ALLOW_APPS[appKey] or TCC_ALLOW_APPS[appBase] or TCC_ALLOW_APPS[app]) then
    writeLog(string.format("tcc skip not-in-allowlist host=%s app=%q title=%q", hostAppName, app, title))
    queueMcp({
      event = "tcc_auto_approve",
      action = "skipped_not_whitelisted",
      app = app,
      category = category,
      host = hostAppName,
      title = title,
      ts = isoNow(),
    })
    tccSeenWindowIds[wid] = now
    return
  end

  -- Check DENY categories
  if category and TCC_DENY_CATEGORIES[category] then
    writeLog(string.format("tcc skip deny-category host=%s app=%q cat=%q", hostAppName, app, category))
    queueMcp({
      event = "tcc_auto_approve",
      action = "skipped_deny_category",
      app = app,
      category = category,
      host = hostAppName,
      title = title,
      ts = isoNow(),
    })
    tccSeenWindowIds[wid] = now
    return
  end

  -- Dual-title DENY scan: some TCC titles embed the category inline (no "access to" phrase)
  for deny, _ in pairs(TCC_DENY_CATEGORIES) do
    if title:lower():find(deny:lower(), 1, true) then
      writeLog(string.format("tcc skip deny-in-title host=%s app=%q deny=%q", hostAppName, app, deny))
      queueMcp({
        event = "tcc_auto_approve",
        action = "skipped_deny_in_title",
        app = app,
        category = deny,
        host = hostAppName,
        title = title,
        ts = isoNow(),
      })
      tccSeenWindowIds[wid] = now
      return
    end
  end

  -- Mark so we don't re-debounce this exact window
  tccSeenWindowIds[wid] = now

  -- 2s debounce then click Allow / OK
  hs.timer.doAfter(DEBOUNCE_SEC, function()
    -- Re-check window still exists + re-check title didn't morph
    local ok_exists = pcall(function() return win:isVisible() end)
    if not ok_exists then return end

    local axWin = hs.axuielement.windowElement(win)
    if not axWin then
      writeLog(string.format("tcc axWin-nil app=%q", app))
      return
    end
    local btn = findButtonInWindow(axWin, { "Allow", "OK", "Allow Once", "Allow While Using App" })
    if btn then
      pcall(function() btn:performAction("AXPress") end)
      writeLog(string.format("tcc approved host=%s app=%q cat=%q", hostAppName, app, tostring(category)))
      queueMcp({
        event = "tcc_auto_approve",
        action = "approved",
        app = app,
        category = category,
        host = hostAppName,
        title = title,
        ts = isoNow(),
      })
    else
      writeLog(string.format("tcc no-button-found host=%s app=%q", hostAppName, app))
      queueMcp({
        event = "tcc_auto_approve",
        action = "no_button_found",
        app = app,
        category = category,
        host = hostAppName,
        title = title,
        ts = isoNow(),
      })
    end
  end)
end

local function scanTccWindows()
  -- Iterate visible windows once per tick; cheap (~dozen entries max)
  local ok, wins = pcall(hs.window.visibleWindows)
  if not ok or not wins then return end
  for _, win in ipairs(wins) do
    local ok_app, app = pcall(function() return win:application() end)
    if ok_app and app then
      local name = app:name() or ""
      if TCC_HOST_APPS[name] then
        pcall(handleTccWindow, win, name)
      end
    end
  end

  -- Garbage-collect old dedupe entries (>5 min)
  local now = nowSec()
  for wid, ts in pairs(tccSeenWindowIds) do
    if (now - ts) > 300 then tccSeenWindowIds[wid] = nil end
  end
end

-- ─── Main tick ─────────────────────────────────────────────────────────────
local function tick()
  -- Always scan TCC dialogs regardless of front app (they can pop behind terminals)
  pcall(scanTccWindows)

  local content, appName = getFrontTerminalText()
  if not content then
    -- Not a terminal or no text: reset debounce so stale prompts don't auto-fire
    lastSig = nil
    lastSeenAt = 0
    return
  end
  local prompt = detectPrompt(content)
  if not prompt then
    lastSig = nil
    lastSeenAt = 0
    return
  end

  local sig = prompt.kind .. "::" .. prompt.target
  local now = nowSec()

  if sig ~= lastSig then
    -- new prompt observed: start debounce window
    lastSig = sig
    lastSeenAt = now
    return
  end

  -- Same prompt still visible. Suppress re-fire for 10s after last action.
  if sig == lastActionSig and (now - lastActionAt) < 10 then
    return
  end

  -- Debounce window satisfied?
  if (now - lastSeenAt) < DEBOUNCE_SEC then return end

  local allow = loadAllow()
  local approved
  if prompt.kind == "edit" or prompt.kind == "write" then
    approved = pathMatches(prompt.target, allow)
  elseif prompt.kind == "bash" then
    approved = bashMatches(prompt.target, allow)
  else
    approved = false
  end

  local action = approved and "approved" or "skipped_not_whitelisted"
  writeLog(string.format("app=%s kind=%s target=%q action=%s", appName or "?", prompt.kind, prompt.target, action))
  queueMcp({
    event = "auto_approve",
    action = action,
    kind = prompt.kind,
    target = prompt.target,
    app = appName,
    ts = isoNow(),
  })

  lastActionSig = sig
  lastActionAt = now

  if approved then
    -- Press "1" then Enter to select "Yes"
    hs.eventtap.keyStroke({}, "1", 30000)
    hs.timer.doAfter(0.1, function()
      hs.eventtap.keyStroke({}, "return", 30000)
    end)
  end
  -- On skip we do nothing — let the human decide. Re-evaluation is gated by 10s window above.
end

function M.start()
  if timer then return end
  timer = hs.timer.doEvery(POLL_INTERVAL, function()
    local ok, err = pcall(tick)
    if not ok then writeLog("tick_error: " .. tostring(err)) end
  end)
  writeLog("auto_approve_claude_prompts started poll=" .. POLL_INTERVAL .. "s debounce=" .. DEBOUNCE_SEC .. "s (Claude + TCC layers active)")
end

function M.stop()
  if timer then timer:stop(); timer = nil; writeLog("auto_approve_claude_prompts stopped") end
end

function M.status()
  return {
    active = timer ~= nil,
    lastSig = lastSig,
    lastSeenAt = lastSeenAt,
    lastActionSig = lastActionSig,
    lastActionAt = lastActionAt,
  }
end

return M
