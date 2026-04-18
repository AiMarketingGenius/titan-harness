# LUMINA TYPOGRAPHY + LAYOUT HARDENING SPEC
**Date:** 2026-04-17 EOD
**Problem Solon flagged:** Lumina passes pages with weak typography and awkward headline breaks. She isn't critiquing hard enough on font size, font style, hierarchy, or headline layout symmetry.
**Fix:** hoist typography and headline layout into a dedicated scoring category with measurable hard-thresholds Lumina can't hand-wave past.

---

## PART 1 — ROOT CAUSE

Current Lumina rubric (Doc 24) has 6 categories. Typography lives buried inside "Visual Design Prescription Engine" (Doc 15), which is too broad — a page with nice colors and okay spacing can pass while the typography is garbage.

Missing critiques:
- Font size below readable thresholds on body + headlines
- Hierarchy violations (H1 and H2 same visual weight, or H2 larger than H1)
- **Headline line-break asymmetry** — e.g., 8 words on line 1 then 2 words orphaned on line 2
- **Orphan / widow words** in headlines or body paragraphs
- Inconsistent font weights across similar elements
- Line-height too tight (cramped) or too loose (disconnected)
- Mixing more than 2 type families without deliberate contrast
- CTA button text too small to read on mobile

---

## PART 2 — NEW SCORING CATEGORY — TYPOGRAPHY & LAYOUT RHYTHM

Add as a 7th standalone category in Lumina's rubric. Weight: equal to the other 6 (or higher if Solon wants — typography is a trust signal).

### 2.1 — Hard thresholds (auto-fail if violated)

| Check | Desktop threshold | Mobile threshold | Auto-severity if violated |
|---|---|---|---|
| Body text font-size | ≥16px | ≥16px | 🔴 CRITICAL |
| H1 font-size | ≥40px (hero), ≥32px (other) | ≥28px | 🔴 CRITICAL if smaller |
| H2 font-size | ≥28px | ≥22px | 🟡 IMPORTANT |
| H3 font-size | ≥20px | ≥18px | 🟡 IMPORTANT |
| CTA button text | ≥16px | ≥16px | 🔴 CRITICAL |
| Line-height (body) | 1.5-1.7 | 1.5-1.7 | 🟡 IMPORTANT outside range |
| Line-height (headlines) | 1.1-1.3 | 1.1-1.3 | 🟡 IMPORTANT outside range |
| Letter-spacing on uppercase eyebrows | 0.05-0.15em | same | 🟢 OPTIMIZE outside range |
| Max characters per line (body) | 50-75 char | 40-65 char | 🟡 IMPORTANT outside range |
| Font family count on page | ≤2 (body + headline) | same | 🟡 IMPORTANT if 3+ without justification |
| Hierarchy: H1 > H2 > H3 | visual size + weight must descend | same | 🔴 CRITICAL if violated |
| H1 count per page | exactly 1 | same | 🔴 CRITICAL if 0 or 2+ |

### 2.2 — Headline balance check (the Solon-flagged issue)

Specific rule: **no orphaned word at end of multi-line headline.**

Examples of what Lumina must flag as 🔴 CRITICAL:

```
❌ BAD:
"How Chambers of Commerce Increase Non-Dues Revenue With AI
Marketing"
                              ^-- single-word orphan

❌ BAD:
"Generate Non-Dues Revenue, Reduce Board Workload, And Deliver A
Benefit"
                              ^-- orphan

✅ GOOD (balanced):
"How Chambers of Commerce Increase Non-Dues Revenue
With AI-Powered Marketing"

✅ GOOD (symmetrical):
"Generate Non-Dues Revenue Without
Adding Staff or Workload"
```

**Lumina's check:**
- Count words per line of every multi-line headline
- Flag if line 2+ has ≤30% the word count of line 1 (e.g., 8 + 2 = orphan; 5 + 3 = acceptable)
- Flag if a single word sits alone on a line
- Flag if a preposition or article ends a line (dangling "the," "of," "with," "a")
- Recommend: suggest balanced break points OR suggest `text-wrap: balance` CSS + explicit `<br>` breaks
- Severity: 🟡 IMPORTANT for body, 🔴 CRITICAL for H1 and H2

### 2.3 — Orphan and widow check (body copy)

- No single word on the last line of a paragraph (widow)
- No single line at the top of a new column/section from the previous paragraph (orphan)
- Severity: 🟢 OPTIMIZE on body, 🟡 IMPORTANT on hero / above-the-fold

### 2.4 — Hierarchy visual-weight check

Not just font-size — also font-weight + color + spacing must form a clear hierarchy:
- H1 must be visually more dominant than H2 (via size + weight combined)
- Body must have clear weight separation from headlines
- CTAs must have dominant visual weight on page (size + color + contrast)
- If any two hierarchy levels look interchangeable at a glance → 🟡 IMPORTANT flag

### 2.5 — Type-family discipline

- Maximum 2 type families per page unless explicitly brand-approved
- Display + body should have deliberate contrast (not two similar sans-serifs)
- Font weights used across the page: flag if >4 weights (cognitive overload)
- Severity: 🟡 IMPORTANT

### 2.6 — Reading width and density

- Body text line length 50-75 characters (narrower on mobile, wider OK on content pages)
- Paragraph spacing: `margin-bottom` equal to at least 1 × line-height
- Hero section breathing room: headline should have ≥48px vertical space from preceding element

---

## PART 3 — WHAT TO ADD TO LUMINA'S SYSTEM PROMPT

Drop this block directly into Lumina's system instructions, in the "CRITIQUE RULES" or equivalent section:

```
TYPOGRAPHY & LAYOUT RHYTHM (SCORING CATEGORY 7 — EQUAL WEIGHT):

This is a HARD-SCORED category. You cannot pass a page visually if 
typography or headline layout fails these checks. Specific rules:

1. MEASURE FONT SIZES. For every page audited, extract or estimate:
   - H1, H2, H3 font-size (px) on desktop and mobile
   - Body text font-size
   - CTA button text size
   - Line-height on body and headlines
   Compare against thresholds in LUMINA_TYPOGRAPHY_LAYOUT_HARDENING.md. 
   Any violation = auto-severity per the threshold table.

2. CHECK HEADLINE LINE BREAKS. For any multi-line headline:
   - Count words per line
   - Flag orphaned single words at end
   - Flag line 2 with <30% word count of line 1
   - Flag prepositions/articles ending a line
   - RECOMMEND: balanced break points OR text-wrap: balance CSS + 
     explicit <br> tags
   - Severity: 🟡 IMPORTANT body, 🔴 CRITICAL H1/H2

3. CHECK HIERARCHY. Visual weight must descend H1 > H2 > H3 > body.
   If any two levels look interchangeable → 🟡 IMPORTANT flag.

4. CHECK H1 COUNT. Exactly one H1 per page, no exceptions unless 
   explicitly justified. 🔴 CRITICAL if violated.

5. CHECK TYPE FAMILY COUNT. Max 2 per page unless brand-approved.

6. CHECK READING LINE LENGTH. Body text 50-75 characters per line 
   desktop, 40-65 mobile.

7. FLAG ORPHANS AND WIDOWS. Especially in hero sections and 
   above-the-fold content.

OUTPUT FORMAT for typography findings:

Each typography finding must include:
- Specific element (e.g., "H1 on homepage hero")
- Measured current value (e.g., "font-size: 28px mobile, 36px desktop")
- Threshold violated (e.g., "desktop H1 hero should be ≥40px")
- Severity emoji + tier
- Exact fix with target value (e.g., "change to 44px desktop, 32px mobile")
- Revenue/conversion impact estimate where applicable

NO hedging. NO "consider increasing." Say the specific number.

DO NOT PASS a page with a Typography & Layout Rhythm score <7/10 
without flagging every issue and rating the page NEEDS WORK or FAIL 
overall.
```

---

## PART 4 — REFERENCE LIBRARY UPDATE FOR LUMINA KB

Add to Lumina's knowledge base (Doc 15 Visual Design Prescription Engine, or a new Doc 15A if cleaner):

### 4.1 — Proven typography scales (give Lumina specific targets to prescribe)

**Modern SaaS scale (recommended for AMG and most clients):**
- Hero H1: 56-72px desktop / 36-44px mobile
- Section H2: 40-48px desktop / 28-32px mobile
- Sub H3: 24-28px desktop / 20-24px mobile
- Body: 18px desktop / 16px mobile
- Small / captions: 14px desktop / 14px mobile
- Button text: 16-18px both

**Bold editorial scale (content-heavy, blog-forward):**
- Hero H1: 64-96px desktop / 40-56px mobile
- Similar step-down from there

**Compact scale (enterprise B2B, info-dense):**
- Hero H1: 44-56px desktop / 32-36px mobile
- Body: 16-17px desktop / 16px mobile

Lumina prescribes a scale appropriate to brand/vertical, not "just make it bigger."

### 4.2 — Balanced headline writing guidance

When Lumina recommends new headline copy AND layout:
- Target 4-8 words on a single line if possible
- If 2 lines needed, aim for 40/60 to 60/40 word split
- Break on meaningful phrase boundaries, not mid-clause
- Use `text-wrap: balance` where supported (modern browsers)
- Provide explicit `<br>` breakpoint as fallback

### 4.3 — Live-site typography extraction mechanism

When Lumina audits a page, she must extract real measurements:
- For static analysis: request client paste computed styles from DevTools OR Titan (via Stagehand) fetches computed styles from the live URL
- For screenshots only: estimate from visible pixel heights vs. known body copy anchor
- Never assume or guess — measure or flag as ⚠️ UNMEASURED

---

## PART 5 — VERIFICATION HOOK

Add to Lumina's audit deliverable template:

```
TYPOGRAPHY & LAYOUT RHYTHM SCORECARD

Category Score: X/10

Hard-threshold violations found: [count]
- [element]: measured [value] → threshold [value] → severity [tier]
- [element]: measured [value] → threshold [value] → severity [tier]
...

Headline balance issues:
- [element]: [current break pattern] → recommended break: [suggested]

Hierarchy issues:
- [issue description] → fix: [specific]

Overall typography verdict: [OPTIMAL / PASS / NEEDS WORK / FAIL]

Revenue impact estimate for typography fixes: $[X]/month

Implementation time: [hours]
```

If Lumina's audit lacks this scorecard section → dual-grader auto-fails.

---

## PART 6 — WHEN TO APPLY THIS TO AMG SITE

For the weekend sprint:
- Titan extracts AMG live-site current typography values (per Addendum #5 brand token extraction)
- All new AMG pages shipped this weekend get Typography & Layout Rhythm scorecard review by Lumina
- Any pages shipping with a score <8/10 must fix before ship — not after
- Solon sees the scorecard in the Sunday 6pm handoff note alongside dual-engine scores

For going forward:
- Lumina's rubric updates in her Claude project KB (Titan via Stagehand)
- System prompt updates reference this new category
- Every CRO audit deliverable from this point includes Typography & Layout Rhythm as its own scored section

---

**End of file. Shipping for Titan weekend boot absorption + Lumina KB update.**
