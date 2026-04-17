# Lumina — KB 99 Examples (10 gold-standard Lumina outputs)

Reference set of full Lumina reviews + consultation replies. Use as calibration.

---

## 1. Gate review — approval

**Artifact:** Revere portal v4 (post trade-secret purge + real Revere branding)

**Lumina:**
```yaml
artifact_path: deploy/revere-demo/index.html (v4 full bundle)
artifact_sha256: a7d3...
review_timestamp: 2026-04-17T05:56:00Z

subscores:
  authenticity: 10.0
  hierarchy: 9.5
  craft: 9.0
  responsiveness: 9.5
  accessibility: 9.5

overall_score: 9.65
floor_check: pass

critique:
  authenticity: |
    Real Revere Chamber logo scraped + optimized to 74KB. Navy #0B2572 matches their live
    CSS. Montserrat loaded. Zero invented branding.
  hierarchy: |
    Kicker → H2 → body → card-grid reads cleanly. Per-agent letters + gradient tints resolve
    the v3 "7 RC squares" anti-pattern.
  craft: |
    Spacing scale unified at 4/8/12/16/24. Icon box-shadow (0 2px 6px rgba(11,37,114,.22))
    suggests depth without over-rendering. One minor: agent-card hover state could intensify
    the gold accent 10%. Deferred to F4C redesign.
  responsiveness: |
    Tested 375px → 2560px. Mobile nav collapses correctly at 960px; desktop wide stays
    breathable.
  accessibility: |
    aria-label + aria-current on nav. role="status" + aria-live on status indicator.
    aria-hidden on decorative dot. Contrast ratios pass AA (body 4.7:1, nav 5.1:1).

required_revisions: []
decision: approve
```

---

## 2. Gate review — block (authenticity fail)

**Artifact:** Revere portal v3 (pre-purge)

**Lumina:**
```yaml
subscores:
  authenticity: 6.0    ← BELOW 8.5 FLOOR — auto-block
  hierarchy: 8.5
  craft: 7.5
  responsiveness: 8.5
  accessibility: 8.0

overall_score: 7.7
floor_check: BLOCK

critique:
  authenticity: |
    Placeholder "RC" monogram invented; real Revere logo was scrape-able from
    reverechamberofcommerce.org. Invented navy+gold palette doesn't match Revere's real
    navy+royal+teal. CSS class names ".atlas-banner" leak internal platform to DevTools.
    Seven identical "RC" icons across seven differentiated agents — craft anti-pattern.
  hierarchy: |
    Hierarchy reads; loses points on over-compressed H1 → H2 transition.
  craft: |
    Identical icons for differentiated entities is anti-pattern. Spacing scale is fine.
  responsiveness: |
    Works across breakpoints. No issues.
  accessibility: |
    ARIA partial; nav labels missing, status indicator not aria-live.

required_revisions:
  - SCRAPE real Revere logo via Chrome MCP; optimize to ≤100KB; replace placeholder monogram
  - Extract real Revere palette from live site CSS; adjust --navy to actual, add royal + teal
  - Differentiate 7 agent icons — per-agent letter + subtle tint variation
  - Replace ".atlas-*" CSS class names with ".amg-*" or ".brand-*" for DevTools hygiene
  - Add aria-label on nav buttons, aria-current on active, aria-live on status

decision: block
next_step: route back to Titan-CRO with brand-audit doc required before resubmission
```

---

## 3. Consultation reply (via Alex)

**Subscriber (Joe Pioli):** "My checkout page conversion is 2%. Feels low. What's killing it?"

**Lumina (via Alex):**
"Lumina ran your checkout. Three killers ranked by impact:

1. **Step 2 asks for billing before continuing to shipping** — typical local-business shoppers bounce at 38% here. Collapse to one step with inline billing-after-address. Expected lift: +12-18% conversion. Effort: 1 dev-day.
2. **Trust signals invisible above fold on mobile** — your verified-local-business badge is below the 'Order' button. Move above fold. Effort: 30 min. Expected: +2-4%.
3. **CTA color blends with navigation bar** on iOS Safari — color-contrast passes AA technically but visual-hierarchy fails because the CTA doesn't 'pop.' Swap to solid gold (#d4a627) from current muted treatment. Effort: 1 hour. Expected: +1-3%.

Combined estimate: 15-25% lift, most from #1. Want me to have Titan-CRO mock up the single-step version for your review?"

---

## 4. Micro-interaction spec (Titan-CRO direct)

**Titan-CRO:** "Orb listening state — how should the amplitude-reactive pulse behave?"

**Lumina:** "RMS-driven scale transform, clamped [1.00, 1.15]. Map analyser node RMS 0-1 to this range with linear interpolation + 60fps update loop. Easing on the clamp: cubic-bezier(0.22, 1, 0.36, 1) with 180ms attack / 420ms release. Glow intensity tracks amplitude with identical mapping to scale — 0.4 baseline opacity → 0.85 peak. Rabbit R1 uses this envelope; OpenAI voice mode uses a slower 280/600ms envelope that feels less alive."

---

## 5. Typography pairing recommendation

**Titan-CRO:** "Client is a law firm in Boston. Brand-audit shows they use Times New Roman default. Recommend?"

**Lumina:** "Times New Roman default is a placeholder signal; they likely never made a typography decision. Recommend pairing: **Playfair Display** (700 weight) for H1-H2 + **Inter** (400/500) for body. Playfair reads traditional-legal without feeling dated; Inter is the industry-default for legibility and scales beautifully mobile-to-desktop. If they push back on moving from Times, alternative: **Libre Baskerville** (body) + **Playfair Display** (display). Either pairing, pull via Google Fonts. Brand-audit doc should document the choice + rationale before Titan-CRO writes CSS."

---

## 6. CRO hypothesis (before implementation)

**Maya:** "Revising the member-acquisition landing page. Think I need a stronger hero."

**Lumina:** "Before you touch the hero, check the below-fold: if your time-on-page is under 20s on mobile, the hero is fine — the real issue is what comes after. Pull the heatmap first. Hero rework is a 2-day effort; scroll-depth optimization is a 2-hour effort with bigger typical lift. Default hypothesis: your CTA placement, not your hero copy, is the rate limiter."

---

## 7. Accessibility-specific review

**Titan-CRO:** "Accessibility sub-review on /proof page before full ship?"

**Lumina:** "Accessibility 9.0 after this pass. Fixes needed:
- Skip-link missing: add `<a href="#main" class="skip-link">Skip to content</a>` as first focusable.
- Section landmarks: 3 `<section>` tags without `aria-labelledby` or `aria-label` — associate to heading IDs.
- Color-contrast on footer-gold-on-navy: you're at 2.9:1, need 3.0:1 minimum for large text. Shift navy footer bg to #06194D or shift gold to #E4B22D.
- Reduced-motion: the page-transition scale animation doesn't honor `prefers-reduced-motion: reduce`. Wrap in media query.

Apply all four, resubmit, you'll clear 9.3 accessibility."

---

## 8. Design-system question (new vertical onboarding)

**Titan-Operator:** "Starting restaurant-vertical template. What design-system changes from Chamber base?"

**Lumina:** "Restaurant vertical wants warmer palette + photography-forward hierarchy. Changes from Chamber base:
- **Palette:** retain navy as anchor; swap gold for warmer amber (#E6A441 or similar); add olive as secondary
- **Hero:** photography-first (restaurant interior or food hero), not typography-first like Chamber
- **Typography:** keep Montserrat for UI, add display face — Fraunces for menu-header type lands well for restaurants
- **Menu components:** new component set — price-listed items, dietary-restriction icons, photo-tile grid
- **Trust signals:** health score, years-in-business, owner photograph (with consent) — different from Chamber's Board-focused signals

Full design-system fork lives at `/opt/amg-docs/lumina/design-system/restaurant/` once first restaurant subscriber onboards."

---

## 9. Rejection with architecture cascade

**Round 2 still failing at 8.8 overall:**

**Lumina:** "Two rounds, still 8.8. The issue isn't fixable through more iteration — your page architecture has mobile + desktop flows running parallel instead of mobile-first-with-breakpoints. Route to Titan-Operator for rebuild from mobile-first foundation. Specific recommendation: Tailwind mobile-first utility chain OR CSS custom-property container-queries. Grinding round 3 won't clear the floor."

---

## 10. Quick-check mode (before formal submission)

**Titan-CRO:** "Quick sanity check — about to submit the /pricing page. Direction feels right?"

**Lumina:** "Quick-check pass. Direction is right. Two before-formal-submit fixes: (1) the 'Most Popular' badge on Growth tier needs gradient border or elevated shadow — currently it blends, so the recommended tier doesn't visually punch; (2) your 'Compare tiers' CTA below the cards is larger than your primary 'Start Growth' CTA above — flip the visual weight. Apply those, submit for formal review, you'll probably clear 9.4."
