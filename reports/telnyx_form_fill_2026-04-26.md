# Telnyx Toll-Free Verification — FILL & SUBMIT

**Time required:** 5 minutes. 3 fields YOU type, everything else copy-paste from this doc.

**Portal URL** (click directly):
https://portal.telnyx.com/#/messaging/profiles/40019dca-c961-486a-a453-42f82d1b5a41

In the Telnyx portal: click into the Messaging Profile → **Toll-Free Verification** tab → **Start Verification**.

---

## ⚠ ONLY 3 FIELDS YOU TYPE (the rest is copy-paste below)

| # | Field | What to type |
|---|---|---|
| 1 | **Legal Business Name** | Your registered business legal name (e.g., "AI Marketing Genius LLC" or "Solon Zafiropoulos" if sole prop) |
| 2 | **Business Address** | Your business address — street, city, state, ZIP |
| 3 | **EIN / Tax ID** | Only if Telnyx asks for it (often optional for low-volume profiles). Your IRS-issued EIN, or SSN if sole prop. |

That's it. Every other field is pre-filled below — just copy-paste.

---

## ✅ ALL OTHER FIELDS (copy-paste verbatim)

### Business Information section

| Field | Value (copy-paste) |
|---|---|
| Corporate Website | `https://aimarketinggenius.io` |
| Business Address — Country | `United States` |
| Business Contact First Name | `Solon` |
| Business Contact Last Name | `Zafiropoulos` |
| Business Contact Email | `ads@drseo.io` |
| Business Contact Phone | `+1-617-797-0402` |

### Use Case section

**Use Case Categories** — check both boxes:
- [x] Account Notification
- [x] 2FA / Authentication

**Use Case Description** — paste this verbatim:

```
Internal operational alerting and 2FA for a single, owner-operated business.
This number sends operational alerts and authentication codes EXCLUSIVELY to
the business owner, Solon Zafiropoulos, on his personal phone +1-617-797-0402.

There are no third-party message recipients. The recipient IS the business
operator, who has explicitly opted in by procuring this Telnyx infrastructure
specifically for personal operational alerting from his own backend systems
(server health monitoring, dispatch confirmations, security incident alerts,
daily operations digests, AI agent factory escalations).

Volume is low (1-25 messages/day, 100-500/month). All messages are transactional
or operational in nature, never marketing.
```

### Opt-In Workflow section

**Opt-In Type:** `Owner-Operated / B2B Internal / Single-Recipient`

**Opt-In Language** — paste this verbatim:

```
The recipient (+1-617-797-0402) is the sole owner and operator of the business
holding this messaging profile. Consent was established at the time the owner
procured this Telnyx number and configured it to deliver alerts to his own
phone. Opt-out is available at any time by replying STOP, in compliance with
TCPA and CTIA guidelines.
```

**Opt-In Image / Screenshot:** Skip — not applicable (single-recipient internal alerting, not consumer-facing form).

### Sample Messages section

Paste each in a separate sample-message slot:

**Sample 1:**
```
Hercules audit complete. AIMG ship status: GREEN across 5/6 platforms. Reply DETAIL for breakdown or PAUSE to halt dispatches.
```

**Sample 2:**
```
P0 alert: Cerberus detected anomalous login attempt on amg-staging from 198.51.100.42. Reply 1 to acknowledge or BLOCK to lockdown.
```

**Sample 3:**
```
Daily digest 2026-04-27: 47 dispatches (44 PASS, 2 PATCH, 1 REJECT). 0 escalations. API spend MTD: $43/$250 budget. All systems green.
```

### Volume Estimate section

| Field | Value |
|---|---|
| Daily messages (typical) | `1-5` |
| Daily messages (peak) | `25` |
| Monthly total estimate | `100-500` |
| Production phone number | `+1-888-437-2001` |
| Estimated launch date | `2026-04-26` (today; already provisioned) |

---

## 📋 What happens after you submit

1. Telnyx reviews 1-3 business days (usually faster for low-volume tollfree).
2. You'll get an email at ads@drseo.io when verified.
3. The moment it clears: outbound SMS to your iPhone +16177970402 starts working immediately. No code change needed on our side — the daemon is already polling.
4. First test SMS will arrive within 30 seconds of you replying any text to +1-888-437-2001.

---

## 🔧 Behind the scenes (no action needed)

- **Toll-free number:** +1-888-437-2001 (purchased + assigned to Messaging Profile id `40019dca-c961-486a-a453-42f82d1b5a41`)
- **Webhook URL configured:** https://n8n.aimarketinggenius.io/webhook/telnyx-inbound
- **Inbound systemd unit:** `amg-telnyx-inbound.service` (live on VPS port 5681)
- **Outbound script:** `scripts/telnyx_send.py` (ready, gated on verification)
- **Failed test SMS msg_id from earlier:** `40319dca-c9e9-43d9-89d3-da727490ca22` (sent 2026-04-26T17:15:23Z, status `delivery_failed`, Telnyx error 40329 — that's what this form fixes)

---

— Titan, 2026-04-26
