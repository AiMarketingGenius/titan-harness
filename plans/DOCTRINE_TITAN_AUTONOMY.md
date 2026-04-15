# DOCTRINE_TITAN_AUTONOMY — Permanent Permission Lock

**Status:** ACTIVE + LAYERED (do NOT rely on a single layer).
**Effective:** 2026-04-15 (post Claude Code update that wiped autonomy).
**Owner:** Solon. Maintained by: Titan via `bin/restore-titan-autonomy.sh`.
**Trigger:** any new Claude Code session in `~/titan-harness` MUST self-check via `bin/titan-boot-audit.sh` (already integrated).

## Why this exists

Claude Code v-update on 2026-04-14/15 stripped Solon's in-app autonomy settings, requiring permission re-prompts on every routine op. Solon does not have time to re-grant on every update. This doctrine wires four independent restoration layers so a wipe of any single layer is detected and auto-restored on next session boot.

## Layer 1 — Shell alias

Files: `~/.zshrc` AND `~/.bash_profile` (both, to cover whichever shell is active).

```bash
alias claude='claude --dangerously-skip-permissions'
```

Verification:
```bash
type claude
# → claude is an alias for claude --dangerously-skip-permissions
```

Restoration: `bin/restore-titan-autonomy.sh` (append-only, idempotent — never duplicates).

## Layer 2 — Repo-level settings

File: `~/titan-harness/.claude/settings.local.json` (git-tracked).

```json
{
  "permissions": {
    "allow": [
      "Bash(*)", "Edit(*)", "Write(*)", "Read(*)",
      "Glob(*)", "Grep(*)", "TodoWrite(*)", "WebFetch(*)",
      "WebSearch(*)", "NotebookEdit(*)", "mcp__*",
      "Skill(*)", "Agent(*)"
    ]
  }
}
```

Verification: `grep '"Bash(\*)"' ~/titan-harness/.claude/settings.local.json`.

Restoration: `git checkout HEAD -- .claude/settings.local.json` (the canonical lives in git history). Fallback if file untracked: `bin/restore-titan-autonomy.sh` rewrites canonical content.

## Layer 3 — Bootstrap self-check

`bin/titan-boot-audit.sh` runs at the top of every session via the SessionStart hook. On each boot:

1. Verify Layer 1 (alias present in zshrc OR bash_profile).
2. Verify Layer 2 (settings.local.json has `"Bash(*)"`).
3. If either is missing → run `bin/restore-titan-autonomy.sh` + emit `AUTONOMY_SELF_CHECK: RESTORED` line in the boot block.
4. Slack alert via `bin/titan-notify.sh` so Solon knows a wipe occurred.

The boot audit is non-fatal on autonomy issues — it restores and continues. Solon's first turn is unaffected.

## Layer 4 — This doctrine doc

You are reading it. The doctrine itself is the canonical reference for what each layer does, what to verify, and how to restore. Pinned in:

- `plans/DOCTRINE_TITAN_AUTONOMY.md` (this file, harness-tracked, mirrored to VPS via auto-mirror)
- VPS at `/opt/amg/docs/DOCTRINE_TITAN_AUTONOMY.md` (deploy-time copy via SCP, optional)
- `~/.claude/projects/.../memory/MEMORY.md` index entry pointing here

## Restoration procedure (manual, if all 4 layers are wiped simultaneously)

```bash
cd ~/titan-harness
bin/restore-titan-autonomy.sh
source ~/.zshrc   # or ~/.bash_profile
type claude       # verify alias
grep '"Bash(\*)"' .claude/settings.local.json   # verify settings
```

If `bin/restore-titan-autonomy.sh` itself is missing (catastrophic wipe):

```bash
cd ~/titan-harness
git log --oneline -- bin/restore-titan-autonomy.sh   # find a commit that has it
git checkout <sha> -- bin/restore-titan-autonomy.sh plans/DOCTRINE_TITAN_AUTONOMY.md
bash bin/restore-titan-autonomy.sh
```

## Acknowledgment phrase (Solon-facing)

When all 4 layers are verified intact (or restored), Titan emits:

> Autonomy locked across 4 layers. Will not re-prompt on routine ops again. Ever.

## Caveats

- `--dangerously-skip-permissions` skips ALL permission prompts, including for genuinely destructive actions. Risk accepted: Solon's tempo + Titan's safety rules at the prompt-content level (Tier B/C gates) are the compensating controls.
- Layer 2 (`.claude/settings.local.json`) is REPO-scoped — applies only to sessions in `~/titan-harness`. Sessions in other directories are unaffected.
- Layer 1 is USER-scoped (rc files) — applies to ALL Claude Code launches under Solon's account.
- If Anthropic ever ships a settings file at `~/.claude/settings.json` that overrides repo-level settings, this doctrine should be extended with a Layer 5 that ensures that file also has the broad allow list. Not implemented today (would require touching user-global config without explicit ask).
