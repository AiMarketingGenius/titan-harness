"""
titan-harness/lib/alexandria.py

Library of Alexandria helper — catalog search, manifest refresh, preflight
doctrine-placement check, promote-to-canon action.

Implements the 2026-04-11 Mega Directive Part 3 (Library of Alexandria)
with the conflict-checked merge model: a thin catalog layer over existing
`plans/` (doctrine) + VPS `/opt/amg-titan/solon-corpus/` (raw harvest).

Public API:
  refresh_index()                 — refresh ALEXANDRIA_INDEX.md timestamps + counts
  search(query, section=None)     — grep-style search across doctrine + corpus
  promote(section, source_ref,
          note)                    — copy an artifact into
                                     library_of_alexandria/<section>/promoted/
                                     + index + Slack-notify
  preflight_check(paths)           — return list of doctrine files outside the
                                     approved tree (used by bin/alexandria-preflight.sh)
  list_sections()                  — return canonical 7-section list

Canonical sections:
  solon_os, perplexity_threads, claude_threads, emails, looms,
  fireflies_meetings, other_sources
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_ROOT = REPO_ROOT / "library_of_alexandria"
INDEX_PATH = LIBRARY_ROOT / "ALEXANDRIA_INDEX.md"
PLANS_DIR = REPO_ROOT / "plans"
BASELINES_DIR = REPO_ROOT / "baselines"
TEMPLATES_DIR = REPO_ROOT / "templates"
VPS_CORPUS_ROOT = Path("/opt/amg-titan/solon-corpus")  # only exists on VPS

SECTIONS = [
    "solon_os",
    "perplexity_threads",
    "claude_threads",
    "emails",
    "looms",
    "fireflies_meetings",
    "other_sources",
]

# Canonical-top-level operating docs allowed at repo root
APPROVED_ROOT_DOCS = {
    "README.md",
    "CORE_CONTRACT.md",
    "CLAUDE.md",
    "INVENTORY.md",
    "RADAR.md",
    "IDEA_TO_EXECUTION_PIPELINE.md",
    "RELAUNCH_CLAUDE_CODE.md",
    "SESSION_PROMPT.md",
    "P9.1_CUTOVER_REPORT.md",
    "HERCULES_BACKFILL_REPORT.md",
    "ALEXANDRIA_INDEX.md",
    "MIRROR_STATUS.md",
}

# Paths where new doctrine files are ALLOWED to land
APPROVED_DOCTRINE_PARENTS = [
    "plans",
    "plans/merchant-stack-applications",
    "plans/control-loop",
    "plans/briefs",
    "baselines",
    "templates",
    "library_of_alexandria",
    "config",
    "docs",
]


# ---------------------------------------------------------------------------
# Section listing + index refresh
# ---------------------------------------------------------------------------

def list_sections() -> list[str]:
    """Return the canonical 7-section list."""
    return list(SECTIONS)


def _count_corpus_files(section: str) -> int:
    """Count files in the VPS corpus for a given section. Returns 0 on Mac
    (where the corpus is not mounted) unless the SSHFS tree exists."""
    section_to_corpus_subdir = {
        "perplexity_threads": "perplexity",
        "claude_threads": "claude-threads",
        "emails": "gmail",
        "looms": "loom",
        "fireflies_meetings": "fireflies",
        "other_sources": "slack",  # + mcp-decisions checked separately
    }
    if section not in section_to_corpus_subdir:
        return 0
    subdir = VPS_CORPUS_ROOT / section_to_corpus_subdir[section]
    if not subdir.is_dir():
        return 0  # running on Mac without VPS mount
    try:
        return sum(1 for _ in subdir.rglob("*") if _.is_file())
    except Exception:
        return 0


def refresh_index() -> dict:
    """Update ALEXANDRIA_INDEX.md's metrics block + last-refresh timestamp.

    Returns a dict of {section: file_count} that was computed.
    """
    if not INDEX_PATH.is_file():
        sys.stderr.write(f"alexandria: {INDEX_PATH} missing\n")
        return {}

    counts: dict[str, int] = {}
    for section in SECTIONS:
        if section == "solon_os":
            counts[section] = _count_plans_files()
        else:
            counts[section] = _count_corpus_files(section)

    index_text = INDEX_PATH.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    index_text = re.sub(
        r"- \*\*Last index refresh:\*\* .*",
        f"- **Last index refresh:** {now}",
        index_text,
        count=1,
    )
    # Also refresh the per-section counts block if present
    for section, count in counts.items():
        index_text = re.sub(
            rf"  - ({section.replace('_', r'[ _]')}:?) \d+",
            lambda m, c=count, s=section: f"  - {s.replace('_', ' ')}: {c}",
            index_text,
            count=1,
            flags=re.IGNORECASE,
        )

    INDEX_PATH.write_text(index_text, encoding="utf-8")
    return counts


def _count_plans_files() -> int:
    """Count doctrine files in plans/ (gitignored on purpose)."""
    if not PLANS_DIR.is_dir():
        return 0
    return sum(1 for _ in PLANS_DIR.rglob("*.md") if _.is_file())


# ---------------------------------------------------------------------------
# Search across doctrine + corpus
# ---------------------------------------------------------------------------

def search(query: str,
           section: Optional[str] = None,
           max_results: int = 50) -> list[dict]:
    """Grep-style search across doctrine + (VPS-mounted) corpus.

    Returns a list of {path, line_number, snippet} dicts.

    On Mac, only searches the doctrine tree (repo-local). On VPS, also
    searches the corpus tree when reachable.
    """
    results: list[dict] = []
    targets: list[Path] = []

    if section is None or section == "solon_os":
        # Doctrine tree
        if PLANS_DIR.is_dir():
            targets.append(PLANS_DIR)
        targets.append(REPO_ROOT / "CORE_CONTRACT.md")
        targets.append(REPO_ROOT / "CLAUDE.md")
        targets.append(REPO_ROOT / "INVENTORY.md")
        targets.append(REPO_ROOT / "RADAR.md")
        targets.append(REPO_ROOT / "IDEA_TO_EXECUTION_PIPELINE.md")
        targets.append(REPO_ROOT / "RELAUNCH_CLAUDE_CODE.md")
        if BASELINES_DIR.is_dir():
            targets.append(BASELINES_DIR)

    if (section is None or section != "solon_os") and VPS_CORPUS_ROOT.is_dir():
        targets.append(VPS_CORPUS_ROOT)

    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    for target in targets:
        if not target.exists():
            continue
        if target.is_file():
            _search_file(target, pattern, results, max_results)
        elif target.is_dir():
            for p in target.rglob("*"):
                if len(results) >= max_results:
                    break
                if p.is_file() and p.suffix in (".md", ".txt", ".json", ".yaml", ".yml", ".sql", ".py"):
                    _search_file(p, pattern, results, max_results)
        if len(results) >= max_results:
            break

    return results[:max_results]


def _search_file(path: Path, pattern: re.Pattern,
                 out: list[dict], max_results: int) -> None:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                if len(out) >= max_results:
                    return
                if pattern.search(line):
                    out.append({
                        "path": str(path),
                        "line_number": lineno,
                        "snippet": line.rstrip()[:200],
                    })
    except Exception:
        return


# ---------------------------------------------------------------------------
# Promote to canon
# ---------------------------------------------------------------------------

def promote(section: str, source_ref: str, note: str,
            post_to_slack: bool = True) -> Optional[Path]:
    """Copy an artifact into library_of_alexandria/<section>/promoted/ + add
    an index entry + (optionally) notify Aristotle on Slack.

    source_ref can be:
      - a path (relative to repo or absolute)
      - a catalog row id (format: "perplexity:<row>", "claude:<uuid>")
    """
    if section not in SECTIONS:
        sys.stderr.write(f"alexandria: unknown section {section}\n")
        return None

    promoted_dir = LIBRARY_ROOT / section / "promoted"
    promoted_dir.mkdir(parents=True, exist_ok=True)

    src = Path(source_ref)
    if not src.is_absolute():
        src = REPO_ROOT / source_ref
    if not src.is_file():
        sys.stderr.write(f"alexandria: source not found: {src}\n")
        return None

    dest = promoted_dir / src.name
    try:
        shutil.copy2(src, dest)
    except Exception as e:
        sys.stderr.write(f"alexandria: copy failed: {e}\n")
        return None

    # Append to index
    if INDEX_PATH.is_file():
        entry = (
            f"\n- *(promoted {datetime.now(timezone.utc).strftime('%Y-%m-%d')})* "
            f"`library_of_alexandria/{section}/promoted/{src.name}` — {note}\n"
        )
        with open(INDEX_PATH, "a", encoding="utf-8") as f:
            f.write(entry)

    # Slack notification
    if post_to_slack:
        try:
            sys.path.insert(0, str(REPO_ROOT / "lib"))
            from aristotle_slack import post_update  # type: ignore
            post_update(
                title=f"Library promotion: {section}",
                body_md=f"Promoted `{src.name}` to canonical Library.\n\n{note}",
                file_path=dest,
                file_kind="promoted",
            )
        except Exception as e:
            sys.stderr.write(f"alexandria: slack notify failed: {e}\n")

    return dest


# ---------------------------------------------------------------------------
# Preflight — detect doctrine files outside the approved tree
# ---------------------------------------------------------------------------

def _is_approved_doctrine_path(rel_path: str) -> bool:
    """True if `rel_path` (relative to repo root) is an approved doctrine
    location per the Library of Alexandria placement rule."""
    if "/" not in rel_path and rel_path in APPROVED_ROOT_DOCS:
        return True
    for parent in APPROVED_DOCTRINE_PARENTS:
        if rel_path.startswith(parent + "/") or rel_path == parent:
            return True
    # Top-level Python/shell code lives in lib/ + scripts/ + bin/ — not doctrine
    if rel_path.startswith(("lib/", "scripts/", "bin/", "sql/", "hooks/",
                             "services/", "templates/", "deploy/",
                             ".claude/", ".git/")):
        return True
    # dotfiles + config at root
    if rel_path in {".gitignore", ".editorconfig", "policy.yaml", "install.sh"}:
        return True
    return False


def _is_doctrine_file(path: Path) -> bool:
    """Heuristic: markdown files are doctrine unless they live in code dirs."""
    if path.suffix.lower() != ".md":
        return False
    rel = str(path.relative_to(REPO_ROOT))
    if rel.startswith(("lib/", "scripts/", "bin/", "sql/", "hooks/", "deploy/")):
        return False
    return True


def _is_gitignored(path: Path) -> bool:
    """Return True iff `path` is gitignored. Uses `git check-ignore` as the
    single source of truth so we never drift from .gitignore."""
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(path)],
            capture_output=True,
            timeout=5,
        )
        return r.returncode == 0  # 0 = ignored, 1 = not ignored, 128 = error
    except Exception:
        return False


def preflight_check(paths: Optional[Iterable[Path]] = None) -> list[str]:
    """Scan the repo for doctrine files outside the approved tree.

    Returns a list of violation messages (empty = clean).

    Gitignored files are skipped — auto-generated build artifacts like
    RADAR_SUMMARY.md and files under plans/ don't count as doctrine-
    placement violations since they never land in version control.

    If `paths` is given, only scan those paths (used by pre-commit hook
    to check staged files). Otherwise scan the whole repo.
    """
    violations: list[str] = []

    if paths is None:
        paths_iter: Iterable[Path] = (
            p for p in REPO_ROOT.rglob("*.md")
            if ".git" not in p.parts
        )
    else:
        paths_iter = (Path(p) for p in paths)

    for p in paths_iter:
        if not p.is_file():
            continue
        if not _is_doctrine_file(p):
            continue
        if _is_gitignored(p):
            continue
        try:
            rel = str(p.relative_to(REPO_ROOT))
        except ValueError:
            continue
        if not _is_approved_doctrine_path(rel):
            violations.append(
                f"doctrine file outside approved tree: {rel} "
                f"(allowed: plans/, baselines/, templates/, "
                f"library_of_alexandria/, top-level operating docs)"
            )
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    parser = argparse.ArgumentParser(prog="alexandria")
    parser.add_argument("--refresh", action="store_true",
                        help="Refresh ALEXANDRIA_INDEX.md counts + timestamp")
    parser.add_argument("--search", type=str, metavar="QUERY")
    parser.add_argument("--section", type=str,
                        help=f"Limit search/promote to one of: {SECTIONS}")
    parser.add_argument("--promote", nargs=2,
                        metavar=("PATH", "NOTE"),
                        help="Promote an artifact to Library canon: --promote <path> '<note>'")
    parser.add_argument("--preflight", action="store_true",
                        help="Scan for doctrine files outside the approved tree")
    parser.add_argument("--list-sections", action="store_true")
    parser.add_argument("--no-slack", action="store_true",
                        help="Skip Slack notification on --promote")
    args = parser.parse_args()

    if args.list_sections:
        for s in list_sections():
            print(s)
        return 0

    if args.refresh:
        counts = refresh_index()
        print(json.dumps(counts, indent=2))
        return 0

    if args.search:
        results = search(args.search, section=args.section)
        for r in results:
            print(f"{r['path']}:{r['line_number']}: {r['snippet']}")
        return 0 if results else 1

    if args.promote:
        if not args.section:
            sys.stderr.write("ERROR: --promote requires --section\n")
            return 2
        path, note = args.promote
        dest = promote(args.section, path, note, post_to_slack=not args.no_slack)
        if dest:
            print(f"promoted: {dest}")
            return 0
        return 1

    if args.preflight:
        violations = preflight_check()
        if violations:
            print(f"⚠️  {len(violations)} doctrine placement violations:", file=sys.stderr)
            for v in violations:
                print(f"  - {v}", file=sys.stderr)
            return 1
        print("✅ doctrine placement clean")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
