# Library of Alexandria — Section 2: Perplexity Threads

**Physical home (harvested JSON):** `/opt/amg-titan/solon-corpus/perplexity/` (VPS)
**Physical home (raw screenshots):** `library_of_alexandria/perplexity_threads/raw_history_screens/` (repo-local, this dir)
**Physical home (OCR catalog):** `library_of_alexandria/perplexity_threads/perplexity_catalog.md`
**Harvester:** `/opt/amg-titan/solon-corpus/harvest_perplexity.py` (shipped 2026-04-11, pending `PERPLEXITY_COOKIE_HEADER` env var from Solon)
**Current state:** 2 artifacts on disk (stub harvest). Full harvest pending Solon 2FA session.

---

## Subfolders

- **`raw_history_screens/`** — Solon drops full-page screenshots of his Perplexity Threads history here. Titan OCRs them, extracts title + date + snippet + shared URL, builds the catalog table in `perplexity_catalog.md`.
- **`harvested/`** → symlink / reference to `/opt/amg-titan/solon-corpus/perplexity/` on the VPS. Populated by the harvester.

---

## Catalog format (`perplexity_catalog.md`)

```markdown
| Approx Date | Title | Snippet | Shared URL | Canon? |
|---|---|---|---|---|
| 2026-03-15 | Voice AI v2 architecture critique | "For voice AI, you need separate STT and LLM..." | https://www.perplexity.ai/search/... | ⬜ |
| 2026-04-03 | Merchant stack analysis | "Paddle's underwriting for AI services is..." | https://www.perplexity.ai/search/... | ⬜ |
```

Canon column flips to ✅ when a thread is promoted to Library canon (linked from `ALEXANDRIA_INDEX.md` + announced to `#titan-aristotle`).

---

## Promotion-to-canon flow

1. Titan or Aristotle identifies a thread worth keeping
2. Titan calls `lib/alexandria.py --promote perplexity_threads --source "<catalog row id>" --note "<why>"`
3. `alexandria.py` copies the full JSON to `library_of_alexandria/perplexity_threads/promoted/<slug>.json`
4. `alexandria.py` appends a line to `ALEXANDRIA_INDEX.md` under this section
5. `lib/aristotle_slack.post_update()` fires a notification to `#titan-aristotle`
6. RADAR updated automatically on next refresh cycle

---

## Solon action items

- **Drop screenshots** in `raw_history_screens/` whenever you have time — Titan OCRs them asynchronously
- **Provide Perplexity session cookie header** (Solon action #3b in NEXT_TASK) — unblocks full thread harvest
- **Review promoted threads** periodically (Titan surfaces via Aristotle) — confirm or reject canonization
