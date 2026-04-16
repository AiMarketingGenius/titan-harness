# Lead Qualifying Questions — Levar / JDJ Investment Properties

**Purpose:** The core seller-intake question set that runs through the website form, the chatbot, the SMS intake sequence, and the AI voice callback. Same 9 questions everywhere so data is consistent across channels.

**Audience:** Levar reviews + edits. Once approved, Titan codes it into the chatbot flow, the SMS nurture, the GHL form, and the voice-AI qualification script (Phase B).

**Status:** Draft v1 — awaiting Levar's edits at the 1pm kickoff or Tuesday standing call.

---

## The 9 Questions

Every inbound lead — whether they come via form, chat, or voice — gets these 9. Order matters: the earliest disqualifiers go first so we don't waste anyone's time.

### 1. Are you the legal owner of the property?
- **Yes / Yes, jointly with a spouse or co-owner / No (tenant, family member, other)**
- **Rejects:** renters, unauthorized parties. Hard disqualifier.

### 2. Where is the property located?
- **Free text: City, State, Zip**
- **Rejects:** anything outside MA (primary), NC, SC, AR (expansion markets). Polite "we don't currently buy in that area" response with referral-out option.

### 3. What's your mortgage situation?
- **Paid off / Current on payments / 1–3 months behind / 4+ months behind / In active foreclosure / Not sure**
- **Informs:** urgency + offer structure. "Active foreclosure" flags a priority call within the hour.

### 4. What's your reason for selling?
- **Inherited property / Divorce or separation / Job relocation / Tired landlord / Behind on payments / Condition of property / Downsizing / Just want out / Other**
- **Informs:** which angle the call opens with. Levar's team handles a divorce seller very differently than an inherited-property seller.

### 5. What's the condition of the house?
- **Move-in ready / Cosmetic updates needed / Major repairs needed / Uninhabitable / Don't know**
- **Informs:** initial offer range. Gives Levar signal before he drives by.

### 6. What's your timeline to sell?
- **This week / Within 30 days / 30–60 days / 60–90 days / Flexible**
- **Informs:** which path to pitch (cash close vs delayed close). Also routes urgency — "this week" gets a same-day callback.

### 7. Are you currently listed with a real estate agent?
- **Yes / No / Contract just expired**
- **Informs:** ethics check. If yes, we ask them to consult their agent first or wait until contract expires. Levar won't interfere with active listings.

### 8. What's the best way to reach you?
- **Phone / Text / Email / All**
- **Informs:** routing. Phone-preferred sellers get the voice callback first. Text-preferred get SMS.

### 9. What's your name, phone number, and email?
- **Full name / Phone / Email**
- **Standard contact capture, last so we don't scare anyone off early.**

---

## Automatic Disqualifiers (no callback, respectful decline)

- Not the legal owner (Q1 = No)
- Outside MA/NC/SC/AR (Q2 outside target markets)
- Currently under contract with an agent with active listing (Q7 = Yes)

**Decline language (all channels):**
> *"Thanks for reaching out. Based on what you shared, we're not the right fit for this property right now. If your situation changes — your listing expires, the property transfers into your name, or you're looking in our target markets — please reach out again."*

---

## Automatic Priority Flags (escalate immediately)

- Q3 = "In active foreclosure" → SMS to Levar within 60 sec: "HOT LEAD: foreclosure in [city]"
- Q6 = "This week" → SMS to Levar within 60 sec: "HOT LEAD: needs to close this week, [city]"
- Q4 = "Divorce" + Q6 ≤ 30 days → SMS to Levar within 60 sec: "TIME-SENSITIVE: divorce + fast timeline"

---

## Levar's custom rules (TO BE FILLED IN BY LEVAR)

Please edit and send back:

**Zip codes to skip within target markets:**
_[Levar fills in]_

**Minimum equity / loan-to-value threshold:**
_[Levar fills in]_

**Property types we don't touch:**
- [ ] Condos
- [ ] Mobile homes
- [ ] Multi-family 5+ units
- [ ] Commercial
- [ ] Vacant land
- [ ] Other: _____

**Dollar range of deals we pursue:**
- Minimum home value (ARV): $_____
- Maximum home value (ARV): $_____

**Situations we do NOT handle:**
- [ ] Active litigation on the property
- [ ] Title issues / liens we can't resolve at closing
- [ ] Owner-occupied with seller not moving out (leaseback situations)
- [ ] Other: _____

**Any other hard rules:**
_[Levar fills in]_

---

## Field mapping (for Titan — post-approval)

Each answer maps to a GHL custom field + AMG Supabase lead record:
- Q1 → `legal_owner` (enum)
- Q2 → `property_city`, `property_state`, `property_zip` (text)
- Q3 → `mortgage_status` (enum)
- Q4 → `sale_reason` (enum)
- Q5 → `property_condition` (enum)
- Q6 → `timeline` (enum)
- Q7 → `currently_listed` (enum)
- Q8 → `preferred_contact` (enum)
- Q9 → `contact_name`, `contact_phone`, `contact_email`

Auto-mirrored from AMG Supabase → Levar's GHL via webhook on insert.

---

## Next step

Levar edits in red, sends back, Titan locks into the intake flow. Target live: Week 2 Day 10.
