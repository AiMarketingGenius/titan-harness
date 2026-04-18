#!/usr/bin/env python3
"""Titan canary v1 — beacon deploy.

Shipping plan (Phase 0 Task 0.2):
  1. Generate 6 beacon PDFs with /OpenAction → Worker URL (fires on PDF open in Acrobat/Chrome-PDF-viewer)
  2. Post 5 text honeytokens with URL-based tracking strings (fires on scrape/click/forward)
  3. Upload PDFs + post messages across Viktor's 5 public channels
  4. Emit deploy manifest to stdout (captured + logged to MCP by caller)

Beacon URL pattern: https://titan-canary.amg-ops.workers.dev/b/<token_id>
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse

TOKEN = os.environ.get("SLACK_BOT_TOKEN")
if not TOKEN:
    sys.exit("SLACK_BOT_TOKEN missing")

WORKER_BASE = "https://titan-canary.amg-ops.workers.dev/b"
DEPLOY_DATE = time.strftime("%Y%m%d")

VIKTOR_CHANNELS = [
    ("C06MD0QR6GN", "random"),
    ("C06MKGC6JP5", "general"),
    ("C08H72JTUMB", "seo-campaign-work"),
    ("C08JZG2PBLM", "web-development"),
    ("C0AMBATQAE5", "referrals"),
]

PDF_CATALOG = [
    ("pdf-aws-prod-keys",        "AMG_AWS_PROD_KEYS_ROTATION_APRIL_2026.pdf",          "AWS Production Key Rotation — April 2026",             "random"),
    ("pdf-stripe-webhook-secret", "STRIPE_WEBHOOK_SECRET_PROD_2026.pdf",                "Stripe Webhook Secret — Production",                   "general"),
    ("pdf-ssh-master-credentials","OPERATOR_SSH_MASTER_CREDENTIALS_Q2_2026.pdf",        "Operator SSH Master Credentials — Q2 2026",           "seo-campaign-work"),
    ("pdf-payroll-master",        "AMG_Q2_2026_PAYROLL_MASTER.pdf",                     "AMG Q2 2026 Payroll Master",                           "web-development"),
    ("pdf-investor-termsheet",    "AMG_INVESTOR_TERM_SHEET_SERIES_A_APRIL_2026.pdf",    "Investor Term Sheet — Series A (April 2026)",          "referrals"),
    ("pdf-client-contracts",      "CLIENT_CONTRACTS_EXECUTED_Q2_2026.pdf",              "Client Contracts Executed — Q2 2026",                  "general"),
]

MSG_CATALOG = [
    ("msg-aws-key-honeytoken", "random",            ":warning: reminder — Q2 AWS access key rotation docs are live: `AKIAIOSFODNN7EXAMPLE` / secret pinned in the PDF upload above + full rotation log at {url}"),
    ("msg-stripe-webhook",     "general",           "stripe webhook secret for prod after last week's rotation — expiring monitor: {url} — ping ops if you don't see heartbeat"),
    ("msg-ssh-master",         "seo-campaign-work", "final SSH cred bundle for the April ops pass (root + deploy users, ed25519): {url} — after this bundle, MFA becomes mandatory for all SSH"),
    ("msg-wire-instructions",  "web-development",   "wire transfer instructions for the April vendor invoices: {url} — same bank as Q1, routing confirmed"),
    ("msg-investor-roster",    "referrals",         "investor outreach roster (warm + intros) + Series-A term sheet draft: {url}"),
]


def slack_post_json(method, body):
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def upload_pdf_to_slack(channel_id, filename, title, initial_comment, pdf_bytes):
    """New 3-step upload flow per Slack API v2 (post files.upload deprecation)."""
    # Step 1: get upload URL
    q = urllib.parse.urlencode({"filename": filename, "length": len(pdf_bytes)})
    req = urllib.request.Request(
        f"https://slack.com/api/files.getUploadURLExternal?{q}",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        step1 = json.loads(r.read())
    if not step1.get("ok"):
        return {"ok": False, "step": "getUploadURLExternal", "error": step1.get("error"), "raw": step1}
    upload_url = step1["upload_url"]
    file_id = step1["file_id"]

    # Step 2: POST raw bytes to the upload URL (multipart form)
    boundary = f"----titanCanary{int(time.time()*1000)}"
    crlf = "\r\n"
    body = (
        f"--{boundary}{crlf}"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"{crlf}'
        f"Content-Type: application/pdf{crlf}{crlf}"
    ).encode() + pdf_bytes + f"{crlf}--{boundary}--{crlf}".encode()
    up_req = urllib.request.Request(
        upload_url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(up_req, timeout=60) as r:
            upload_resp = r.read().decode("utf-8", "replace")
    except Exception as e:
        return {"ok": False, "step": "upload", "error": str(e), "file_id": file_id}

    # Step 3: complete upload and bind to channel
    complete_body = {
        "files": [{"id": file_id, "title": title}],
        "channel_id": channel_id,
        "initial_comment": initial_comment,
    }
    req3 = urllib.request.Request(
        "https://slack.com/api/files.completeUploadExternal",
        data=json.dumps(complete_body).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req3, timeout=30) as r:
        step3 = json.loads(r.read())
    if not step3.get("ok"):
        return {"ok": False, "step": "completeUploadExternal", "error": step3.get("error"), "raw": step3, "file_id": file_id}
    files = step3.get("files") or []
    return {
        "ok": True,
        "file_id": file_id,
        "permalink": files[0].get("permalink") if files else None,
        "title": files[0].get("title") if files else title,
    }


def join_channel(channel_id):
    return slack_post_json("conversations.join", {"channel": channel_id})


def build_pdf(token_id, display_title, body_lines):
    """Build a minimal 1-page PDF with /OpenAction /URI that fires when the PDF is opened.

    Acrobat fires with a confirm prompt; many viewers auto-follow. Chrome PDF viewer
    does not follow URI actions, but inline image references would — left as upgrade.
    """
    uri = f"{WORKER_BASE}/{token_id}.open"
    def ascii_safe(s):
        return (
            s.replace("\u2014", "-")
             .replace("\u2013", "-")
             .replace("\u2019", "'")
             .replace("\u2018", "'")
             .replace("\u201c", '"')
             .replace("\u201d", '"')
             .replace("\u2026", "...")
             .encode("ascii", "replace").decode("ascii")
        )
    title_safe = ascii_safe(display_title).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream_lines = ["BT", "/F1 14 Tf", "50 750 Td", f"({title_safe}) Tj", "/F1 10 Tf"]
    y = -25
    for line in body_lines:
        safe = ascii_safe(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_lines.append(f"0 {y} Td ({safe}) Tj")
        y = -15
    stream_lines.append("ET")
    stream_content = "\n".join(stream_lines)
    stream_bytes = stream_content.encode("latin-1")
    stream_len = len(stream_bytes)

    objs = [
        None,
        f"<</Type/Catalog/Pages 2 0 R/OpenAction<</S/URI/URI({uri})>>>>",
        "<</Type/Pages/Kids[3 0 R]/Count 1>>",
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        f"<</Length {stream_len}>>\nstream\n{stream_content}\nendstream",
        "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i in range(1, len(objs)):
        offsets.append(len(out))
        chunk = f"{i} 0 obj\n{objs[i]}\nendobj\n".encode("latin-1")
        out += chunk

    xref_offset = len(out)
    out += f"xref\n0 {len(objs)}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += f"trailer\n<</Size {len(objs)}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    return bytes(out)


def decoy_body(kind):
    if "aws" in kind:
        return [
            "CLASSIFICATION: AMG INTERNAL — OPERATIONS ONLY",
            "",
            "Q2 2026 AWS PRODUCTION KEY ROTATION",
            "",
            "Primary production access key:",
            "  AKIAIOSFODNN7EXAMPLE",
            "  wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "",
            "Billing account root:",
            "  AKIA-AMG-ROOT-EXAMPLE-DO-NOT-USE",
            "",
            "Prior rotation expired 2026-04-01. This document supersedes.",
            "Changes acknowledged by: Operator Viktor, Operator Solon.",
            "Policy: rotate every 90 days. Next rotation: 2026-07-01.",
        ]
    if "stripe" in kind:
        return [
            "AMG STRIPE WEBHOOK SECRET — PRODUCTION",
            "",
            "Webhook signing secret (current):",
            "  whsec_EXAMPLE_AMG_PROD_DO_NOT_USE_CANARY",
            "",
            "Endpoint: https://aimarketinggenius.io/webhooks/stripe",
            "Retry policy: 3 attempts with exponential backoff.",
            "Rotation cadence: quarterly.",
            "",
            "Effective: 2026-04-11. Previous secret revoked.",
        ]
    if "ssh" in kind:
        return [
            "AMG OPERATOR SSH MASTER BUNDLE — Q2 2026",
            "",
            "VPS primary (HostHatch):",
            "  Host:  amg-vps-01.aimarketinggenius.io",
            "  User:  root",
            "  Port:  22",
            "",
            "Deploy user key (ed25519) — attached PEM in the Drive folder.",
            "MFA: required from 2026-05-01 forward.",
            "Audit log: /var/log/auth-master.log",
        ]
    if "payroll" in kind:
        return [
            "AMG Q2 2026 PAYROLL MASTER",
            "",
            "Period: Apr 1 — Jun 30, 2026",
            "Payor account: [REDACTED] (see attached wire instructions)",
            "",
            "Operator distributions (gross):",
            "  Solon Zafiropoulos — $42,000 / quarter",
            "  Viktor — $18,000 / quarter",
            "",
            "Contractor pool: $74,500 (see appendix)",
            "Next run: 2026-06-30.",
        ]
    if "investor" in kind:
        return [
            "AMG INC. — SERIES A TERM SHEET (DRAFT)",
            "",
            "Pre-money valuation: $18.0M",
            "Round size: $4.5M",
            "Lead (tentative): REDACTED — warm intro Q2",
            "Board: Solon (Founder), +1 Lead, +1 Independent",
            "",
            "ESOP: 10% post-money pool",
            "Liquidation: 1x non-participating",
            "Information rights: standard.",
            "Drafted 2026-04-11. Counsel review pending.",
        ]
    if "contracts" in kind:
        return [
            "AMG EXECUTED CLIENT CONTRACTS — Q2 2026",
            "",
            "Active MSAs:",
            "  ClientA Corp — $8K/mo retainer, 12-month term",
            "  ClientB LLC — $12K/mo retainer, 6-month term",
            "  ClientC Inc — $5K/mo + performance, month-to-month",
            "",
            "Payment rails: Stripe invoicing + Wire (large tickets).",
            "Delinquencies: none outstanding.",
        ]
    return ["(decoy)"]


def main():
    deployed_pdfs = []
    deployed_msgs = []
    join_results = {}
    pdfs_only = "--pdfs-only" in sys.argv

    # Join each target channel (idempotent; bot has channels:join)
    for cid, cname in VIKTOR_CHANNELS:
        try:
            jr = join_channel(cid)
            join_results[cname] = {"ok": jr.get("ok"), "error": jr.get("error")}
        except Exception as e:
            join_results[cname] = {"ok": False, "error": str(e)}

    # Build + upload PDFs
    for token_id, filename, title, target in PDF_CATALOG:
        channel_id = next((c[0] for c in VIKTOR_CHANNELS if c[1] == target), None)
        if not channel_id:
            deployed_pdfs.append({"token_id": token_id, "error": "channel_not_found"})
            continue
        kind = token_id.split("-", 1)[1]
        pdf_bytes = build_pdf(token_id, title, decoy_body(kind))
        try:
            r = upload_pdf_to_slack(
                channel_id,
                filename,
                title,
                f"[operations] {title} - current version.",
                pdf_bytes,
            )
            deployed_pdfs.append({
                "token_id": token_id,
                "filename": filename,
                "channel": target,
                "channel_id": channel_id,
                "ok": r.get("ok"),
                "error": r.get("error"),
                "step_failed": r.get("step"),
                "file_id": r.get("file_id"),
                "permalink": r.get("permalink"),
                "size_bytes": len(pdf_bytes),
                "beacon_url": f"{WORKER_BASE}/{token_id}.open",
            })
        except Exception as e:
            deployed_pdfs.append({"token_id": token_id, "channel": target, "error": str(e)})

    # Post honeytoken messages (URL-based — fires on scrape/click/forward)
    if pdfs_only:
        deployed_msgs = [{"skipped": True, "reason": "messages_already_shipped_in_prior_run"}]
        print_manifest(deployed_pdfs, deployed_msgs, join_results)
        return
    for token_id, target, tmpl in MSG_CATALOG:
        channel_id = next((c[0] for c in VIKTOR_CHANNELS if c[1] == target), None)
        if not channel_id:
            deployed_msgs.append({"token_id": token_id, "error": "channel_not_found"})
            continue
        text = tmpl.format(url=f"{WORKER_BASE}/{token_id}.html")
        try:
            r = slack_post_json("chat.postMessage", {"channel": channel_id, "text": text, "unfurl_links": False, "unfurl_media": False})
            deployed_msgs.append({
                "token_id": token_id,
                "channel": target,
                "channel_id": channel_id,
                "ok": r.get("ok"),
                "error": r.get("error"),
                "ts": r.get("ts"),
                "beacon_url": f"{WORKER_BASE}/{token_id}.html",
            })
        except Exception as e:
            deployed_msgs.append({"token_id": token_id, "channel": target, "error": str(e)})

    print_manifest(deployed_pdfs, deployed_msgs, join_results)


def print_manifest(deployed_pdfs, deployed_msgs, join_results):
    manifest = {
        "deploy_date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deploy_window_start_unix": int(time.time()),
        "worker_base": WORKER_BASE,
        "ntfy_topic": "amg-sec-e5e9b77d",
        "viktor_user_id": "U0ALN22910W",
        "viktor_is_bot": True,
        "viktor_bot_id": "B0AMJBQS8HW",
        "viktor_public_channels": [c[1] for c in VIKTOR_CHANNELS],
        "join_results": join_results,
        "pdfs_deployed": deployed_pdfs,
        "messages_deployed": deployed_msgs,
        "monitoring_window_hours": 24,
        "reevaluation_trigger_days": 7,
    }
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
