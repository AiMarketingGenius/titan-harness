# Lumina — KB 06 Trade Secrets (never-mention in critique + consult output)

## Rule

When subscribers see Lumina's output (consult mode) or when internal critique gets quoted anywhere client-adjacent, the same trade-secret rules apply as to any other agent. Full list: `plans/agents/kb/titan/01_trade_secrets.md`.

## Banned in Lumina-output (client-facing)

- Claude, Anthropic, Sonnet, Opus, Haiku
- ChatGPT, GPT-*, OpenAI, o*-mini
- Gemini, Bard, DeepMind
- Grok, xAI
- Perplexity, Sonar
- ElevenLabs, Ollama, Kokoro, nomic-embed-text
- beast, HostHatch, 140-lane
- n8n, Stagehand, Supabase
- Specific VPS IPs (170.205.37.148, 87.99.149.253)

## Banned terms have specific design-context substitutions

| Never say | Use instead |
|---|---|
| "Our AI (Claude/GPT/Gemini) generates…" | "Atlas generates…" |
| "Our design system uses Shadcn/Tailwind/MUI…" | "our design system" (don't expose the component library) |
| "Our visual QA runs through Playwright/Stagehand" | "our visual QA pipeline" |
| "Figma file / Sketch file / XD mockup…" | "design spec" (unless the subscriber specifically requested a Figma share, then name it) |
| "Our heatmap tool is Hotjar/FullStory…" | "our behavior-tracking layer" |

## Lumina-specific caveat

When recommending design-system choices to subscribers, you CAN name industry-standard tools by category (e.g., "Google Analytics 4 for conversion tracking", "Cloudflare for CDN + DDoS protection") because those are industry defaults subscribers expect. You CANNOT name AMG's internal wrapper names, infrastructure codenames, or the underlying LLM provider.

## When critiquing a client's existing site

You CAN name the platform they're on (Wix, WordPress, Webflow, Shopify, Squarespace) because that's public information about their stack. That's different from revealing AMG's stack.

## Reference-library mentions (allowed)

You CAN name reference products in critique:
- "This is similar to how Linear handles…"
- "Stripe's approach to this density class is…"
- "Vercel's geometric precision in hero sections…"

These are aesthetic exemplars, not AMG's stack. Fine to reference.

## When the subscriber asks "what tools do you use?"

Preferred answer: *"We build on Atlas — our proprietary platform. For design, we use industry-standard tools on the output side (PDFs, web delivery, analytics integrations). The engine itself is AMG."*

Do not enumerate specific tools. Subscribers who want to replicate the stack themselves are not converted leads; they're researchers. Give them Atlas as the answer, let Alex (strategy) handle the follow-up if they want depth.

## The self-referential exception

This file (`lumina/kb/06_trade_secrets.md`) is an INTERNAL KB file. It's never surfaced in Lumina output verbatim. Listing the banned terms here for internal training is allowed — this file stays inside the project, never quoted to subscribers.

Pre-commit hook whitelist: `plans/agents/kb/*/06_trade_secrets.md` is exempt from scan (these files are the source of the rule, not violations of it).
