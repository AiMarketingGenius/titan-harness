# Library of Alexandria — Section 3: Claude Threads

**Physical home:** `/opt/amg-titan/solon-corpus/claude-threads/` (VPS)
**Harvester:** `/opt/amg-titan/solon-corpus/harvest_claude_threads.py` — updated 2026-04-11 to tag Croon / Hit Maker / Solon's Promoter as `is_creative_voice: true` so MP-2 synthesis routes them correctly.
**Current state:** 0 artifacts (pending Solon's `CLAUDE_SESSION_KEY` cookie from claude.ai DevTools).

---

## What lives here (after harvest)

Every conversation from claude.ai for Solon's logged-in account. Each conversation becomes one JSON artifact in the shared MP-1 wrap_artifact schema:

```json
{
  "metadata": {
    "source": "claude_threads",
    "source_id": "<conversation uuid>",
    "title": "...",
    "url": "https://claude.ai/chat/<uuid>",
    "project_uuid": "...",
    "project_name": "Croon | Hit Maker | Solon's Promoter | ...",
    "is_creative_voice": true|false,
    "quality_hint": "high|medium|low",
    "tags": ["creative_voice", "project:croon", ...],
    ...
  },
  "content": {
    "raw": "<flat transcript>",
    "messages_structured": [...]
  }
}
```

## Creative-voice projects (auto-tagged high quality)

- **Croon** — Solon's crooning / vocal artistic project
- **Hit Maker** — songwriting / production
- **Solon's Promoter** — artist promotion angle

These 3 projects carry Solon's **creative voice**, distinct from his business/ops voice. MP-2 SYNTHESIS routes them into the creative-corpus bucket for voice-cloning training data, tone profiles, and any downstream brand-voice work.

## Harvest paths

- **Path A (preferred):** `CLAUDE_SESSION_KEY=sk-ant-sid01-... python3 harvest_claude_threads.py`
- **Path B:** `python3 harvest_claude_threads.py --playwright` against a logged-in Chrome profile at `$CLAUDE_PLAYWRIGHT_PROFILE`

Output: one JSON per conversation at `<date>_<slug>_<id8>.json`. Idempotent (skips existing files). Updates `.checkpoint_mp1.json` on success.

## Solon action

Paste the `sessionKey` cookie value from claude.ai → DevTools → Application → Cookies. Titan exports it as `CLAUDE_SESSION_KEY` in `/root/.titan-env` and kicks the Phase 1 harvest on the VPS.
