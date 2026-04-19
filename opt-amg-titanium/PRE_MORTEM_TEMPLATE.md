# Pre-mortem template

**Purpose:** every production-bound commit carries a 3-question
pre-mortem file committed alongside the change. `pre-proposal-gate.sh`
blocks commits without it. 48 hours post-ship, Titan checks whether
the actual outcome matches the pre-mortem answers; mismatches feed
the post-mortem-to-rule pipeline (Titanium Gap 1).

## Filename convention

`PRE_MORTEM_<CT-ID>_<yyyy-mm-dd>.md` at the commit root, e.g.
`PRE_MORTEM_CT-0419-09_2026-04-19.md`.

## Three mandatory questions

### Q1 — Most likely failure mode in the next 48 hours

Specific, not generic. "It might fail" is not an answer. "The
Supabase RLS policy on `cross_project_session_state` could reject
thread-close writes from the titan service role if the policy treats
titan as a regular user" is an answer.

### Q2 — Exact rollback procedure

Commands or MCP task-id to invoke. Not "revert the commit". Write
the actual sequence:

```
1. git revert <commit-sha>
2. git push origin master
3. ssh vps 'cd /opt/titan-harness && git fetch && git reset --hard origin/master'
4. ssh vps 'systemctl restart amg-titanium-post-mortem.timer'
5. MCP log_decision tag=[rollback, titanium-v1.0, <ct-id>]
```

### Q3 — Leading indicator visible BEFORE full failure

Log pattern, metric threshold, user report, probe output. "Users
would complain" is not an answer. "`regression_integrity_probe.sh`
probe #7 (Paddle-only reference scan) returns >0 hits OR the daily
heartbeat log at `/opt/amg-mcp-archive/heartbeat.log` shows
consecutive failures ≥2" is an answer.

## Worked example — CT-0419-08 permission plague fix

### Q1
Claude Code update 1.x.y changes the grammar of `permissions.allow`
such that the new specific-path globs we added (`Edit(/Users/.../**)`)
stop being honored while the bare wildcards remain. Titan autonomous
runs would start prompting again despite the fix.

### Q2
1. `git revert e26097a`
2. `git push origin master`
3. Solon reloads Hammerspoon: `open hammerspoon://reload`
4. Titan `log_decision` tag=[rollback, ct-0419-08, permission-plague-regression]
5. Open Tasks queue, re-queue CT-0419-08-v2 with updated allow-list grammar

### Q3
Hammerspoon `~/titan-harness/logs/auto_approve.log` shows
`skipped_not_whitelisted` events within 1 hour of a Claude Code
update being installed. OR Solon observes a live Allow/Deny dialog
mid-autonomous run.

## 48-hour match review

After 48 hours, Titan re-opens the pre-mortem file and answers:

- **Did Q1's failure mode hit?** yes/no + evidence
- **If yes, did Q3's indicator catch it before Solon noticed?** yes/no
- **If Q1 mode hit AND Q3 indicator was NOT caught** → GAP. Feed it
  to `post_mortem_to_rule.sh` with tag `[pre-mortem-gap, indicator-missing]`.
- **If Q1 mode hit AND Q3 indicator caught** → validates the probe;
  no action needed beyond a confirmation log.
- **If Q1 mode did not hit** → either the pre-mortem was accurate
  (no issue) OR it was inaccurate (we missed the actual failure
  mode). The second case also feeds post-mortem-to-rule with tag
  `[pre-mortem-miss, failure-mode-prediction-gap]`.

Review is appended to the same pre-mortem file; the commit history
shows the evolution.
