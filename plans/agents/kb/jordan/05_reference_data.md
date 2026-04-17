# Jordan — KB 05 Reference Data

## Encyclopedia v1.3

Chamber AI Advantage / pricing / program terms sourced from `library_of_alexandria/chamber-ai-advantage/CHAMBER_AI_ADVANTAGE_ENCYCLOPEDIA_v1_3.md`. SEO pricing:
- SEO audit (one-time): $500-1500 depending on complexity (v1.3 §4.5)
- Ongoing SEO (bundled in Starter/Growth/Pro tiers)
- Hourly custom: $300 simple / $400 standard / $500 complex (v1.3 §4.5)

## client_facts (via op_get_client_facts RPC)

Per-subscriber SEO context:
- `seo_priority_keywords` — target keyword list
- `seo_competitor_domains` — top-3 local competitors
- `seo_service_area` — geographic radius + named cities
- `seo_primary_category` — GBP primary category
- `seo_nap_canonical` — authoritative name/address/phone

## SEO tool stack (industry-standard, nameable when relevant)

- **Google Search Console** — subscriber's own account, service-user access
- **Google Business Profile Manager** — subscriber-owned
- **Google Analytics 4** — subscriber-owned property
- **Ahrefs / SEMrush** — AMG subscriptions for competitor + backlink analysis
- **BrightLocal** — citation audit + monitoring
- **Screaming Frog SEO Spider** — technical crawl audits
- **Google's Rich Results Test** — schema validation
- **PageSpeed Insights / Lighthouse** — Core Web Vitals
- **SchemaApp / JSON-LD Generator** — schema markup tools

Name these tools when subscribers ask (they're industry-standard); don't volunteer internal automation stack.

## Ranking benchmarks (directional, not promises)

- **Local pack (3-pack) entry:** typically 4-8 weeks for a well-optimized GBP with 40+ citations
- **Position shift of 5+:** typically 2-4 weeks for on-page optimization with matched content
- **Algorithm-update recovery:** 4-8 weeks typical; sometimes longer for helpful-content-update recoveries
- **New-domain ranking:** 6-12 months for competitive local terms; 3-6 months for long-tail

## Google algorithm timeline (current reference)

Track + cite by name:
- **Helpful Content Update** — ongoing since 2022, now part of Core
- **E-E-A-T emphasis** — increased weight since Dec 2022
- **Local Service Ads (LSA)** — ongoing rollout across categories
- **Review signals weight** — increased weight for local pack since 2023
- **Core Web Vitals** — ranking factor since 2021 (ongoing)

When a subscriber's ranking drops, correlate against recent confirmed Google updates via Search Engine Roundtable / Google Search Central blog / Moz algorithm history.

## Schema.org quick-ref (most-used for local)

- **LocalBusiness** (or subtype: Restaurant, Dentist, LegalService, etc.)
- **Service** — for service-specific pages
- **FAQ** — for FAQ sections (rich-result eligible)
- **Review + AggregateRating** — if genuine reviews exist
- **Organization** — for the parent brand
- **BreadcrumbList** — for deep-link navigation visibility
- **Event** — for Chamber events, workshops, launches
- **Article** — for blog posts

Always validate via Google's Rich Results Test before shipping.

## GBP optimization checklist (scoring template for subscriber audits)

1. Primary category chosen (+ up to 10 secondary) — 10 pts
2. Services fully listed with descriptions — 10 pts
3. Attributes complete (all relevant to category) — 10 pts
4. Hours accurate + special-hours set when needed — 5 pts
5. NAP consistent with website + other directories — 10 pts
6. Photos: 20+ quality photos (interior, exterior, team, products, work samples) — 10 pts
7. Weekly post cadence for 90+ days — 10 pts
8. Q&A fully answered (at least 5 questions with responses) — 5 pts
9. Review count: 50+ reviews with 90%+ response rate — 15 pts
10. Review velocity: 5+ new reviews/month sustained — 10 pts
11. Products/services fully listed — 5 pts

Target: 85+ for mature businesses; 70+ for newer businesses within first 6 months.

## Citation directory priority tiers

**Tier 1 (always):** Google Business Profile, Yelp, Bing Places, Apple Maps, Facebook Places, Yellow Pages, Superpages, Foursquare, TripAdvisor (hospitality), BBB

**Tier 2 (category-specific):**
- Legal: Avvo, Justia, FindLaw, Martindale
- Medical: Healthgrades, Vitals, WebMD, RateMDs, Zocdoc
- Home services: Angi, HomeAdvisor, Thumbtack, Houzz
- Restaurants: OpenTable, Resy, Zagat, Grubhub, DoorDash
- Retail: Yahoo Local (sunset 2026-04), Manta, Yellowpages.com

**Tier 3 (local/regional):** Chamber of Commerce directory, regional business directories, BBB local

## Common SEO failure patterns (document when diagnosed)

- **NAP drift** — inconsistent name/address/phone across directories
- **Category confusion** — primary GBP category doesn't match actual core service
- **Thin-content** — pages under 300 words competing with 1500+ word competitors
- **Missing schema** — no structured data on pages that could get rich results
- **Slow mobile** — LCP >4s on 4G connection
- **Duplicate content** — same content on multiple pages/domains without canonicals
- **Over-optimization** — keyword-stuffed titles/headings/body; triggers spam signals

## Monthly SEO report template

Sections:
1. **Executive summary** — rankings up/down, traffic up/down, notable wins, issues
2. **Ranking changes** — top 20 keywords, position change vs last month
3. **Traffic metrics** — GSC impressions + clicks; GA4 sessions + conversions
4. **GBP Insights** — calls, direction-requests, website-visits from GBP
5. **Citation audit** — any inconsistencies found + fix status
6. **Upcoming work** — next month's focus + expected outcomes
7. **Blockers** — anything subscriber or Solon needs to decide
