# Library of Alexandria — Section 4: Emails

**Physical home:** `/opt/amg-titan/solon-corpus/gmail/` (VPS)
**Harvester:** ❌ not yet written — `/opt/amg-titan/solon-corpus/harvest_gmail.py` is the gap. See Thread 1 DR (`plans/PLAN_2026-04-11_sales-inbox-crm-agent.md`) for the Gmail API + Pub/Sub + OAuth flow it will share.
**Current state:** 0 artifacts (blocker: harvester missing + Gmail OAuth consent + GCP project).

---

## What will live here (after harvest)

MP-1 Phase 5 Gmail corpus — every email Solon has sent + received in the AMG sales alias, normalized into the shared MP-1 wrap_artifact schema with subject, sender, recipient, thread id, body, attachments metadata (never attachment bytes), and a `pii_redacted: false` flag.

## Overlap with Thread 1 Sales Inbox Autopilot

The Thread 1 sales inbox agent (`lib/sales_inbox.py`) uses the same Gmail API surface (users.watch + Pub/Sub push notifications + labels + drafts.create). The harvester for Phase 5 will share the OAuth token + Google Cloud project setup with Thread 1. **Build them together** — one OAuth bootstrap, two consumers.

## Privacy scope

- Corpus: SENT + INBOX of the sales alias only (not personal)
- Retention: 90 days on disk in `/opt/amg-titan/solon-corpus/gmail/` (matches Thread 1 retention)
- PII handling: `pii_redacted: false` initially; redaction pass runs in MP-2 SYNTHESIS before any artifact is shared beyond Titan's internal tools
- Never included: attachment bodies, forwarded chains from non-AMG senders, anything marked personal

## Solon action

See NEXT_TASK action items #3 (batched 2FA session — Gmail OAuth consent is the Phase 5 part) + #7 (Thread 1 Gmail OAuth + GCP Pub/Sub).
