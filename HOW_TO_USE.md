# titan-harness — How To Use

> A plain-English walkthrough for Solon. Zero jargon. Every command below is copy-paste ready.
> If you want to see any of this run live, say **"Titan, walk me through X"** and I'll execute it for you.

Last updated: 2026-04-10 — covers Phase G.1 (idea hook), G.2 (policy-as-code), G.3 (war room)

---

## The One-Paragraph Summary

The `titan-harness` is the nervous system that wraps every task I (Titan) run for you. It catches ideas you say out loud, enforces the rules you've set down, grades my plans before they go live, and writes an audit log of everything I touch. All configuration lives in **one file** (`policy.yaml`) so you can tune my behavior without me touching code. Every file mentioned below lives in one of two places:

- **Your Mac (canonical):** `~/titan-harness/`
- **Your VPS (runtime):** `/opt/titan-harness/`

The Mac is where we EDIT. The VPS is where things RUN. A push from Mac auto-mirrors to both the VPS and to `github.com/AiMarketingGenius/titan-harness`.

---

## Part 1: The "Lock It" Idea Hook (Phase G.1 — shipped)

### What it does
Whenever you're talking to me (Titan) in Claude Code and you drop the phrase **"lock it"** or the emoji 🔒 anywhere in your message, everything you said gets captured as a raw idea and saved to Supabase. This way nothing you spitball falls on the floor.

### When it runs
Automatically. Every single time you submit a prompt, the hook scans it. No action needed from you.

### Where the captures go
- **Supabase table:** `public.ideas` in project `egoazyasyrhslluossli`
- **Slack ping:** posts to `#amg-admin` with "🔒 Idea locked by mac-solon: [title]"

### How to see your captured ideas
On either Mac or VPS:
```bash
~/titan-harness/bin/idea-list.sh          # lists captured ideas
~/titan-harness/bin/idea-list.sh --status captured   # only unpromoted
```

### How to promote an idea to a real task
```bash
~/titan-harness/bin/idea-promote.sh <idea-id>
```
This moves it from `ideas` → `tasks` table so I start working on it.

### How to delete an idea you regret
```bash
~/titan-harness/bin/idea-delete.sh <idea-id>
```
Soft delete — marks it `dead`, does not actually remove the row (audit trail).

### How to turn it off
Edit `~/titan-harness/policy.yaml` and set `idea_capture.enabled: false`. Then push. Or yell "stop capturing ideas" in Slack and I'll flip it for you.

### Common failure mode
If a capture fails, you'll see nothing in Slack. Check `~/titan-harness/bin/idea-health.sh` — it reports queue length, last drain time, and any errors.

---

## Part 2: Policy As Code — `policy.yaml` (Phase G.2 — shipped)

### What it does
Everything the harness does is driven by **one YAML file**: `policy.yaml`. Change a value there, push, and my behavior changes everywhere — no code edits.

### Where it lives
```
~/titan-harness/policy.yaml
```

### What's inside
Top-level sections:
- `harness` — project ID (currently `EOM`)
- `pre_tool_gate` — which tools require an active task before I can use them
- `idea_capture` — the "lock it" hook config (trigger phrase, emoji, etc.)
- `idea_drain` — how often the drainer pushes ideas to Supabase
- `war_room` — the Perplexity grading loop config (see Part 3)
- `install_test` — self-test config

### Common edits you might want to make
| What you want | What to change |
|---|---|
| Change the idea trigger word from "lock it" to something else | `idea_capture.trigger_phrase: "remember this"` |
| Stop the drainer from pinging Slack on every capture | `idea_drain.slack.enabled: false` |
| Raise the war room cost ceiling | `war_room.cost_ceiling_cents_per_exchange: 50` |
| Turn off war room entirely | `war_room.enabled: false` |
| Let me use Write/Edit without an active task (NOT recommended) | `pre_tool_gate.require_active_task: false` |

### How to apply a change
1. Edit `~/titan-harness/policy.yaml` on your Mac
2. `cd ~/titan-harness && git add policy.yaml && git commit -m "tune: X" && git push`
3. Mirror auto-syncs to VPS. I pick up the new values on next hook fire.

Or just tell me in plain English: "Titan, change the war room cost ceiling to 50 cents" and I'll do the edit + commit + push for you.

---

## Part 3: The War Room (Phase G.3 — shipped TODAY)

### What it does
Before I mark a plan, spec, or architecture doc as "done", it goes through Perplexity (the sonar-pro model) for an **independent grade**. If Perplexity says it's A or B, I ship it silently. If it's C or worse, I send it back to Claude Haiku to revise based on Perplexity's feedback, then re-grade. Up to 3 rounds. Hard cost cap: 25 cents per round, 75 cents per session max. **You only get a Slack ping if the final grade is C or below** — the questionable ones. A and B never bother you.

### Where the files live
| File | Role |
|---|---|
| `lib/war_room.py` | The brain — grades, revises, logs |
| `bin/war-room.sh` | The CLI — you can run it manually |
| `bin/war-room-shim.sh` | The auto-trigger — decides which tasks get war-roomed |
| `sql/003_war_room_exchanges.sql` | The audit table schema |
| Supabase `public.war_room_exchanges` | Every single round of every session, logged forever |

### When the war room auto-fires
The shim looks at the task's `task_type` and `tags`. It fires when **any** of these match:
- `task_type` contains the word `plan`, `architecture`, `spec`, or `phase`
- `tags` include any of: `war_room`, `plan_finalization`, `architecture_decision`, `phase_completion`

Routine client work (blog writes, SEO audits, product copy) is **not** graded — it would burn Perplexity budget for no reason.

### How to war-room something manually (from Mac or VPS)
```bash
# Grade a file and just print the grade
~/titan-harness/bin/war-room.sh \
  --input ~/path/to/plan.md \
  --phase "MP-1" \
  --trigger plan_finalization

# Grade and write the (possibly revised) version to a new file
~/titan-harness/bin/war-room.sh \
  --input ~/path/to/plan.md \
  --output ~/path/to/plan.refined.md \
  --phase "MP-1" \
  --trigger plan_finalization

# Pipe mode — grade whatever's in your clipboard or stdin
cat some-spec.md | ~/titan-harness/bin/war-room.sh \
  --phase "architecture" \
  --trigger architecture_decision
```

Or just say **"Titan, war-room this"** and point me at the text.

### How to see the results
Every war-room run writes to `public.war_room_exchanges` in Supabase. You can query it directly, or ask me:

- **"Show me the last 5 war-room sessions"** → I'll pull from Supabase and summarize
- **"Show me every C-grade or below from this week"** → same
- **"What did Perplexity say about the MP-1 plan?"** → I pull the group by `phase='MP-1'` and walk you through the issues

### The Slack pings you'll get
You'll **only** see a Slack message when:
- Final grade is C, D, F, or ERROR (the noise filter)
- Each ping includes: phase, trigger, round count, terminal reason, cost, and the `exchange_group_id` so you can jump straight to the Supabase row

Example:
> :warning: **War Room — grade C needs eyeballs**
> Project/Phase: EOM / MP-1 (plan_finalization)
> Rounds: 3 | Terminal: `max_rounds` | Cost: `10.50¢`
> Group ID: `3cc22bcf-fc54-4d10-982a-9c6cc9ac3551`
> Plan lacks concrete token accounting and error handling paths.

### How to turn it off
```bash
# Quick toggle in policy.yaml
# war_room.enabled: true   → false
```
Or just say "Titan, turn off the war room."

### Common failure modes
- **"Skipped: no-trigger"** — task's type/tags didn't match. Add a tag like `war_room` if you want it graded.
- **"Skipped: too-short:150b"** — deliverable was under 200 bytes. Not worth grading.
- **"graded:C:3:10.50:kept-original"** — war room ran, Haiku's revision blew up past 5× the original size, so the size-sanity guard rejected it and kept the original text. Still logged in Supabase.
- **"war-room failed rc=2"** — usually means `PERPLEXITY_API_KEY` isn't in env. Check `/opt/titan-processor/.env` on VPS.

---

## Part 4: What Lives Where — The File Map

```
~/titan-harness/                        ← canonical (edit here)
├── policy.yaml                         ← the config file. Change behavior here.
├── install.sh                          ← one-time installer. Re-run after policy edits.
├── README.md                           ← the tl;dr
├── HOW_TO_USE.md                       ← THIS DOC
├── bin/
│   ├── idea-list.sh                    ← list captured ideas
│   ├── idea-promote.sh                 ← promote idea → task
│   ├── idea-delete.sh                  ← soft-delete an idea
│   ├── idea-edit.sh                    ← edit an idea
│   ├── idea-drain.sh                   ← manually trigger the queue drainer
│   ├── idea-health.sh                  ← check drainer health
│   ├── war-room.sh                     ← grade a doc via Perplexity + Haiku
│   └── war-room-shim.sh                ← auto-trigger for titan-queue-watcher
├── hooks/
│   ├── user-prompt-idea.sh             ← catches "lock it" on every prompt
│   ├── pre-tool-gate.sh                ← blocks Write/Edit without active task
│   ├── post-tool-log.sh                ← audit log for every tool I use
│   ├── session-start.sh                ← boot audit on new session
│   └── session-end.sh                  ← cleanup on session end
├── lib/
│   ├── titan-env.sh                    ← loads env vars for hooks
│   ├── policy-loader.sh                ← parses policy.yaml → env vars
│   └── war_room.py                     ← Perplexity + Claude grading loop
├── services/
│   ├── titan-ideas-drain.service       ← systemd unit (VPS)
│   ├── titan-ideas-drain.timer         ← systemd timer (VPS, every 60s)
│   ├── com.titan.ideas.drain.plist     ← launchd plist (Mac)
│   └── titan-queue-watcher.patch.md    ← docs for the queue-watcher patch
└── sql/
    ├── 001_ideas_table.sql             ← public.ideas schema
    └── 003_war_room_exchanges.sql      ← public.war_room_exchanges schema
```

---

## Part 5: The "Ask Titan" Shortcuts

You never have to run any of this yourself. These phrases in Slack or chat will make me do the work:

| Say this | I'll do this |
|---|---|
| "Titan, show me today's captured ideas" | Query `public.ideas WHERE created_at > today` |
| "Titan, promote idea <id>" | Move from ideas → tasks |
| "Titan, war-room this plan" | Run bin/war-room.sh on whatever you point at |
| "Titan, show me the last war-room session" | Query `public.war_room_exchanges` newest group, walk you through it |
| "Titan, any C-grades this week?" | Same table, filtered on `grade IN ('C','D','F','ERROR')` |
| "Titan, turn off the war room" | Edit policy.yaml, commit, push |
| "Titan, raise the war-room cost ceiling to 50¢" | Same |
| "Titan, walk me through <anything>" | Live demo via screen share / Stagehand |
| "Titan, what's in policy.yaml right now?" | Read + summarize the active config |

---

## Part 6: Emergency Kill Switches

If anything goes sideways and you just want it **off**, these are the levers:

```bash
# --- Stop the idea hook from capturing ---
# Edit policy.yaml: idea_capture.enabled: false → push

# --- Stop the drainer from pushing ideas to Supabase ---
ssh -i ~/.ssh/id_ed25519_amg root@170.205.37.148 \
  "systemctl stop titan-ideas-drain.timer"

# --- Stop the war room from auto-grading anything ---
# Edit policy.yaml: war_room.enabled: false → push

# --- Stop the queue watcher entirely (nuclear) ---
ssh -i ~/.ssh/id_ed25519_amg root@170.205.37.148 \
  "systemctl stop titan-queue-watcher"

# --- Restore queue-watcher to pre-G.3 state (un-wire war room) ---
ssh -i ~/.ssh/id_ed25519_amg root@170.205.37.148 \
  "cp /usr/local/bin/titan_queue_watcher.py.pre-g3-bak \
      /usr/local/bin/titan_queue_watcher.py && \
   systemctl restart titan-queue-watcher"
```

Or just say **"Titan, kill X"** and I'll pull the right lever.

---

## Part 7: What's Next (So You Know What To Expect)

Still to ship:
- **G.4** — wrap MP-1 (Solon OS corpus harvest) and MP-2 (synthesis) in the harness so their blueprints auto-grade through the war room
- **MP-1 harvest resume** — actually run the harvest
- **Atlas Layer 2 portal** — the client-facing UI layer
- **Voice AI Path B** — RunPod worker for the voice side

After each one ships, this doc gets a new "Part N" section. If I ever mark something "done" without teaching you how to use it, call me out — that's a violation of your standing rule and I need to fix it immediately.

---

## Questions you might have right now

**Q: Do I need to memorize any of this?**
No. This doc exists so you don't have to. I know all of it. Just ask me in plain English.

**Q: Can I read the war-room Supabase rows myself without asking you?**
Yes — go to `https://egoazyasyrhslluossli.supabase.co/project/_/editor` and open the `war_room_exchanges` table. But it's usually faster to just say "Titan, show me X."

**Q: What if I want to try something experimental without breaking production?**
Tell me "sandbox mode" and I'll work off a branch or a temp file. Nothing I do in the harness touches production Supabase rows unless I explicitly commit + push.

**Q: Can this whole thing be undone?**
Yes. Every file has a backup (`.pre-g3-bak`, `.pre-g2-bak`, etc.) on the VPS. Revert procedure for each phase is documented in `services/titan-queue-watcher.patch.md` and the per-phase commit messages.
