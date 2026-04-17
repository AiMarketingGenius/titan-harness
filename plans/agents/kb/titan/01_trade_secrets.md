# Titan KB — 01 Trade Secrets (NEVER-MENTION list, enforced by pre-commit hook)

## Hard never-mention in any CLIENT-FACING surface

Any file committed under these paths is scanned by `/opt/titan-harness/.git/hooks/pre-commit-tradesecret-scan.sh`. If it finds any term below, the commit is BLOCKED.

**Client-facing paths:**
- `deploy/` (and subdirs — includes demo portals, production web bundles)
- `portal/`, `site/`, `marketing/`
- `revere-*`, `chamber-*` (any path containing these)
- `plans/agents/kb/{alex,maya,jordan,sam,riley,nadia,lumina}/` (subscriber-agent KBs — the text may be quoted to end users)

**Whitelist (internal paths — terms allowed):**
- `plans/` (except subscriber KB subtrees above)
- `lib/`, `scripts/`, `bin/`, `config/`, `sql/`
- `infra/`, `docs/internal/`
- `.git/`, `.github/`
- `library_of_alexandria/`
- `CLAUDE.md`, `MEMORY.md`, `RADAR.md`, `MIRROR_STATUS.md`, `INVENTORY.md`, `CORE_CONTRACT.md`
- This file (`titan/kb/01_trade_secrets.md`) — it's the source of truth about the list, not a leak

## The banned-term set

### Underlying AI vendors + models (never in client-facing)
- `Claude`, `Anthropic`, `Sonnet`, `Opus`, `Haiku` (any Claude model name)
- `ChatGPT`, `GPT-4`, `GPT-5`, `OpenAI`, `o1`, `o3`, `o4-mini`, `GPT Turbo`
- `Gemini`, `Google DeepMind`, `Bard`
- `Grok`, `xAI`
- `Perplexity`, `Sonar`, `Sonar Pro`, `Sonar Deep Research`
- `Llama`, `Meta AI`
- `Mistral`
- `ElevenLabs` (the voice engine)
- `Ollama`, `nomic-embed-text`
- `Kokoro`

### Infrastructure codenames + component names (never in client-facing)
- `beast`, `HostHatch` (VPS codenames)
- `140-lane`, `140 concurrent lanes`, `140-lane queue`
- `n8n` (workflow engine)
- `Stagehand` (browser automation)
- `Supabase` (database vendor)
- `Postgres`, `Redis`, `Bull queue`, `Docker`, `Caddy`, `LiteLLM`, `Infisical` (when describing the platform to clients)
- `VPS IP` specifics: `170.205.37.148`, `87.99.149.253`
- `kill chain`, `kill switch` (internal ops terminology)
- `Hermes` (voice codename — internal only), `Argus Panoptes`, `Hippocrates`, `Iris`, `Ploutos` (Greek codenames are internal)

### Allowed in client-facing
- **Atlas** — AMG's flagship platform name, can and should be used client-facing
- **AMG** / **AI Marketing Genius** — company brand
- **AI Memory Vault**, **Einstein Fact Checker**, **Hallucinometer** — productized module names
- **Chamber AI Advantage**, **Chamber OS** — program names
- **Mobile Command** — product name (the mobile interface, not the codename for infrastructure behind it)
- Agent names: **Alex, Maya, Jordan, Sam, Riley, Nadia, Lumina**

## Preferred substitutions (client-facing)

| Banned | Use instead |
|---|---|
| "I'm Claude / ChatGPT / Gemini" | "I'm [Agent Name], your AMG [role]" |
| "Our AI uses GPT-4 / Claude / Gemini" | "Our AI uses Atlas — AMG's proprietary engine" |
| "Ollama" / "nomic-embed-text" | "our memory layer" |
| "ElevenLabs" | "our voice engine" |
| "the Claude API" | "our AI platform" |
| "140 concurrent lanes on beast + HostHatch" | "production-grade infrastructure" |
| "n8n workflow" | "automation" |
| "Supabase database" | "our data layer" |
| "Stagehand browser automation" | "browser automation" / "our browser engine" |

## Regex patterns the pre-commit hook checks (authoritative)

```
\b(Claude|Anthropic|Sonnet|Opus|Haiku|ChatGPT|GPT-[0-9]|OpenAI|o[0-9]-mini|Gemini|Bard|Grok|xAI|Perplexity|Sonar|Llama|Mistral|ElevenLabs|Kokoro|Ollama|nomic-embed-text)\b
\b(HostHatch|beast-primary|beast VPS)\b
\b140[\s-]lane\b
\bn8n\b
\bStagehand\b
\bSupabase\b
\b(kill.chain|kill.switch)\b
170\.205\.37\.148
87\.99\.149\.253
```

Case-insensitive. Word boundary on terms that could appear in normal prose (e.g., `grok` is too common in English when lowercase — but inside client-facing marketing copy, if `Grok` capitalized appears, it's a leak).

## Exceptions + overrides

If a banned term is genuinely required in client-facing (rare — e.g., a press release explicitly comparing to competitors), override the hook by prefixing the file's first line with `# LEAK_OVERRIDE: <reason>` — this requires commit message tag `[LEAK_OVERRIDE]` matching the reason, and the override is logged to `/opt/amg-docs/leak-overrides.log` for later audit.

Default: if you think you need an override, you probably don't. The override path exists to avoid grinding on false positives; it's not a bypass.

## Why this matters

- **Moat:** AMG's value is Atlas + agent KBs + operator playbook + Chamber partnerships. Not "we wrap Claude." If a client learns the base model, they DIY with the same model + save money, fail, and we lose account + referral.
- **Premium brand:** clients hear brand names underneath and think "same thing I can buy direct from [vendor]." Naming dilutes our premium.
- **Security:** infrastructure codenames (beast, HostHatch, 140-lane) in client-facing surfaces give attackers surface-mapping info they shouldn't have.
- **Enforcement recurrence:** 2026-04-17 — Solon caught leaks in the Revere portal v3 demo ("Powered by Atlas", "Live on beast + HostHatch · 140-lane queue"). Pre-commit hook prevents this recurring.
