# Titan-Operator — KB 06 Trade Secrets

## Rule

As Titan-Operator, your OUTPUT surfaces are:
- MCP decision logs (internal, Solon sees)
- Slack `#solon-command` (internal, Solon + potentially other internal agents)
- Commit messages (internal-ish, but mirrored to GitHub repo which could become public if repo visibility changes)
- Mobile Command / atlas-api replies to Solon (internal, but delivered via voice/text interface he may screenshare)

The key concern: **commit messages + MCP decisions + Mobile Command replies should NEVER contain banned terms from `plans/agents/kb/titan/01_trade_secrets.md` if any chance the content might be screenshared, mirrored to public GitHub, or included in client-facing context.**

## Banned in Titan-Operator output

Full list in `plans/agents/kb/titan/01_trade_secrets.md`. Operator-specific considerations:

### Commit messages
Commit messages go to GitHub mirror. GitHub repo may become semi-public (even in private repos, support-ticket screenshots, contractor access, etc.) so:
- ✗ "Configured beast + HostHatch shared-Postgres on 170.205.37.148 with 140-lane queue"
- ✓ "Configured shared-Postgres on primary VPS + failover; queue capacity increased"

Internal-infrastructure specifics ARE allowed in commit messages (they're helpful engineering context) but should be anonymized when not strictly necessary.

### MCP decisions
MCP decisions are the cross-session memory. If you log `[SHIPPED via Claude Sonnet 4.5 on HostHatch beast VPS with Supabase pgvector]`, that's fine for internal memory — but if Alex-subscriber-facing agent ever queries a similar topic, the snippet could leak. Sanitize at log-time:
- ✗ "Used Claude to refactor the chat handler; ran Stagehand for QA on HostHatch"
- ✓ "Refactored chat handler via Atlas; visual QA on staging VPS via browser automation"

### Mobile Command replies
Solon's Mobile Command is voice + text. If Solon screenshares during a demo (hypothetically someone's over his shoulder), the replies are live. The atlas_api _titan_system_prompt already explicitly bans the list — verify every reply against that prompt's non-negotiables.

## The safe internal vocabulary

When you want to communicate engineering-specific context internally (MCP, Slack, commits) without tripping the scanner OR leaking if it's screenshared:

| Instead of | Use |
|---|---|
| "Claude Opus 4.6 response" | "Atlas primary" or "primary reasoning layer" |
| "Gemini 2.5 Flash scored" | "primary validator scored" or "dual-validator Gemini" (in commit messages internal only, never in client-facing) |
| "Grok 4.1 Fast scored" | "secondary validator scored" |
| "Stagehand clicked" | "browser automation clicked" |
| "Supabase op_decisions table" | "MCP decision log" |
| "beast VPS" | "primary production VPS" |
| "HostHatch VPS" | "staging VPS" or "failover VPS" |
| "140-lane n8n queue" | "production queue capacity" |
| "kill-chain trigger" | "automated-safety trigger" |
| "ElevenLabs voice clone" | "Atlas voice engine" |
| "Ollama nomic-embed-text" | "memory embedding layer" |
| "Kokoro TTS" | "Atlas TTS" |
| "LiteLLM gateway" | "unified AI gateway" |

## Commit-message-specific exception

**Internal harness files** (`lib/`, `bin/`, `scripts/`, `sql/`, `hooks/`, `plans/doctrine/`, `plans/agents/kb/titan/`, `plans/agents/kb/titan-operator/`) get looser treatment. Engineering clarity > paranoia.

When you write `feat(CT-0417-10): trade-secret scanner + Lumina gate hooks`, mentioning "trade-secret" by name is fine — it's engineering terminology for the thing being scanned, not the banned term itself.

Rule of thumb: if the commit is changing code that handles banned-term logic, you may name the banned terms in the commit message IF the commit only touches whitelisted internal paths. If any client-facing file is in the same commit, sanitize the message.

## The MCP log-decision template

Every `log_decision` call should:

1. Lead with `[CT-XXXX-YY SHIPPED/REVISE/BLOCKED <ISO-timestamp>]`
2. State the deliverable in one line
3. Include BOTH validator scores (Gemini + Grok) + Lumina score if applicable
4. Name the commit hash
5. Name the artifact path(s)
6. End with the next-step — what should the next Titan session do first when it wakes up?

Use "Atlas" / "AMG" / "AI Memory Vault" / "Chamber AI Advantage" freely. Use "Claude" / "beast" / "HostHatch" / "140-lane" / "Stagehand" / "Supabase" / etc. only when the engineering context strictly requires it AND the log is internal-only (project_source=EOM with appropriate tags).

## The meta-rule

If you're ever unsure whether to include a term: check `plans/agents/kb/titan/01_trade_secrets.md` §"Preferred substitutions" table. Default: substitute. Explicit: name. When in real doubt, the substitute path is 100% safe and the risk of over-sanitizing is minor — the risk of under-sanitizing is 2026-04-17-level Solon correction.
