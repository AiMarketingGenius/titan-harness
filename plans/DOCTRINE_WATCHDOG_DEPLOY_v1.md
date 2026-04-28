# DOCTRINE — Watchdog Deploy v1

**Status:** ACTIVE
**Effective:** 2026-04-28 (CT-0428-23)
**Owner:** Titan
**Related:** CT-0427-57 (Watchdog v0.1 build), CT-0428-10 (Docker probe fix), CT-0428-23 (this doctrine)

---

## 1. Canonical location

`~/titan-harness/bin/watchdog/` on Mac (Solon's machine) is the **canonical source**. Mirrors flow:

```
Mac ~/titan-harness/bin/watchdog/
        │
        ▼  (post-commit hook → git push origin master)
VPS bare /opt/titan-harness.git
        │
        ▼  (post-receive hook → checkout)
VPS working /opt/titan-harness/bin/watchdog/
        │
        ▼  (symlink, this doctrine)
VPS scheduled /opt/amg-titan/scripts/watchdog/
```

All four legs hold identical content because the last leg is a symbolic link to the third.

## 2. Why a symlink (not a copy)

Pre-2026-04-28, `/opt/amg-titan/scripts/watchdog/` was a separate file copy from `/opt/titan-harness/bin/watchdog/`. Patches required manual `cp` from the harness mirror to the scheduled location after every push. CT-0428-10 surfaced this trap: the watchdog Docker-probe fix landed via auto-mirror at `/opt/titan-harness/bin/watchdog/` but did NOT propagate to the scheduled `/opt/amg-titan/scripts/watchdog/`, requiring an extra manual copy.

Symlinking eliminates the dedupe trap permanently. Future watchdog patches mirror through the harness once and become live at the scheduled location automatically.

## 3. Cron schedule (as of 2026-04-28)

```
*/5  * * * * /opt/amg-titan/scripts/watchdog/fast.py    >> /var/log/amg-watchdog.log 2>&1
*/15 * * * * /opt/amg-titan/scripts/watchdog/slow.py    >> /var/log/amg-watchdog.log 2>&1
0    4 * * * /opt/amg-titan/scripts/watchdog/daily.py   >> /var/log/amg-watchdog.log 2>&1
```

Cron invokes the .py files **directly** (relying on the `#!/usr/bin/env python3` shebang + executable bit). So `chmod +x` is required on `fast.py`, `slow.py`, `daily.py`, and `verify.py`. The harness commits these as mode `100755`. `lib.py` and `config.json` do not need `+x` — they're imported, not executed.

## 4. Patch flow

Going forward, to update any watchdog file:

1. Edit at `~/titan-harness/bin/watchdog/<file>` on Mac.
2. Commit + push. Auto-mirror cascade lands the change at `/opt/titan-harness/bin/watchdog/<file>` on VPS.
3. **Symlink resolves transparently** — `/opt/amg-titan/scripts/watchdog/<file>` is now the new content at no manual cost.
4. Cron picks up the new code on the next */5 (fast), */15 (slow), or daily 04:00 (daily) tick.

## 5. Hot-reload guarantee

`fast.py`, `slow.py`, `daily.py` are stateless (read config + state, write receipt, exit). No long-running daemon. Symlink swap during a cron cycle is safe — the running process loaded code at start; the next invocation loads the new code from the symlinked path.

If a watchdog ever becomes a long-running daemon, the symlink approach still works for subsequent invocations but will not affect the in-flight process; that's acceptable since the daemon model isn't currently used.

## 6. Verification (run after any harness watchdog change)

```bash
ssh root@vps '
# 1. Confirm symlink intact
test -L /opt/amg-titan/scripts/watchdog && \
  readlink /opt/amg-titan/scripts/watchdog
# Expected: /opt/titan-harness/bin/watchdog

# 2. Confirm fresh content visible at scheduled path
sha256sum /opt/titan-harness/bin/watchdog/slow.py \
          /opt/amg-titan/scripts/watchdog/slow.py
# Expected: identical hashes

# 3. Manual smoke
python3 /opt/amg-titan/scripts/watchdog/slow.py && \
  tail -2 /var/log/amg-watchdog.log
'
```

## 7. Backup retention

Pre-symlink content is preserved at `/opt/amg-titan/scripts/watchdog.legacy.20260428/` for two cron cycles after symlink creation, then removed. If a future regression requires fall-back, the harness git history (`bin/watchdog/`) is the authoritative recovery source — the legacy backup is convenience only.

## 8. Rollback

If the symlink misbehaves (extremely unlikely given the symlink-vs-copy semantics):

```bash
ssh root@vps '
rm /opt/amg-titan/scripts/watchdog
cp -rp /opt/titan-harness/bin/watchdog /opt/amg-titan/scripts/watchdog
chmod +x /opt/amg-titan/scripts/watchdog/{fast,slow,daily,verify}.py
'
```

This restores the pre-doctrine copy-based deploy. Harness remains canonical either way.

---

*End of DOCTRINE_WATCHDOG_DEPLOY_v1.md.*
