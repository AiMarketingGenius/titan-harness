# Titan-Paid-Ads — KB 06 Trade Secrets

Banned in ad creative + landing pages + tracking parameters (full list: `plans/agents/kb/titan/01_trade_secrets.md`):
- AI vendors (Claude, Anthropic, GPT-*, OpenAI, Gemini, Grok, Perplexity)
- Services (ElevenLabs, Ollama, Kokoro)
- Infra (beast, HostHatch, 140-lane, n8n, Stagehand, Supabase)
- VPS IPs

Allowed:
- Atlas, AMG / AI Marketing Genius, agent names
- Ad platform names (Meta, Google, LinkedIn, TikTok — subscribers expect)
- Tracking tech (Meta Pixel, Google Analytics, GTM, UTM — industry standards)
- Performance tools (Google Ads, Meta Ads Manager, Campaign Manager)

## Ad creative — EXTRA trade-secret vigilance

Ads are PAID amplification. A leaked banned term in ad copy reaches thousands of impressions. Pre-commit scan + Lumina review + Maya voice review all apply.

- ❌ Ad headline: "AI-Powered by Claude for Your Marketing"
- ✅ Ad headline: "Lynn Real Estate Marketing, Powered by Atlas"
- ❌ Ad body: "Our GPT-4 analysis shows..."
- ✅ Ad body: "Your team at AMG runs 24/7..."

## UTM parameter content

UTM params appear in subscriber's analytics + browser URLs. Keep clean:

- ✅ `?utm_source=meta&utm_medium=paid&utm_campaign=spring_launch`
- ❌ `?utm_source=claude_generated_campaign` (leaks in browser + analytics)

## When subscribers ask "how do you decide on targeting?"

Alex relays: *"Your AMG team uses Atlas to synthesize audience data + platform signals. Specific platform tools (Meta Ads Manager audiences, Google keyword planner) feed the targeting; Atlas ties it together."*

Do not enumerate: specific ML model behind audience-optimization, internal automation.

## Self-check before launching campaign

1. Zero banned terms in ad headline + body + description + image-alt
2. UTM parameters clean
3. Landing page trade-secret-scan clean
4. Subscriber approval on file for creative + targeting + budget
5. Platform policy compliance (discrimination rules for housing/employment; substantiation for health/wealth claims)

5/5 → launch. <5 → revise.
