"""
lib/doctrine_freshness.py
Ironclad architecture §3.4 — check core doctrine files for a <!-- last-research: YYYY-MM-DD -->
marker and flag any file older than --max-age-days.

Used by bin/titan-boot-audit.sh during cold boot and by the night-grind scheduler
to queue background research refresh tasks.

Exit code:
  0 — all tracked files fresh
  1 — one or more files stale (list printed to stdout)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path


TRACKED = [
    "CLAUDE.md",
    "CORE_CONTRACT.md",
    "policy.yaml",
    "RADAR.md",
    "INVENTORY.md",
]

MARKER_RE = re.compile(r"<!--\s*last-research:\s*(\d{4}-\d{2}-\d{2})\s*-->")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", required=True)
    parser.add_argument("--max-age-days", type=int, default=14)
    args = parser.parse_args()

    harness = Path(args.harness).expanduser()
    cutoff = _dt.date.today() - _dt.timedelta(days=args.max_age_days)

    stale: list[str] = []
    for name in TRACKED:
        f = harness / name
        if not f.exists():
            continue
        text = f.read_text(errors="ignore")
        m = MARKER_RE.search(text)
        if not m:
            stale.append(f"{name} — no last-research marker")
            continue
        try:
            dt = _dt.date.fromisoformat(m.group(1))
        except ValueError:
            stale.append(f"{name} — unparseable marker: {m.group(1)}")
            continue
        if dt < cutoff:
            age = (_dt.date.today() - dt).days
            stale.append(f"{name} — stale by {age - args.max_age_days}d (last {dt.isoformat()})")

    if stale:
        print("[doctrine-freshness] STALE:")
        for s in stale:
            print(f"  - {s}")
        sys.exit(1)

    print("[doctrine-freshness] All tracked doctrine files fresh.")


if __name__ == "__main__":
    main()
