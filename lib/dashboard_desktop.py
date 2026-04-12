#!/usr/bin/env python3
"""
lib/dashboard_desktop.py
MP-3 §3 — Desktop Solon OS Control Center

Full-width desktop dashboard at ops.aimarketinggenius.io/desktop
Sections: Overview · Kill Chain · Reviewer Loop · VPS Health · MCP Decisions · Clients · Titan Session
"""

from __future__ import annotations

from string import Template
from datetime import datetime, timezone

from lib.dashboard_api import get_dashboard_data


DESKTOP_HTML = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Solon OS — Atlas Control Center</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', system-ui, sans-serif; background: #0a0a0a; color: #e5e5e5; -webkit-font-smoothing: antialiased; }
.topbar { display: flex; align-items: center; gap: 16px; padding: 12px 24px; background: #111; border-bottom: 1px solid #262626; position: sticky; top: 0; z-index: 100; }
.orb { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700; color: #fff; cursor: pointer; transition: all 0.3s; }
.orb:hover { transform: scale(1.1); }
.orb-green { background: #22c55e; box-shadow: 0 0 16px #22c55e44; }
.orb-yellow { background: #eab308; box-shadow: 0 0 16px #eab30844; }
.orb-orange { background: #f97316; box-shadow: 0 0 20px #f9731644; }
.orb-red { background: #ef4444; box-shadow: 0 0 24px #ef444466; animation: pulse 1s ease-in-out infinite; }
@keyframes pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.06); } }
.topbar-title { font-size: 18px; font-weight: 600; }
.topbar-status { font-size: 12px; color: #a3a3a3; }
.topbar-right { margin-left: auto; display: flex; gap: 12px; align-items: center; }
.topbar-right a { color: #60a5fa; text-decoration: none; font-size: 13px; }

.grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; padding: 20px 24px; max-width: 1600px; margin: 0 auto; }
.grid-2 { grid-column: span 2; }
.grid-3 { grid-column: span 3; }

.panel { background: #171717; border-radius: 12px; padding: 18px; }
.panel h3 { font-size: 13px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }

.stat { font-size: 32px; font-weight: 700; }
.stat-green { color: #22c55e; }
.stat-yellow { color: #eab308; }
.stat-label { font-size: 12px; color: #a3a3a3; margin-top: 2px; }

.progress-bar { height: 6px; background: #262626; border-radius: 3px; overflow: hidden; margin-top: 8px; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); border-radius: 3px; }

.health-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.health-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.health-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

.client-card { background: #1a1a1a; border-radius: 8px; padding: 12px; margin-bottom: 8px; display: flex; align-items: center; gap: 12px; }
.client-card:hover { background: #222; }
.client-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.client-name { font-size: 14px; font-weight: 600; }
.client-meta { font-size: 12px; color: #a3a3a3; }
.client-kpis { margin-left: auto; text-align: right; }
.client-kpi { font-size: 12px; color: #a3a3a3; }

.decision-row { padding: 8px 0; border-bottom: 1px solid #222; font-size: 13px; display: flex; gap: 12px; }
.decision-time { color: #525252; min-width: 60px; }
.decision-text { flex: 1; }

.titan-session { padding: 12px; background: #1a1a1a; border-radius: 8px; font-size: 13px; }
.titan-active { color: #22c55e; font-weight: 600; }
.titan-idle { color: #a3a3a3; }

.approval-item { background: #1a1a1a; border-radius: 8px; padding: 10px 12px; margin-bottom: 6px; border-left: 3px solid #eab308; display: flex; justify-content: space-between; align-items: center; }
.approval-title { font-size: 13px; font-weight: 500; }
.approval-risk { font-size: 11px; padding: 2px 6px; border-radius: 4px; }
.risk-low { background: #22c55e22; color: #22c55e; }
.risk-medium { background: #eab30822; color: #eab308; }
.risk-high { background: #ef444422; color: #ef4444; }

.slack-btn { display: inline-block; background: #4A154B; color: #fff; padding: 6px 12px; border-radius: 6px; font-size: 12px; text-decoration: none; cursor: pointer; }

.lane-row { display: flex; gap: 4px; margin-bottom: 4px; }
.lane-cell { flex: 1; padding: 6px; background: #1a1a1a; border-radius: 4px; font-size: 11px; text-align: center; }
.lane-active { background: #22c55e22; border: 1px solid #22c55e44; }
.lane-pending { background: #eab30822; border: 1px solid #eab30844; }
.lane-idle { background: #17171799; }

.footer { text-align: center; padding: 16px; font-size: 11px; color: #525252; }
</style>
</head>
<body>

<div class="topbar">
  <div class="orb orb-$orb_color" id="atlas-orb" title="Click to speak">S</div>
  <div>
    <div class="topbar-title">Solon OS</div>
    <div class="topbar-status">$orb_drivers</div>
  </div>
  <div class="topbar-right">
    <a href="/mobile">Mobile</a>
    <a href="slack://open">Open Slack</a>
  </div>
</div>

<div class="grid">

  <!-- Overview -->
  <div class="panel">
    <h3>Sprint</h3>
    <div class="stat stat-green">$sprint_pct%</div>
    <div class="stat-label">$sprint_name</div>
    <div class="progress-bar"><div class="progress-fill" style="width:$sprint_pct%"></div></div>
  </div>

  <div class="panel">
    <h3>Orb State</h3>
    <div class="stat" style="color:$orb_css_color">$orb_label_upper</div>
    <div class="stat-label">Pulse: $orb_pulse</div>
    <div style="margin-top:8px;font-size:12px;color:#a3a3a3;">$orb_drivers</div>
  </div>

  <div class="panel">
    <h3>Pending Approvals</h3>
    <div class="stat stat-yellow">$approval_count</div>
    <div class="stat-label">Hard Limit items awaiting decision</div>
    $approvals_desktop_html
  </div>

  <!-- 7-Subsystem Health -->
  <div class="panel grid-2">
    <h3>Subsystem Health (7 Lanes)</h3>
    <div class="health-grid">
      $health_desktop_html
    </div>
  </div>

  <!-- Titan Session -->
  <div class="panel">
    <h3>Titan Session</h3>
    <div class="titan-session">
      <div class="titan-active">Titan is working on: MP-3/MP-4 implementation</div>
      <div style="margin-top:6px;font-size:12px;color:#a3a3a3;">Subsystem: harness · ETA: ongoing</div>
    </div>
  </div>

  <!-- Kill Chain -->
  <div class="panel grid-3">
    <h3>Kill Chain — Today's Completed Tasks</h3>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      $killchain_html
    </div>
  </div>

  <!-- Clients -->
  <div class="panel grid-2">
    <h3>Client Pipelines</h3>
    $clients_desktop_html
    <div style="margin-top:8px;">
      <h3 style="margin-top:12px;">7-Lane View (Sample Client)</h3>
      <div>
        <div class="lane-row">
          <div class="lane-cell" style="font-weight:600;background:transparent;">Inbound</div>
          <div class="lane-cell" style="font-weight:600;background:transparent;">Outbound</div>
          <div class="lane-cell" style="font-weight:600;background:transparent;">Nurture</div>
          <div class="lane-cell" style="font-weight:600;background:transparent;">Onboard</div>
          <div class="lane-cell" style="font-weight:600;background:transparent;">Fulfill</div>
          <div class="lane-cell" style="font-weight:600;background:transparent;">Report</div>
          <div class="lane-cell" style="font-weight:600;background:transparent;">Upsell</div>
        </div>
        <div class="lane-row">
          <div class="lane-cell lane-active">Active</div>
          <div class="lane-cell lane-idle">Paused</div>
          <div class="lane-cell lane-active">Running</div>
          <div class="lane-cell lane-active">Step 3/5</div>
          <div class="lane-cell lane-pending">Queued</div>
          <div class="lane-cell lane-active">Current</div>
          <div class="lane-cell lane-idle">—</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Reviewer Loop + VPS -->
  <div class="panel">
    <h3>Reviewer Loop</h3>
    <div style="font-size:13px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Monthly spend</span><span>$$0.60 / $$5.00</span></div>
      <div class="progress-bar"><div class="progress-fill" style="width:12%;background:#60a5fa"></div></div>
      <div style="display:flex;justify-content:space-between;margin-top:8px;margin-bottom:4px;"><span>Daily calls</span><span>5 / 5</span></div>
      <div class="progress-bar"><div class="progress-fill" style="width:100%;background:#eab308"></div></div>
    </div>
    <h3 style="margin-top:16px;">VPS Health</h3>
    <div style="font-size:13px;color:#a3a3a3;">
      <div>CPU: ~12% · RAM: 8.2G/56G · Disk: 34%</div>
      <div style="margin-top:4px;">Last healthcheck: just now</div>
    </div>
  </div>

</div>

<div class="footer">Atlas · Solon OS Control Center · $timestamp</div>

<script>
setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>""")


def render_desktop_html(data: dict | None = None) -> str:
    """Render the desktop Solon OS Control Center."""
    if data is None:
        data = get_dashboard_data()

    orb = data["orb"]

    # Health items
    health_items = []
    for h in data.get("health", []):
        dot_color = {"healthy": "#22c55e", "needs_attention": "#eab308", "unknown": "#525252"}.get(h["status"], "#525252")
        health_items.append(
            f'<div class="health-item"><div class="health-dot" style="background:{dot_color}"></div>'
            f'<span>{h["name"]}: {h["status"]}</span></div>'
        )

    # Client cards
    client_cards = []
    for c in data.get("clients", []):
        dot_class = f'dot-{c["health_color"]}'
        blocker_text = f'{c["open_blockers"]} blockers' if c["open_blockers"] > 0 else "No blockers"
        client_cards.append(f"""<div class="client-card">
  <div class="client-dot" style="background:{'#22c55e' if c['health_color']=='green' else '#eab308' if c['health_color']=='yellow' else '#f97316'}"></div>
  <div>
    <div class="client-name">{c['name']}</div>
    <div class="client-meta">{c['stage']}</div>
  </div>
  <div class="client-kpis">
    <div class="client-kpi">{c['last_task']} · {c['last_task_elapsed']}</div>
    <div class="client-kpi">{blocker_text}</div>
  </div>
</div>""")

    # Approvals
    approval_items = []
    for a in data.get("approvals", []):
        risk_class = f"risk-{a['risk']}"
        approval_items.append(
            f'<div class="approval-item"><span class="approval-title">{a["client"]} — {a["action"]}</span>'
            f'<span class="approval-risk {risk_class}">{a["risk"].upper()}</span></div>'
        )
    if not approval_items:
        approval_items = ['<div style="font-size:12px;color:#525252;margin-top:8px;">None pending</div>']

    # Kill chain (placeholder — will be wired to real task completions)
    killchain_items = [
        '<div style="background:#1a1a1a;padding:8px 12px;border-radius:6px;font-size:12px;">MP-3.01 Intent Classifier</div>',
        '<div style="background:#1a1a1a;padding:8px 12px;border-radius:6px;font-size:12px;">MP-3.02 Approval System</div>',
        '<div style="background:#1a1a1a;padding:8px 12px;border-radius:6px;font-size:12px;">MP-3.03 Orb State Machine</div>',
        '<div style="background:#1a1a1a;padding:8px 12px;border-radius:6px;font-size:12px;">MP-3.06 Health Flags</div>',
        '<div style="background:#1a1a1a;padding:8px 12px;border-radius:6px;font-size:12px;">MP-3.04 Mobile Dashboard</div>',
    ]

    return DESKTOP_HTML.safe_substitute(
        orb_color=orb["color"],
        orb_css_color=orb["css_color"],
        orb_label_upper=orb["color"].upper(),
        orb_pulse=orb["pulse"],
        orb_drivers=orb["drivers"][0] if orb["drivers"] else "",
        sprint_name=data["sprint"]["name"],
        sprint_pct=data["sprint"]["completion_pct"],
        approval_count=len(data.get("approvals", [])),
        approvals_desktop_html="\n".join(approval_items),
        health_desktop_html="\n".join(health_items),
        clients_desktop_html="\n".join(client_cards),
        killchain_html="\n".join(killchain_items),
        timestamp=data.get("timestamp", "")[:19],
    )
