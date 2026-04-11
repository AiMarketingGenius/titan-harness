# Library of Alexandria — Section 6: Fireflies Meetings

**Physical home:** `/opt/amg-titan/solon-corpus/fireflies/` (VPS)
**Harvester:** `/opt/amg-titan/solon-corpus/harvest_fireflies.py` (pre-session, works)
**Current state:** **48 artifacts on disk** (5 high-quality) — reconciled from Fireflies GraphQL API 2026-04-10.

---

## What lives here

Every Fireflies meeting transcript from Solon's Fireflies account: title, attendees, date, duration, raw sentences (speaker-separated), meeting summary (overview + action items + topics + keywords), normalized wrap_artifact JSON.

## Schema

```json
{
  "metadata": {
    "source": "fireflies",
    "source_id": "<transcript id>",
    "title": "...",
    "url": "https://app.fireflies.ai/view/<id>",
    "original_date": "YYYY-MM-DDThh:mm:ssZ",
    "duration_ms": ...,
    "attendees": ["email1@...", "email2@..."],
    "quality_hint": "high|medium|low",
    ...
  },
  "content": {
    "raw": "<speaker-labeled transcript>",
    "summary": "<Fireflies-generated overview>",
    "action_items": [...],
    "keywords": [...],
    "topics": [...]
  }
}
```

## Integration with Thread 2 Proposal Spec Generator

The Thread 2 call-notes → spec.yaml generator (`lib/proposal_spec_generator.py`) reads these Fireflies artifacts directly:

```bash
build_proposal.py --from-fireflies-id <transcript-id> --prospect-json prospect.json --template ... --out ...
```

The extractor:
1. Loads the Fireflies JSON from `/opt/amg-titan/solon-corpus/fireflies/transcripts/<file>.json`
2. Maps attendee emails to prospect metadata (fuzzy match)
3. Runs the 3-step LLM chain (entity extraction → plan matching → spec composition)
4. Emits a valid `spec.yaml` that passes Gates 1+2+3

## Harvest refresh

Re-run the harvester when new meetings land:
```bash
FIREFLIES_API_KEY=<key> python3 harvest_fireflies.py
```
Idempotent — skips existing files.

## Solon action

None — this section is live. Harvest can be re-run whenever new meetings exist.
