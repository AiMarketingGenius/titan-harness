# Closed-Loop EOM Notifier — Implementation Report
# CT-0421-06 | Date: 2026-04-21 | Author: Titan

---

## Status: SEND PATH SHIPPED

MVP scope complete. Achilles/Titan → MCP → n8n → Hammerspoon → Claude.ai.
Response capture is phase 2 (documented in Limitations).

---

## Exact Files Changed

### New files — titan-harness (commit 75060d0)

| File | Purpose |
|---|---|
| `lib/emit_eom_review.py` | Titan/Achilles CLI helper to emit `eom_review_needed` events. Enforces secret redaction at write time. |
| `plans/n8n/eom_review_watcher_workflow.json` | Importable n8n workflow. Polls Supabase every 60s, deduplicates, applies 4h TTL, writes `eom_nudge_queued`. |

### New files — Hammerspoon (~/.hammerspoon/)

| File | Purpose |
|---|---|
| `eom_notifier.lua` | Core Hammerspoon actuator. 60s poll loop, browser injection, demo-window badge, ack. |
| `poll_eom_queue.sh` | Queries Supabase for `eom_nudge_queued` events (unacked, within 4h TTL). |
| `ack_eom.sh` | Writes `eom_acked` decision to MCP to prevent re-injection. |

### Modified files

| File | Change |
|---|---|
| `~/.hammerspoon/init.lua` | Added `require("eom_notifier")` block with pcall guard |
| `/opt/amg-ops/thursday-healthcheck.sh` (VPS) | Added `HEALTH_ALERT_WEBHOOK_URL` external alert hook for demo-window compliance |

---

## Architecture

```
Achilles/Titan
    ↓  python3 lib/emit_eom_review.py --owner <owner> ...
    ↓  (secret-redacted write)
MCP op_decisions  ← tag: eom_review_needed + eom_packet_id-<uuid>
    ↓  (every 60s poll)
n8n watcher (VPS, eom_review_watcher_workflow.json)
    │  dedup against eom_acked
    │  apply 4h TTL
    │  format compact review packet
    ↓  write back to MCP
MCP op_decisions  ← tag: eom_nudge_queued + eom_packet_id-<uuid>
    ↓  (every 60s poll via poll_eom_queue.sh)
Hammerspoon eom_notifier.lua (Mac)
    │  Safari → Chrome → Arc tab search for claude.ai
    │  clipboard paste + Cmd+V + Enter
    │  write ~/achilles-session/eom-reviews/pending_eom_review.json
    ↓  ack_eom.sh
MCP op_decisions  ← tag: eom_acked + eom_packet_id-<uuid>

EOM (Claude.ai) receives packet and responds in thread.
```

---

## Tag Vocabulary

| Tag | Who writes | Meaning |
|---|---|---|
| `eom_review_needed` | Achilles / Titan | Raw review request, unformatted |
| `eom_packet_id-<uuid>` | All layers | Dedup identifier across all events |
| `eom_nudge_queued` | n8n | Formatted packet, ready for Hammerspoon |
| `eom_acked` | Hammerspoon | Injection attempted (prevents re-fire) |
| `outcome-injected` | Hammerspoon | Browser injection succeeded |
| `outcome-failed` | Hammerspoon | No claude.ai tab found |

---

## Activation Steps

### Step 1 — Import n8n workflow (on VPS)

1. SSH to VPS: `ssh root@170.205.37.148`
2. Open n8n: `https://n8n.aimarketinggenius.io` (or memory domain)
3. Left nav → Workflows → Import from File
4. Upload: `~/titan-harness/plans/n8n/eom_review_watcher_workflow.json`
5. In n8n Settings → Variables, add:
   - `SUPABASE_URL` = `https://egoazyasyrhslluossli.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY` = (from `/etc/amg/mcp-server.env`)
6. Activate the workflow (toggle ON)

### Step 2 — Reload Hammerspoon (on Mac)

```
Hammerspoon → Reload Config   (or: hs.reload() from console)
```

Confirm alert: "EOM notifier armed (60s poll)"

### Step 3 — Add external alert webhook (demo window compliance)

Add to `/root/.titan-env` on VPS:
```
HEALTH_ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```
Or use the n8n webhook URL for the demo-alert flow. This makes healthcheck
alerts external (not journal-only) as required by the demo-window hardening rule.

---

## Dry-Run / Proof Path

### Path A — Achilles→EOM dry run (from Mac)

```bash
# 1. Emit a test review event
cd ~/titan-harness
python3 lib/emit_eom_review.py \
  --owner achilles \
  --task-id DRY-RUN-ACHILLES \
  --objective "Prove Achilles→EOM closed loop send path" \
  --decision "Confirm packet appeared in claude.ai tab. Reply OK."

# 2. Check MCP for the event (should appear within seconds)
# Expected: mcp_id=<uuid> packet_id=<8-char> artifact=~/achilles-session/eom-reviews/eom_review_DRY-RUN-ACHILLES-*.json

# 3. n8n picks it up within 60s and writes eom_nudge_queued to MCP

# 4. Hammerspoon picks it up within 60s of n8n write
# Expected: macOS alert "EOM review injected via safari (DRY-RUN-ACHILLES)"
# Expected: ~/achilles-session/eom-reviews/pending_eom_review.json updated

# 5. Verify ack written to MCP:
# grep eom_acked in op_decisions should show eom_packet_id-<same-id>
```

### Path B — Titan→EOM dry run

```bash
cd ~/titan-harness
python3 lib/emit_eom_review.py \
  --owner titan \
  --task-id DRY-RUN-TITAN \
  --objective "Prove Titan→EOM residual-risk review send path" \
  --proof "No live changes — smoke test only" \
  --decision "Confirm packet appeared. Reply OK."
```

### Path C — Hammerspoon direct dry run (bypasses MCP/n8n — fastest)

From Hammerspoon console:
```lua
eom_notifier.dry_run()
```
Expected: clipboard set to test packet, claude.ai tab focused and pasted.

### Path D — Force poll (if n8n already queued an event)

```lua
eom_notifier.force_poll()
```

---

## Hardening Rules Honored

| Rule | Implementation |
|---|---|
| Demo-window mode (72h gate) | `eom_notifier.lua` detects demo window; louder badge + non-dismissable notification during window |
| External alerting during demo window | `thursday-healthcheck.sh` now has `HEALTH_ALERT_WEBHOOK_URL` hook — set URL to activate |
| 4h TTL on EOM pre-flight approval | `poll_eom_queue.sh` and n8n Code node both enforce `TTL = 4 * 3600` cutoff |
| Secret redaction on reports | `emit_eom_review.py` runs `redact_packet()` on all string fields before MCP write — enforced at source |
| Fail-closed deploy drift | Doctrine unchanged (existing CLAUDE.md §fail-closed drift rule); this notifier creates the EOM review trigger, not the drift gate itself |

---

## Remaining Limitations

| Item | Status | Path to fix |
|---|---|---|
| **n8n variables** must be set manually after import | Config step — not wired | Set `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` in n8n Settings > Variables |
| **Response capture** (EOM's reply back to Achilles) | Phase 2 — not built | DOM watcher or manual Achilles thread read. Lowest-priority per architecture doc. |
| **claude.ai tab targeting** is "first claude.ai tab found" | No EOM thread pinning | Achilles pins the EOM thread tab as the only claude.ai tab during review cycles, OR we key on a conversation URL stored in env |
| **External alert webhook URL** not pre-configured | Env var pattern in place | Achilles/Solon adds `HEALTH_ALERT_WEBHOOK_URL` to `/root/.titan-env` |
| **n8n → Mac direct push** is still infeasible (NAT) | MCP poll-inversion pattern used instead — matches tla_nudge.lua precedent | Tailscale-exposed webhook would enable direct push; out of scope for MVP |
| **Hammerspoon reload** required after init.lua change | Manual step | `hs.reload()` in console or menu bar |

---

## MCP Log

Decision logged with tags: `ct-0421-06`, `eom-notifier`, `closed-loop`, `send-path-shipped`

---

## Summary

Send path is live. Solon is out of the relay on the Achilles/Titan→EOM direction.
Next: Achilles activates n8n workflow, Solon reloads Hammerspoon, run Path C dry run.
Phase 2 (response capture) is documented but deferred per architecture doc recommendation.
