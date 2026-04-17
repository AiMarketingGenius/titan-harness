# Nadia — KB 05 Reference Data

## Encyclopedia v1.3

Outbound bundled in Growth + Pro tiers (v1.3 §4). Chamber outreach + national partner-program outreach scoped separately (v1.3 §13-14).

## client_facts

Per-subscriber outbound context:
- `outbound_icp` — ICP definition (role, company-size, geography, industry)
- `outbound_approved_copy_categories` — Standing Approval categories per subscriber
- `outbound_sender_domain` — warmed sender, SPF/DKIM/DMARC verified
- `outbound_crm_endpoint` — where replies get logged
- `outbound_opt_out_list` — authoritative opt-out (merged across all campaigns)
- `outbound_frequency_cap` — max touches per prospect, per quarter
- `outbound_voice_samples` — subscriber voice for personalized touches

## Outbound channels + benchmarks (directional)

### Cold email
- Industry reply-rate benchmarks (B2B):
  - Generic / spray: 0.5-2%
  - Well-targeted ICP + personalization: 5-12%
  - Highly researched Tier-1 prospects: 15-30%
- Meeting-book rate typically 10-25% of replies
- Frequency cap: max 5 touches per prospect per sequence; 90-day cooldown before re-sequencing
- Sender reputation critical; single compromised sender kills deliverability for weeks

### LinkedIn outbound
- Connection-request acceptance: 20-40% for well-targeted
- Reply-after-accept: 5-15%
- Message-back rate on cold 1st-degree: 2-8%
- LinkedIn's own TOS: avoid automation that simulates human behavior (Sales Navigator is platform-owned, OK; 3rd-party automation flagged + accounts banned)

### Phone / voicemail
- Connect rate: 3-8% for cold B2B
- Voicemail drop + return rate: 1-4%
- TCPA restrictions on SMS; phone cold-calling governed by state laws + DNC registries

### Direct mail (rare)
- Open-rate 60-90% (physical mail still performs)
- Reply-rate 1-5% typical
- High cost per contact ($3-20+), reserve for high-ACV targets only

### Conference / event outbound
- Pre-event research + scheduled 1:1 meetings at events: highest-conversion channel
- Post-event follow-up within 48 hours; drops sharply after

## Sequence templates (starting patterns)

### 5-touch cold email sequence
- **Touch 1 — Hook** (Day 1): specific-research opener + small ask + single CTA. ≤100 words.
- **Touch 2 — Value** (Day 8): new angle + case-study-level-of-proof + same ask. ≤120 words.
- **Touch 3 — Break-up** (Day 13): acknowledge non-response + easy yes/no/later + polite close. ≤80 words.
- **Touch 4 — Pattern-interrupt** (Day 27): different channel (email → LinkedIn, or short personal note). ≤60 words.
- **Touch 5 — Final** (Day 58): new context (time-sensitive event, new offering, quarter-end) + final ask. ≤80 words.

### 3-touch LinkedIn sequence
- **Touch 1:** Connection request with personal note (name/company reference).
- **Touch 2:** Post-accept thank + one-line value-prop + single question. ≤300 chars.
- **Touch 3:** Short post-engagement follow-up (if they interacted with content). ≤200 chars.

### Warm-intro request sequence
- **Touch 1:** Direct ask to mutual connection, specific context, give-them-an-easy-out. ≤80 words.
- **Touch 2:** Thank if intro happens; gracious if it doesn't.

## CAN-SPAM compliance quick-ref

- Unsubscribe link on every commercial email
- Honest "From" name (person or business; not deceptive)
- Honest subject line (no "RE:" where no conversation, no "URGENT" unless it is)
- Physical business address in footer
- Opt-out honored within 10 business days (industry best: immediate)
- Cannot sell or transfer email addresses of opted-out users

## TCPA quick-ref (SMS)

- Explicit prior consent required (TCPA is stricter than CAN-SPAM)
- "Reply STOP" on every message
- Time-of-day restrictions (generally 8am-9pm local)
- DNC list respected
- Penalties real: $500-1500 per violation

## GDPR quick-ref (if targeting EU)

- Legal basis required (consent / legitimate interest / contract)
- Data minimization (only collect what's needed)
- Right to access + erasure + portability + objection
- DPA (Data Processing Agreement) with vendors
- 72-hour breach notification

## Deliverability infrastructure

- **SPF** — sender-policy-framework DNS record; anti-spoofing
- **DKIM** — DomainKeys Identified Mail; cryptographic signing
- **DMARC** — policy wrapper; report-only → quarantine → reject progression
- **Sender-reputation monitoring** — tools like MxToolbox, Postmark monitor; domain reputation tracked by Google/Outlook
- **Domain warm-up** — gradual volume ramp (50/day → 200/day over 30 days for new sending domain)
- **Separate domains for outbound vs transactional** — sends from nadia-outbound.joespizza.com not orders.joespizza.com

## Industry-standard outbound tool names (allowed when subscriber asks)

- Apollo, ZoomInfo, Hunter.io, LinkedIn Sales Navigator (prospect research)
- Lemlist, Instantly, Mailshake, Outreach, Salesloft, Smartlead (sequencers)
- PhantomBuster (LinkedIn automation — caution re: TOS)
- Calendly (meeting booking)

Name these when subscribers ask; don't volunteer internal AMG automation.

## Compliance audit per sequence pre-launch

- [ ] Target list consent-verified (opt-in source documented)
- [ ] Sender identity honest
- [ ] All subject lines non-deceptive
- [ ] Opt-out link on every touch
- [ ] Physical address in footer
- [ ] Frequency-cap enforced
- [ ] 90-day cooldown honored
- [ ] Opt-out list synchronized across all sender domains
- [ ] Subscriber approval of prospect list + copy + sequence logged
