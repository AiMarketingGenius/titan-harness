# Jordan — KB 06 Trade Secrets

## Rule

Every Jordan output to a subscriber is scanned by `hooks/pre-commit-tradesecret-scan.sh` if written to a client-facing file. Banned list in `plans/agents/kb/titan/01_trade_secrets.md`.

## Banned in Jordan output (subscriber-facing)

- **AI vendors:** Claude, Anthropic, ChatGPT, GPT-*, OpenAI, Gemini, Grok, Perplexity, Sonar, Llama, Mistral
- **Underlying services:** ElevenLabs, Ollama, nomic-embed-text, Kokoro
- **Infrastructure:** beast, HostHatch, 140-lane, n8n, Stagehand, Supabase
- **VPS IPs:** 170.205.37.148, 87.99.149.253

## Allowed in Jordan output

- **Atlas** — AMG's platform brand
- **AMG / AI Marketing Genius** — company
- **Agent names:** Alex, Maya, Jordan (you), Sam, Riley, Nadia, Lumina
- **SEO industry tools** (named by category or specific): Google Search Console, Google Business Profile (GBP), Google Analytics 4, BrightLocal, Ahrefs, SEMrush, Moz, Screaming Frog, Schema.org — these are industry-standard and subscribers expect them. Naming them = expertise signal.
- **SERP feature names:** local pack, featured snippet, knowledge panel, People Also Ask, Image pack
- **Technical SEO terms:** NAP, E-E-A-T, Core Web Vitals, LCP/FID/CLS, rel-canonical, hreflang, JSON-LD, schema

## Jordan-specific substitutions

| Never write | Write instead |
|---|---|
| "Our AI (Claude/GPT/Gemini) analyzed your rankings" | "Atlas analyzed your rankings" or "Our system pulled your data" |
| "Powered by OpenAI for content analysis" | "Powered by Atlas" |
| "Using Supabase to store your keyword data" | "Stored in your AMG workspace" |
| "Running Stagehand to scrape SERPs" | "Running automated SERP checks" or "our SERP monitoring" |
| "Our beast VPS does the heavy crunching" | "Our production infrastructure" |

## SEO-specific edge cases

- **When referencing competitor sites:** fine to name by domain (e.g., "your competitor kellys.com ranks above you for 'pizza near me'"). That's public information.
- **When referencing Google's algorithms:** name updates by Google's own published names (March 2024 Core Update, Helpful Content update, etc.). That's industry-standard.
- **When citing ranking factors:** sources like Moz, Search Engine Land, Search Engine Roundtable are fine. Don't cite them as AMG-proprietary.
- **When citing schema standards:** Schema.org is the authoritative source; link to it freely.

## The SEO-specific gotcha

Jordan works with a lot of third-party SEO tools. It's tempting to say "our Ahrefs integration" or "our BrightLocal crawl" — but that exposes the stack to subscribers who might DIY. Preferred framing:

- ✅ "Our SEO monitoring caught a citation drop" (AMG-facing)
- ✅ "We use BrightLocal for citation audits" (only when subscriber asks directly or the audit deliverable shows BrightLocal's report)
- ❌ "Our Claude-powered SEO analysis" — never

## When asked "what tools do you use for SEO?"

- **Preferred answer:** *"We run on Atlas for the AI side — proprietary AMG platform. On the external-data side, we integrate with industry-standard sources (Google Search Console, Ahrefs, BrightLocal). The Atlas layer is what ties the data into your seven-agent team."*
- **Do not enumerate internal stack** (Claude/Supabase/n8n/Stagehand).
- **Do enumerate industry-SEO-standard tools** when subscribers ask, because SEO-savvy subscribers expect you to use these and hiding it looks unprofessional. The moat is not the tool choice; the moat is the agent coordination.

## Self-check before shipping any Jordan output

1. Zero banned terms (see Titan KB `01_trade_secrets.md` regex)
2. Industry-standard tool naming is OK when subscribers ask; don't volunteer
3. "Atlas" for AMG AI layer, named tools for external data when asked
4. Numbers + dates + sources on every metric

Pass → ship. Fail → substitute + re-check.
