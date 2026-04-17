# Maya — KB 06 Trade Secrets (never-mention list for copy)

## Rule

Every piece of copy you draft for subscriber-facing surfaces is scanned by `hooks/pre-commit-tradesecret-scan.sh` on commit. Any banned term = commit blocked. Full list: `plans/agents/kb/titan/01_trade_secrets.md`. This file is a Maya-specific operating reference.

## The critical few (will absolutely block a commit)

- **Claude, Anthropic** — never. Atlas is the engine. AMG is the company.
- **ChatGPT, GPT-4, GPT-5, OpenAI** — never. Atlas.
- **Gemini, Bard** — never. Atlas.
- **Grok, xAI** — never. Atlas.
- **Perplexity, Sonar** — never.
- **ElevenLabs** — never. Say "our voice engine" or "Atlas voice."
- **Ollama, nomic-embed-text, Kokoro** — never. Say "our memory layer" / "our voice engine."

## Infrastructure never in subscriber copy

- **beast, HostHatch** — never. Say "our production infrastructure."
- **140-lane, 140 concurrent lanes** — never. Say "production-grade capacity."
- **n8n, Stagehand, Supabase** — never. Say "our automation layer" / "our data layer."
- **VPS IPs** (170.205.37.148, 87.99.149.253) — never.
- **Hermes, Argus Panoptes, Hippocrates, Iris, Ploutos** — internal Greek codenames, never in subscriber copy. The one public-facing exception: **Atlas** (the platform brand).

## Allowed in subscriber copy

- **Atlas** — primary platform brand, use freely
- **AMG / AI Marketing Genius** — company brand
- **Agent names:** Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina
- **Program/module brands:** Chamber AI Advantage, Chamber OS, Mobile Command, AI Memory Vault, Einstein Fact Checker, Hallucinometer, Founding Partner, Meeting Intelligence, AI Project Manager
- **Competitor names** (when subscriber asks — acknowledge without trashing): Infinite Views, typical Webflow shops, typical local agencies
- **Generic industry categories:** SEO, GBP, CRM, CRO, programmatic ads — these are standard terminology

## Maya-specific substitution table

| Never write | Write instead |
|---|---|
| "Our AI (Claude/ChatGPT/Gemini) crafted this email…" | "Your Atlas team drafted this email…" |
| "Powered by GPT-4" | "Powered by Atlas" |
| "Our Claude-backed chatbot" | "Your AMG chatbot" |
| "Using natural language processing via [vendor]" | "Using Atlas" |
| "Integration with [Supabase/n8n/Stagehand]" | "Integration with our platform" |
| "140 concurrent AI workflows per second" | "production-grade capacity" (if you must quantify, use generic "high-volume") |
| "Our Ollama-based memory" | "Your persistent Atlas memory" |
| "ElevenLabs voice clone" | "Your Atlas voice" |
| "Running on our HostHatch + beast VPS cluster" | "Running on production-grade infrastructure" |

## Competitor mentions (copy-specific rules)

When a subscriber's brand has an established competitor positioning, you CAN acknowledge competitors by category:

- ✓ "Unlike typical Webflow shops that hand over a site and vanish, AMG builds a system that keeps running."
- ✓ "Most agencies stop at the website. AMG keeps your seven agents running 24/7."
- ✗ "Infinite Views only builds Webflow sites." — naming competitors in broadly-distributed copy risks defamation + free advertising. Acknowledge the category, not the company, in durable copy.

Exception: 1:1 sales conversations / pitch decks where a competitor is the active comparison — naming is fine, factual framing only.

## Testimonials + case studies

You NEVER fabricate a quote or a metric. Every:

- Testimonial has a real named person with signed approval to quote
- Case study has real metrics with documented source (signed client agreement, dashboard screenshot, etc.)
- Member-business reference has an actual business Solon recognizes — or you escalate: *"Need Solon to name a real Revere member business here — I flagged this at [line X]."*

If the content needs a testimonial and no approved one exists: write around it ("member feedback has been strong") or flag TBD. Never fill with a fake name.

## Emoji policy

Default: no emoji in AMG copy unless the subscriber's own brand voice uses them.

Subscriber-brand exceptions (use subscriber voice):
- Joe's Pizza of Revere likely uses 🍕 sparingly — match
- Revere Chamber Board-level copy → no emoji
- Member social captions → platform-appropriate (IG captions can emoji, LinkedIn articles should not)

## When unsure

If a specific word might be a trade-secret violation and isn't in this list: assume it is. Check `plans/agents/kb/titan/01_trade_secrets.md` authoritative regex. Or escalate to Titan for a ruling.

Cost of over-caution: a benign word gets substituted for a brand name. Cost of under-caution: moat eroded, commit blocked, Solon correction.
