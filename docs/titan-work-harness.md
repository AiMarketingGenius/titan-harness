TITAN WORK HARNESS — MANDATORY FOR ALL MULTI-STEP TASKS
Version: 2.0 | Supersedes all prior harness docs

══════════════════════════════════════════════════════════════════

IRON LAW: You stop when your message ends. Period.

══════════════════════════════════════════════════════════════════

EVERY TURN YOU MUST:

  STEP 1 — TURN OPEN
    Write the TITAN TURN OPEN block (task, checkpoint, status).

  STEP 2 — DO REAL WORK
    Make tool calls. Run bash. Write files. Commit.
    Every claim must be backed by output in this same turn.

  STEP 3 — CHECKPOINT REPORT
    End with the full TITAN CHECKPOINT REPORT block.
    No exceptions. No partial reports.

  STEP 4 — NEXT PROMPT
    Give Solon the exact copy-paste prompt for the next turn.

══════════════════════════════════════════════════════════════════

FORBIDDEN PHRASES (any of these = automatic stall flag):

  ✗  "I'm working in the background"
  ✗  "Continuing after this message"
  ✗  "I'll handle that next"
  ✗  "Working on it now" [without a tool call following immediately]
  ✗  "This will take a moment" [without a tool call following immediately]
  ✗  "I've completed X" [without proof in this turn]
  ✗  Any future-tense promise without same-turn evidence

══════════════════════════════════════════════════════════════════

STALL RULE:
  If you cannot complete the declared checkpoint:
    - Say so immediately.
    - State exactly why.
    - Show what was partially done (with evidence).
    - Give the resume prompt.
    - Do NOT go silent. Do NOT fabricate completion.

══════════════════════════════════════════════════════════════════

APPLIES TO: Hermes/voice stack, Atlas subsystems, MP-3, MP-4,
            CT series tasks, infra changes, all other multi-step work.
