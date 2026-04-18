# Lumina — KB 08 Typography Reference Anchors

**Status:** LOCKED 2026-04-17 per Solon directive — added after a gap where Lumina graded the AMG Chamber CTA band against the prompt spec (small font sizes, low letter-spacing, wrong weights) instead of against the AI Memory Guard live-site benchmark. Solon's eyes caught it; Lumina didn't. This KB closes that gap permanently.

**Rule supersedes:** any previous "match the prompt spec" pattern. Lumina's floor is now: **match or exceed the AI Memory Guard live-site typography system on every AMG surface. Prompt specs below AIMG typographic craft fail authenticity AND craft scoring, regardless of whether Lovable or whoever implemented the spec correctly.**

---

## 1. The rule

**Before approving any client-facing AMG visual artifact, Lumina MUST:**

1. Open the reference site (AI Memory Guard for AMG / Linear / Stripe / Vercel for other contexts) and measure actual computed typography values — font family, size, weight, letter-spacing, line-height, color.
2. Compare the artifact's values against those measurements.
3. If the artifact's typography reads smaller, thinner, or flatter than the reference, FLAG — regardless of whether the artifact matches the prompt spec.
4. The prompt spec is an input. The reference library is the benchmark. **When they conflict, the reference wins.**

A failure here is a dimension-craft + dimension-authenticity double-hit:
- **Authenticity** fails because AMG surfaces should feel as premium as AIMG (they're the same company's brand family)
- **Craft** fails because professional web design grammar (weight, tracking, optical tightening) matters as much as point size

---

## 2. AI Memory Guard live-site typography system (measured 2026-04-17T22:00Z via Chrome MCP)

This is the canonical AMG quality benchmark until Solon explicitly supersedes it.

### 2.1 Font family
- Primary: **Inter** (geometric humanist sans, strong at all sizes)
- Fallback stack: `Inter, -apple-system, "system-ui", "Segoe UI", sans-serif`

### 2.2 Headings
| Element | Size | Weight | Line-height | Letter-spacing |
|---|---|---|---|---|
| H1 (hero) | **62px** | **800** | 66.96px (1.08) | **-1.55px** (optical tighten) |
| H2 (section headers) | **44px** | **800** | 50.6px (1.15) | **-0.88px** |
| H2 (closing / hero-adjacent) | **48px** | **800** | 52.8px (1.10) | **-1.2px** |
| H3 (feature titles) | **19px** | **700** | 29.45px (1.55) | normal |

### 2.3 Body
| Element | Size | Weight | Line-height |
|---|---|---|---|
| Body baseline | **16px** | 400 | 24.8px (1.55) |
| Lead / sub-headline | **18px** | 400 | 28.8px (1.6) |
| Feature description | **16px** | 400 | 25.6px (1.60) |
| Fine print / meta | **13–14px** | 400 | 20.15–22.4px |

### 2.4 Eyebrow labels (uppercase kickers)
| Size | Weight | Letter-spacing | Color |
|---|---|---|---|
| **11–12px** | **700** | **2.16px (18% of font-size)** | bright accent on dark |

**Critical rule:** eyebrows at 11–12px work ONLY with letter-spacing ≥ 15% and weight ≥ 700. Below either threshold → reads amateur. Spec `letter-spacing: 0.15em` to `0.18em` for anything uppercase at 11–14px.

### 2.5 Buttons
| Type | Size | Weight | Padding | Radius |
|---|---|---|---|---|
| Primary CTA | **14–15px** | **700** | 11–13px × 18–24px | **10px** |
| Secondary CTA | **14.5px** | 600 | 13px × 24px | 10px |
| Small utility | **14px** | 700 | 10px × 18px | 8px |

**Critical rule:** button text at 14–16px reads premium ONLY with weight ≥ 700. Weight 600 at these sizes feels like body-text-on-a-button. Bump weight to 700 before increasing size.

### 2.6 Color discipline (on dark navy bg #0a0f1c)
- Primary text: **#F5F7FB** (bright near-white — brighter than AMG's #FFFFFF? Same visual weight.)
- Secondary text: `rgba(245,247,251,0.78)` — soft but still legible
- Meta text: `rgba(245,247,251,0.55)` — truly muted
- Accent: saturated brand primary at full opacity only on primary CTAs, 0.1 overlay for chips

---

## 3. AMG chamber CTA band — FAILED against this benchmark (2026-04-17)

**Chamber band spec I wrote + approved:**
- Eyebrow: 12px / weight 600 / letter-spacing 0.96px (8%) ❌
- H2: 42px / weight 700 / no letter-spacing correction ❌
- Sub-headline: 18px / weight 400 ✅
- Button: 16px / weight 600 / padding 14×28 ❌
- Trust row: 14px / weight 400 ❌ (should be ≥15px for a hero-adjacent trust row)

**Why it failed:**
- Eyebrow tracking half what AIMG uses (0.96px vs 2.16px) — reads amateur
- H2 weight 700 instead of 800 — lacks confidence
- H2 no optical letter-spacing — flat
- Button weight 600 at 16px — body-text-on-a-button feel, not CTA
- Trust row 14px not sufficient on hero-adjacent placement

**Corrected spec (matches AIMG typographic craft):**
- Eyebrow: **14px / weight 700 / letter-spacing 2.1px (15%) / uppercase**
- H2: **46px / weight 800 / line-height 1.15 / letter-spacing -0.92px**
- Sub-headline: **20px / weight 400 / line-height 1.55**
- Button: **16px / weight 700 / padding 16×32 / radius 10px**
- Trust row: **16px / weight 400 / line-height 1.55**

---

## 4. Lumina's updated review protocol (mandatory on every review)

### Step 1 — Reference measurement
Before scoring, open the reference site (AI Memory Guard for AMG surfaces) and pull computed styles for:
- H1 / H2 / H3 sizes + weights + letter-spacing + line-height
- Body + sub-headline sizes
- Eyebrow letter-spacing (this is where most specs fail)
- Button sizes + weights + padding + radius
- Color discipline

Log these in the review YAML under `reference_measurements`.

### Step 2 — Comparison table
In the critique, include a table comparing each element's measured value vs. the artifact's measured value. Flag any delta.

### Step 3 — Decision rule
- **Artifact matches or exceeds reference on every element** → authenticity + craft both ≥9.3
- **Any element below reference by >10% (size) or >20% (letter-spacing / weight)** → craft dimension caps at 8.5, triggers revise
- **Multiple elements below** → authenticity dimension also caps at 9.0 (reads as lesser brand)

### Step 4 — Never rubber-stamp the prompt spec
If the prompt spec itself is below reference, flag THE SPEC, not "but the implementation matches the spec." Send back to Titan-CRO (or whoever wrote the prompt) with the delta callout.

---

## 5. AMG typography system decision (pending Solon)

**Current state:** AMG uses DM Sans site-wide (verified 2026-04-17 live).
**AI Memory Guard:** uses Inter.

These are different typefaces. At the same point size + weight + letter-spacing, Inter renders denser + more authoritative than DM Sans.

**Open question for Solon:** should AMG switch to Inter site-wide to match AIMG's typographic craft? Or keep DM Sans and apply AIMG's grammar (weight + tracking + optical tightening) to DM Sans?

**Default until Solon decides:** keep DM Sans site-wide, apply AIMG's typographic grammar (heavier weights, tighter optical letter-spacing, proper eyebrow tracking) to every AMG surface. New sections use the corrected spec in §3.

If Solon wants the Inter switch, that's a separate brand-system PR — not a one-section fix.

---

## 6. Changelog

- **2026-04-17** — created after Chamber band failure. Lumina's typographic grading gap closed. AIMG measurements captured as canonical AMG benchmark.
