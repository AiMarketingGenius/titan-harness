# TITAN BLOCKER ESCALATION LADDER
**Date:** 2026-04-17 EOD
**Supersedes:** Addendum guardrail 4.3 (auto-Perplexity consult) — this is the refined escalation ladder

---

## THE LADDER

When Titan hits a wall (stuck, blocked, can't proceed):

### Rung 1 — Self-solve (5 min)
Quick diagnostic. Check logs, retry once, look at immediate error. If resolved in 5 min → proceed.

### Rung 2 — Sonar Basic (default unblock tool)
If still stuck after 5 min → query Perplexity **Sonar Basic** via API.

- Use as-is. No Deep Research.
- No multi-step research prompts.
- Simple query: describe the blocker, ask for solution.
- Apply the answer. If it works → proceed, log decision to MCP.

### Rung 3 — Sonar Pro (only if Sonar Basic fails)
If Sonar Basic's answer doesn't resolve → escalate to Sonar Pro, same simple query pattern.

- Still no DR.
- Still no multi-step research.
- One query, take the answer, try it.

### Rung 4 — Escalate to Solon
If Sonar Pro also fails → log blocker to `#solon-command` with:
- What's broken
- What Sonar Basic said (with URL/snippet)
- What Sonar Pro said (with URL/snippet)
- What Titan tried
- Recommended next move

---

## COST CONTEXT

- Sonar Basic: $1/M input + $1/M output + $5/1,000 grounding requests
- Sonar Pro: $3/M input + $15/M output + $5/1,000 grounding
- Typical blocker query: ~1,500 input / 800 output / 1 grounding
  - Sonar Basic per query: ~$0.008
  - Sonar Pro per query: ~$0.017

At 20 Sonar Basic queries/week: ~$8.50/year. Trivial.

---

## RULES

- **Never skip Sonar Basic** — it's the default. Don't jump straight to Pro.
- **No Deep Research** on blockers. DR is for strategic analysis, not unblocking.
- **One query per rung.** If the answer doesn't work, escalate, don't re-query the same rung.
- **Log every Sonar query + answer to MCP** with tag `titan-blocker-unblock` for pattern analysis.
- **15-min timer** from blocker-start to Rung 2. Don't let Titan spin for 30 minutes on Rung 1.

---

## WHAT NOT TO DO

- No Deep Research for day-to-day blockers
- No Grok adjudication for blockers (Grok is a grader, not an unblocker)
- No "let me investigate further" loops without going up a rung
- No quiet stuck-mode — if Titan's stuck, MCP sees it

---

**This replaces guardrail 4.3 in TITAN_AUTONOMY_GUARDRAILS_AND_DUAL_GRADER_MATH.md with the refined ladder above.**
