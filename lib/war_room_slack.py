"""
titan-harness/lib/war_room_slack.py

Slack-routed Perplexity grading for war_room.py.

Motivation
----------
When the direct Perplexity API quota is exhausted (observed 2026-04-11),
war-room grading cannot fall back to a different model without losing the
sonar-pro live-research characteristic that grade quality depends on.

The Perplexity Slack app provides an alternate routing: post a grading
prompt to a dedicated channel, @mention the Perplexity bot, poll the
thread for its reply, parse the reply back into a GradeResult. Slower
than direct API (~30-90s per round) but bypasses the API quota and
creates a human-auditable channel where Solon or any team member can
scroll back through grading rationale.

Design
------
1. SlackWarRoom class mirrors WarRoom.grade() signature in war_room.py so
   the dispatcher can swap implementations based on policy.yaml's
   war_room.slack_grading_enabled flag.
2. Each grading round becomes one Slack message with an `@perplexity`
   mention and a structured "you are grading Titan output, return JSON
   grade/issues/recommendations" user prompt.
3. conversations.replies polling (every slack_grading_poll_interval_s
   seconds, up to slack_grading_timeout_s) watches for a reply from the
   Perplexity bot user_id in the same thread.
4. Reply text is parsed with the same _parse_grade_json helper used by
   direct-API grading.
5. Every round logs to public.war_room_exchanges with a `slack_message_ts`
   field (stored in raw_response) for correlation with the Slack archive.

Privacy
-------
`slack_grading_privacy_mode: "strict"` (policy default) refuses to post
any content containing patterns that look like credentials, PII, or
client-identifying information. The privacy scan is conservative —
false positives are preferable to false negatives because this channel
is cross-team visible.

Disabled by default
-------------------
policy.yaml's `slack_grading_enabled: false` means this module is
dormant until Solon flips the flag. Rationale: it requires the Perplexity
Slack app to be installed to the AMG workspace, a dedicated channel to
exist, and a slack bot token to be exported.

Environment
-----------
- SLACK_BOT_TOKEN       xoxb-... bot-scoped token (chat:write, channels:history)
- SLACK_WARROOM_CHANNEL_ID  C-prefixed channel id (policy override)
- SLACK_PERPLEXITY_BOT_USER_ID  U-prefixed Perplexity bot user id (policy override)
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

# Reuse types + helpers from war_room.py so this module doesn't drift
# from the direct-API path. All shared grading semantics live there.
try:
    from war_room import (
        GradeResult,
        Round,
        WarRoomSession,
        GRADE_ORDER,
        _build_grading_user_message,
        _parse_grade_json,
        _log_round_to_supabase,
        _post_slack,
        _resolve_credentials,
        _load_policy,
        DEFAULT_REVISER_MODEL,
    )
except ImportError:
    # Allow running this file standalone for testing
    GradeResult = None  # type: ignore
    GRADE_ORDER = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}  # type: ignore


SLACK_API_BASE = "https://slack.com/api"
DEFAULT_POLL_INTERVAL = 3
DEFAULT_TIMEOUT = 180


# ---------------------------------------------------------------------------
# Privacy scan
# ---------------------------------------------------------------------------

_PII_PATTERNS = [
    re.compile(r"(?i)(?:api[-_]?key|secret|bearer|authorization:)\s*[:=]?\s*['\"]?[\w\-\.]{16,}"),
    re.compile(r"(?i)(?:password|passwd)\s*[:=]\s*['\"]?[\w\-\.!@#\$%]{6,}"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{16}\b"),  # Card number
    re.compile(r"(?i)(?:ein|tax\s*id)[\s:#]*\d{2}-?\d{7}"),
    re.compile(r"(?i)sk-ant-[\w\-]{20,}"),  # Claude sessionKey / API key
    re.compile(r"(?i)sk-proj-[\w\-]{20,}"),  # OpenAI project key
    re.compile(r"(?i)xoxb-[\w\-]{20,}"),  # Slack bot token
    re.compile(r"(?i)xoxp-[\w\-]{20,}"),  # Slack user token
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"(?i)ghp_[\w]{30,}"),  # GitHub personal access token
    re.compile(r"(?i)(?:client[-_ ]?name|customer[-_ ]?id|account[-_ ]?number)[\s:]+['\"]?[\w\- ]+"),
]


def _privacy_violations(text: str, mode: str = "strict") -> list[str]:
    """Return a list of privacy violations found in `text`. Empty list = clean."""
    violations: list[str] = []
    if mode == "off":
        return violations
    for pat in _PII_PATTERNS:
        m = pat.search(text)
        if m:
            violations.append(f"pattern matched: {pat.pattern[:60]}...")
    return violations


# ---------------------------------------------------------------------------
# Slack Web API helpers (stdlib only, no requests dependency)
# ---------------------------------------------------------------------------

def _slack_call(method: str, token: str, body: dict | None = None,
                params: dict | None = None, timeout: int = 15) -> dict:
    """POST to Slack Web API or GET for query-param-only methods."""
    if params is not None:
        url = f"{SLACK_API_BASE}/{method}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )
    else:
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(
            f"{SLACK_API_BASE}/{method}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _post_grading_message(token: str, channel_id: str, bot_user_id: str,
                           prompt: str) -> tuple[Optional[str], dict]:
    """Post the grading prompt and return (thread_ts, raw_response)."""
    text = f"<@{bot_user_id}> {prompt}"
    resp = _slack_call("chat.postMessage", token, body={
        "channel": channel_id,
        "text": text,
        "unfurl_links": False,
        "unfurl_media": False,
    })
    if not resp.get("ok"):
        return None, resp
    return resp.get("ts"), resp


def _poll_for_bot_reply(token: str, channel_id: str, thread_ts: str,
                        bot_user_id: str, poll_interval_s: int,
                        timeout_s: int) -> Optional[dict]:
    """Poll conversations.replies until the Perplexity bot replies in-thread."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = _slack_call("conversations.replies", token, params={
            "channel": channel_id,
            "ts": thread_ts,
            "limit": "20",
        })
        if not resp.get("ok"):
            sys.stderr.write(f"war_room_slack: replies error: {resp.get('error')}\n")
            time.sleep(poll_interval_s)
            continue
        for msg in resp.get("messages", []):
            # Skip the original prompt message
            if msg.get("ts") == thread_ts:
                continue
            if msg.get("user") == bot_user_id or msg.get("bot_id"):
                # Perplexity bot returns its answer as `text`. Some workspace
                # configurations deliver it in `blocks` (rich-text); prefer
                # flattened text, fall back to block walk.
                text = msg.get("text", "")
                if not text and msg.get("blocks"):
                    text = _flatten_blocks(msg["blocks"])
                if text:
                    return {"text": text, "ts": msg.get("ts"), "raw": msg}
        time.sleep(poll_interval_s)
    return None


def _flatten_blocks(blocks: list) -> str:
    parts: list[str] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        for element in b.get("elements", []) or []:
            if isinstance(element, dict):
                inner = element.get("elements") or []
                for sub in inner:
                    if isinstance(sub, dict) and sub.get("text"):
                        parts.append(sub["text"])
                if element.get("text"):
                    parts.append(element["text"])
        if b.get("text"):
            t = b["text"]
            if isinstance(t, dict) and t.get("text"):
                parts.append(t["text"])
            elif isinstance(t, str):
                parts.append(t)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# SlackWarRoom — drop-in replacement for WarRoom._grade_once
# ---------------------------------------------------------------------------

class SlackWarRoom:
    """Drop-in alternative to WarRoom for Slack-routed Perplexity grading.

    Usage (from war_room.py dispatcher):
        if policy.get("slack_grading_enabled"):
            swr = SlackWarRoom(policy=policy, creds=creds)
            return swr.grade(titan_output=..., phase=..., trigger_source=...)

    Environment variables override policy.yaml channel + bot id if set:
        SLACK_WARROOM_CHANNEL_ID
        SLACK_PERPLEXITY_BOT_USER_ID
        SLACK_BOT_TOKEN
    """

    def __init__(self, policy: Optional[dict[str, Any]] = None,
                 creds: Optional[dict[str, str]] = None,
                 instance_id: Optional[str] = None):
        self.policy = policy or (_load_policy() if _load_policy else {})
        self.creds = creds or (_resolve_credentials() if _resolve_credentials else {})
        self.instance_id = instance_id or socket.gethostname()

        self.token = (os.environ.get("SLACK_BOT_TOKEN")
                      or self.creds.get("SLACK_BOT_TOKEN", ""))
        self.channel_id = (os.environ.get("SLACK_WARROOM_CHANNEL_ID")
                           or str(self.policy.get("slack_grading_channel_id", "")))
        self.bot_user_id = (os.environ.get("SLACK_PERPLEXITY_BOT_USER_ID")
                            or str(self.policy.get("slack_grading_bot_user_id", "")))
        self.poll_interval = int(self.policy.get("slack_grading_poll_interval_s",
                                                  DEFAULT_POLL_INTERVAL))
        self.timeout_s = int(self.policy.get("slack_grading_timeout_s",
                                              DEFAULT_TIMEOUT))
        self.privacy_mode = str(self.policy.get("slack_grading_privacy_mode",
                                                 "strict"))

    # ------------------------------------------------------------------
    # Preflight — refuse to run if config is incomplete
    # ------------------------------------------------------------------

    def preflight_error(self) -> Optional[str]:
        """Return human-readable error string if not ready; None if OK."""
        if not self.token:
            return ("SLACK_BOT_TOKEN not set — export via /root/.titan-env or the "
                    "process env. Required scopes: chat:write, channels:history, "
                    "groups:history")
        if not self.channel_id or not self.channel_id.startswith("C"):
            return ("slack_grading_channel_id not set or not a C-prefixed channel id. "
                    "Populate policy.yaml war_room.slack_grading_channel_id with the "
                    "actual channel id (not the #name).")
        if not self.bot_user_id or not self.bot_user_id.startswith("U"):
            return ("slack_grading_bot_user_id not set or not a U-prefixed user id. "
                    "Install the Perplexity Slack app, invite it to the war-room "
                    "channel, then find its user id via users.info and populate "
                    "policy.yaml.")
        return None

    # ------------------------------------------------------------------
    # Public API — matches WarRoom.grade() signature so the dispatcher
    # can swap implementations transparently.
    # ------------------------------------------------------------------

    def grade(self,
              titan_output: str,
              phase: str,
              trigger_source: str = "manual",
              context: str = "",
              project_id: Optional[str] = None) -> Any:
        """Run one grading round through the Slack channel.

        Returns a WarRoomSession-compatible object. If the direct war_room
        module is not importable (standalone test), returns a dict.
        """
        if _load_policy is None:
            # Standalone test mode — return a dict
            return self._grade_standalone(titan_output, phase, trigger_source)

        import uuid as _uuid
        session = WarRoomSession(
            exchange_group_id=str(_uuid.uuid4()),
            project_id=project_id or self.policy.get("project_id", "EOM"),
            phase=phase,
            trigger_source=trigger_source,
        )

        err = self.preflight_error()
        if err:
            sys.stderr.write(f"war_room_slack: preflight failed: {err}\n")
            grade_err = GradeResult(
                grade="ERROR", issues=[err], recommendations=[],
                summary="preflight failed",
                raw_response="", input_tokens=0, output_tokens=0,
            )
            session.rounds.append(Round(1, titan_output, grade_err))
            session.terminal_reason = "error"
            return session

        # Privacy scan — refuse to post credentials/PII/client data
        full_prompt_plaintext = titan_output + "\n\n" + (context or "")
        violations = _privacy_violations(full_prompt_plaintext, self.privacy_mode)
        if violations:
            msg = (f"refused to post — {len(violations)} privacy violations: "
                   f"{violations[:3]}")
            sys.stderr.write(f"war_room_slack: {msg}\n")
            grade_err = GradeResult(
                grade="ERROR", issues=[msg], recommendations=[],
                summary="privacy block",
                raw_response="", input_tokens=0, output_tokens=0,
            )
            session.rounds.append(Round(1, titan_output, grade_err))
            session.terminal_reason = "error"
            return session

        # Build the grading user message — same prompt as direct API
        prompt = _build_grading_user_message(titan_output, phase, trigger_source, context)

        # Post to Slack
        thread_ts, post_resp = _post_grading_message(
            self.token, self.channel_id, self.bot_user_id, prompt
        )
        if not thread_ts:
            err_str = f"Slack post failed: {post_resp.get('error', 'unknown')}"
            grade_err = GradeResult(
                grade="ERROR", issues=[err_str], recommendations=[],
                summary="slack post failed",
                raw_response=json.dumps(post_resp),
                input_tokens=0, output_tokens=0,
            )
            session.rounds.append(Round(1, titan_output, grade_err))
            session.terminal_reason = "error"
            return session

        # Poll for reply
        reply = _poll_for_bot_reply(
            self.token, self.channel_id, thread_ts, self.bot_user_id,
            self.poll_interval, self.timeout_s,
        )
        if not reply:
            err_str = (f"Perplexity bot did not reply within {self.timeout_s}s "
                       f"(thread_ts={thread_ts})")
            grade_err = GradeResult(
                grade="ERROR", issues=[err_str], recommendations=[],
                summary="slack timeout",
                raw_response="",
                input_tokens=0, output_tokens=0,
            )
            session.rounds.append(Round(1, titan_output, grade_err))
            session.terminal_reason = "error"
            return session

        # Parse the bot's reply into a GradeResult
        reply_text = reply["text"]
        grade_letter, issues, recs, summary = _parse_grade_json(reply_text)

        grade_result = GradeResult(
            grade=grade_letter,
            issues=issues,
            recommendations=recs,
            summary=summary,
            raw_response=reply_text + f"\n\n[slack_message_ts={reply['ts']}]",
            input_tokens=0,   # Slack path doesn't expose token counts
            output_tokens=0,
            cost_cents=0.0,   # Slack app is billed under the Perplexity Slack plan
        )

        session.rounds.append(Round(1, titan_output, grade_result))
        session.terminal_reason = ("passed"
                                    if GRADE_ORDER.get(grade_letter, 0) >= 5
                                    else "needs_revision")

        # Log + Slack ping (fire-and-forget)
        try:
            table = self.policy.get("log_table", "war_room_exchanges")
            _log_round_to_supabase(
                self.creds, table, session, session.rounds[-1],
                converged=True,
                terminal_reason=session.terminal_reason,
                instance_id=self.instance_id,
            )
        except Exception as e:
            sys.stderr.write(f"war_room_slack: supabase log failed: {e}\n")

        return session

    def _grade_standalone(self, titan_output: str, phase: str,
                          trigger_source: str) -> dict:
        """Standalone-test path that returns a plain dict instead of WarRoomSession."""
        err = self.preflight_error()
        if err:
            return {"error": err, "grade": "ERROR"}
        return {"grade": "NOT_IMPLEMENTED_IN_STANDALONE",
                "message": ("this path is only reachable when war_room.py "
                            "is not importable — import it first")}


# ---------------------------------------------------------------------------
# CLI entry point — for smoke testing from the command line
# ---------------------------------------------------------------------------

def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="war_room_slack")
    parser.add_argument("--preflight", action="store_true",
                        help="Run preflight check and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be posted without actually posting")
    parser.add_argument("--text", default="Smoke test output from war_room_slack",
                        help="Titan output text to grade")
    parser.add_argument("--phase", default="smoke_test")
    args = parser.parse_args()

    swr = SlackWarRoom()

    if args.preflight:
        err = swr.preflight_error()
        if err:
            print(f"FAIL: {err}")
            return 2
        print("OK: SlackWarRoom preflight passed")
        print(f"  channel: {swr.channel_id}")
        print(f"  bot: {swr.bot_user_id}")
        print(f"  poll interval: {swr.poll_interval}s")
        print(f"  timeout: {swr.timeout_s}s")
        print(f"  privacy mode: {swr.privacy_mode}")
        return 0

    if args.dry_run:
        print("DRY RUN — would post to Slack:")
        print(f"  channel: {swr.channel_id or '<UNSET>'}")
        print(f"  bot mention: @{swr.bot_user_id or '<UNSET>'}")
        print(f"  text head: {args.text[:200]}")
        violations = _privacy_violations(args.text, swr.privacy_mode)
        if violations:
            print(f"  PRIVACY BLOCK — {len(violations)} violations:")
            for v in violations:
                print(f"    - {v}")
            return 3
        print("  privacy: clean")
        return 0

    print("ERROR: only --preflight and --dry-run are supported as CLI modes. "
          "Integrate via war_room.py dispatcher for live runs.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
