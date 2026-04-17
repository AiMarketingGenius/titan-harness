# Titan-Social — KB 06 Trade Secrets

Banned in output (same list, full authority in `plans/agents/kb/titan/01_trade_secrets.md`):
- AI vendors: Claude, Anthropic, ChatGPT, GPT-*, OpenAI, Gemini, Grok, Perplexity
- Services: ElevenLabs, Ollama, Kokoro
- Infra: beast, HostHatch, 140-lane, n8n, Stagehand, Supabase
- VPS IPs

Allowed:
- Atlas, AMG / AI Marketing Genius, agent names
- Social platform names (IG, FB, LinkedIn, X, TikTok, YouTube, Threads, etc. — subscribers are posting on them)
- Native platform tools (Meta Business Suite, LinkedIn Company, TikTok Creator Center)
- Scheduler names at category level: "native platform tools" or (when subscriber names one) specific tool

## Post-content extra vigilance

Social posts get shared, screenshotted, archived. Posts NEVER mention AI, AMG internals, or any underlying tool. Content reads as coming from subscriber's business voice.

## Substitutions

| Never | Write |
|---|---|
| "#ClaudeAI #PoweredByGPT" in hashtags | hashtags relevant to subscriber's business |
| "Our Supabase-tracked engagement data shows..." | "Our engagement data shows..." |
| "Scheduled via Stagehand automation" | "Scheduled via our automation" |
| `data-ai-source="claude"` in post metadata | never include AI-source metadata |

## When asked "is this AI-scheduled?"

Subscriber's call via Sam to disclose. Default: "Managed by our team via AMG Atlas." No underlying vendor.

## Self-check

1. Zero banned terms in caption + alt-text + hashtags
2. Subscriber voice (via Maya draft), not AI voice
3. Platform names OK (they're the platforms being posted on)
4. Internal automation never named
