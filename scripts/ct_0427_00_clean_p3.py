#!/usr/bin/env python3
"""Clean up P3 Anthropic warning text in master doc — final 16/16 polish."""
import re

MASTER = "/home/amg/kb/AMG_UNIFIED_MASTER_CREDENTIALS.md"

with open(MASTER) as f:
    content = f.read()

# Remove the now-stale "MANUAL ROW — SOLON FILL ONLY THIS ONE" warning + fallback path
# Keep only the row that's already filled with the actual key
new_block = """### P3. Anthropic API key — achilles_fallback

✅ **FILLED 2026-04-27** — Solon-supplied via console.anthropic.com.
Key created in console with label `amg_admin_titan` (functions as a regular
API key for `achilles_fallback` agent — verified working on /v1/models +
/v1/messages haiku ping). Anthropic Admin API requires `sk-ant-admin01-*`
tier key (not yet provisioned); future programmatic key creation deferred
until that admin tier is available.

| Agent | Key | Status |
|-------|-----|--------|
| `achilles_fallback` | `<KEY_REDACTED_FROM_SOURCE>` | verified 2026-04-28T01:03Z (live on /v1/models + /v1/messages haiku ping) |
"""

# Match the entire P3 block (between '### P3. Anthropic' and '### P4.')
pattern = (
    r"### P3\. Anthropic API key — achilles_fallback\n.*?"
    r"(?=### P4\. Post-CT-0427-01)"
)
new_content, n = re.subn(pattern, new_block + "\n", content, flags=re.DOTALL)
print(f"replacements made: {n}")

# Sanity check
if "MANUAL ROW — SOLON FILL" in new_content:
    # Only the SECTION P P3 should have been touched; if there are OTHER MANUAL ROW
    # markers (unlikely), they stay
    print("WARN: MANUAL ROW marker still present somewhere")
if "FILLED 2026-04-27" not in new_content:
    print("FAIL: replacement didn't insert FILLED marker")
    raise SystemExit(2)

with open(MASTER, "w") as f:
    f.write(new_content)

print(f"master doc lines: {len(new_content.splitlines())}")
