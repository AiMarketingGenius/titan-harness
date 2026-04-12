"""
lib/doctrine_extractor.py
Ironclad architecture §3.1 — extract doctrine deltas from a research pull
and surface them as proposed patches. Does NOT auto-patch doctrine files;
that requires Solon review per CORE_CONTRACT §0.9.4.

Outputs:
  plans/research/<date>_<slug>.proposed-patches.md   — human review file

Usage:
  python3 lib/doctrine_extractor.py --input <path> --class <CLASS> --harness <dir>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DOCTRINE_SECTION_RE = re.compile(
    r"^##\s*3\.\s*Recommended doctrine changes\s*$",
    re.MULTILINE | re.IGNORECASE,
)
NEXT_SECTION_RE = re.compile(r"^##\s*\d+\.", re.MULTILINE)


def extract_doctrine_section(text: str) -> str:
    m = DOCTRINE_SECTION_RE.search(text)
    if not m:
        return ""
    start = m.end()
    rest = text[start:]
    n = NEXT_SECTION_RE.search(rest)
    return rest[: n.start()].strip() if n else rest.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--class", dest="klass", default="RESEARCH")
    parser.add_argument("--harness", required=True)
    args = parser.parse_args()

    src = Path(args.input).expanduser()
    if not src.exists():
        print(f"[doctrine_extractor] input not found: {src}", file=sys.stderr)
        sys.exit(1)

    text = src.read_text()
    doctrine = extract_doctrine_section(text)
    if not doctrine or doctrine.lower() == "none":
        print("[doctrine_extractor] No doctrine deltas proposed.")
        return

    patches_path = src.with_name(src.stem + ".proposed-patches.md")
    patches_path.write_text(
        "# Proposed doctrine patches\n\n"
        f"> Source: {src.name}\n"
        f"> Directive class: {args.klass}\n\n"
        "These are extracted suggestions — they are NOT auto-applied.\n"
        "Review, run bin/harness-conflict-check.sh against any target file,\n"
        "then patch with Edit and commit under a [DOCTRINE-PATCH] tag.\n\n"
        "---\n\n"
        f"{doctrine}\n"
    )
    print(f"[doctrine_extractor] Wrote proposed patches: {patches_path}")


if __name__ == "__main__":
    main()
