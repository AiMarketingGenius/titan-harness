-- ============================================================================
-- sql/008b_crm_seed_backfill.sql
-- CT-0417-29 T6 — backfill 5 active/committed clients into crm_contacts +
-- crm_deals + crm_activities + crm_persistent_memory.
-- Source: client_facts (operator Supabase) + CT-0417-19 RCoC crawl + MCP decision log
-- ============================================================================

-- Use deterministic UUIDs so re-running is idempotent and matches client_facts
-- existing client_id values where present.

-- ----------------------------------------------------------------------------
-- 1. Insert the 5 contacts (idempotent via UPSERT on slug)
-- ----------------------------------------------------------------------------

INSERT INTO public.crm_contacts (
    id, slug, display_name, contact_name, contact_email, contact_phone,
    company, address, city, state, zip, timezone,
    persistent_memory_ref, source_channel, tags
) VALUES
    ('00199f08-9378-4670-9a8d-d4f63ff01fc6'::uuid, 'jdj-levar',
     'JDJ Investment Properties (Levar)', 'Levar', 'levar@jdjinvestments.com', NULL,
     'JDJ Investment Properties', NULL, 'Lynn', 'MA', NULL, 'America/New_York',
     gen_random_uuid(), 'founding-member-onboarding',
     ARRAY['founding-member','real-estate','active','priority']),

    ('11111111-1111-1111-1111-000000000001'::uuid, 'shop-unis',
     'Shop UNIS', 'Kay Tan', 'hello@unistechnology.com', '1-877-864-7464',
     'UNIS Technology', NULL, 'Toronto', 'ON', NULL, 'America/Toronto',
     gen_random_uuid(), 'inbound-engagement',
     ARRAY['shopify','active','blog-automation','quarterly-billing']),

    ('22222222-2222-2222-2222-000000000002'::uuid, 'paradise-park-novi',
     'Paradise Park Novi', 'Jeff Wainwright', NULL, '(248) 735-1050',
     'Paradise Park', '45799 Grand River Ave, Novi, MI 48374', 'Novi', 'MI', '48374', 'America/Detroit',
     gen_random_uuid(), 'inbound-engagement',
     ARRAY['wix','active','crisis-recovery','birthday-bookings']),

    ('33333333-3333-3333-3333-000000000003'::uuid, 'revel-roll-west',
     'Revel & Roll West', 'James St. John', NULL, '(269) 488-3800',
     'Revel & Roll West', '4500 Stadium Drive, Kalamazoo, MI', 'Kalamazoo', 'MI', NULL, 'America/Detroit',
     gen_random_uuid(), 'inbound-engagement',
     ARRAY['custom-website','active','quarterly-billing']),

    ('a4143ec3-26eb-4cf9-bcb1-7b5a1a5d80d5'::uuid, 'revere-chamber',
     'Revere Chamber of Commerce', 'Don Martelli', 'donmartelli@gmail.com', '617-413-6773',
     'Revere Chamber of Commerce', '313 Broadway, Revere MA, 02151', 'Revere', 'MA', '02151', 'America/New_York',
     gen_random_uuid(), 'board-courtesy-pilot',
     ARRAY['chamber-of-commerce','founding-partner','board-courtesy','bilingual','pitch-shipped'])
ON CONFLICT (slug) DO UPDATE SET
    display_name   = EXCLUDED.display_name,
    contact_name   = EXCLUDED.contact_name,
    contact_email  = EXCLUDED.contact_email,
    contact_phone  = EXCLUDED.contact_phone,
    company        = EXCLUDED.company,
    address        = EXCLUDED.address,
    city           = EXCLUDED.city,
    state          = EXCLUDED.state,
    zip            = EXCLUDED.zip,
    tags           = EXCLUDED.tags,
    updated_at     = now();

-- ----------------------------------------------------------------------------
-- 2. Active deals (one per client)
-- ----------------------------------------------------------------------------

INSERT INTO public.crm_deals (contact_id, title, stage, amount_cents, currency, metadata, expected_close)
SELECT id,
    'JDJ Investment Properties — AMG Founding Member, Phase 1 acquisition stack',
    'closed-won', 0, 'USD',
    jsonb_build_object(
        'tier','founding_member',
        'pricing_note','Founding Member — pricing per founding-member terms; geo-exclusive Lynn-Revere through month 12',
        'phase_1_priorities', jsonb_build_array('A2P','GBP','Voice AI Callback','CRO','Chatbot intake'),
        'cadence','Tuesday 30-min Zoom',
        'preferred_comm','SMS + email (Alex CC Solon through 90-day mark)'
    ), NULL
FROM public.crm_contacts WHERE slug = 'jdj-levar'
ON CONFLICT DO NOTHING;

INSERT INTO public.crm_deals (contact_id, title, stage, amount_cents, currency, metadata)
SELECT id,
    'Shop UNIS — Blog automation + content engine',
    'closed-won', 350000, 'USD',
    jsonb_build_object(
        'pricing','$3,500/month',
        'term_months', 12,
        'billing','quarterly via wire transfer',
        'last_delivery','29-blog batch shipped Apr 2-4 2026',
        'spelling_lock','Sun Jammer (two words, Title Case) — never SunGemmer/SunJammer/sungemmer'
    )
FROM public.crm_contacts WHERE slug = 'shop-unis'
ON CONFLICT DO NOTHING;

INSERT INTO public.crm_deals (contact_id, title, stage, amount_cents, currency, metadata)
SELECT id,
    'Paradise Park — Birthday-booking crisis recovery + LeadSnap citation cleanup',
    'closed-won', 189900, 'USD',
    jsonb_build_object(
        'pricing','$1,899/month',
        'billing','Square',
        'crisis','Birthday-party booking collapse since Sept 2025',
        'hypothesis','LeadSnap citation damage'
    )
FROM public.crm_contacts WHERE slug = 'paradise-park-novi'
ON CONFLICT DO NOTHING;

INSERT INTO public.crm_deals (contact_id, title, stage, amount_cents, currency, metadata)
SELECT id,
    'Revel & Roll West — Quarterly retainer',
    'closed-won', 207900, 'USD',
    jsonb_build_object(
        'pricing','$6,236.88 / quarter (~$2,079/mo)',
        'billing','Square',
        'comm_preference','James prefers text for quick items'
    )
FROM public.crm_contacts WHERE slug = 'revel-roll-west'
ON CONFLICT DO NOTHING;

INSERT INTO public.crm_deals (contact_id, title, stage, amount_cents, currency, metadata, expected_close)
SELECT id,
    'Revere Chamber AI Advantage — Founding Partner #1 (Board Courtesy 50%)',
    'discovery', NULL, 'USD',
    jsonb_build_object(
        'tier','founding_partner_1_of_10',
        'rev_share','18% (vs 15% standard)',
        'board_courtesy','50% off setup + monthly + hourly',
        'bundle_target','Chamber OS Essentials → Full Operational',
        'membership_pricing_verified','Individual $100 / Small $250 / Large $500 / Corporate $1000-3yr / Non-Profit $225',
        'pitch_status','demo portal shipped CT-0417-23, board-pitch-ready 1pm 2026-04-17',
        'next_action','Don decision on Founding Partner agreement'
    ), '2026-05-01'::date
FROM public.crm_contacts WHERE slug = 'revere-chamber'
ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. Activity history seed (representative recent activities per client)
-- ----------------------------------------------------------------------------

INSERT INTO public.crm_activities (contact_id, activity_type, direction, summary, body, actor, actor_role, occurred_at)
SELECT c.id, 'note', 'internal',
    'Founding Member onboarding — Phase 1 priorities locked',
    'A2P/10DLC SMS registration (Telnyx ticket #4471), GBP claim+optimize, Voice AI Callback agent <60s response, 1-page CRO audit, seller-intake chatbot on /sell. Geo-exclusive Lynn-Revere through month 12.',
    'titan', 'operator', '2026-04-10 14:00:00+00'::timestamptz
FROM public.crm_contacts c WHERE c.slug = 'jdj-levar'
UNION ALL
SELECT c.id, 'note', 'internal',
    'Apr 2-4 blog batch shipped',
    '~29 blog posts published via custom Shopify app integration (Mar 18 setup → Apr 2-4 push). Kay Tan reviewed and approved short/clear bullet style.',
    'titan', 'operator', '2026-04-04 18:00:00+00'::timestamptz
FROM public.crm_contacts c WHERE c.slug = 'shop-unis'
UNION ALL
SELECT c.id, 'note', 'internal',
    'Birthday-party booking crisis triage',
    'Booking volume collapsed since Sept 2025. Hypothesis: LeadSnap citation poisoning. Next: full citation audit + GBP repair.',
    'titan', 'operator', '2026-04-08 16:00:00+00'::timestamptz
FROM public.crm_contacts c WHERE c.slug = 'paradise-park-novi'
UNION ALL
SELECT c.id, 'meeting', 'outbound',
    'Quarterly retainer renewal',
    'James (GM) confirmed quarterly billing schedule via Square. Prefers text for quick items, email for longer comms.',
    'titan', 'operator', '2026-04-05 15:00:00+00'::timestamptz
FROM public.crm_contacts c WHERE c.slug = 'revel-roll-west'
UNION ALL
SELECT c.id, 'note', 'internal',
    'CT-0417-19 shipped — RCoC crawl + hero concept v1 + RFP validation',
    'Live-site crawl validated $100/$250/$500/$1000-3yr/$225 RFP tiers verbatim. Don Martelli confirmed as President. /meet-our-board returns 404 — citable pitch hook. Hero concept v1 dual-graded 9.68 (Gemini 9.5 / Grok 9.87). Patrick staleness flag: zero internal references; correct for any external doc.',
    'titan', 'operator', '2026-04-17 11:38:00+00'::timestamptz
FROM public.crm_contacts c WHERE c.slug = 'revere-chamber'
UNION ALL
SELECT c.id, 'demo', 'outbound',
    'Board pitch deck shipped — Atlas-sole-speaker portal v5 live',
    'CT-0417-25 + CT-0417-27 deployed: Atlas-sole-speaker refactor (one voice, nine hands, parallel-lane fan-out) + Mobile Command infra. Portal at checkout.aimarketinggenius.io/revere-demo/ (pw revere2026). Encyclopedia v1.4.1 roster collapsed 10→9.',
    'titan', 'operator', '2026-04-17 15:40:00+00'::timestamptz
FROM public.crm_contacts c WHERE c.slug = 'revere-chamber'
ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. Persistent memory namespaces (seed each contact with ≥3 high-importance memories)
-- ----------------------------------------------------------------------------

INSERT INTO public.crm_persistent_memory (contact_id, namespace_id, memory_type, text_content, importance, written_by, valid_from)
SELECT c.id, c.persistent_memory_ref, mem.mt, mem.txt, mem.imp, 'titan-backfill-2026-04-17', '2026-04-17 16:00:00+00'
FROM public.crm_contacts c, LATERAL (VALUES
    ('jdj-levar','rule', 'Geo-exclusive Lynn-Revere MA through month 12. Cannot accept other competitive real-estate clients in same market.', 10),
    ('jdj-levar','preference','Levar prefers SMS + email; Alex CCs Solon on all founding-member comms through 90-day mark.', 9),
    ('jdj-levar','context','Friendly competitor Tariq Washington / Beacon Hill Capital — Levar offered 3-way call to showcase AMG work if Tariq engages.', 7),
    ('jdj-levar','blocker','Telnyx A2P ticket #4471 submitted 2026-04-09; expected 7-10 business days. SMS launch gated on approval.', 9),
    ('jdj-levar','timeline','Weekly Tuesday Zoom 30 min (kickoff confirmed).', 8),

    ('shop-unis','rule','Canonical spelling: Sun Jammer (two words, Title Case). NEVER SunGemmer / Sungemmer / SunJammer (no space) / sun jammer (lowercase). Kay lock from March 2026.', 10),
    ('shop-unis','preference','Kay Tan reviews all content; prefers short/clear bullets.', 9),
    ('shop-unis','contact-detail','HQ Toronto + US fulfillment Dallas; quarterly billing wire transfer.', 7),
    ('shop-unis','timeline','Apr 2-4 batch: ~29 blogs shipped via custom Shopify app set up Mar 18.', 8),

    ('paradise-park-novi','blocker','Birthday-party booking volume collapsed since Sept 2025. Active crisis. Hypothesis: LeadSnap citation damage.', 10),
    ('paradise-park-novi','preference','Jeff Wainwright COO — engineering-minded, data-driven, wants metrics not narrative.', 9),
    ('paradise-park-novi','contact-detail','Wix platform; Square billing; 45799 Grand River Ave Novi MI 48374.', 7),

    ('revel-roll-west','preference','James St. John GM — texts for quick items, email for longer. Quarterly check-ins.', 9),
    ('revel-roll-west','contact-detail','4500 Stadium Drive Kalamazoo MI; (269) 488-3800; custom website with direct access.', 8),

    ('revere-chamber','rule','Don Martelli is sole verified Chamber President. Any internal/external doc naming Patrick or anyone else as Chamber leadership is STALE — correct to Don.', 10),
    ('revere-chamber','rule','Founding Partner #1 status — 18% rev-share locked for life vs 15% standard, plus 50% Board courtesy on all setup + monthly + hourly fees.', 10),
    ('revere-chamber','fact','Membership tiers verified live 2026-04-17: Individual $100 / Small Business $250 / Large Business $500 / Corporate $1,000 (valid 3 years, effective $333/yr) / Non-Profit $225.', 9),
    ('revere-chamber','context','RCoC /meet-our-board returns 404 — broken board page is citable pitch hook for "we rebuild governance surface in week 1."', 8),
    ('revere-chamber','context','Bilingual Chamber community (English + Spanish). Demo + collateral must acknowledge.', 7),
    ('revere-chamber','decision','Atlas-sole-speaker architecture lock 2026-04-17 — admin talks ONLY to Atlas, 8 specialists run silently backstage. Encyclopedia v1.4.1 §10.5.2.5 non-negotiable.', 10),
    ('revere-chamber','timeline','Board pitch portal shipped 2026-04-17 1pm ET. Don decision on Founding Partner agreement pending.', 9)
) AS mem(slug, mt, txt, imp)
WHERE c.slug = mem.slug
ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- 5. Verification queries (run after to confirm)
-- ----------------------------------------------------------------------------
-- SELECT slug, display_name, contact_name FROM public.crm_contacts ORDER BY slug;
-- SELECT c.slug, d.title, d.stage FROM public.crm_deals d JOIN public.crm_contacts c ON c.id=d.contact_id ORDER BY c.slug;
-- SELECT c.slug, count(*) AS act FROM public.crm_activities a JOIN public.crm_contacts c ON c.id=a.contact_id GROUP BY c.slug ORDER BY c.slug;
-- SELECT c.slug, count(*) AS mem FROM public.crm_persistent_memory m JOIN public.crm_contacts c ON c.id=m.contact_id GROUP BY c.slug ORDER BY c.slug;
