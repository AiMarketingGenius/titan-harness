# ENV_DIFFS_MCP.md

> Ironclad architecture §5.5 — per-environment variable map + write-rules.
> Enforced at import time by `lib/env_guard.py`.

## Mac (`~/titan-harness`)

- `TITAN_ENV=mac`
- `TITAN_HARNESS_DIR=~/titan-harness`
- `SUPABASE_URL` — from macOS keychain (`security find-generic-password -a solon -s titan_supabase -w`)
- `GITHUB_TOKEN` — from macOS keychain (`security find-generic-password -a solon -s titan_github -w`)
- `SSH_KEY_PATH=~/.ssh/id_titan_vps`
- `TITAN_VPS_HOST=root@170.205.37.148`
- Writable: yes (pre-commit + post-commit hooks active)

## VPS (`/opt/titan-harness-work`)

- `TITAN_ENV=vps`
- `TITAN_HARNESS_DIR=/opt/titan-harness-work`
- `SUPABASE_URL` — from `/etc/titan-secrets.env` (700, root)
- `GITHUB_TOKEN` — from `/etc/titan-secrets.env`
- Writable: yes (working tree; bare repo at `/opt/titan-harness.git` is the push target)

## MCP / EOM (`/opt/mcp/titan-context`)

- `TITAN_ENV=mcp`
- `TITAN_HARNESS_DIR=/opt/mcp/titan-context`  (read-only export)
- **No write permissions.** Any import of a writing module raises via `env_guard.assert_writable`.
- Exported artifacts:
  - `doctrine/` — mirror of root-level doctrine files
  - `CLAUDE.md`, `CORE_CONTRACT.md`, `RADAR.md`, `policy.yaml`
  - `SPRINT_STATE.json` — current sprint + CTs
  - `snapshot-ts.txt` — ISO timestamp of last sync

## Rules

1. Any script that mutates harness state MUST `from env_guard import assert_writable`
   at the top and call it before any filesystem or git write.
2. Secrets never appear in the harness repo. `.gitignore` + `git secrets` pre-commit
   hook block commits that would include them.
3. The MCP export is regenerated ONLY by the VPS post-receive hook
   (`/opt/titan-harness.git/hooks/post-receive`, installed per §2.5).
4. EOM sessions read `snapshot-ts.txt` at start. If older than 5 minutes, they run
   `bin/mcp-sync.sh` before proceeding.
