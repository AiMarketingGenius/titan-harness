# Persistent Memory Proof — 2026-04-26

**Verdict:** Extension NOT firing in this Chrome instance.

## Evidence (live JS exec on https://www.kimi.com/)

```json
{
  "sessionStatus": null,
  "keys": ["__tea_session_id_20001731", "kimi-web-extension-disabled"],
  "localKeys": [],
  "hasBootstrapDOMMarker": false,
  "inputElements": [{"tag":"DIV","content":""}],
  "allCookies": []
}
```

`amg.hercules.bootstrap.status.v1` is `null`, no DOM marker, no inject. The
side-channel `kimi-web-extension-disabled` is also present, suggesting Kimi
has its own extension-blocking flag set in sessionStorage which may be
suppressing the injector even if loaded.

## Bypass snippet (paste into Kimi composer manually)

```
Hercules online. Bootstrap memory load: pull the latest restart packet
from MCP (project_source=EOM, tag=RESTART_HANDOFF, count=1) and reply
with the packet contents + first action.
```

## Manual extension load steps (Solon-side)

1. Open `chrome://extensions/`
2. Toggle "Developer mode" (top right)
3. Click "Load unpacked"
4. Select directory: `/Users/solonzafiropoulos1/achilles-harness/agents/hercules/chrome_bootstrap_injector/`
5. Confirm "AMG Hercules Bootstrap Injector v1.0.0" appears with no errors
6. Reload kimi.com — the injector should fire on next visit

## Why we can't auto-load

Claude_in_Chrome MCP can't navigate `chrome://extensions/` (browser
restriction) and can't drive the native file-picker for "Load unpacked."
This is the one piece that needs Solon's keyboard.

## Auto-trigger after load

The extension's content_script.js (post-fix `5569dff`) should:
1. Detect `kimi.com` host match per manifest.json `host_permissions`
2. Fetch packet from local bootstrap server (`http://localhost/*`)
3. Set `sessionStorage["amg.hercules.bootstrap.status.v1"] = "sent"`
4. Auto-fill the composer DIV with the bootstrap text

If after manual load the snippet still doesn't auto-send, debug by:
- Open DevTools → Application → Service Workers → confirm the injector's
  background.js is "activated"
- Check console for fetch errors from the local bootstrap server
