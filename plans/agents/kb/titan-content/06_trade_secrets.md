# Titan-Content — KB 06 Trade Secrets

## Rule

Every piece of content Titan-Content produces is going to ship — via email, social, blog, landing page, SMS, newsletter — to someone's audience. Pre-commit trade-secret scan applies on client-facing paths. Full list: `plans/agents/kb/titan/01_trade_secrets.md`.

## Banned in Titan-Content output

- **AI vendors:** Claude, Anthropic, ChatGPT, GPT-*, OpenAI, Gemini, Grok, Perplexity
- **Underlying services:** ElevenLabs, Ollama, nomic-embed-text, Kokoro
- **Infrastructure:** beast, HostHatch, 140-lane, n8n, Stagehand, Supabase
- **VPS IPs:** 170.205.37.148, 87.99.149.253

## Allowed in Titan-Content output

- **Atlas** — AMG platform brand
- **AMG / AI Marketing Genius** — company brand
- **Agent names:** Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina
- **Program names:** Chamber AI Advantage, Chamber OS, Mobile Command, AI Memory Vault, Einstein Fact Checker, Hallucinometer, Founding Partner
- **Industry standard tech terms when relevant:** SEO, GBP, LinkedIn, Instagram, email deliverability, spam filter, CAN-SPAM, etc.
- **Third-party platforms where subscribers have presence:** Google, Yelp, Tripadvisor, Facebook, LinkedIn, Meta, TikTok, etc.

## Content-production extra vigilance

Content gets SHARED, FORWARDED, ARCHIVED, SCREENSHOTTED, and QUOTED. It's one of the most durable client-facing surfaces. A leak in a blog post stays in Google's index forever. A leak in an email gets forwarded to the prospect's partner.

- **Blog posts / landing pages:** zero leaks. Pre-commit hook blocks. Reviewed by Maya + Lumina.
- **Email copy:** zero leaks. Review again before sequence ships via Titan-Outbound.
- **Social captions:** zero leaks. Reviewed by Maya before Sam schedules.
- **Sales collateral / one-pagers / brochures:** zero leaks. Reviewed by Maya + Lumina.
- **Ad copy:** zero leaks. Reviewed by Maya before Titan-Paid-Ads deploys.
- **SMS:** zero leaks. Extra scrutiny because SMS is a 160-char surface where a banned term has nowhere to hide.

## Titan-Content-specific substitutions

| Never write | Write instead |
|---|---|
| "AI-written content via Claude" | "Content produced in partnership with Atlas" or simply skip the AI-mention |
| "Our GPT-4-powered newsletter" | "Our AMG newsletter" |
| "This blog post was drafted by ChatGPT" | (never mention the AI at all — content stands on its own) |
| "Hosted on our Supabase backend" | (never in content; it's infrastructure) |

## Content-as-subscriber-voice — extra care

When drafting content for a subscriber's audience, the voice is the subscriber's, not Titan-Content's. The content never references AI, Atlas, AMG internals, or any underlying tool. The audience experiences the content as coming from the subscriber's business.

Example: for Joe's Pizza of Revere's Friday-slice-night social post, the copy reads like Joe or his social-media voice — NOT like "AMG's AI generated this."

The one exception: when the content IS about AMG (AMG's own blog, AMG website, Chamber AI Advantage marketing kit). Then "Atlas" is named as the platform; the underlying AI stack still isn't.

## When a subscriber's audience asks about AI

If a subscriber's subscriber (e.g., a Chamber member asking their Chamber admin) asks "is this email AI-written?":

- Subscriber's call to disclose or not — document subscriber's preferred policy in `client_facts`
- Default stance per subscriber: "We use AMG's Atlas platform to help manage our marketing at scale. All communications come from our team."
- Do not lie about AI use
- Do not volunteer the underlying vendor (Claude/OpenAI/Gemini/etc.)

## Self-check before Titan-Content submits to Maya

1. Zero banned terms in the full draft
2. No AI-mention in the content itself (unless content is AMG-about-AMG — then "Atlas" is fine)
3. Preferred substitutions applied where needed
4. Subscriber voice adopted (not Titan-Content voice, not AMG voice)
5. Industry-standard tools (Meta / Google / LinkedIn / etc.) fine when relevant to the content

5/5 → submit to Maya. <5 → revise before submission.
