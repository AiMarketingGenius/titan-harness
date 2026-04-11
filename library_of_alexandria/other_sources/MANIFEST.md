# Library of Alexandria — Section 7: Other Sources

**Physical home:** `/opt/amg-titan/solon-corpus/slack/` + `/opt/amg-titan/solon-corpus/mcp-decisions/` (VPS) + catch-all for any future source type
**Owner:** Titan (COO)
**Current state:** Slack 19 files, MCP decisions 1 file (bulk-scored tally from Phase 7)

---

## Contents

### Slack (MP-1 Phase 6)
- **Path:** `/opt/amg-titan/solon-corpus/slack/channels/`
- **Artifacts:** 19 channel snapshots, 7 high-quality
- **Content:** message exports from key AMG Slack channels (exec, sales, war-room). Normalized per-channel JSON with date ranges, participant lists, high-signal thread extraction.
- **Harvester:** ad-hoc script run during Phase 6 (2026-04-10). Re-run requires fresh Slack export.

### MCP decisions (MP-1 Phase 7)
- **Path:** `/opt/amg-titan/solon-corpus/mcp-decisions/decisions.jsonl`
- **Artifacts:** 773 decision records (90 high, 682 medium, 1 low)
- **Content:** every `log_decision` call Titan has made across all projects, with rationale + embeddings + conflict-detection output. The canonical record of "why did we decide X."
- **Access:** grep / ripgrep the JSONL directly, or query via `lib/alexandria.py --section other_sources --search "<query>"`.

### Catch-all for future source types

Any new harvest source that doesn't fit into the other 6 canonical sections lands here until it earns its own section. Examples of future candidates:
- **Notion workspaces** — if AMG ever adopts Notion
- **Google Drive documents** — via Drive API
- **GitHub issues / PRs** — already accessible via `gh` CLI but not harvested
- **Telegram / WhatsApp** — if relevant to client conversations
- **Twitter / X DMs** — separate from marketing surface

## Promotion-to-canonical-section policy

When "Other Sources" accumulates >100 artifacts of a single type, that type graduates to its own top-level Library section with its own manifest. Titan proposes the split; Solon approves.

## Solon action

None ongoing — refresh the Slack export when new channels are worth harvesting.
