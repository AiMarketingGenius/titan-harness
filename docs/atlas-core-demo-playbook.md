# Atlas Core Demo Playbook

**Version:** 1.0 — POST-R3 Phase 4
**Last updated:** 2026-04-12
**Live URL:** https://ops.aimarketinggenius.io

---

## Demo Client Profile

| Field | Value |
|---|---|
| **Name** | Atlas Demo Co |
| **Project ID** | `atlas-demo-co` |
| **Vertical** | HVAC services |
| **Status** | Active |
| **Domain** | atlasdemo.co |
| **Pipeline** | 7-lane (Prospect → Qualified → Proposal → Negotiation → Onboarding → Active → Completed) |
| **Task summary** | 4 completed, 2 in-progress, 1 blocked |
| **Blocker** | Payment terms review — client requested Net-45, needs Solon approval |

### Pipeline State

| Lane | Status | Tasks |
|---|---|---|
| Prospect | Complete | Initial outreach (done), Discovery call (done) |
| Qualified | Complete | Budget confirmed $3K/mo (done) |
| Proposal | Active | SOW draft v2 sent (done), Awaiting signature (in progress) |
| Negotiation | Active | Payment terms review (blocked — Net-45 request) |
| Onboarding | Running | GBP access collected (done), NAP data audit (in progress) |
| Active | Queued | — |
| Completed | Idle | — |

---

## Pre-Demo Checklist

1. Verify VPS is running: `curl -s https://ops.aimarketinggenius.io/api/dashboard/health | python3 -m json.tool`
2. Verify orb state: `curl -s https://ops.aimarketinggenius.io/api/dashboard/orb | python3 -m json.tool`
3. Confirm `sql/008_demo_client.sql` has been applied in Supabase SQL Editor
4. Open both dashboards in separate tabs:
   - Mobile: https://ops.aimarketinggenius.io/mobile
   - Desktop: https://ops.aimarketinggenius.io/desktop

---

## Scene 1 — The Orb (System Health at a Glance)

**What to show:** Mobile dashboard header with the orb

**Dashboard URL:** https://ops.aimarketinggenius.io/mobile

**Talking points:**
- "This is Atlas — your AI operations center. The orb tells you everything at a glance."
- "Green means all systems healthy. Yellow means something needs attention. Red means action required now."
- "It checks 7 subsystems every 30 seconds: voice AI, LLM routing, client pipeline, MCP memory, n8n workflows, Supabase, and the reviewer loop."

**Expected behavior:**
- Orb displays green (all subsystems healthy) with slow pulse
- Health section shows 7 subsystems with green dots
- If any subsystem is degraded, orb shifts to yellow with medium pulse

**API check:**
```
curl -s https://ops.aimarketinggenius.io/api/dashboard/orb
```
Expected: `{"color": "green", "pulse": "slow", "drivers": [...]}`

---

## Scene 2 — Client Pipeline (Atlas Demo Co)

**What to show:** Desktop dashboard — Client Pipelines section + 7-Lane View

**Dashboard URL:** https://ops.aimarketinggenius.io/desktop

**Talking points:**
- "Each client gets a 7-lane pipeline. You see exactly where every deal sits."
- "Atlas Demo Co is an HVAC company — they're in Onboarding right now."
- "Notice the orange blocker on Negotiation: they want Net-45 payment terms. That's flagged for the owner to decide, not buried in an email."
- "Green tasks are done. Blue is in progress. Orange needs attention. Everything is tracked automatically."

**Expected behavior:**
- Client card shows "Atlas Demo Co" with health dot
- 7-lane pipeline renders below with status per lane
- Task cards show color-coded status (green/blue/orange)
- Blocked task shows warning icon with note about Net-45

**API check:**
```
curl -s https://ops.aimarketinggenius.io/api/dashboard/desktop
```

---

## Scene 3 — Kill Chain + VPS Health (Operational Proof)

**What to show:** Desktop dashboard — Kill Chain + VPS Health sections

**Dashboard URL:** https://ops.aimarketinggenius.io/desktop

**Talking points:**
- "Kill Chain shows what got done today — pulled live from our decision log. This is accountability, not a to-do list."
- "VPS Health: load, memory, disk — all monitored. We track days-to-full so you never wake up to a full disk."
- "The nightly suite runs 10 tests automatically at 3 AM. If anything breaks, we know before you do."

**Expected behavior:**
- Kill Chain section shows today's completed decisions (from MCP)
- VPS Health shows load, RAM, disk percentages
- Sprint progress bar shows current completion percentage
- Reviewer Loop shows monthly spend and daily call counts

**API check:**
```
curl -s https://ops.aimarketinggenius.io/api/dashboard/health
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Dashboards return 502 | SSH to VPS, restart Atlas API: `cd /opt/titan-harness && python3 lib/atlas_api.py &` |
| Demo client not visible | Apply `sql/008_demo_client.sql` in Supabase SQL Editor |
| Orb shows red | Check health endpoint — identify which subsystem is down |
| Pipeline shows static fallback | Verify Supabase env vars are set in VPS: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| Caddy returns 404 | Check Caddy config: `caddy validate --config /etc/caddy/Caddyfile` |

---

## SQL Dependency

This playbook requires `sql/008_demo_client.sql` applied to Supabase project `egoazyasyrhslluossli`. The migration creates:
- `client_pipeline_lanes` table with RLS
- `client_pipeline_tasks` table with RLS
- Demo client record in `clients`
- 7 pipeline lanes + 8 sample tasks
