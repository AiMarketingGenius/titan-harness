# Telnyx Toll-Free Verification — Paste-Ready Packet

**Status:** Outbound SMS to +16177970402 returning `delivery_failed` (error 40329 "Tollfree number is not verified"). Submit this form, wait 1-3 business days for Telnyx approval, then SMS bridge goes live both directions.

**Portal:** https://portal.telnyx.com/#/messaging/profiles/40019dca-c961-486a-a453-42f82d1b5a41

Click into the Messaging Profile → Toll-Free Verification tab → Start Verification.

---

## Form Fields (paste / fill)

### Business Information

| Field | Value |
|---|---|
| Business Name | **[FILL — legal business name on file with IRS]** |
| Corporate Website | https://aimarketinggenius.io |
| Business Address (street) | **[FILL]** |
| Business Address (city) | **[FILL]** |
| Business Address (state) | **[FILL]** |
| Business Address (ZIP) | **[FILL]** |
| Business Address (country) | United States |
| Business Contact First Name | Solon |
| Business Contact Last Name | Zafiropoulos |
| Business Contact Email | ads@drseo.io |
| Business Contact Phone | +1-617-797-0402 |
| EIN / Tax ID | **[FILL — only if Telnyx prompts]** |

### Use Case

**Use Case Categories** (check both):
- [x] Account Notification
- [x] 2FA / Authentication

**Use Case Description** (paste verbatim):

```
Internal operational alerting and 2FA for a single, owner-operated business.
This number sends operational alerts and authentication codes EXCLUSIVELY to
the business owner, Solon Zafiropoulos, on his personal phone +1-617-797-0402.

There are no third-party message recipients. The recipient IS the business
operator, who has explicitly opted in by procuring this Telnyx infrastructure
specifically for personal operational alerting from his own backend systems
(server health, dispatch confirmations, security incident notifications, daily
operations digests).

Volume is low (1-25 messages/day, 100-500/month). All messages are transactional
or operational, never marketing.
```

### Opt-In Workflow

**Opt-In Type:** Owner-Operated / B2B Internal / Single-Recipient

**Opt-In Language** (paste verbatim):

```
The recipient (+1-617-797-0402) is the sole owner and operator of the business
holding this messaging profile. Consent was established at the time the owner
procured this Telnyx number and configured it to deliver alerts to his own
phone. Opt-out is available at any time by replying STOP, in compliance with
TCPA and CTIA guidelines.
```

**Opt-In Image / Screenshot:** Not applicable (single-recipient internal alerting, not consumer-facing form).

### Sample Messages

Paste all three:

1.
```
Hercules audit complete. AIMG ship status: GREEN across 5/6 platforms. Reply DETAIL for breakdown or PAUSE to halt dispatches.
```

2.
```
P0 alert: Cerberus detected anomalous login attempt on amg-staging from 198.51.100.42. Reply 1 to acknowledge or BLOCK to lockdown.
```

3.
```
Daily digest 2026-04-27: 47 dispatches (44 PASS, 2 PATCH, 1 REJECT). 0 escalations. API spend MTD: $43/$250 budget. All systems green.
```

### Volume Estimate

| Field | Value |
|---|---|
| Daily messages (typical) | 1-5 |
| Daily messages (peak) | 25 |
| Monthly total estimate | 100-500 |
| Production phone number | +1-888-437-2001 |
| Estimated launch date | 2026-04-26 (already provisioned, awaiting verification) |

---

## What to do (5 minutes)

1. Open the portal link above.
2. Fill the **[FILL]** fields (business name, address, EIN if asked) — should take 90 seconds.
3. Paste the use case + opt-in + sample messages from this packet verbatim.
4. Submit.
5. Telnyx reviews in 1-3 business days. Approval → outbound SMS unblocks automatically.

Until approved:
- Hercules → Solon notifications fall back to macOS notifications via `mercury_mcp_notifier` + `~/AMG/hercules-inbox/` markdown drops.
- Inbound SMS (Solon → Hercules) still works fully — webhook is live on VPS port 5681.

---

## Behind the scenes (no action needed)

- **Toll-free number:** +1-888-437-2001 (purchased + assigned to Messaging Profile id `40019dca-c961-486a-a453-42f82d1b5a41`)
- **Webhook URL configured:** https://n8n.aimarketinggenius.io/webhook/telnyx-inbound
- **Inbound systemd unit:** `amg-telnyx-inbound.service` (live on VPS, port 5681)
- **Outbound script:** `/opt/amg-monitor/telnyx_send.py` (ready, gated on verification)
- **Failed test SMS msg_id:** `40319dca-c9e9-43d9-89d3-da727490ca22` (sent 2026-04-26T17:15:23Z, status `delivery_failed`, Telnyx error 40329)

— Titan, 2026-04-26
