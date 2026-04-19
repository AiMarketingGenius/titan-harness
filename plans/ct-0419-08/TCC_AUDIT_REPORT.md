# CT-0419-08 — macOS TCC Pre-Grant Audit Report

**Date:** 2026-04-19
**Host:** Mac mini (Darwin 25.3.0)
**User:** solonzafiropoulos1

## Scope

Layer A of CT-0419-08 permission-plague fix. Audits macOS Transparency /
Consent / Control (TCC) grants for Titan-adjacent apps so that autonomous
Steroids sessions never trigger a Privacy & Security dialog mid-run.

Paired with Layer B (Hammerspoon auto-approve for stray TCC dialogs that
slip past pre-granting). A + B together cover system-level dialogs. L1
(settings.json allow-list) + L2 (--dangerously-skip-permissions) cover
Claude-Code-level dialogs.

## Observable state (2026-04-19 15:12 UTC)

Direct TCC.db read is blocked — reading it requires Full Disk Access, and
the audit tool doesn't have it. So the following is inferred from behavior
rather than declarative read.

| Check | Result |
|---|---|
| Hammerspoon is running | **yes** (pids 10177 + 97604 LaunchAgent) |
| Accessibility (via osascript + System Events frontmost-query) | **ALLOWED** |
| Files & Folders (read `$HOME/Documents`) | **ALLOWED** |
| Full Disk Access (read `$HOME/Library/Application Support/com.apple.TCC/TCC.db`) | **DENIED** |

## Required grants for Titan autonomy

| App / Binary | Category | Status | Rationale |
|---|---|---|---|
| Hammerspoon | Accessibility | **must be ALLOWED** | `hs.eventtap.keyStroke`, AX read |
| Hammerspoon | Input Monitoring | **must be ALLOWED** | low-level key inject |
| Terminal / iTerm / Ghostty | Accessibility | must be ALLOWED | drives Claude CLI + AX observers |
| Terminal / iTerm / Ghostty | Full Disk Access | **missing per inference** | edit across `$HOME`, read TCC.db |
| Terminal / iTerm / Ghostty | Automation → System Events | must be ALLOWED | AX-driven handler fallbacks |
| Claude (desktop, if used) | Files and Folders | must be ALLOWED | cross-app data reads (dialog observed 2026-04-19) |
| /bin/zsh | Full Disk Access | must be ALLOWED | login shell — inherits to child procs |
| /usr/bin/osascript | Accessibility | **ALLOWED** (verified functional) | UI scripting fallbacks |

### Explicit DENY — never auto-granted by Layer B handler

Sensitive hardware + personal-data categories. If a dialog surfaces for any
of these, the Hammerspoon Layer B handler logs + skips; human must click.

- Camera
- Microphone
- Screen Recording (+ Screen & System Audio Recording)
- Contacts
- Calendar / Calendars
- Reminders
- Photos
- Location Services
- HomeKit
- Speech Recognition
- Bluetooth
- Media Library / Music / Apple Music
- Health

## Action plan (Solon)

Grants are gated behind a user-visible toggle by design (SIP). The Titan
harness cannot write to TCC.db. Solon runs the audit helper to jump to
each pane:

```bash
bin/tcc-audit.sh open-settings
```

Verify each pane has the expected entries turned on:

1. **Privacy → Accessibility:** Hammerspoon, Terminal (or your default
   terminal), osascript (rarely shown — OK if absent).
2. **Privacy → Full Disk Access:** Terminal, iTerm2 (if used), Ghostty
   (if used), `/bin/zsh` (add via "+" → navigate to `/bin/zsh`).
3. **Privacy → Input Monitoring:** Hammerspoon.
4. **Privacy → Automation:** Hammerspoon → System Events enabled; your
   terminal → System Events enabled.
5. **Privacy → Files and Folders:** Claude (desktop app, if running —
   enable whichever folders it asks for like Documents / Desktop).

Panes that should be **audit-only, no changes:** Camera, Microphone,
Screen Recording, Contacts, Calendar, Reminders, Photos, Location.

## Why pre-granting matters

Titan's autonomous Steroids runs happen post-Stop-hook-restart, while
Solon is AFK. A mid-run TCC dialog blocks forward progress until Solon
returns and clicks Allow. Pre-granting Layer A eliminates the prompt at
source; Layer B auto-dismisses any stray dialog that slips through
(e.g. app updates reset specific grants to "ask again next time").

## Verification protocol (AC 9)

After a future autonomous Steroids session:

1. `grep -c tcc_auto_approve ~/titan-harness/logs/auto_approve.log` — total TCC events.
2. `grep tcc ~/titan-harness/logs/auto_approve.log | awk '{print $NF}' | sort | uniq -c` — tally by action.
3. MCP query: `search_memory "auto-approve" tags=["tcc-auto-approve"]` — MCP-side audit trail.

Acceptance: zero dialogs surfaced to Solon during a 60-min autonomous run.
If `skipped_deny_category` events appear, that is correct behavior (Layer B
caught a dialog and deferred to human, as designed).

## Non-SIP-bypassing approach

This audit and helper explicitly do NOT:

- disable SIP
- edit TCC.db directly
- inject grant rows via private APIs
- use `sudo spctl --master-disable`
- rely on third-party permission spoofers

The only programmatic action available is `tccutil reset <category> <bundle>`
which resets a stale DENY/stuck-prompt entry so it re-asks fresh; grants
must still come via UI click.
