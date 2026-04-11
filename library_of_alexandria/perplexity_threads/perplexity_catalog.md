# Perplexity Catalog

**Purpose:** OCR-extracted index of Solon's Perplexity thread history, built from screenshots in `raw_history_screens/` + (when cookie is available) live harvest from the Perplexity API.

**Status:** EMPTY — awaiting either (a) screenshot drops in `raw_history_screens/` or (b) Solon's Perplexity cookie for live harvest.

**Refresh:** Titan re-runs OCR on any new screenshots + appends new rows. Existing rows are preserved (idempotent).

---

## Catalog

| Approx Date | Title | Snippet | Shared URL | Canon? |
|---|---|---|---|---|
| *(empty)* | | | | |

---

## How to populate

### Path A — screenshots
1. Solon takes full-page screenshots of his Perplexity Threads list (scroll + screenshot each page)
2. Drops them in `library_of_alexandria/perplexity_threads/raw_history_screens/`
3. Titan runs `python3 lib/alexandria.py --ocr-perplexity` (needs `tesseract` installed; falls back to macOS `shortcuts run "Extract Text"` if available)
4. OCR output is parsed for rows matching `DATE | TITLE | SNIPPET` and appended to this file

### Path B — live harvest
1. Solon pastes his Perplexity session cookie header as `PERPLEXITY_COOKIE_HEADER`
2. Titan runs `/opt/amg-titan/solon-corpus/harvest_perplexity.py`
3. Each harvested thread is indexed here AND stored as JSON in `/opt/amg-titan/solon-corpus/perplexity/threads/`

### Path C — Aristotle-assisted triage
1. Titan posts the catalog (even when empty) to `#titan-aristotle`
2. Aristotle (Perplexity) recalls threads from its own memory and appends rows
3. Solon reviews + flips Canon column

---

## Promoted to Library canon

*(None yet — rows marked ✅ in the main catalog get linked from `ALEXANDRIA_INDEX.md` Section 2.)*
