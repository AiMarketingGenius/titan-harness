#!/usr/bin/env python3
"""
titan-harness/scripts/radar_refresh.py

Refreshes RADAR.md from live sources + generates RADAR_SUMMARY.md and a
5-line Slack-pasteable status. Invoked daily via cron OR on every session
boot.

Sources scanned:
  - RADAR.md itself (preserves manual annotations)
  - ~/titan-session/NEXT_TASK.md (local ephemeral)
  - INVENTORY.md (5-day build inventory)
  - plans/PLAN_*.md (IdeaBuilder plans)
  - plans/MP_*.md (megaprompt phase outputs)
  - MCP operator_tasks queue (via get_task_queue MCP tool — outside cron scope)
  - Supabase mp_runs table (if credentials available)

Output:
  - RADAR.md (in place, merge-preserving)
  - RADAR_SUMMARY.md (generated fresh each run)
  - stdout: 5-line Slack-pasteable status (Now / Next / Parked big rocks / Blocked on Solon / ETA)

Phase status: STUB — full implementation TODO. Currently reads existing
RADAR.md and refreshes the Last-refreshed timestamp + produces a
minimal RADAR_SUMMARY.md. Auto-archiving of Parked>7 Days rows and
Slack delivery are TODO.

Exit codes:
  0 — refresh succeeded
  1 — generic error
  2 — RADAR.md missing (run manually: copy template from plans/)
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RADAR_PATH = REPO_ROOT / "RADAR.md"
SUMMARY_PATH = REPO_ROOT / "RADAR_SUMMARY.md"
INVENTORY_PATH = REPO_ROOT / "INVENTORY.md"
NEXT_TASK_PATH = Path.home() / "titan-session" / "NEXT_TASK.md"
PLANS_DIR = REPO_ROOT / "plans"


def _read_file(p: Path) -> str:
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _update_last_refreshed(radar_text: str) -> str:
    """Bump the Last-refreshed timestamp in RADAR.md."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return re.sub(
        r"\*\*Last refreshed:\*\* .*",
        f"**Last refreshed:** {now}",
        radar_text,
        count=1,
    )


def _extract_section(radar_text: str, heading: str) -> list[str]:
    """Pull lines under `## heading` until the next `## ` heading."""
    pattern = rf"^## {re.escape(heading)}$"
    lines = radar_text.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if re.match(pattern, line):
            in_section = True
            continue
        if in_section:
            if line.startswith("## ") or line.startswith("---"):
                break
            if line.strip().startswith("- "):
                out.append(line.strip())
    return out


def _count_bullets_in(radar_text: str, heading: str) -> int:
    return len(_extract_section(radar_text, heading))


def _generate_summary(radar_text: str) -> str:
    """Build RADAR_SUMMARY.md from the full RADAR.md."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    open_mp = _count_bullets_in(radar_text, "Open Megaprompts & Phases")
    open_infra = _count_bullets_in(radar_text, "Open Infra / Harness Items")
    blocked = _count_bullets_in(radar_text, "Blocked on Solon (actionable items)")
    parked = _count_bullets_in(radar_text, "Parked > 7 Days")

    priority_lines = _extract_section(radar_text, "Execution Priority (default pull order when Solon hasn't explicitly overridden)")
    top3 = priority_lines[:3] if priority_lines else ["(no priority set)"]

    summary = f"""# RADAR SUMMARY — {now}

## Now (top execution priority)
{top3[0] if len(top3) > 0 else '—'}

## Next
{top3[1] if len(top3) > 1 else '—'}

## After that
{top3[2] if len(top3) > 2 else '—'}

## Counts
- Open megaprompts/phases: {open_mp}
- Open infra/harness items: {open_infra}
- Blocked on Solon: {blocked}
- Parked >7 days: {parked}

## Upgrade candidates when Solon approves
- P9.1 Docker worker pool 60h canary/soak — PARKED, code shipped
- n8n queue-mode cutover — PARKED, needs Redis + worker pool

## Slack-pasteable 5-line status
```
Now: {top3[0][2:150] if top3 and len(top3) > 0 else '—'}
Next: {top3[1][2:150] if len(top3) > 1 else '—'}
Parked big rocks: {parked} | Blocked on Solon: {blocked}
Open MPs/phases: {open_mp} | Open infra: {open_infra}
ETA: see RADAR.md for per-item estimates
```
"""
    return summary


def _check_parked_over_7_days(radar_text: str) -> list[str]:
    """TODO: parse item dates from RADAR.md and flag anything >7 days stale.
    Returns list of item names to ask Solon about. Currently stubbed — needs
    a per-item date annotation format in RADAR.md first (add `(seen YYYY-MM-DD)`
    suffix to each bullet)."""
    # TODO: real implementation. For now, return empty.
    return []


def main() -> int:
    if not RADAR_PATH.is_file():
        sys.stderr.write(
            f"ERROR: {RADAR_PATH} not found. Create it first from "
            "the canonical template.\n"
        )
        return 2

    radar = _read_file(RADAR_PATH)
    refreshed = _update_last_refreshed(radar)

    try:
        RADAR_PATH.write_text(refreshed, encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"ERROR writing RADAR.md: {e}\n")
        return 1

    summary = _generate_summary(refreshed)
    try:
        SUMMARY_PATH.write_text(summary, encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"ERROR writing RADAR_SUMMARY.md: {e}\n")
        return 1

    # TODO: integrate with scripts/solon_os_control_loop.py to auto-post
    # summary to Perplexity Slack channel when war_room.slack_grading_enabled.

    parked = _check_parked_over_7_days(refreshed)
    if parked:
        print("\n⚠️  Items parked >7 days needing Solon decision:")
        for item in parked:
            print(f"  - {item}")

    # 5-line Slack-pasteable status on stdout
    lines = summary.split("\n")
    in_code = False
    status_lines = []
    for line in lines:
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            status_lines.append(line)
    for line in status_lines:
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
