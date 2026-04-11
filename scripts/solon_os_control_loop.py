#!/usr/bin/env python3
"""
titan-harness/scripts/solon_os_control_loop.py

Daily Solon OS Control Loop generator.

Invoked by cron every morning (server time), configurable via
policy.yaml autopilot.control_loop_cron. Generates a package containing:

1. Snapshot of INVENTORY.md + RADAR.md key sections
2. Titan's proposed top 3 moves for Solon today (1-2 sentences each)
3. Parked big rocks Titan thinks Solon should reconsider (from Parked > 7 Days)

Package is written to plans/control-loop/SOLON_OS_CONTROL_LOOP_YYYY-MM-DD.md
and (when policy.yaml war_room.slack_grading_enabled is true) posted to the
Perplexity Slack war-room channel with tag:
  SOLON_OS_CONTROL_LOOP / YYYY-MM-DD

Goal: when Solon opens Perplexity in the morning and says "Use today's
Solon OS Control Loop package and tell me what to do first," Perplexity
already has the context Titan sent.

Phase status: STUB — package generation logic works today, Slack posting
requires policy.yaml war_room.slack_grading_enabled=true + SLACK_BOT_TOKEN
to be set. Top-3-moves heuristic is currently a simple priority ordering;
full LLM-generated reasoning is TODO.

Exit codes:
  0 — package generated and (optionally) posted
  1 — generic error
  2 — RADAR.md or INVENTORY.md missing
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RADAR_PATH = REPO_ROOT / "RADAR.md"
INVENTORY_PATH = REPO_ROOT / "INVENTORY.md"
PACKAGES_DIR = REPO_ROOT / "plans" / "control-loop"
PACKAGES_DIR.mkdir(parents=True, exist_ok=True)


def _read(p: Path) -> str:
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8")


def _extract_radar_section(radar_text: str, heading: str,
                           max_lines: int = 20) -> str:
    """Pull a section from RADAR.md by heading, capped at max_lines."""
    import re
    pattern = rf"^## {re.escape(heading)}"
    lines = radar_text.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if re.match(pattern, line):
            in_section = True
            out.append(line)
            continue
        if in_section:
            if line.startswith("## ") or line.startswith("---"):
                break
            out.append(line)
            if len(out) >= max_lines:
                break
    return "\n".join(out)


def _build_top_3_moves(radar_text: str) -> list[str]:
    """Return 3 suggested moves for Solon today, each 1-2 sentences.

    Simple heuristic v1: pulls from the Execution Priority section and
    the Blocked on Solon section, picking the 3 items with the highest
    downstream unlock value.

    TODO: replace with LLM-driven reasoning that reads NEXT_TASK.md
    history + recent decisions + today's calendar and returns
    personalized suggestions via lib/llm_client.
    """
    moves: list[str] = []

    # Move 1 — the top execution priority blocker
    if "sql/006" in radar_text and "pending Solon apply" in radar_text:
        moves.append(
            "Apply `sql/006_payment_link_tests.sql` and `sql/007_autopilot_suite.sql` "
            "in Supabase SQL Editor (5 min). This gates Gate 3 end-to-end AND unlocks "
            "every autopilot thread."
        )

    if "Perplexity API quota" in radar_text and "401" in radar_text:
        moves.append(
            "Top up Perplexity API credits at perplexity.ai/settings/api (2 min). "
            "This restores the direct-API war-room grading path and unblocks every "
            "DR run tonight."
        )

    if "Slack bot token" in radar_text and "Perplexity Slack app" in radar_text:
        moves.append(
            "Install the Perplexity Slack app to AMG workspace, create "
            "#titan-perplexity-warroom channel, paste the bot token. This flips "
            "the COO ↔ Perplexity routing to Slack-primary per the new CORE_CONTRACT §0."
        )

    # Fallback — use execution priority top entries
    if len(moves) < 3:
        import re
        priority_match = re.search(
            r"## Execution Priority.*?\n\n((?:\d+\..*\n)+)",
            radar_text,
            re.DOTALL,
        )
        if priority_match:
            for line in priority_match.group(1).splitlines():
                if len(moves) >= 3:
                    break
                line = line.strip()
                if line and line[0].isdigit():
                    moves.append(line[3:].strip())

    return moves[:3]


def _build_parked_big_rocks(radar_text: str) -> list[str]:
    """Extract items from Parked > 7 Days section. Returns list of titles."""
    import re
    section = _extract_radar_section(radar_text, "Parked > 7 Days", max_lines=30)
    rocks: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("- ") and "None yet" not in line:
            rocks.append(line[2:].split(" —")[0].split(":")[0].strip("`").strip())
    return rocks


def _build_package() -> str:
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    radar = _read(RADAR_PATH)
    inventory = _read(INVENTORY_PATH)

    if not radar or not inventory:
        raise FileNotFoundError("RADAR.md and/or INVENTORY.md missing")

    exec_priority = _extract_radar_section(radar, "Execution Priority (default pull order when Solon hasn't explicitly overridden)")
    blocked_section = _extract_radar_section(radar, "Blocked on Solon (actionable items)", max_lines=25)
    open_mps = _extract_radar_section(radar, "Open Megaprompts & Phases", max_lines=15)

    top3 = _build_top_3_moves(radar)
    parked_rocks = _build_parked_big_rocks(radar)

    package = f"""# SOLON_OS_CONTROL_LOOP / {today}

**Generated:** {now} by Titan (COO)
**Tag:** `SOLON_OS_CONTROL_LOOP / {today}`
**For:** Perplexity (Strategy + Research Co-pilot) to ingest when Solon says
"Use today's Solon OS Control Loop package and tell me what to do first."

---

## Titan's proposed top 3 moves for Solon today

"""
    for i, move in enumerate(top3, 1):
        package += f"**{i}.** {move}\n\n"

    if not top3:
        package += "*No top-3 moves computed — RADAR may need a refresh.*\n\n"

    package += f"""---

## RADAR snapshot — Execution Priority

{exec_priority}

---

## RADAR snapshot — Blocked on Solon (hands-on items)

{blocked_section}

---

## RADAR snapshot — Open Megaprompts & Phases

{open_mps}

---

## Parked big rocks to reconsider

"""
    if parked_rocks:
        for rock in parked_rocks[:10]:
            package += f"- {rock}\n"
    else:
        package += "*None yet parked >7 days — Titan will surface candidates here as items age.*\n"

    package += """

---

## How to use

When Solon opens Perplexity in the morning, he can simply say:

> Use today's Solon OS Control Loop package and tell me what to do first.

Perplexity already has this package in the `#titan-perplexity-warroom` Slack
channel (if `slack_grading_enabled=true`). Perplexity should:

1. Review the top-3 moves and agree, reorder, or replace them
2. Flag any parked big rocks Solon should unpark today
3. Return a single "here's what you do first" recommendation with ETA

Titan executes against whatever Solon + Perplexity agree to.
"""
    return package


def _post_to_slack(package_text: str, filename: str) -> bool:
    """Post the package to the Perplexity Slack war-room channel if enabled.
    Uses the existing lib/war_room_slack infrastructure."""
    try:
        sys.path.insert(0, str(REPO_ROOT / "lib"))
        from war_room_slack import _slack_call, _load_policy  # type: ignore
    except ImportError:
        sys.stderr.write(
            "solon_os_control_loop: war_room_slack not importable; "
            "skipping Slack post.\n"
        )
        return False

    policy = _load_policy() if _load_policy else {}
    if not policy.get("slack_grading_enabled"):
        sys.stderr.write(
            "solon_os_control_loop: policy.slack_grading_enabled is false; "
            "package written to disk only.\n"
        )
        return False

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    channel = os.environ.get("SLACK_WARROOM_CHANNEL_ID",
                             policy.get("slack_grading_channel_id", ""))
    if not token or not channel:
        sys.stderr.write(
            "solon_os_control_loop: SLACK_BOT_TOKEN or channel id not set.\n"
        )
        return False

    today = date.today().isoformat()
    header = f":compass: *SOLON_OS_CONTROL_LOOP / {today}*\n\n"
    # Slack chat.postMessage has a ~40k char limit per message; trim if huge.
    text = header + package_text[:35000]
    resp = _slack_call("chat.postMessage", token, body={
        "channel": channel,
        "text": text,
        "unfurl_links": False,
    })
    if resp.get("ok"):
        sys.stderr.write(f"solon_os_control_loop: posted to {channel}\n")
        return True
    sys.stderr.write(
        f"solon_os_control_loop: Slack post failed: {resp.get('error')}\n"
    )
    return False


def main() -> int:
    try:
        package = _build_package()
    except FileNotFoundError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"ERROR: {type(e).__name__}: {e}\n")
        return 1

    today = date.today().isoformat()
    filename = f"SOLON_OS_CONTROL_LOOP_{today}.md"
    out_path = PACKAGES_DIR / filename
    out_path.write_text(package, encoding="utf-8")
    print(f"wrote: {out_path}")

    _post_to_slack(package, filename)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
