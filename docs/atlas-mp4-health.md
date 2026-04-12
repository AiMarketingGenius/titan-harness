# Atlas MP-4 Health Monitoring — Operations Guide

## Overview

MP-4 health monitoring runs 12 per-service health checks every 60s and a 10-test nightly suite at 08:00 UTC (3:00 AM ET). All results are written to JSONL under `/var/log/titan/`.

## Installed Timers

### Per-Service Health Checks (60s interval)

```bash
# List all active timers
systemctl list-timers 'titan-health-check@*'

# Check a specific service
systemctl status titan-health-check@kokoro.timer
```

| Timer | Service Checked | JSONL Path |
|---|---|---|
| `titan-health-check@kokoro.timer` | Kokoro TTS (port 8880) | `/var/log/titan/kokoro-health.jsonl` |
| `titan-health-check@hermes.timer` | Hermes Pipeline (port 8082) | `/var/log/titan/hermes-health.jsonl` |
| `titan-health-check@mcp.timer` | MCP (memory.aimarketinggenius.io) | `/var/log/titan/mcp-health.jsonl` |
| `titan-health-check@n8n.timer` | n8n (port 5678) | `/var/log/titan/n8n-health.jsonl` |
| `titan-health-check@caddy.timer` | Caddy (port 80) | `/var/log/titan/caddy-health.jsonl` |
| `titan-health-check@titan_processor.timer` | titan-processor (systemd) | `/var/log/titan/titan-processor-health.jsonl` |
| `titan-health-check@titan_bot.timer` | Slack titan-bot | `/var/log/titan/titanbot-health.jsonl` |
| `titan-health-check@supabase.timer` | Supabase REST API | `/var/log/titan/supabase-health.jsonl` |
| `titan-health-check@r2.timer` | Cloudflare R2 | `/var/log/titan/r2-health.jsonl` |
| `titan-health-check@reviewer_budget.timer` | Reviewer Loop budget | `/var/log/titan/reviewer-budget-health.jsonl` |
| `titan-health-check@vps_disk.timer` | VPS disk usage | `/var/log/titan/vps-disk-health.jsonl` |
| `titan-health-check@vps_cpu_memory.timer` | VPS CPU/memory | `/var/log/titan/vps-cpu-memory-health.jsonl` |

### Nightly Health Suite (08:00 UTC daily)

```bash
systemctl status titan-nightly-health.timer
```

- **Output:** `/var/log/titan/nightly-suite-YYYYMMDD.jsonl`
- **Tests:** 10 (vps-resources, disk-capacity, kokoro-synth, hermes-pipeline, mcp-roundtrip, n8n-workflows, supabase-query, r2-secondary, reviewer-budget, caddy-tls)
- **Timeout:** 20 minutes total
- **Slack digest:** Posted to `#titan-ops` on completion

## JSONL Schema

Every health check entry follows this schema:

```json
{
  "ts": "2026-04-12T07:16:16Z",
  "service": "kokoro",
  "status": "healthy",
  "detail": "synth_latency_ms=4, port=8880",
  "metrics": {"latency_ms": 4, "port": 8880},
  "check_version": "1"
}
```

**Status values:** exactly `healthy` | `degraded` | `dead`. No other values accepted.

## Manual Operations

```bash
# Run all health checks manually
source /root/.titan-env && python3 /opt/titan-harness/scripts/health_check.py --all

# Run a single check
source /root/.titan-env && python3 /opt/titan-harness/scripts/health_check.py kokoro

# Run nightly suite manually
source /root/.titan-env && python3 /opt/titan-harness/scripts/nightly_health_suite.py

# Check latest health for a service
tail -1 /var/log/titan/kokoro-health.jsonl | python3 -m json.tool
```

## Thresholds (per MP-4 Section 1.2)

| Service | Healthy | Degraded | Dead |
|---|---|---|---|
| Kokoro | latency < 400ms | 400-800ms | > 800ms or no response |
| MCP | roundtrip < 500ms | 500-2000ms | > 2000ms or failure |
| Supabase | query < 300ms | 300-1000ms | > 1000ms or failure |
| VPS Disk | < 70% used | 70-85% | > 85% |
| VPS CPU | load < 1x cores | 1-2x cores | > 2x sustained |
