# Claude Code — Canonical-Folder Lock + Parked-State Audit (CT-0417-27 T1)

**Status:** audit + doctrine · **NO destructive actions executed** · Solon reviews + flips the switches.
**Author:** Titan · **Date:** 2026-04-17 · **Scope:** Mac `~/titan-harness` + VPS `/opt/titan-harness`.

This doctrine covers **four surfaces**:

1. Claude Code folder registry (§3)
2. Orphan sessions in non-canonical project dirs (§4)
3. Parked git branches (§5)
4. Remote Control panel integration spec (§7)

A single Solon-driven cleanup pass across all four leaves the system with exactly one canonical boot path per machine, zero unindexed historical sessions, zero stale branch surfaces, and a Mobile-Command surface to monitor and manage folder-lock state from the phone.

---

## 1. Rationale

Claude Code's folder picker remembers every project path ever opened. Wrong selection at session start = no MCP, no harness, stale state, possible silent data loss. Lock picker to canonical paths only + migrate any historical sessions worth keeping + remove parked branches that look like live options but aren't + give Mobile Command visibility into the lock.

| Machine | Canonical path |
|---|---|
| **Mac** | `~/titan-harness` |
| **VPS** (`170.205.37.148`) | `/opt/titan-harness` *(see §6 VPS-path reconciliation — brief specified `-work` suffix; production uses the non-suffixed path)* |

---

## 2. Pre-cleanup snapshot (executed 2026-04-17 15:14 UTC)

```
~/titan-harness/.backups/claude-code-registry-20260417-1115.tar.gz   (4.3 GB)
```

**Restore one-liner** (rolls back every change in §3 + §4 below):

```bash
tar xzf ~/titan-harness/.backups/claude-code-registry-20260417-1115.tar.gz \
  -C ~ --strip-components=0
```

Covers `~/Library/Application Support/Claude/` + `~/.claude/` (app state, session cache, registered-projects registry, per-session logs, permissions, plugins). 4.3 GB includes transient Chrome/Electron caches which rebuild automatically — safe to delete the archive once you verify post-cleanup state.

---

## 3. Mac Claude Code project-folder registry

**Registry location:** `~/.claude/projects/` — one directory per registered project, directory name = path flattened with `-` separators.

**Before state (4 entries):**

| # | Registry entry | Resolved path | Sessions | Canonical? | Action |
|---|---|---|---|---|---|
| 1 | `...-Library-Mobile-Documents-com-apple-CloudDocs-4TB-EasySto-BACKUP-...-AI-Marketing-Genius-Buildout-Specs-From-Perplex-18be73p51sjma` | iCloud backup path | 2 | NO | **MIGRATE sessions → DELETE registry entry** (§4.2) |
| 2 | `...-Library-Mobile-Documents-com-apple-CloudDocs-4TB-EasySto-BACKUP-...-AMG-Agent-Folders` | iCloud backup path | **127** | NO | **TRIAGE sessions (§4.1) → ARCHIVE or MIGRATE → DELETE** |
| 3 | `-Users-solonzafiropoulos1-bin-titan-harness` | `~/bin/titan-harness` (stale stub, 3 sessions, 3.7 MB) | 3 | **DUPLICATE of #4** — same conceptual project | **DEDUPE: merge 3 sessions → canonical #4, then DELETE entry #3** |
| 4 | `-Users-solonzafiropoulos1-titan-harness` | `~/titan-harness` (live, 42 sessions, 157 MB) | 42 | **YES — canonical** | **KEEP** |

### 3.1 Dedupe proposal for entries #3 ↔ #4

Solon's call: dedupe, not just delete. Entries #3 and #4 are the same project — someone pointed Claude Code at `~/bin/titan-harness` on 3 occasions and at `~/titan-harness` on 42. Both dirs are arguably "titan-harness" at the user's mental model layer. Merge:

```bash
# Review before executing — migrates the 3 orphan sessions into the canonical dir.
mkdir -p "$HOME/.claude/projects/-Users-solonzafiropoulos1-titan-harness/migrated-from-bin-2026-04-17"
cp -a "$HOME/.claude/projects/-Users-solonzafiropoulos1-bin-titan-harness/"*.jsonl \
      "$HOME/.claude/projects/-Users-solonzafiropoulos1-bin-titan-harness/"*/ \
      "$HOME/.claude/projects/-Users-solonzafiropoulos1-titan-harness/migrated-from-bin-2026-04-17/" 2>/dev/null
# Then delete the non-canonical entry + the stale stub directory
rm -rf "$HOME/.claude/projects/-Users-solonzafiropoulos1-bin-titan-harness"
rm -rf "$HOME/bin/titan-harness"     # or `ln -s ~/titan-harness ~/bin/titan-harness` if anything still points there
```

### 3.2 iCloud-backup registry deletions (after §4 triage completes)

```bash
rm -rf "$HOME/.claude/projects/-Users-solonzafiropoulos1-Library-Mobile-Documents-com-apple-CloudDocs-4TB-EasySto-BACKUP-My-Mac-Desktop-Folder-2025-Businesses-LeadGen-Flat-Fee-Mastery-AMG-Agent-Folders"
rm -rf "$HOME/.claude/projects/-Users-solonzafiropoulos1-Library-Mobile-Documents-com-apple-CloudDocs-4TB-EasySto-BACKUP-My-Mac-Desktop-Folder-2025-Businesses-LeadGen-Flat-Fee-Mastery-AI-Marketing-Genius-Buildout-Specs-From-Perplex-18be73p51sjma"
```

### Expected post-state

```bash
$ ls ~/.claude/projects/
-Users-solonzafiropoulos1-titan-harness
```

One canonical entry. Claude Code folder picker then shows only `~/titan-harness`.

---

## 4. Orphan-session triage in non-canonical dirs

### 4.1 AMG-Agent-Folders (127 sessions)

Solon flagged the "OpenAI key reminder" Ready session as needing migration before deleting the folder.

**Grep sweep** for OpenAI / API-key mentions across the 127 session files returned dozens of matches — the grep is too broad to single out THE reminder session automatically. Triage approach:

```bash
# Step 1 — narrow to sessions mentioning "reminder" AND "openai"
RING="$HOME/.claude/projects/-Users-solonzafiropoulos1-Library-Mobile-Documents-com-apple-CloudDocs-4TB-EasySto-BACKUP-My-Mac-Desktop-Folder-2025-Businesses-LeadGen-Flat-Fee-Mastery-AMG-Agent-Folders"
for f in "$RING"/*.jsonl; do
  if grep -l -i "openai" "$f" > /dev/null && grep -l -i "reminder" "$f" > /dev/null; then
    echo "$f ($(wc -l < "$f") lines)"
  fi
done

# Step 2 — open each candidate in a pager and pick THE right one
#   (recommended: 3-5 candidates max; spot-check via `head -200` on each)

# Step 3 — migrate the chosen session to the canonical project dir
mkdir -p "$HOME/.claude/projects/-Users-solonzafiropoulos1-titan-harness/migrated-amg-agent-folders-2026-04-17"
cp -a "<chosen-session-uuid>.jsonl" "$HOME/.claude/projects/-Users-solonzafiropoulos1-titan-harness/migrated-amg-agent-folders-2026-04-17/"
# Repeat for any other sessions worth keeping.

# Step 4 — only then run the registry deletion in §3.2 to drop the 127-session backup folder.
```

**Alternative (lower-risk):** skip the deletion and just remove the registry *display* entry while leaving the on-disk files intact (Claude Code picker doesn't show folders that aren't in `~/.claude/projects/`, but cross-referencing a different mechanism might still find them). I recommend the full migrate-then-delete path — it's bounded, backed up, and the backup archive covers rollback.

### 4.2 Buildout-Specs-From-Perplex (2 sessions)

Only 2 sessions. Migrate both unconditionally, then delete:

```bash
SRC="$HOME/.claude/projects/-Users-solonzafiropoulos1-Library-Mobile-Documents-com-apple-CloudDocs-4TB-EasySto-BACKUP-My-Mac-Desktop-Folder-2025-Businesses-LeadGen-Flat-Fee-Mastery-AI-Marketing-Genius-Buildout-Specs-From-Perplex-18be73p51sjma"
DEST="$HOME/.claude/projects/-Users-solonzafiropoulos1-titan-harness/migrated-buildout-specs-2026-04-17"
mkdir -p "$DEST"
cp -a "$SRC"/* "$DEST"/
```

---

## 5. Parked git branches — audit + recommendation

Origin remote (`ssh://170.205.37.148/opt/titan-harness.git`) currently carries these non-master branches:

| Branch | HEAD commit | Diverged from master? | Files-delta vs master | Recommendation |
|---|---|---|---|---|
| `gate3-and-relaunch-2026-04-11` | `f1ab8b0 Gate 3 payment link tester + mirror relaunch docs` | NO unique commits (merged or superseded) | 484 files / −81,250 lines (branch is stale *behind* master, massive test-file deletions from an older sprint — master has already absorbed the useful bits) | **ARCHIVE-then-DELETE** — tag `archive/gate3-and-relaunch-2026-04-11` before `git push origin --delete gate3-and-relaunch-2026-04-11`. Preserves history as a retrievable tag. |
| `wip/boot-untracked-2026-04-16` | `3c369a2 WIP: boot-time untracked snapshot 2026-04-16` | 1 commit unique (the WIP snapshot) | 197 files / −26,877 lines vs master (again, branch is older state, master has moved on) | **REVIEW the single WIP commit, then ARCHIVE-then-DELETE.** If `3c369a2` has anything not already in master (spot-check with `git show 3c369a2 --stat`), cherry-pick that to master first; then tag + drop. |
| `ct-0417-25-atlas-sole-speaker` | (live, in-flight) | 3 commits (Atlas-sole-speaker refactor) | +2951/−128 | **KEEP** — merging to master at 2:20 PM ET cron per CT-0417-25 pitch-safety window. |
| `vps-drift-2026-04-11` | (legacy, historical VPS drift capture) | (historical) | (large) | **KEEP (archival)** — useful forensic snapshot, no harm on origin |

### 5.1 Archive-then-delete script (review, then execute)

```bash
cd ~/titan-harness

# Archive tags (cheap, preserve history forever)
git tag archive/gate3-and-relaunch-2026-04-11  origin/gate3-and-relaunch-2026-04-11
git tag archive/wip-boot-untracked-2026-04-16  origin/wip/boot-untracked-2026-04-16
git push origin --tags

# Delete remote branches
git push origin --delete gate3-and-relaunch-2026-04-11
git push origin --delete wip/boot-untracked-2026-04-16

# Prune local tracking refs
git fetch --prune
```

If a future forensic pass needs those branches back: `git checkout -b gate3-and-relaunch-2026-04-11 archive/gate3-and-relaunch-2026-04-11` rematerializes them instantly.

---

## 6. VPS — path reconciliation

Brief-specified canonical: `/opt/titan-harness-work`
Current production canonical: `/opt/titan-harness`

Evidence that `/opt/titan-harness` is the live path:

- `atlas-api.service` unit has `WorkingDirectory=/opt/titan-harness`
- Git origin remote: `ssh://170.205.37.148/opt/titan-harness.git`
- Post-commit auto-mirror log prints `MIRROR:MAC→VPS OK` against `/opt/titan-harness.git`
- Feature branch `ct-0417-25-atlas-sole-speaker` landed there minutes ago at commit `4abfb5b`

**Recommendation (Option A, default):** reconcile doctrine to `/opt/titan-harness`. A path rename would require editing ≥9 systemd units + the bare-repo remote + every mirror hook + every reference across scripts/; high risk for zero functional gain.

**Option B (if you want the `-work` suffix as a convention):** schedule a maintenance window, rename the bare repo + working tree + all systemd units + update the origin remote on Mac, and track that as a separate ticket (CT-0417-27b). Not now.

Flag your choice before Task 2 (`boot-self-heal.sh`) wires the path — §8 below defaults to `/opt/titan-harness` until you say otherwise.

---

## 7. Remote Control panel integration (Mobile Command)

Mobile Command gets a new **"Remote Control"** panel that makes the folder-lock state visible and actionable from phone. Spec:

### 7.1 Surface

- New route on atlas-api: `GET /api/titan/folder-lock/status` + `POST /api/titan/folder-lock/verify`
- New view tab on `ops.aimarketinggenius.io/titan` (the existing Titan Mobile Command surface): **"Remote Control"** — alongside the existing Titan-chat tab + the CT-0417-27 T3/T4 Restart + Effort buttons.

### 7.2 GET `/api/titan/folder-lock/status` response

```json
{
  "canonical": {
    "mac":  "/Users/solonzafiropoulos1/titan-harness",
    "vps":  "/opt/titan-harness"
  },
  "mac": {
    "registry_entries":       1,
    "canonical_present":      true,
    "non_canonical_present":  false,
    "last_drift_detected":    null,
    "last_snapshot_path":     ".backups/claude-code-registry-20260417-1115.tar.gz"
  },
  "vps": {
    "working_tree_head":      "4abfb5b",
    "working_tree_branch":    "master",
    "systemd_atlas_api":      "active",
    "systemd_titan_agent":    "failed"
  },
  "branches": {
    "archived": ["archive/gate3-and-relaunch-2026-04-11", "archive/wip-boot-untracked-2026-04-16"],
    "active_feature_branches": ["ct-0417-25-atlas-sole-speaker"]
  },
  "last_verified": "2026-04-17T15:14:00Z"
}
```

### 7.3 POST `/api/titan/folder-lock/verify`

Runs an on-demand drift check:
- List `~/.claude/projects/` on Mac (via a local ops-agent that phones home to atlas-api over the Solon-OAuth-or-bearer-token mechanism from CT-0417-27 T3/T4)
- Compare to the canonical allow-list (§3 above)
- If drift detected, return a card payload listing the non-canonical entries + a "flag to MCP" CTA
- If clean, return a green status card

### 7.4 UI affordance on Mobile Command

Remote Control panel shows four status pills (all green if healthy):

- **Folder lock** → status pill + tap to run `verify`
- **VPS services** → atlas-api + titan-agent health
- **Branches** → active feature branches + archived-only count
- **Snapshot backup** → last archive timestamp + size; tap reveals the restore one-liner

Red pill on any = tap to open the corresponding doctrine section in a modal, with a "message Solon" escalation button.

### 7.5 Build sequence

1. Folder-lock GET endpoint — simple status return, read-only, zero risk
2. Folder-lock POST `verify` endpoint — runs the drift check
3. Mobile Command UI tab — new `.nav-btn` alongside existing tabs, renders the 4 pills
4. Wiring to CT-0417-27 T3/T4 auth token (shared with Restart + Effort)
5. Log every `verify` call to MCP with `project_source=EOM`, tag `folder-lock-check`

Ship after CT-0417-27 T3 + T4 land (they share the auth layer).

---

## 8. Execution order — when Solon greenlights §3 + §4 + §5 deletions

1. **§4.1** — triage AMG-Agent-Folders, migrate the "OpenAI key reminder" session + anything else worth keeping
2. **§4.2** — migrate 2 sessions from Buildout-Specs-From-Perplex
3. **§3.1** — dedupe `~/bin/titan-harness` → canonical, delete stub dir
4. **§3.2** — delete 2 iCloud-backup registry entries
5. **§5.1** — tag + delete both parked branches
6. **§5 verification** — fresh Claude Code session → folder picker shows only `~/titan-harness`, MCP handshake green, `pwd` in session = canonical
7. **§6** — confirm VPS path canonical choice (default `/opt/titan-harness`)
8. **§7** — Remote Control panel ships as part of CT-0417-27 T3/T4 bundle

After step 7:

```bash
log_decision(
  project_source="EOM",
  text="CT-0417-27 T1: Claude Code folder-lock applied on Mac. Deduped ~/bin/titan-harness into canonical ~/titan-harness (3 sessions preserved under migrated-from-bin-2026-04-17/). Archived 2 iCloud-backup project dirs after triage+migration. Archived 2 parked branches (gate3-and-relaunch + wip/boot-untracked) as archive/* tags. Canonical: only ~/titan-harness visible in Claude Code picker. Backup: .backups/claude-code-registry-20260417-1115.tar.gz (4.3 GB).",
  tags=["ct-0417-27", "folder-lock", "mac", "executed"]
)
```

---

## 9. What this doc deliberately does NOT do

- Does not execute any `rm` or `git push --delete`. Every such command in §3.1 / §3.2 / §5.1 is a *review-then-Solon-runs* command, not a Titan auto-run.
- Does not migrate sessions (§4.1 needs human judgment to pick THE OpenAI-key-reminder session; the grep hit dozens).
- Does not change any VPS path or rename any systemd unit (§6 defaults to current canonical until you say otherwise).
- Does not deploy the Remote Control panel (§7 waits on CT-0417-27 T3/T4 auth layer).
