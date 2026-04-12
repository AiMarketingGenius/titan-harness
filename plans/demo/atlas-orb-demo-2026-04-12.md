# Atlas Orb Demo Script — 2026-04-12

## Prerequisites

- VPS running at `170.205.37.148` with Atlas API on port 8081
- Caddy proxying `ops.aimarketinggenius.io` → localhost:8081
- Slack workspace with titan-bot configured
- iPhone with Safari for mobile view
- Mac with Chrome for desktop view

## URLs

| Surface | URL |
|---|---|
| Desktop dashboard | `https://ops.aimarketinggenius.io/desktop` |
| Mobile dashboard | `https://ops.aimarketinggenius.io/mobile` |
| Voice orb (main) | `https://ops.aimarketinggenius.io/` |
| API status | `https://ops.aimarketinggenius.io/api/status` |
| Orb state API | `https://ops.aimarketinggenius.io/api/dashboard/orb` |
| Health API | `https://ops.aimarketinggenius.io/api/dashboard/health` |

---

## Demo Sequence (3 scenes, ~10 minutes)

### Scene 1: Green State — "What did you ship today?" (3 min)

**Setup:** All systems healthy (orb should be GREEN).

1. **Mac:** Open `ops.aimarketinggenius.io/desktop` in Chrome
   - Expected: Dark dashboard with green orb in topbar, sprint at 92%, 7 subsystems healthy, kill chain showing today's completed items
   - Verify: Orb is GREEN with slow pulse

2. **iPhone:** Open `ops.aimarketinggenius.io/mobile` in Safari
   - Expected: Single-column dark dashboard, green orb header, 3 client tiles, sprint bar
   - Verify: Touch targets are finger-friendly, no horizontal scroll

3. **Slack DM to titan-bot:** Send `What did you ship today?`
   - Expected: Structured reply with header "Atlas Status — today", sections for Shipments/Failures/Pending Approvals, dashboard link
   - Intent classification: `status` with params `{timeframe: today, scope: global}`

4. **Voice (optional):** Press the orb on desktop → speak "What did you ship today?"
   - Expected: Hermes duplex pipeline activates, Kokoro synthesizes response
   - Verify: Response within 3s, no artifacts, clean audio

**Scene 1 pass criteria:**
- [ ] Desktop dashboard loads with green orb
- [ ] Mobile dashboard loads correctly on iPhone
- [ ] Slack status query returns structured answer
- [ ] Voice response is clean (if testing voice path)

---

### Scene 2: P1 Incident — Orb Turns Orange (4 min)

**Setup:** Simulate a P1 by stopping a Tier 2 service.

5. **VPS terminal:** Stop Caddy temporarily
   ```bash
   ssh root@170.205.37.148 "systemctl stop caddy"
   ```

6. **Wait 60s** for health check to fire and detect Caddy dead

7. **Check orb state API:**
   ```bash
   curl -s https://ops.aimarketinggenius.io/api/dashboard/orb | python3 -m json.tool
   ```
   - Expected: `"color": "orange"` or `"red"`, driver includes "caddy" or "P1"

8. **Mac desktop:** Refresh dashboard
   - Expected: Orb in topbar changed to ORANGE or RED with medium/fast pulse
   - Subsystem health shows Caddy as degraded/dead
   - Incident notification visible in kill chain or as alert

9. **iPhone mobile:** Refresh
   - Expected: Orb header changed color, health section shows caddy issue

10. **Slack DM:** Send `What broke today?`
    - Expected: Status reply with Caddy listed under Failures/Degraded, severity noted

11. **Slack DM:** Send `Stop everything.`
    - Expected: Emergency stop confirmation with scope=global, list of halted operations, resume instructions

12. **Resolve:** Restart Caddy
    ```bash
    ssh root@170.205.37.148 "systemctl start caddy"
    ```

13. **Wait 60s**, verify orb returns to GREEN on next health check cycle

**Scene 2 pass criteria:**
- [ ] Orb changes to orange/red when Caddy stops
- [ ] Dashboard reflects the degraded state
- [ ] "What broke today?" shows Caddy issue
- [ ] "Stop everything" returns correct emergency stop
- [ ] Orb returns to green after Caddy restart

---

### Scene 3: JDJ Client Day — Onboarding Kill Chain (3 min)

14. **Slack DM:** Send `Where is Levar's onboarding at?`
    - Expected: Status reply with client-specific onboarding stage, last task, blockers

15. **Slack DM:** Send `Prepare JDJ kickoff brief`
    - Expected: One-pager brief with client info, checklist, 30-day plan (via task_trigger intent → kickoff brief generator)

16. **Desktop dashboard:** Click into client pipelines section
    - Expected: JDJ tile shows current onboarding stage, 7-lane view with per-subsystem status

17. **Mobile dashboard:** Tap JDJ client tile
    - Expected: Client tile shows stage, last task + elapsed time, blocker count

18. **Slack DM:** Send `Show me Atlas KPIs for this week.`
    - Expected: Reporting reply with metrics sections + dashboard link

**Scene 3 pass criteria:**
- [ ] Client-specific status query works
- [ ] Kickoff brief generates correctly
- [ ] Dashboard shows client pipeline view
- [ ] KPI report returns structured data

---

## Post-Demo Verification

After all 3 scenes:

```bash
# Verify health checks are running
ssh root@170.205.37.148 "systemctl list-timers 'titan-health-check@*' --no-pager"

# Verify JSONL logs exist
ssh root@170.205.37.148 "ls -la /var/log/titan/*.jsonl"

# Check latest orb state
curl -s https://ops.aimarketinggenius.io/api/dashboard/orb

# Check all subsystem health
curl -s https://ops.aimarketinggenius.io/api/dashboard/health | python3 -m json.tool
```

---

## Key Implementation Files

| Module | File | Lines | Tests |
|---|---|---|---|
| Intent classifier | lib/intent_classifier.py | 260 | 31/31 |
| Intent handlers | lib/intent_handlers.py | 262 | (via classifier tests) |
| Approval system | lib/approval_system.py | 385 | 12/12 |
| Orb state machine | lib/orb_state_machine.py | 193 | 14/14 |
| Subsystem health | lib/subsystem_health.py | 246 | 12/12 |
| Onboarding flow | lib/onboarding_flow.py | 299 | 11/11 |
| Mobile dashboard | lib/dashboard_api.py | 289 | (render verified) |
| Desktop dashboard | lib/dashboard_desktop.py | 279 | (render verified) |
| Health checks | scripts/health_check.py | 336 | VPS 11/12 |
| Nightly suite | scripts/nightly_health_suite.py | 215 | (10 tests defined) |
| Restart policy | lib/restart_policy.py | 178 | 7/7 |
| Incident manager | lib/incident_manager.py | 220 | 7/7 |
| Lane model | lib/lane_model.py | 145 | 5/5 |
| Perf logger | lib/perf_logger.py | 110 | (log verified) |
| Reviewer budget | lib/reviewer_loop_budget.py | 228 | 7/7 |
| Titan bot | lib/titan_bot.py | 160 | (via classifier) |
| Reorientation | scripts/titan_reorientation.py | 302 | (VPS live run) |
| Atlas API | lib/atlas_api.py | 630 | (routes verified) |

**Total: ~4,337 lines of implementation code, 106/106 tests passing**

---

*Demo script created 2026-04-12. Atlas · Solon OS · MP-3 + MP-4 complete.*
