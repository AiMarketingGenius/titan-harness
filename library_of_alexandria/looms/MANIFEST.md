# Library of Alexandria — Section 5: Looms

**Physical home:** `/opt/amg-titan/solon-corpus/loom/` (VPS)
**Harvester:** `/opt/amg-titan/solon-corpus/harvest_loom.py` (shipped pre-session, pending creds)
**Current state:** 0 artifacts (blocker: Solon Loom API key OR Loom cookie header).

---

## What will live here

Every Loom recording Solon has made: transcript (from Loom's built-in ASR), title, duration, view URL, viewer stats, and a normalized MP-1 wrap_artifact JSON. Video bytes are NOT copied — only metadata + transcript text.

## Harvest paths

- **Path A (preferred):** `LOOM_API_KEY=<key>` from Loom account settings → Developer → API keys
- **Path B:** `LOOM_COOKIE_HEADER=<cookie bundle>` from Loom DevTools if API key not available

## Thread 3 Recurring Marketing Engine integration

The marketing engine (`lib/marketing_engine.py`) reuses Loom content as a source for the **Opus Clip repurposing path** — when a new Loom ships with high-value teaching content, Titan can auto-package it into short-form clips for the weekly marketing surface. See `plans/PLAN_2026-04-11_recurring-marketing-engine.md` Phase 3.

## Solon action

See NEXT_TASK action #3c — Loom creds (either API key or cookie).
