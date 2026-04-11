# titan_queue_watcher.py — Phase G.3 War Room integration patch

The autonomous `titan-queue-watcher.service` runs
`/usr/local/bin/titan_queue_watcher.py` (Python), NOT the legacy
`titan-queue-watcher.sh` that still sits in `/usr/local/bin/` as an
older reference. The Python daemon polls the `tasks` table, claims a
pending task, calls Claude Haiku to produce a deliverable, and marks
the task complete.

Phase G.3 inserts a war-room grading step between "executed" and
"completed". The shim at `bin/war-room-shim.sh` decides whether the
deliverable is war-roomable, invokes `bin/war-room.sh` if so, and
optionally swaps the deliverable for a refined version.

## Where to insert (line reference for titan_queue_watcher.py ~line 389)

Immediately BEFORE:
```python
            # Success — write deliverable
            supa_patch("tasks?id=eq." + task_id, {
                "status": "completed",
                ...
```

## The block to insert

```python
            # --- Phase G.3 War Room integration ---------------------------------
            # Grade non-trivial plan/architecture/phase deliverables before
            # marking complete. Failures are non-fatal and keep the original.
            try:
                import subprocess, tempfile
                _wr_shim = "/opt/titan-harness/bin/war-room-shim.sh"
                if os.path.isfile(_wr_shim) and os.access(_wr_shim, os.X_OK):
                    _wr_tmp = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".txt", delete=False,
                        dir="/tmp", prefix=f"titan_deliverable_{task_id[:8]}_")
                    _wr_tmp.write(deliverable)
                    _wr_tmp.close()
                    _wr_tags = ",".join(task.get("tags", []) or [])
                    _wr_proc = subprocess.run(
                        [_wr_shim, task_id, _wr_tmp.name, task_type, _wr_tags],
                        capture_output=True, text=True, timeout=240)
                    _wr_result = (_wr_proc.stdout or "").strip()
                    log("[WAR-ROOM] " + task_id[:8] + " " + _wr_result)
                    if _wr_result.startswith("graded:") and ":swapped" in _wr_result:
                        try:
                            with open(_wr_tmp.name) as _f:
                                _refined = _f.read()
                            if _refined.strip():
                                deliverable = _refined
                        except OSError:
                            pass
                    try:
                        os.unlink(_wr_tmp.name)
                    except OSError:
                        pass
            except Exception as _wr_e:
                log("[WAR-ROOM] " + task_id[:8] + " shim error: " + str(_wr_e)[:200])
            # --- End Phase G.3 War Room integration -----------------------------
```

## Behavior

- **Non-blocking** — any failure in the shim or war-room is logged but
  does not affect task completion. The original deliverable is preserved.
- **Opt-in per task** — the shim decides whether to actually run the war
  room based on `task_type` substring matching (`plan`, `architecture`,
  `spec`, `phase`) or tag matching (`war_room`, `plan_finalization`,
  `architecture_decision`, `phase_completion`).
- **240-second timeout** — accommodates up to 3 rounds of Perplexity
  grading plus 2 Claude Haiku revisions. Each API call itself has a
  shorter timeout inside `war_room.py`.
- **Swap guardrail** — `war-room-shim.sh` refuses to swap the
  deliverable if the graded version is outside 50%–500% of the original
  size. Prevents accidental truncation from a bad revision.

## Rollback

```bash
# Restore the pre-G.3 version from the on-VPS backup
cp /usr/local/bin/titan_queue_watcher.py.pre-g3-bak \
   /usr/local/bin/titan_queue_watcher.py
systemctl restart titan-queue-watcher
```

The backup was created at Phase G.3 shipment time. The shim itself can
remain installed — it is purely additive and only activates when the
watcher calls it.

## Verification

```bash
# Confirm the patch is in place
grep -c war-room-shim /usr/local/bin/titan_queue_watcher.py   # → 1

# Confirm the shim is executable
test -x /opt/titan-harness/bin/war-room-shim.sh && echo ok

# Inspect the war-room log after the next war-room-eligible task runs
tail -f /var/log/titan-war-room.log
```
