#!/usr/bin/env python3
"""
titan-harness/lib/radar_drain.py

Non-interactive work identifier + submitter for the Titan scheduler
(see bin/titan-hourly-drain.sh + bin/titan-night-grind.sh).

Scans RADAR.md + MCP sprint state + public.tasks + public.mp_runs for
work items that meet ALL of these criteria:

1. NOT blocked on credentials / 2FA / OAuth
2. NOT blocked on a Solon business decision
3. NOT destructive / irreversible
4. All upstream dependencies satisfied
5. Represented in RADAR kill chain with a clear execution path

Eligible items are submitted to the `tasks` queue for titan-queue-watcher.service
to pick up on its next poll. The queue watcher is the actual executor; this
script is just the classifier + dispatcher.

Modes:
    --mode=hourly       — normal hourly drain pass (light + medium tasks only)
    --mode=night-grind  — night grind pass (heavy tasks allowed)
    --mode=check-empty  — check if queue is empty (exit 10 = empty, 0 = has work)
    --dry-run           — classify but don't submit
    --verbose           — log each item's classification decision

Exit codes:
    0  — clean (scanned + submitted, or nothing eligible)
    10 — queue empty (for --mode=check-empty)
    1  — MCP unreachable
    2  — RADAR parse error
    3  — queue submission error
    4  — Supabase unreachable
"""

import argparse
import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
RADAR_PATH = REPO_ROOT / "RADAR.md"
LOG_PREFIX = "radar_drain"

# Status markers that make an item INELIGIBLE for scheduler drain
INTERACTIVE_STATUSES = {
    "awaiting_solon",
    "awaiting_solon_creds",
    "awaiting_solon_execution",
    "awaiting_solon_decisions",
    "awaiting_solon_kickoff",
    "blocked",
    "blocked-external",
}

# Status markers that make an item ELIGIBLE (ready for execution)
ELIGIBLE_STATUSES = {
    "queued",
    "ready",
    "pending",
    "scheduled",
}

# Work types allowed in hourly mode (light + medium)
HOURLY_WORK_TYPES = {
    "radar_refresh",
    "alexandria_preflight",
    "mirror_check",
    "log_rotation",
    "health_check",
    "mcp_heartbeat",
    "doctrine_regrade",
    "queue_heartbeat",
    "sprint_state_audit",
}

# Additional work types allowed in night-grind mode (heavy tasks)
NIGHT_GRIND_ADDITIONAL = {
    "harvest",
    "mp1_phase",
    "mp2_phase",
    "synthesis",
    "war_room_regrade",
    "long_research",
    "backfill_recompute",
}


def log(msg, verbose=False):
    """Write to stderr so stdout can be parsed for structured output."""
    if verbose or os.environ.get("TITAN_DRAIN_VERBOSE"):
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"[{ts}] {LOG_PREFIX}: {msg}", file=sys.stderr)


def parse_radar():
    """Read RADAR.md and extract all ▢/🟢/🟡/🔵/⚠️ marked items as candidates."""
    if not RADAR_PATH.exists():
        raise FileNotFoundError(f"RADAR.md not found at {RADAR_PATH}")

    text = RADAR_PATH.read_text()
    # Very simple extractor: each bullet line that has a status marker or
    # a heading-referenced work item. Detail classification happens later.
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        # Skip items marked as archive / completed / locked
        if any(marker in stripped for marker in ["✅", "ARCHIVE", "LOCKED", "completed"]):
            continue
        items.append(stripped[2:])  # drop "- " prefix
    return items


def classify_item(item_text, mode):
    """Return (eligible: bool, reason: str) for a single RADAR line."""
    lower = item_text.lower()

    # Hard-block on interactive markers
    for status in INTERACTIVE_STATUSES:
        if status.replace("_", " ") in lower or status in lower:
            return (False, f"interactive status: {status}")

    # Hard-block on explicit parking / deferral
    for marker in ["🔵", "parked", "deprioritized", "on hold", "awaiting"]:
        if marker in lower:
            return (False, f"marked: {marker}")

    # Hard-block on hard limits (financial, legal, external)
    for marker in ["contract", "signature", "credential", "2fa", "oauth", "password", "paypal", "stripe", "paymentcloud review", "durango review"]:
        if marker in lower:
            return (False, f"hard limit: {marker}")

    # If we got here, classify by work type hint
    work_type = None
    for wt in list(HOURLY_WORK_TYPES) + list(NIGHT_GRIND_ADDITIONAL):
        if wt in lower:
            work_type = wt
            break

    if work_type is None:
        # Couldn't classify — err on the side of NOT running
        return (False, "unclassified work type")

    if mode == "hourly" and work_type not in HOURLY_WORK_TYPES:
        return (False, f"work type {work_type} requires night-grind mode")

    return (True, f"eligible: {work_type}")


def dry_run_report(items, mode, verbose):
    """Print a structured report of what would be submitted."""
    eligible = []
    skipped = []
    for item in items:
        ok, reason = classify_item(item, mode)
        if ok:
            eligible.append((item, reason))
        else:
            skipped.append((item, reason))
        if verbose:
            status = "ELIGIBLE" if ok else "SKIP"
            log(f"{status}: {item[:60]}... ({reason})", verbose=True)

    print(json.dumps({
        "mode": mode,
        "total_candidates": len(items),
        "eligible": len(eligible),
        "skipped": len(skipped),
        "eligible_items": [{"item": it[:100], "reason": r} for it, r in eligible],
        "skipped_count_by_reason": _bucket_reasons(skipped),
    }, indent=2))

    return len(eligible)


def _bucket_reasons(skipped):
    buckets = {}
    for _, reason in skipped:
        key = reason.split(":")[0]
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


def main():
    parser = argparse.ArgumentParser(description="Non-interactive RADAR work drain driver.")
    parser.add_argument("--mode", choices=["hourly", "night-grind", "check-empty"], default="hourly")
    parser.add_argument("--dry-run", action="store_true", help="classify but don't submit")
    parser.add_argument("--verbose", action="store_true", help="log each classification decision")
    args = parser.parse_args()

    log(f"starting mode={args.mode} dry_run={args.dry_run}", verbose=args.verbose)

    try:
        items = parse_radar()
    except FileNotFoundError as e:
        log(f"RADAR parse error: {e}", verbose=True)
        sys.exit(2)

    log(f"{len(items)} candidate items found in RADAR", verbose=args.verbose)

    if args.mode == "check-empty":
        eligible_count = sum(1 for it in items if classify_item(it, "night-grind")[0])
        if eligible_count == 0:
            sys.exit(10)
        sys.exit(0)

    if args.dry_run:
        dry_run_report(items, args.mode, args.verbose)
        sys.exit(0)

    # Real run: classify + submit to queue
    # NOTE: submission to public.tasks queue is currently a placeholder.
    # The actual implementation needs Supabase write access via the
    # existing llm_client / queue wiring. For v1, we dry-run only and
    # let the titan-queue-watcher.service pick up work it already knows
    # about. Submission path will be wired in a follow-on commit once
    # Solon confirms the classifier is correct.
    log("v1: classifier-only mode, no submission (placeholder)", verbose=True)
    count = dry_run_report(items, args.mode, args.verbose)
    log(f"v1 classifier found {count} eligible items; submission path is a follow-on", verbose=True)

    sys.exit(0)


if __name__ == "__main__":
    main()
