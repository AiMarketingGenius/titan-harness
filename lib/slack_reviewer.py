"""
titan-harness/lib/slack_reviewer.py — Slack-based Perplexity Computer reviewer

Transport layer for bin/review_gate.py when the Perplexity API is unavailable
(quota exhausted, auth failure, etc.) but Perplexity Computer is reachable via
Slack in the #titan-aristotle channel.

Architecture (per DR_TITAN_AUTONOMY_BLUEPRINT.md §9 + user-facing automation):

    Titan (bin/review_gate.py) builds an evidence bundle
        │
        ▼
    SlackReviewer.review(bundle, step_id)
        │
        ├─ POST chat.postMessage → #titan-aristotle mentioning <@reviewer_bot_id>
        │   message body = canonical §9.7 user template rendered with bundle
        │
        ├─ Poll conversations.replies on the thread_ts every 3s for up to 120s
        │   (Computer typically responds in 15-60s for structured prompts)
        │
        ├─ First non-Titan reply = Computer's grade response
        │
        ├─ Extract JSON from the reply text (strip markdown fences if any)
        │
        └─ Return {grade, approved, risk_tags, rationale, remediation}

Silent transport: no secret values ever written to stdout/stderr. The bundle
content itself is posted to a private Slack channel (#titan-aristotle) which
is Solon-controlled — the channel IS the audit surface, and Titan's privacy
scan removes any accidentally-embedded real secrets from the bundle text
before posting.

Dependencies:
  - urllib.request (stdlib only, no third-party install)
  - json (stdlib)
  - time (stdlib)

Configuration (read at init, not hardcoded):
  - SLACK_BOT_TOKEN: from Infisical harness-core/dev, fetched by caller
  - channel_id + reviewer_bot_id: from /root/.infisical/slack-config.json,
    populated by bin/titan-slack-setup.sh during one-time onboarding

Privacy scan: before posting any bundle, regex-strip these patterns
(mirrors policy.yaml idea_capture.redact_patterns):
  sk-ant-sid0[12]-* | sk-* | ghp_* | eyJ* JWT | shp(ss|at|ca)_* |
  __Secure-next-auth.session-token=* | AIza* | st.*.*.* (Infisical tokens)

If any redaction fires, the post is ABORTED (not just redacted) — real
secrets in a review bundle is a P0 session failure per DR §9.6.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


# ─── CONFIG ─────────────────────────────────────────────────────────────────────
SLACK_API_BASE = "https://slack.com/api"
SLACK_CONFIG_PATH = Path("/root/.infisical/slack-config.json")
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 120
REVIEW_MESSAGE_PREAMBLE = (
    "[Titan Reviewer Loop] Autonomous grading request. "
    "Return ONLY a valid JSON object per the schema below. No prose."
)

# Redaction patterns — matches policy.yaml idea_capture.redact_patterns.
# If any of these fire, the post is ABORTED (not just redacted).
_SECRET_PATTERNS = [
    (re.compile(r"sk-ant-sid0[12]-[A-Za-z0-9_-]{20,}"), "claude-session-key"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"),                "openai/anthropic-api-key"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"),                  "github-pat"),
    (re.compile(r"eyJ[A-Za-z0-9_=-]{40,}\.[A-Za-z0-9_=-]+\.[A-Za-z0-9_=-]+"), "jwt"),
    (re.compile(r"shp(ss|at|ca)_[A-Za-z0-9_-]{20,}"),      "shopify-token"),
    (re.compile(r"__Secure-next-auth\.session-token=[A-Za-z0-9_-]+"), "perplexity-session"),
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}"),                "google-key"),
    (re.compile(r"st\.[a-f0-9]{36}\.[A-Za-z0-9]+\.[A-Za-z0-9]+"), "infisical-service-token"),
    (re.compile(r"xoxb-[0-9]+-[0-9]+-[A-Za-z0-9]+"),       "slack-bot-token"),
    (re.compile(r"xoxp-[0-9]+-[0-9]+-[0-9]+-[A-Za-z0-9]+"), "slack-user-token"),
]


class SlackReviewerError(Exception):
    """Raised for any Slack transport or review flow failure. Messages are safe —
    never contain secret values (only names + HTTP codes + bot IDs)."""
    pass


# ─── SLACK API THIN WRAPPER (stdlib only) ───────────────────────────────────────

def _slack_call(method: str, token: str, payload: Optional[dict] = None,
                query: Optional[dict] = None, http_method: str = "POST") -> dict:
    """Call Slack Web API with urllib. Returns parsed JSON body."""
    url = f"{SLACK_API_BASE}/{method}"
    if query:
        from urllib.parse import urlencode
        url += "?" + urlencode(query)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=http_method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SlackReviewerError(f"Slack API {method} HTTP {e.code}")
    except urllib.error.URLError as e:
        raise SlackReviewerError(f"Slack API {method} network error: {type(e).__name__}")
    except json.JSONDecodeError:
        raise SlackReviewerError(f"Slack API {method} returned non-JSON response")

    if not body.get("ok"):
        err = body.get("error", "unknown")
        raise SlackReviewerError(f"Slack API {method} error: {err}")
    return body


# ─── PRIVACY SCAN ──────────────────────────────────────────────────────────────

def _scan_for_secrets(text: str) -> list:
    """Return list of (pattern_name, matched_prefix) for every hit. Empty list = clean."""
    hits = []
    for regex, label in _SECRET_PATTERNS:
        for match in regex.finditer(text):
            matched = match.group(0)
            # Store only the first 12 chars as a safe fingerprint for the error message
            hits.append((label, matched[:12] + "..."))
    return hits


# ─── REVIEWER ───────────────────────────────────────────────────────────────────

class SlackReviewer:
    """Slack-Computer transport for bin/review_gate.py."""

    def __init__(self, token: str, channel_id: str, reviewer_bot_id: str,
                 titan_bot_id: Optional[str] = None):
        self.token = token
        self.channel_id = channel_id
        self.reviewer_bot_id = reviewer_bot_id
        self.titan_bot_id = titan_bot_id  # set by setup script, used to filter Titan's own posts

    @classmethod
    def from_config(cls, token: str, config_path: Path = SLACK_CONFIG_PATH) -> "SlackReviewer":
        """Load channel_id + reviewer_bot_id from disk config written by setup script."""
        if not config_path.exists():
            raise SlackReviewerError(
                f"Slack config missing at {config_path}. "
                f"Run bin/titan-slack-setup.sh to populate."
            )
        try:
            data = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            raise SlackReviewerError(f"Slack config at {config_path} is not valid JSON")
        return cls(
            token=token,
            channel_id=data["channel_id"],
            reviewer_bot_id=data["reviewer_bot_id"],
            titan_bot_id=data.get("titan_bot_id"),
        )

    def _render_review_message(self, bundle: dict, step_id: str, system_prompt: str,
                               user_template: str) -> str:
        """Build the message body Titan posts to Slack.
        First line mentions the reviewer bot. Rest is the canonical §9.7 template.
        """
        mention = f"<@{self.reviewer_bot_id}>"
        rendered_user = user_template.format(
            step_meta=bundle.get("step_meta", ""),
            git_diff=bundle.get("git_diff", ""),
            command_log=bundle.get("command_log", ""),
            metrics=bundle.get("metrics", ""),
            blueprint_ref=bundle.get("blueprint_ref", ""),
        )
        return (
            f"{mention}\n"
            f"{REVIEW_MESSAGE_PREAMBLE}\n"
            f"*Step ID:* `{step_id}`\n\n"
            f"```\n{system_prompt}\n```\n\n"
            f"```\n{rendered_user}\n```"
        )

    def _check_privacy(self, message_body: str) -> None:
        """Abort if the message body contains any real secret pattern."""
        hits = _scan_for_secrets(message_body)
        if hits:
            labels = [h[0] for h in hits]
            raise SlackReviewerError(
                f"P0 ABORT: evidence bundle contains secret-shaped content "
                f"({labels[:5]}...) — refusing to post to Slack. "
                f"Check your bundle generator for leaked values."
            )

    def _post_review_request(self, message_body: str) -> str:
        """Post to #titan-aristotle. Returns the thread timestamp (ts) of the parent message."""
        resp = _slack_call("chat.postMessage", self.token, payload={
            "channel": self.channel_id,
            "text": message_body,
            "unfurl_links": False,
            "unfurl_media": False,
        })
        return resp["ts"]

    def _poll_for_reply(self, thread_ts: str, timeout: int = POLL_TIMEOUT_SECONDS) -> str:
        """Poll conversations.replies for the first non-Titan reply. Returns the reply text."""
        deadline = time.time() + timeout
        seen_count = 1  # the parent message we just posted counts as 1

        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)
            resp = _slack_call(
                "conversations.replies", self.token,
                query={"channel": self.channel_id, "ts": thread_ts, "limit": 50},
                http_method="GET",
            )
            messages = resp.get("messages", [])
            if len(messages) <= seen_count:
                continue

            # Look for the first non-Titan reply after the parent
            for msg in messages[1:]:
                sender = msg.get("user") or msg.get("bot_id") or msg.get("app_id")
                # Skip Titan's own messages if we have the bot ID
                if self.titan_bot_id and sender == self.titan_bot_id:
                    continue
                # Skip empty messages or message_changed events
                text = msg.get("text", "").strip()
                if not text:
                    continue
                return text

            seen_count = len(messages)

        raise SlackReviewerError(
            f"No reviewer reply within {timeout}s on thread {thread_ts}. "
            f"Computer may be offline, rate-limited, or out of credits."
        )

    def _parse_grade(self, reply_text: str) -> dict:
        """Extract the JSON grade object from Computer's reply. Strip markdown fences."""
        text = reply_text.strip()

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if "```" in text:
            # Try to extract content between the first pair of fences
            parts = text.split("```")
            if len(parts) >= 3:
                # Take the middle section; if it starts with a language tag, strip it
                middle = parts[1].strip()
                if middle.startswith("json"):
                    middle = middle[4:].strip()
                text = middle
            else:
                # Fallback: remove all fences and whitespace-normalize
                text = text.replace("```json", "").replace("```", "").strip()

        # Find the JSON object boundaries (first `{` to matching `}`)
        start = text.find("{")
        if start == -1:
            raise SlackReviewerError("Reviewer reply contains no JSON object")

        # Naive brace-matching — fine for the simple response schema
        depth = 0
        end = -1
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == -1:
            raise SlackReviewerError("Reviewer reply JSON object is unterminated")

        json_text = text[start:end]
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            raise SlackReviewerError(f"Reviewer reply JSON parse failed: {e}")

    def review(self, bundle: dict, step_id: str, system_prompt: str,
               user_template: str) -> dict:
        """Full review flow: privacy scan → post → poll → parse → return grade dict.

        Returns dict with keys: grade, approved, risk_tags, rationale, remediation.
        Raises SlackReviewerError on any failure.
        """
        message_body = self._render_review_message(bundle, step_id, system_prompt, user_template)
        self._check_privacy(message_body)
        thread_ts = self._post_review_request(message_body)
        reply_text = self._poll_for_reply(thread_ts)
        return self._parse_grade(reply_text)


# ─── CLI SMOKE TEST (names + sizes only, never values) ────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in ("auth-test", "config-check"):
        print("usage: python3 -m lib.slack_reviewer {auth-test|config-check}", file=sys.stderr)
        sys.exit(2)

    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: SLACK_BOT_TOKEN not in env (set via Infisical or directly)", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "auth-test":
        try:
            resp = _slack_call("auth.test", token)
            print(f"OK workspace={resp.get('team', '?')} bot_user={resp.get('user', '?')} "
                  f"bot_id={resp.get('user_id', '?')[:6]}...")
            sys.exit(0)
        except SlackReviewerError as e:
            print(f"FAIL {e}", file=sys.stderr)
            sys.exit(1)

    if sys.argv[1] == "config-check":
        try:
            rev = SlackReviewer.from_config(token)
            print(f"OK channel_id={rev.channel_id[:6]}... reviewer_bot_id={rev.reviewer_bot_id[:6]}... "
                  f"titan_bot_id={(rev.titan_bot_id or 'unset')[:6]}...")
            sys.exit(0)
        except SlackReviewerError as e:
            print(f"FAIL {e}", file=sys.stderr)
            sys.exit(1)
