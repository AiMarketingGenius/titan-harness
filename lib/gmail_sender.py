"""
titan-harness/lib/gmail_sender.py

CT-0415-08 — Native Gmail SMTP autonomous send module.

Sends email directly via smtp.gmail.com:465 (TLS) as any configured Google Workspace
account or alias for which Solon has generated a Gmail App Password. No Resend,
no drafts, no UI click — Titan sends autonomously.

Credential convention:
    /etc/amg/gmail-<alias>.env  (mode 0400, root-owned)
Format:
    GMAIL_ACCOUNT=growyourbusiness@drseo.io
    GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
    GMAIL_FROM_NAME=Solon / Dr. SEO

The alias in the filename is the local-part + hash of the account (e.g.,
`gmail-growyourbusiness-drseo.env`). One env file per sending identity. Discover
available identities via `list_configured_accounts()`.

Public API:
    send_email(from_alias, to, subject, body_text, *,
               body_html=None, reply_to=None, cc=None, bcc=None) -> dict
    list_configured_accounts() -> list[str]
    send_batch(emails) -> list[dict]  # batch with rate-limit-safe pacing

Limits:
    - Gmail SMTP daily limit: 500 emails/day per sender (free Workspace);
      2000/day (paid). Enforced client-side at 400/day per sender to leave
      headroom; raise SMTPQuotaExceeded if breached.
    - Rate limit: 1 email per 1.5 seconds per sender (avoids Gmail temp-block).

Error handling:
    - Auth failure → flags app-password as invalid, returns structured error
    - Daily quota exceeded → SMTPQuotaExceeded exception
    - Transient network error → single retry with 5s delay, then structured error
    - Message rejected (bounced) → structured error with SMTP code

Logging:
    Every send writes to MCP log_decision with tag `gmail_send` for audit chain.
    Spend tracking: /var/log/amg/gmail-send-counter-YYYYMMDD.jsonl, daily counter.
"""
from __future__ import annotations

import email.mime.multipart
import email.mime.text
import email.utils
import json
import os
import smtplib
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT = 30
DEFAULT_RATE_LIMIT_SEC = 1.5
DAILY_QUOTA_PER_SENDER = 400  # client-side cap; Gmail actual is 500 free / 2000 paid
ENV_DIR = Path(os.environ.get("AMG_ENV_DIR", "/etc/amg"))
COUNTER_DIR = Path(os.environ.get("AMG_GMAIL_COUNTER_DIR", "/var/log/amg"))
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT", "https://memory.aimarketinggenius.io")


class SMTPQuotaExceeded(Exception):
    pass


class SMTPAuthFailed(Exception):
    pass


# ---------------------------------------------------------------------------
# Config discovery
# ---------------------------------------------------------------------------

def _slugify(address: str) -> str:
    """Turn `growyourbusiness@drseo.io` into `growyourbusiness-drseo` for filenames."""
    local, _, domain = address.partition("@")
    domain_base = domain.split(".")[0] if domain else ""
    return f"{local}-{domain_base}"


def _env_file_for(address: str) -> Path:
    return ENV_DIR / f"gmail-{_slugify(address)}.env"


def _load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"gmail env file not found: {path}")
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def list_configured_accounts() -> list[str]:
    """Return list of Gmail account addresses that have env files in ENV_DIR."""
    if not ENV_DIR.is_dir():
        return []
    accounts = []
    for f in ENV_DIR.glob("gmail-*.env"):
        try:
            env = _load_env(f)
            addr = env.get("GMAIL_ACCOUNT")
            if addr:
                accounts.append(addr)
        except Exception:
            continue
    return sorted(accounts)


# ---------------------------------------------------------------------------
# Daily spend tracking
# ---------------------------------------------------------------------------

def _counter_file_for(address: str, *, day: Optional[date] = None) -> Path:
    day = day or date.today()
    return COUNTER_DIR / f"gmail-send-counter-{day.isoformat()}.jsonl"


def _read_today_count(address: str) -> int:
    f = _counter_file_for(address)
    if not f.is_file():
        return 0
    count = 0
    try:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("from") == address and entry.get("status") == "sent":
                    count += 1
            except json.JSONDecodeError:
                continue
    except OSError:
        return 0
    return count


def _append_counter_entry(address: str, entry: dict[str, Any]) -> None:
    try:
        COUNTER_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    f = _counter_file_for(address)
    try:
        with open(f, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry) + "\n")
    except OSError as exc:
        print(f"[gmail_sender] counter write failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# MCP audit log (best-effort)
# ---------------------------------------------------------------------------

def _log_to_mcp(payload: dict[str, Any]) -> None:
    try:
        body = json.dumps({
            "action": "log_decision",
            "data": {
                "project_source": "EOM",
                "tags": ["gmail_send", "ct-0415-08"],
                "text": f"gmail_send from={payload.get('from')} to={payload.get('to')} subj={payload.get('subject')}",
                "rationale": json.dumps(payload),
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{MCP_ENDPOINT}/log_decision",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)  # noqa: S310 — trusted
    except Exception as exc:
        print(f"[gmail_sender] MCP log failed (non-fatal): {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Core send
# ---------------------------------------------------------------------------

def _build_mime(
    *,
    from_line: str,
    to: list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    reply_to: Optional[str] = None,
    cc: Optional[list[str]] = None,
) -> email.mime.multipart.MIMEMultipart:
    msg = email.mime.multipart.MIMEMultipart("alternative" if body_html else "mixed")
    msg["From"] = from_line
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=from_line.split("@")[-1].rstrip(">"))
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(email.mime.text.MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(email.mime.text.MIMEText(body_html, "html", "utf-8"))
    return msg


def send_email(
    from_alias: str,
    to: str | list[str],
    subject: str,
    body_text: str,
    *,
    body_html: Optional[str] = None,
    reply_to: Optional[str] = None,
    cc: Optional[str | list[str]] = None,
    bcc: Optional[str | list[str]] = None,
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC,
) -> dict[str, Any]:
    """
    Send a single email via Gmail SMTP using the app password configured for
    `from_alias`. from_alias can be the full address (growyourbusiness@drseo.io)
    or just the local-part (growyourbusiness) if the account defaults to drseo.io.

    Returns: {"status": "sent"|"failed", "from", "to", "subject",
              "message_id", "count_today", "ts_utc", optional "error"}
    """
    # Normalize
    if isinstance(to, str):
        to = [to]
    if isinstance(cc, str):
        cc = [cc]
    if isinstance(bcc, str):
        bcc = [bcc]

    # Load config for sender
    if "@" not in from_alias:
        # Default to drseo.io if only local-part provided
        from_alias = f"{from_alias}@drseo.io"
    env = _load_env(_env_file_for(from_alias))
    account = env.get("GMAIL_ACCOUNT", from_alias)
    app_pw = env.get("GMAIL_APP_PASSWORD")
    from_name = env.get("GMAIL_FROM_NAME", "")
    if not app_pw:
        raise ValueError(f"GMAIL_APP_PASSWORD missing in env file for {from_alias}")

    # Quota check
    count_today = _read_today_count(account)
    if count_today >= DAILY_QUOTA_PER_SENDER:
        raise SMTPQuotaExceeded(
            f"daily quota reached: {count_today} / {DAILY_QUOTA_PER_SENDER} for {account}"
        )

    # Build MIME
    from_line = f'"{from_name}" <{account}>' if from_name else account
    msg = _build_mime(
        from_line=from_line,
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        reply_to=reply_to,
        cc=cc,
    )
    msg_id = msg.get("Message-ID", "")

    # Recipient list for SMTP envelope (includes bcc)
    envelope_to = list(to) + (cc or []) + (bcc or [])

    # Send
    ctx = ssl.create_default_context()
    attempt_started = time.monotonic()
    last_error = None
    for attempt in range(2):  # single retry
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT, context=ctx) as s:
                s.login(account, app_pw)
                s.send_message(msg, from_addr=account, to_addrs=envelope_to)
            elapsed_ms = round((time.monotonic() - attempt_started) * 1000.0, 0)
            entry = {
                "from": account,
                "to": to,
                "cc": cc,
                "bcc_count": len(bcc or []),
                "subject": subject,
                "status": "sent",
                "message_id": msg_id,
                "elapsed_ms": elapsed_ms,
                "count_today_after": count_today + 1,
                "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            }
            _append_counter_entry(account, entry)
            _log_to_mcp(entry)
            # Rate-limit spacing for immediate next send
            if rate_limit_sec > 0:
                time.sleep(rate_limit_sec)
            return entry
        except smtplib.SMTPAuthenticationError as exc:
            raise SMTPAuthFailed(f"app-password invalid for {account}: {exc}") from exc
        except (smtplib.SMTPException, ConnectionError, OSError) as exc:
            last_error = str(exc)
            if attempt == 0:
                time.sleep(5)
                continue
            entry = {
                "from": account,
                "to": to,
                "subject": subject,
                "status": "failed",
                "error": last_error,
                "attempts": 2,
                "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            }
            _append_counter_entry(account, entry)
            _log_to_mcp(entry)
            return entry
    # unreachable
    raise RuntimeError("send_email: unexpected fall-through")


def send_batch(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Batch send with rate-limiting between sends. Each element: {"from_alias",
    "to", "subject", "body_text", optional body_html/reply_to/cc/bcc}.
    """
    results = []
    for i, e in enumerate(emails):
        try:
            r = send_email(
                e["from_alias"], e["to"], e["subject"], e["body_text"],
                body_html=e.get("body_html"),
                reply_to=e.get("reply_to"),
                cc=e.get("cc"),
                bcc=e.get("bcc"),
            )
            results.append({"idx": i, **r})
        except Exception as exc:
            results.append({
                "idx": i,
                "from": e.get("from_alias"),
                "to": e.get("to"),
                "subject": e.get("subject"),
                "status": "failed",
                "error": str(exc),
            })
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Gmail SMTP autonomous sender (CT-0415-08)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    send = sub.add_parser("send", help="send a single email")
    send.add_argument("--from-alias", required=True, help="e.g. growyourbusiness or growyourbusiness@drseo.io")
    send.add_argument("--to", required=True)
    send.add_argument("--subject", required=True)
    send.add_argument("--body", required=True, help="plain text body")
    send.add_argument("--body-html", default=None)
    send.add_argument("--reply-to", default=None)
    send.add_argument("--cc", default=None)
    send.add_argument("--bcc", default=None)

    sub.add_parser("list-accounts", help="list configured Gmail accounts")

    quota = sub.add_parser("quota", help="show today's send count for a sender")
    quota.add_argument("--from-alias", required=True)

    selftest = sub.add_parser("selftest", help="config-discovery selftest (does not send)")

    args = ap.parse_args()

    if args.cmd == "list-accounts":
        accounts = list_configured_accounts()
        print(json.dumps({"configured_accounts": accounts, "env_dir": str(ENV_DIR)}, indent=2))
        return 0

    if args.cmd == "quota":
        addr = args.from_alias if "@" in args.from_alias else f"{args.from_alias}@drseo.io"
        count = _read_today_count(addr)
        print(json.dumps({"sender": addr, "sent_today": count, "daily_quota": DAILY_QUOTA_PER_SENDER}, indent=2))
        return 0

    if args.cmd == "selftest":
        print(f"[gmail_sender selftest] ENV_DIR = {ENV_DIR}")
        accounts = list_configured_accounts()
        print(f"  configured accounts: {accounts}")
        if not accounts:
            print("  no accounts configured; drop a file at /etc/amg/gmail-<alias>.env to enable")
            return 0
        for a in accounts:
            count = _read_today_count(a)
            print(f"  {a}: today_count={count} / {DAILY_QUOTA_PER_SENDER}")
        return 0

    if args.cmd == "send":
        try:
            result = send_email(
                args.from_alias,
                args.to,
                args.subject,
                args.body,
                body_html=args.body_html,
                reply_to=args.reply_to,
                cc=args.cc,
                bcc=args.bcc,
            )
            print(json.dumps(result, indent=2))
            return 0 if result.get("status") == "sent" else 1
        except Exception as exc:
            print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
            return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
