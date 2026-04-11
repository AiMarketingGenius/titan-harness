"""
titan-harness/lib/aristotle_slack.py

First-class Slack agent integration — Titan ↔ Aristotle (Perplexity-in-Slack).

Motivation (Solon directive 2026-04-11):
  - Treat Aristotle (Perplexity running in the AMG Slack workspace) as a
    first-class co-agent alongside Titan.
  - Whenever Titan materially updates INVENTORY.md, RADAR.md, or ships a
    major DR / blueprint, post to Aristotle's channel with a short summary
    + file/link so Aristotle has ground truth.
  - Daily SOLON_OS_CONTROL_LOOP bundles post to the same channel.
  - When Titan needs research / grading / doctrine, default to asking
    Aristotle in Slack rather than hitting the direct Perplexity API.

Channel: see policy.yaml aristotle.channel_name (default #titan-aristotle).

Public API:
  post_update(title, body_md, file_path=None, file_kind='doc')
  post_inventory_delta(summary, diff_stat)
  post_radar_delta(summary, section_changed)
  post_dr_shipped(plan_path, grade, one_line_summary)
  post_control_loop(package_text, date_iso)
  ask_aristotle(question, context_files=None, timeout_s=300)  → reply text or None

All posting goes through the existing lib/war_room_slack._slack_call
helper (stdlib-only, no new deps). Reuses the privacy scan from
war_room_slack to refuse posting credentials/PII.

Preflight: if SLACK_BOT_TOKEN or the channel id / bot user id are not
set, the module short-circuits with a noop + stderr warning. Never
blocks the caller.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

# Reuse war_room_slack infra (stdlib-only Slack client + privacy scan)
try:
    from war_room_slack import (
        _slack_call,
        _poll_for_bot_reply,
        _privacy_violations,
        _load_policy,
    )
except ImportError:
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from war_room_slack import (  # type: ignore
            _slack_call,
            _poll_for_bot_reply,
            _privacy_violations,
            _load_policy,
        )
    except ImportError:
        _slack_call = None  # type: ignore
        _poll_for_bot_reply = None  # type: ignore
        _privacy_violations = None  # type: ignore
        _load_policy = None  # type: ignore


DEFAULT_CHANNEL_NAME = "#titan-aristotle"
DEFAULT_TIMEOUT_S = 300
DEFAULT_POLL_INTERVAL_S = 3


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def _get_config() -> dict:
    """Resolve channel + bot config from env + policy.yaml aristotle: block."""
    policy = _load_policy() if _load_policy else {}

    # Aristotle block overrides war_room.slack_grading_* block if present
    cfg = {
        "channel_name": (
            os.environ.get("ARISTOTLE_CHANNEL_NAME")
            or policy.get("aristotle_channel_name")
            or DEFAULT_CHANNEL_NAME
        ),
        "channel_id": (
            os.environ.get("ARISTOTLE_CHANNEL_ID")
            or policy.get("aristotle_channel_id")
            or os.environ.get("SLACK_WARROOM_CHANNEL_ID")
            or policy.get("slack_grading_channel_id", "")
        ),
        "bot_user_id": (
            os.environ.get("ARISTOTLE_BOT_USER_ID")
            or policy.get("aristotle_bot_user_id")
            or os.environ.get("SLACK_PERPLEXITY_BOT_USER_ID")
            or policy.get("slack_grading_bot_user_id", "")
        ),
        "token": os.environ.get("SLACK_BOT_TOKEN", ""),
        "enabled": bool(
            policy.get("aristotle_enabled", False)
            or policy.get("slack_grading_enabled", False)
        ),
        "privacy_mode": str(policy.get("aristotle_privacy_mode", "strict")),
    }
    return cfg


def is_ready() -> tuple[bool, str]:
    """Return (ready, reason). ready=True means posting will work."""
    cfg = _get_config()
    if not cfg["enabled"]:
        return False, "aristotle_enabled=false in policy.yaml (set to true to activate)"
    if not cfg["token"]:
        return False, "SLACK_BOT_TOKEN not set (xoxb-... with chat:write + channels:history)"
    if not cfg["channel_id"] or not cfg["channel_id"].startswith("C"):
        return False, "aristotle_channel_id not set or not C-prefixed"
    if not cfg["bot_user_id"] or not cfg["bot_user_id"].startswith("U"):
        return False, "aristotle_bot_user_id not set or not U-prefixed"
    if _slack_call is None:
        return False, "lib/war_room_slack not importable"
    return True, "ready"


# ---------------------------------------------------------------------------
# Core post helpers
# ---------------------------------------------------------------------------

def _post(text: str, thread_ts: Optional[str] = None) -> Optional[str]:
    """Low-level poster. Returns message ts on success, None on failure/noop."""
    ready, reason = is_ready()
    if not ready:
        sys.stderr.write(f"aristotle_slack: skipping post — {reason}\n")
        return None

    cfg = _get_config()

    # Privacy scan
    if _privacy_violations is not None:
        violations = _privacy_violations(text, cfg["privacy_mode"])
        if violations:
            sys.stderr.write(
                f"aristotle_slack: PRIVACY BLOCK ({len(violations)} violations): "
                f"{violations[:2]}\n"
            )
            return None

    body: dict = {
        "channel": cfg["channel_id"],
        "text": text[:39000],  # Slack limit ~40k
        "unfurl_links": False,
        "unfurl_media": False,
    }
    if thread_ts:
        body["thread_ts"] = thread_ts

    resp = _slack_call("chat.postMessage", cfg["token"], body=body)
    if resp.get("ok"):
        return resp.get("ts")
    sys.stderr.write(f"aristotle_slack: post failed: {resp.get('error')}\n")
    return None


def _upload_file(file_path: Path, title: str,
                 initial_comment: str = "") -> Optional[str]:
    """Upload a file to the Aristotle channel via files.upload_v2.

    For now, falls back to inlining the file content as a code block if
    upload_v2 is not available. Returns message ts on success.
    """
    ready, _ = is_ready()
    if not ready:
        return None
    if not file_path.is_file():
        sys.stderr.write(f"aristotle_slack: file missing {file_path}\n")
        return None

    cfg = _get_config()
    content = file_path.read_text(encoding="utf-8", errors="replace")
    max_inline = 35000
    if len(content) <= max_inline:
        text = f"{initial_comment}\n\n*{title}* (`{file_path.name}`)\n\n```\n{content}\n```"
        return _post(text)
    # Too large — post the first ~20k chars + a "truncated" notice
    text = (
        f"{initial_comment}\n\n*{title}* (`{file_path.name}` — TRUNCATED, "
        f"full file on VPS at `/opt/titan-harness/{file_path.relative_to(Path('/Users/solonzafiropoulos1/titan-harness')) if str(file_path).startswith('/Users/solonzafiropoulos1/titan-harness') else file_path}`)\n\n"
        f"```\n{content[:18000]}\n\n... [TRUNCATED — {len(content)} chars total] ...\n\n{content[-2000:]}\n```"
    )
    return _post(text)


# ---------------------------------------------------------------------------
# High-level post helpers (what callers actually use)
# ---------------------------------------------------------------------------

def post_update(title: str, body_md: str,
                file_path: Optional[Path] = None,
                file_kind: str = "doc") -> Optional[str]:
    """Generic update: 'title + 1-3 line body_md + optional file attachment'."""
    text = f":triangular_flag_on_post: *{title}*\n\n{body_md[:2000]}"
    ts = _post(text)
    if ts and file_path and file_path.is_file():
        _upload_file(file_path, title=f"{title} ({file_kind})")
    return ts


def post_inventory_delta(summary: str, diff_stat: str = "") -> Optional[str]:
    """Post a summary of a material INVENTORY.md change."""
    text = (
        f":books: *INVENTORY.md updated*\n\n"
        f"{summary}\n\n"
        + (f"```\n{diff_stat[:500]}\n```" if diff_stat else "")
        + "\n\nFull file: `INVENTORY.md` on master "
        "(https://github.com/AiMarketingGenius/titan-harness/blob/master/INVENTORY.md)"
    )
    return _post(text)


def post_radar_delta(summary: str, section_changed: str = "") -> Optional[str]:
    """Post a summary of a material RADAR.md change."""
    text = (
        f":compass: *RADAR.md updated*"
        + (f" — section: `{section_changed}`" if section_changed else "")
        + f"\n\n{summary[:2000]}\n\n"
        "Full file: `RADAR.md` on master."
    )
    return _post(text)


def post_dr_shipped(plan_path: Path,
                    grade: str,
                    one_line_summary: str) -> Optional[str]:
    """Post that a new DR / blueprint shipped. Includes grade + summary +
    inline content if small enough."""
    title = f"DR shipped: `{plan_path.name}`"
    text = (
        f":rocket: *{title}* — war-room grade **{grade}**\n\n"
        f"{one_line_summary[:500]}\n\n"
        f"File: `plans/{plan_path.name}` on master."
    )
    ts = _post(text)
    if ts and plan_path.is_file():
        _upload_file(plan_path, title=title, initial_comment="")
    return ts


def post_control_loop(package_text: str,
                      date_iso: Optional[str] = None) -> Optional[str]:
    """Post the daily SOLON_OS_CONTROL_LOOP bundle."""
    d = date_iso or date.today().isoformat()
    header = (
        f":sunrise_over_mountains: *SOLON_OS_CONTROL_LOOP / {d}*\n\n"
        "Aristotle — today's context for Solon is below. When he asks "
        "\"Use today's Control Loop package and tell me what to do first,\" "
        "this is the ground truth.\n\n"
    )
    return _post(header + package_text[:35000])


# ---------------------------------------------------------------------------
# Ask Aristotle — blocking Q&A
# ---------------------------------------------------------------------------

def ask_aristotle(question: str,
                  context_files: Optional[list[Path]] = None,
                  timeout_s: int = DEFAULT_TIMEOUT_S) -> Optional[str]:
    """Post a question to Aristotle and wait for a threaded reply.

    context_files get inlined (or truncated) under the question so
    Aristotle has the same ground truth. Blocks up to timeout_s waiting
    for the bot's reply via war_room_slack._poll_for_bot_reply.

    Returns the reply text on success, None on timeout / failure / noop.

    Examples:
      ask_aristotle("grade this DR", context_files=[Path("plans/PLAN_x.md")])
      ask_aristotle("compare these 3 plans and pick the best",
                    context_files=[p1, p2, p3])
      ask_aristotle("summarize our current Atlas doctrine from files I've posted")
    """
    ready, reason = is_ready()
    if not ready:
        sys.stderr.write(f"aristotle_slack: ask skipped — {reason}\n")
        return None

    cfg = _get_config()

    # Build the full prompt
    parts = [f"<@{cfg['bot_user_id']}> {question}"]
    if context_files:
        for fp in context_files:
            if fp.is_file():
                content = fp.read_text(encoding="utf-8", errors="replace")
                # Cap each context file to keep the single-message budget
                if len(content) > 8000:
                    content = content[:6000] + "\n\n... [TRUNCATED] ..."
                parts.append(f"\n\n---\n**{fp.name}**\n```\n{content}\n```")

    full_prompt = "\n".join(parts)

    # Privacy scan
    if _privacy_violations is not None:
        violations = _privacy_violations(full_prompt, cfg["privacy_mode"])
        if violations:
            sys.stderr.write(
                f"aristotle_slack: ASK BLOCKED by privacy scan "
                f"({len(violations)} violations)\n"
            )
            return None

    # Post the question
    resp = _slack_call("chat.postMessage", cfg["token"], body={
        "channel": cfg["channel_id"],
        "text": full_prompt[:39000],
        "unfurl_links": False,
    })
    if not resp.get("ok"):
        sys.stderr.write(f"aristotle_slack: ask post failed: {resp.get('error')}\n")
        return None

    thread_ts = resp.get("ts")
    if not thread_ts or _poll_for_bot_reply is None:
        return None

    # Poll for Aristotle's reply in-thread
    reply = _poll_for_bot_reply(
        cfg["token"], cfg["channel_id"], thread_ts,
        cfg["bot_user_id"], DEFAULT_POLL_INTERVAL_S, timeout_s,
    )
    if not reply:
        sys.stderr.write(
            f"aristotle_slack: Aristotle did not reply within {timeout_s}s "
            f"(thread_ts={thread_ts})\n"
        )
        return None
    return reply.get("text", "")


# ---------------------------------------------------------------------------
# CLI — for manual posts + preflight
# ---------------------------------------------------------------------------

def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="aristotle_slack")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--post-inventory", action="store_true",
                        help="Post an INVENTORY.md delta notification")
    parser.add_argument("--post-radar", action="store_true",
                        help="Post a RADAR.md delta notification")
    parser.add_argument("--post-dr", type=str,
                        help="Post a DR plan (path to plans/PLAN_*.md)")
    parser.add_argument("--summary", type=str, default="",
                        help="One-line summary for delta posts")
    parser.add_argument("--grade", type=str, default="A",
                        help="Grade for --post-dr (e.g. A 9.47/10)")
    parser.add_argument("--ask", type=str,
                        help="Ask Aristotle a question (blocks for reply)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = _get_config()

    if args.preflight:
        ready, reason = is_ready()
        print(f"ready:        {ready}")
        print(f"reason:       {reason}")
        print(f"channel name: {cfg['channel_name']}")
        print(f"channel id:   {cfg['channel_id'] or '<UNSET>'}")
        print(f"bot user id:  {cfg['bot_user_id'] or '<UNSET>'}")
        print(f"token:        {'set' if cfg['token'] else '<UNSET>'}")
        print(f"privacy mode: {cfg['privacy_mode']}")
        return 0 if ready else 2

    if args.dry_run:
        print(f"DRY RUN — would post to {cfg['channel_name']} ({cfg['channel_id'] or 'no-id'})")
        return 0

    if args.post_inventory:
        ts = post_inventory_delta(args.summary or "INVENTORY.md updated")
        print(f"posted ts={ts}" if ts else "post failed/skipped")
        return 0 if ts else 1
    if args.post_radar:
        ts = post_radar_delta(args.summary or "RADAR.md updated")
        print(f"posted ts={ts}" if ts else "post failed/skipped")
        return 0 if ts else 1
    if args.post_dr:
        p = Path(args.post_dr)
        ts = post_dr_shipped(p, args.grade, args.summary or f"{p.name} shipped")
        print(f"posted ts={ts}" if ts else "post failed/skipped")
        return 0 if ts else 1
    if args.ask:
        reply = ask_aristotle(args.ask)
        if reply:
            print(reply)
            return 0
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
