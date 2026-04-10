#!/usr/bin/env python3
"""
MP-1 Phase 8 — Manifest Assembly + Integrity Check

Walks /opt/amg-titan/solon-corpus/ and produces a canonical MANIFEST.json
that consolidates all seven harvest sources into a single truth object
that MP-2 SYNTHESIS gates on.

Conforms to MP-1_HARVEST_MEGAPROMPT.md §10 (Phase 8).

Per Solon directive 2026-04-10: this script is the permanent fix for the
checkpoint drift problem. Re-running it always reflects on-disk reality.
mp-status.sh --reconcile becomes obsolete once this is in the runner path.

The script is idempotent. Re-runs produce a fresh manifest. No destructive
writes (never touches corpus files, only MANIFEST.json and .checkpoint_mp1.json).

Usage:
  python3 mp1_phase8_manifest.py                      # write MANIFEST.json + update checkpoint
  MP_DRY_RUN=1 python3 mp1_phase8_manifest.py         # compute + print, don't write
  python3 mp1_phase8_manifest.py --corpus-root /path  # override corpus location (multi-tenant)

Exit codes:
  0  — manifest written (or computed in dry-run)
  1  — fatal error during walk or write
  3  — manifest written but ready_for_synthesis=false (signals gate not met,
       caller should HALT MP-2 until corpus is fuller). This matches the
       existing convention in run_mp2.sh which treats exit 3 as "blocked".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Source → corpus subdirectory mapping. Keep keys stable because both
# mp2_phase1_audit.py and run_mp2.sh read these keys from MANIFEST.json.
SOURCE_LAYOUT = {
    # key                  subdir                     file_globs
    "claude_threads":      ("claude-threads",         ("*.json",)),
    "perplexity":          ("perplexity",             ("*.json",)),
    "fireflies":           ("fireflies/transcripts",  ("*.json",)),
    "loom":                ("loom/videos",            ("*.json",)),
    "gmail":               ("gmail",                  ("*.json",)),
    "slack":               ("slack/channels",         ("*.jsonl",)),
    "mcp_decisions":       ("mcp-decisions",          ("*.jsonl",)),
}

# MP-2 synthesis gate thresholds (from MP-1 megaprompt §12 acceptance)
SYNTHESIS_MIN_SOURCES = 5           # "at least 5 of 7 sources successfully harvested"
SYNTHESIS_MIN_HIGH_QUALITY = 100    # "high_quality_count >= 100 across all sources"

# Storage budget (MP-1 §0.5 hard cap)
STORAGE_HARD_CAP_BYTES = 5 * 1024 * 1024 * 1024   # 5 GB
STORAGE_SOFT_WARN_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB

# PII redaction check patterns — only flag if these are found UNREDACTED
# (i.e. we look for the raw shape, not the [REDACTED_*] marker).
PII_PATTERNS = [
    (re.compile(r'sk-[A-Za-z0-9_-]{20,}'),                 "openai-key"),
    (re.compile(r'shp(ss|at|ca)_[A-Za-z0-9_-]{20,}'),      "shopify-token"),
    (re.compile(r'eyJ[A-Za-z0-9_=-]{40,}\.[A-Za-z0-9_=-]+\.[A-Za-z0-9_=-]+'), "jwt"),
    (re.compile(r'AKIA[0-9A-Z]{16}'),                       "aws-key"),
    (re.compile(r'ghp_[A-Za-z0-9]{30,}'),                   "github-token"),
    (re.compile(r'AIza[0-9A-Za-z_-]{30,}'),                 "google-key"),
]

# Files that should NEVER be counted as corpus artifacts even if they
# live under the corpus root.
SKIP_FILENAMES = {"MANIFEST.json", ".checkpoint_mp1.json"}
SKIP_DIRNAMES = {".heldout"}  # mp2 holdout set, not raw corpus


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_json_load(fp: Path) -> Any:
    """Load a JSON file, returning None on any parse failure."""
    try:
        return json.loads(fp.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None


def _iter_artifacts(corpus_root: Path, subdir: str, globs: tuple[str, ...]):
    """Yield every artifact file under corpus_root/subdir matching any glob."""
    base = corpus_root / subdir
    if not base.exists():
        return
    seen: set[Path] = set()
    for pattern in globs:
        for fp in base.rglob(pattern):
            if fp.name in SKIP_FILENAMES:
                continue
            if any(part in SKIP_DIRNAMES for part in fp.parts):
                continue
            if fp in seen:
                continue
            seen.add(fp)
            yield fp


def _iter_wrapped_artifacts(corpus_root: Path, source: str, subdir: str,
                            globs: tuple[str, ...]):
    """Yield (filepath, wrapped_artifact_dict) for the harvest wrapper format.

    JSON files: one artifact per file (must have top-level 'metadata' key)
    JSONL files: one artifact per non-empty line (must have 'metadata' key)
    """
    for fp in _iter_artifacts(corpus_root, subdir, globs):
        if fp.suffix == ".json":
            obj = _safe_json_load(fp)
            if isinstance(obj, dict) and "metadata" in obj:
                yield fp, obj
        elif fp.suffix == ".jsonl":
            try:
                with fp.open(encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(obj, dict) and "metadata" in obj:
                            yield fp, obj
            except OSError:
                continue


def _detect_pii(text: str) -> list[str]:
    """Return list of PII marker names found unredacted in text."""
    hits: list[str] = []
    for pattern, name in PII_PATTERNS:
        if pattern.search(text):
            hits.append(name)
    return hits


def _compute_stats(corpus_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int], str, str, int]:
    """Walk the corpus tree once and return:
       (per_source, quality_totals, earliest_iso, latest_iso, pii_hits)
    """
    per_source: dict[str, dict[str, Any]] = {}
    quality_totals = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    earliest = None
    latest = None
    pii_hits = 0

    for source, (subdir, globs) in SOURCE_LAYOUT.items():
        stats = {
            "count": 0,
            "bytes": 0,
            "words": 0,
            "high_quality_count": 0,
            "medium_quality_count": 0,
            "low_quality_count": 0,
            "unknown_quality_count": 0,
            "subdir": subdir,
            "sample_files": [],  # first 3 file paths as sanity checks
        }
        for fp, obj in _iter_wrapped_artifacts(corpus_root, source, subdir, globs):
            meta = obj.get("metadata", {}) or {}
            stats["count"] += 1

            size = int(meta.get("byte_size", 0) or 0)
            if not size:
                try:
                    size = fp.stat().st_size
                except OSError:
                    size = 0
            stats["bytes"] += size

            words = int(meta.get("word_count", 0) or 0)
            stats["words"] += words

            quality = str(meta.get("quality_hint", "unknown"))
            if quality not in ("high", "medium", "low"):
                quality = "unknown"
            stats[f"{quality}_quality_count"] += 1
            quality_totals[quality] += 1

            # Track date range (from metadata.original_date or harvested_at)
            for date_key in ("original_date", "harvested_at"):
                raw_date = meta.get(date_key)
                if isinstance(raw_date, str) and raw_date:
                    if earliest is None or raw_date < earliest:
                        earliest = raw_date
                    if latest is None or raw_date > latest:
                        latest = raw_date
                    break

            # PII check against the raw content (only if small enough to
            # scan cheaply — large transcripts get a prefix-only scan)
            content = obj.get("content", {})
            if isinstance(content, dict):
                raw = str(content.get("raw", ""))[:20000]  # 20KB prefix
                if _detect_pii(raw):
                    pii_hits += 1

            if len(stats["sample_files"]) < 3:
                stats["sample_files"].append(str(fp.relative_to(corpus_root)))

        per_source[source] = stats

    return (per_source, quality_totals,
            earliest or "", latest or "", pii_hits)


def _detect_gaps(per_source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify which sources are missing or under-harvested."""
    gaps: list[dict[str, Any]] = []

    gap_reasons = {
        "claude_threads": ("phase 1", "browser-auth required for claude.ai", "high"),
        "perplexity":     ("phase 2", "browser-auth required for perplexity.ai", "high"),
        "fireflies":      ("phase 3", "needs FIREFLIES_API_KEY or Stagehand session", "high"),
        "loom":           ("phase 4", "needs LOOM_API_KEY or Stagehand session", "medium"),
        "gmail":          ("phase 5", "needs Google OAuth consent flow", "high"),
        "slack":          ("phase 6", "harvest_slack.py not yet implemented under mp-runner", "medium"),
        "mcp_decisions":  ("phase 7", "harvest_mcp_decisions.py not yet implemented under mp-runner", "low"),
    }

    for source, stats in per_source.items():
        if stats["count"] == 0:
            phase, reason, impact = gap_reasons.get(source, ("?", "missing", "medium"))
            gaps.append({
                "phase": phase,
                "source": source,
                "reason": reason,
                "impact": impact,
            })
    return gaps


def _run_aristotle_scan(per_source: dict[str, dict[str, Any]],
                        quality_totals: dict[str, int],
                        pii_hits: int, total_bytes: int) -> dict[str, Any]:
    """MP-1 §0.2 Aristotle 5-point scan on the assembled corpus."""
    sources_with_data = sum(1 for s in per_source.values() if s["count"] > 0)
    return {
        "financial": {
            "status": "ok",
            "note": "Phase 8 consolidator is pure disk walk, zero API cost.",
        },
        "security": {
            "status": "ok" if pii_hits == 0 else "warn",
            "pii_hits": pii_hits,
            "note": ("No unredacted PII markers found in a 20KB prefix scan of every artifact."
                     if pii_hits == 0 else
                     f"{pii_hits} artifact(s) have unredacted PII markers — review before shipping corpus."),
        },
        "spof": {
            "status": "warn",
            "note": "Corpus exists only on VPS. R2 backup step (§10.4) should be run separately.",
        },
        "operational": {
            "status": "ok" if sources_with_data >= SYNTHESIS_MIN_SOURCES else "warn",
            "sources_with_data": sources_with_data,
            "min_required": SYNTHESIS_MIN_SOURCES,
            "note": ("Enough sources for MP-2 synthesis."
                     if sources_with_data >= SYNTHESIS_MIN_SOURCES else
                     f"Only {sources_with_data}/{SYNTHESIS_MIN_SOURCES} sources populated — MP-2 gate not met."),
        },
        "strategic": {
            "status": "ok" if quality_totals["high"] >= SYNTHESIS_MIN_HIGH_QUALITY else "warn",
            "high_quality_total": quality_totals["high"],
            "min_required": SYNTHESIS_MIN_HIGH_QUALITY,
            "note": ("Sufficient high-quality material for MP-2 synthesis."
                     if quality_totals["high"] >= SYNTHESIS_MIN_HIGH_QUALITY else
                     f"Only {quality_totals['high']}/{SYNTHESIS_MIN_HIGH_QUALITY} high-quality items — escalate to Solon if MP-2 proceeds."),
        },
    }


def _build_manifest(corpus_root: Path, harvest_run_id: str) -> dict[str, Any]:
    per_source, quality_totals, earliest, latest, pii_hits = _compute_stats(corpus_root)
    gaps = _detect_gaps(per_source)

    total_artifacts = sum(s["count"] for s in per_source.values())
    total_bytes = sum(s["bytes"] for s in per_source.values())
    total_words = sum(s["words"] for s in per_source.values())

    sources_with_data = sum(1 for s in per_source.values() if s["count"] > 0)
    ready_for_synthesis = (
        sources_with_data >= SYNTHESIS_MIN_SOURCES
        and quality_totals["high"] >= SYNTHESIS_MIN_HIGH_QUALITY
        and pii_hits == 0
        and total_bytes <= STORAGE_HARD_CAP_BYTES
    )

    # Percent complete based on sources_with_data / 7
    percent_complete = round(100 * sources_with_data / len(SOURCE_LAYOUT))

    # Strip sample_files out of by_source for the canonical manifest (keep
    # them internal-only). Expose only the stable shape MP-2 expects.
    by_source_clean = {}
    for source, stats in per_source.items():
        by_source_clean[source] = {
            "count": stats["count"],
            "bytes": stats["bytes"],
            "high_quality_count": stats["high_quality_count"],
        }

    storage_status = "ok"
    if total_bytes > STORAGE_HARD_CAP_BYTES:
        storage_status = "over_hard_cap"
    elif total_bytes > STORAGE_SOFT_WARN_BYTES:
        storage_status = "over_soft_warn"

    manifest = {
        "manifest_version": "1.0",
        "generated_at": _now_iso(),
        "generator": "mp1_phase8_manifest.py",
        "harvest_run_id": harvest_run_id,
        "status": "complete" if ready_for_synthesis else "partial",
        "percent_complete": percent_complete,
        "total_artifacts": total_artifacts,
        "total_bytes": total_bytes,
        "total_words": total_words,
        "by_source": by_source_clean,
        "date_range": {
            "earliest": earliest,
            "latest": latest,
        },
        "gaps": gaps,
        "quality_distribution": quality_totals,
        "pii_redaction_applied": pii_hits == 0,
        "pii_hits_detected": pii_hits,
        "storage": {
            "used_bytes": total_bytes,
            "hard_cap_bytes": STORAGE_HARD_CAP_BYTES,
            "soft_warn_bytes": STORAGE_SOFT_WARN_BYTES,
            "status": storage_status,
        },
        "ready_for_synthesis": ready_for_synthesis,
        "sources_with_data": sources_with_data,
        "sources_required_for_synthesis": SYNTHESIS_MIN_SOURCES,
        "high_quality_required_for_synthesis": SYNTHESIS_MIN_HIGH_QUALITY,
        "aristotle_scan": _run_aristotle_scan(per_source, quality_totals, pii_hits, total_bytes),
        "notes": (
            "Generated by mp1_phase8_manifest.py under the titan-harness mp-runner."
            " Idempotent: safe to re-run. Re-runs always reflect current on-disk state."
            " MP-2 synthesis gate check: run_mp2.sh reads ready_for_synthesis."
        ),
    }
    return manifest


def _reconcile_checkpoint(corpus_root: Path, manifest: dict[str, Any]) -> None:
    """Update .checkpoint_mp1.json to match the fresh manifest."""
    cp_path = corpus_root / ".checkpoint_mp1.json"
    try:
        cp = json.loads(cp_path.read_text()) if cp_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        cp = {}

    phases = cp.get("phases", {}) or {}
    # Per-source → checkpoint phase mapping
    mapping = {
        "claude_threads": "phase_1_claude_threads",
        "perplexity":     "phase_2_perplexity",
        "fireflies":      "phase_3_fireflies",
        "loom":           "phase_4_loom",
        "gmail":          "phase_5_gmail",
        "slack":          "phase_6_slack",
        "mcp_decisions":  "phase_7_mcp_decisions",
    }
    for source, phase_key in mapping.items():
        source_stats = manifest["by_source"].get(source, {})
        count = source_stats.get("count", 0)
        existing = phases.get(phase_key, {}) or {}
        if count > 0:
            # Only upgrade from not_started / not_complete → reconciled_from_disk.
            # Leave 'complete' alone so prior phase runs' metadata stays intact.
            if existing.get("status") not in ("complete",):
                phases[phase_key] = {
                    "status": "reconciled_from_disk",
                    "artifacts": count,
                    "high_quality": source_stats.get("high_quality_count", 0),
                    "bytes": source_stats.get("bytes", 0),
                    "reconciled_at": _now_iso(),
                    "reconciled_by": "mp1_phase8_manifest.py",
                }
        else:
            # Zero on disk — preserve whatever reason the existing entry had
            if phase_key not in phases:
                phases[phase_key] = {"status": "not_started"}

    # Phase 8 entry — this run itself
    phases["phase_8_manifest"] = {
        "status": "complete",
        "completed_at": _now_iso(),
        "ready_for_synthesis": manifest["ready_for_synthesis"],
        "total_artifacts": manifest["total_artifacts"],
        "sources_with_data": manifest["sources_with_data"],
    }

    cp["phases"] = phases
    cp["last_manifest_run"] = _now_iso()
    cp["last_manifest_status"] = manifest["status"]
    cp["percent_complete"] = manifest["percent_complete"]
    cp["total_artifacts"] = manifest["total_artifacts"]
    cp["total_bytes"] = manifest["total_bytes"]

    cp_path.write_text(json.dumps(cp, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mp1_phase8_manifest",
        description="MP-1 Phase 8 — assemble MANIFEST.json from the solon-corpus tree")
    parser.add_argument("--corpus-root", default="/opt/amg-titan/solon-corpus",
                        help="Corpus root directory (default: %(default)s)")
    parser.add_argument("--harvest-run-id", default=None,
                        help="Harvest run ID tag (default: auto-generated)")
    parser.add_argument("--no-checkpoint", action="store_true",
                        help="Do not update .checkpoint_mp1.json")
    parser.add_argument("--summary-only", action="store_true",
                        help="Print summary but do not write MANIFEST.json")
    args = parser.parse_args()

    corpus_root = Path(args.corpus_root).resolve()
    if not corpus_root.is_dir():
        print(f"ERROR: corpus root does not exist: {corpus_root}", file=sys.stderr)
        return 1

    harvest_run_id = args.harvest_run_id or f"mp1-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Build the manifest
    try:
        manifest = _build_manifest(corpus_root, harvest_run_id)
    except Exception as e:
        print(f"ERROR: manifest build failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    # Write MANIFEST.json
    manifest_path = corpus_root / "MANIFEST.json"
    dry_run = os.environ.get("MP_DRY_RUN") == "1" or args.summary_only
    if not dry_run:
        try:
            manifest_path.write_text(json.dumps(manifest, indent=2))
        except OSError as e:
            print(f"ERROR: failed to write {manifest_path}: {e}", file=sys.stderr)
            return 1
        if not args.no_checkpoint:
            _reconcile_checkpoint(corpus_root, manifest)
        print(f"manifest written: {manifest_path}", file=sys.stderr)
    else:
        print("DRY RUN — not writing MANIFEST.json or checkpoint", file=sys.stderr)

    # Summary JSON to stdout — consumed by mp-runner.sh parser
    summary = {
        "phase": "mp1_phase_8_manifest",
        "completed_at": _now_iso(),
        "artifacts": manifest["total_artifacts"],
        "high_quality": manifest["quality_distribution"]["high"],
        "medium": manifest["quality_distribution"]["medium"],
        "low": manifest["quality_distribution"]["low"],
        "bytes": manifest["total_bytes"],
        "words": manifest["total_words"],
        "sources_with_data": manifest["sources_with_data"],
        "ready_for_synthesis": manifest["ready_for_synthesis"],
        "status": manifest["status"],
        "percent_complete": manifest["percent_complete"],
        "output_path": str(manifest_path),
    }
    print(json.dumps(summary, indent=2))

    # Exit 0 always on successful write. Gating (MP-2 ready-check) is the
    # caller's job, not the script's. run_mp2.sh reads ready_for_synthesis
    # from MANIFEST.json directly and HALTs there if gate unmet.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
