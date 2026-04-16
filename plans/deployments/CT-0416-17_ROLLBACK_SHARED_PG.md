# CT-0416-17 — ROLLBACK: SHARED POSTGRES + REDIS → LOCAL SQLITE + LOCAL REDIS

**Created:** 2026-04-16 23:35Z (during migration)
**Mirrored to:** `/opt/n8n/ROLLBACK_SHARED_PG.md` on both VPS via cascade

---

## WHEN TO RUN THIS ROLLBACK

ANY of:
- Workflow count diverges from 41 on either VPS after cutover
- Active workflow count diverges from 4 on either VPS
- Credentials fail to import / decrypt on Postgres side
- Either VPS n8n container refuses to start on Postgres
- Webhook end-to-end fails for >2 min after cutover
- Any production workflow execution fails during cutover window
- Beast cannot connect to HostHatch Postgres (network / auth)
- Postgres container itself crashes within first 30 min of cutover

---

## ROLLBACK STEPS (run on BOTH VPS in parallel)

### Step 1 — Stop n8n containers (both VPS, simultaneous)

```bash
# HostHatch
ssh root@170.205.37.148 "cd /opt/n8n && docker compose stop n8n"

# Beast
ssh -i ~/.ssh/id_ed25519_amg root@87.99.149.253 \
  "cd /opt/n8n && docker compose stop n8n"
```

### Step 2 — Restore docker-compose.yml from pre-migration backup

```bash
# HostHatch
ssh root@170.205.37.148 \
  "cp /opt/n8n/docker-compose.yml.pre-shared-pg.bak /opt/n8n/docker-compose.yml"

# Beast
ssh -i ~/.ssh/id_ed25519_amg root@87.99.149.253 \
  "cp /opt/n8n/docker-compose.yml.pre-shared-pg.bak /opt/n8n/docker-compose.yml"
```

### Step 3 — Restore sqlite from backup (only if Postgres path corrupted local sqlite)

```bash
# Find latest backup file (timestamp-named)
LATEST_BAK=$(ssh root@170.205.37.148 "ls -t /root/n8n-sqlite-pre-shared-pg-*.bak | head -1")

# HostHatch — copy backup back into container volume
ssh root@170.205.37.148 "docker stop n8n-n8n-1 && \
  docker cp $LATEST_BAK n8n-n8n-1:/home/node/.n8n/database.sqlite && \
  docker start n8n-n8n-1"

# Beast — same pattern
LATEST_BAK_B=$(ssh -i ~/.ssh/id_ed25519_amg root@87.99.149.253 "ls -t /root/n8n-sqlite-pre-shared-pg-*.bak | head -1")
ssh -i ~/.ssh/id_ed25519_amg root@87.99.149.253 \
  "docker stop n8n-n8n-1 && \
   docker cp $LATEST_BAK_B n8n-n8n-1:/home/node/.n8n/database.sqlite && \
   docker start n8n-n8n-1"
```

### Step 4 — Re-start n8n on both VPS

```bash
# Both VPS — bring n8n back up with restored compose + sqlite
ssh root@170.205.37.148 "cd /opt/n8n && docker compose up -d"
ssh -i ~/.ssh/id_ed25519_amg root@87.99.149.253 "cd /opt/n8n && docker compose up -d"
```

### Step 5 — Verify rollback parity

```bash
# Both VPS should show 41 workflows / 4 active / 4 credentials / executions matching pre-migration count
# Run sqlite_parity.py against both and confirm numbers match.
```

### Step 6 — Optional: tear down Postgres if rollback was permanent

```bash
# Only run if you're SURE Postgres is dead-and-buried (workflows safely back on sqlite):
ssh root@170.205.37.148 "cd /opt/n8n-postgres && docker compose down -v"
# This deletes the postgres volume — IRREVERSIBLE. Only do this if you've confirmed
# all workflow data is back in sqlite via Step 5 verification.
```

### Step 7 — Log to MCP

```python
# Via Titan MCP:
log_decision(
  text="[ROLLBACK CT-0416-17 EXECUTED 2026-04-16 <ts>Z] Reverted to local sqlite + local redis on both VPS. Reason: <specific blocker>. Workflow count restored: HostHatch 41/4 + Beast 41/4. Production traffic resumed.",
  project_source="EOM",
  tags=["rollback", "ct-0416-17", "shared-pg-failed"]
)
```

---

## ARTIFACTS PRESERVED (do NOT delete during rollback)

- `/root/n8n-sqlite-pre-shared-pg-<ts>.bak` (175MB on each VPS) — sqlite snapshot
- `/opt/n8n-pg-migration/workflow-export-pre-pg.json` (206KB on HostHatch) — n8n CLI export
- `/opt/n8n-pg-migration/credentials-export-pre-pg.json` (2.5KB on HostHatch) — credentials export
- `/opt/n8n/docker-compose.yml.pre-shared-pg.bak` on both VPS — pre-migration compose

---

## EXPECTED RESTORE TIME

- Stop n8n: ~5 sec per VPS
- Restore compose + sqlite: ~30 sec per VPS
- n8n startup: ~12 sec per VPS
- **Total: ~60-90 sec end-to-end** (faster than the migration itself)

Production webhook traffic affected during this window. Post-rollback, behavior matches the pre-migration state exactly (HostHatch serving 70 lanes via local redis, Beast hot-standby with 70 idle lanes, sqlite per-VPS).
