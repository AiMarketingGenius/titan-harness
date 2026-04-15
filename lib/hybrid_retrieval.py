"""
titan-harness/lib/hybrid_retrieval.py

CT-0414-07 Phase 2.1 — hybrid retrieval for grok_review.

Assembles the context bundle that accompanies a doctrine/plan artifact on its
way to the secondary-AI reviewer (Grok or Perplexity sonar). The bundle
prevents reviewer blind-spots where it otherwise grades an artifact in
isolation from the harness conventions, prior grades, and doctrine-freshness
guardrails that shaped it.

Bundle composition (deterministic, ordered):
    1. Artifact content (the doctrine / plan / spec file itself)
    2. Related doctrine pointers (e.g. if artifact is DR-AMG-ACCESS-REDUNDANCY-01,
       include CORE_CONTRACT.md section 0 + CLAUDE.md section 12 IDEA BUILDER
       grading rules + any named cross-references in the artifact)
    3. Structural code context (file path hierarchy around referenced lib/
       or bin/ paths; AST-light — first N lines of each + docstring)
    4. Prior grades for this artifact ID or nearby siblings (if present in
       plans/review_bundles/)
    5. Doctrine-freshness marker (last-research date, age in days, stale flag
       if > 14 days per CLAUDE.md section 17.6)

Semantic snippets from MCP search_memory are OPTIONAL — the module tries a
best-effort HTTP call and falls back to local-only context if MCP is
unreachable.

Public API:
    build_bundle(artifact_path, rubric_name, context_paths=None,
                 include_mcp_snippets=True) -> dict
    bundle_to_prompt(bundle) -> str

Output is a JSON-serializable dict safe to pass to any chat/completions API.
"""
from __future__ import annotations

import ast
import json
import os
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT", "http://memory.aimarketinggenius.io")
FRESHNESS_STALE_DAYS = 14  # per CLAUDE.md section 17.6
MAX_CODE_CTX_LINES = 60    # first N lines of each code-context file
MAX_DOCTRINE_EXCERPT_CHARS = 3000
MAX_PRIOR_GRADES = 3


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class CodeContextEntry:
    path: str
    first_lines: str
    docstring: Optional[str] = None


@dataclass
class PriorGrade:
    step_id: str
    grade: float
    timestamp: str
    source: str


@dataclass
class Bundle:
    artifact_path: str
    artifact_content: str
    rubric_name: str
    related_doctrine: dict[str, str] = field(default_factory=dict)
    code_context: list[CodeContextEntry] = field(default_factory=list)
    prior_grades: list[PriorGrade] = field(default_factory=list)
    doctrine_freshness: dict[str, Any] = field(default_factory=dict)
    mcp_snippets: list[dict[str, Any]] = field(default_factory=list)
    built_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "artifact_content": self.artifact_content,
            "rubric_name": self.rubric_name,
            "related_doctrine": self.related_doctrine,
            "code_context": [asdict(e) for e in self.code_context],
            "prior_grades": [asdict(p) for p in self.prior_grades],
            "doctrine_freshness": self.doctrine_freshness,
            "mcp_snippets": self.mcp_snippets,
            "built_at": self.built_at,
        }


# ---------------------------------------------------------------------------
# Core retrieval steps
# ---------------------------------------------------------------------------

def _read_artifact(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_related_doctrine(artifact_text: str) -> dict[str, str]:
    """
    Scan artifact for references to doctrine files (CLAUDE.md, CORE_CONTRACT.md,
    DOCTRINE_*, DR_*) and pull a short excerpt from each.
    """
    out: dict[str, str] = {}
    candidates = ["CLAUDE.md", "CORE_CONTRACT.md"]
    # Scan for explicit mentions of DOCTRINE_* or DR_* in artifact
    for word in artifact_text.split():
        w = word.strip("`.,;:()[]<>\"'")
        if (w.startswith("DOCTRINE_") or w.startswith("DR_")) and w.endswith(".md"):
            candidates.append(f"plans/{w}")
        if (w.startswith("DOCTRINE_") or w.startswith("DR_")) and "/" not in w:
            candidates.append(f"plans/{w}.md")
    # Dedupe + read (cap size)
    seen: set[str] = set()
    for rel in candidates:
        if rel in seen:
            continue
        seen.add(rel)
        p = REPO_ROOT / rel
        if p.is_file():
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
                out[rel] = txt[:MAX_DOCTRINE_EXCERPT_CHARS]
            except OSError:
                continue
    return out


def _code_ctx_for_path(rel_path: str) -> Optional[CodeContextEntry]:
    p = REPO_ROOT / rel_path
    if not p.is_file():
        return None
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    first = "\n".join(lines[:MAX_CODE_CTX_LINES])
    docstring: Optional[str] = None
    if p.suffix == ".py":
        try:
            mod = ast.parse("\n".join(lines))
            docstring = ast.get_docstring(mod)
        except (SyntaxError, ValueError):
            pass
    return CodeContextEntry(path=rel_path, first_lines=first, docstring=docstring)


def _extract_code_context(artifact_text: str, extra_paths: list[str]) -> list[CodeContextEntry]:
    """
    Pull first N lines + module docstring for every lib/*.py or bin/*.sh path
    mentioned in the artifact, plus any caller-supplied extras.
    """
    referenced: set[str] = set(extra_paths)
    for word in artifact_text.split():
        w = word.strip("`.,;:()[]<>\"'")
        if (w.startswith("lib/") or w.startswith("bin/") or w.startswith("opa/")) and "." in w:
            referenced.add(w)
    out: list[CodeContextEntry] = []
    for rel in sorted(referenced):
        entry = _code_ctx_for_path(rel)
        if entry is not None:
            out.append(entry)
    return out


def _load_prior_grades(artifact_path: Path) -> list[PriorGrade]:
    """
    Look in plans/review_bundles/ for prior grade_result.json files whose
    step_meta.json artifact_path matches or siblings-of.
    """
    bundles_dir = REPO_ROOT / "plans" / "review_bundles"
    if not bundles_dir.is_dir():
        return []
    grades: list[PriorGrade] = []
    artifact_name = artifact_path.name
    for sub in sorted(bundles_dir.iterdir(), reverse=True):
        if not sub.is_dir():
            continue
        meta_file = sub / "step_meta.json"
        grade_file = sub / "grade_result.json"
        if not (meta_file.is_file() and grade_file.is_file()):
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            grade = json.loads(grade_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        meta_artifact = str(meta.get("artifact_path", ""))
        if artifact_name in meta_artifact or meta_artifact.endswith(artifact_name):
            grades.append(
                PriorGrade(
                    step_id=str(meta.get("step_id", sub.name)),
                    grade=float(grade.get("grade", 0.0)),
                    timestamp=str(grade.get("timestamp_utc", "")),
                    source=str(grade.get("transport_used", "unknown")),
                )
            )
        if len(grades) >= MAX_PRIOR_GRADES:
            break
    return grades


def _doctrine_freshness(artifact_text: str) -> dict[str, Any]:
    """
    Detect the last-research marker `<!-- last-research: YYYY-MM-DD -->` and
    compute age in days. Flag stale if age exceeds FRESHNESS_STALE_DAYS.
    """
    marker = "last-research:"
    out: dict[str, Any] = {
        "marker_present": False,
        "last_research": None,
        "age_days": None,
        "stale": False,
        "stale_threshold_days": FRESHNESS_STALE_DAYS,
    }
    for line in artifact_text.splitlines():
        if marker in line:
            try:
                raw = line.split(marker, 1)[1].strip().rstrip("-->").strip()
                date_str = raw.split()[0]
                last = datetime.strptime(date_str, "%Y-%m-%d")
                age = (datetime.now() - last).days
                out.update(
                    marker_present=True,
                    last_research=date_str,
                    age_days=age,
                    stale=age > FRESHNESS_STALE_DAYS,
                )
                break
            except (ValueError, IndexError):
                continue
    return out


def _mcp_snippets(query: str, count: int = 3) -> list[dict[str, Any]]:
    """
    Best-effort MCP search_memory call. Returns [] on any failure.
    """
    try:
        payload = json.dumps({"action": "search_memory", "data": {"query": query, "count": count}}).encode("utf-8")
        req = urllib.request.Request(
            f"{MCP_ENDPOINT}/search_memory",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — trusted MCP
            body = json.loads(resp.read().decode("utf-8"))
        results = body.get("results", [])
        return results[:count] if isinstance(results, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_bundle(
    artifact_path: str | os.PathLike[str],
    rubric_name: str,
    context_paths: Optional[list[str]] = None,
    include_mcp_snippets: bool = True,
    mcp_query: Optional[str] = None,
) -> dict[str, Any]:
    path = Path(artifact_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"artifact not found: {path}")

    artifact_text = _read_artifact(path)

    bundle = Bundle(
        artifact_path=str(path),
        artifact_content=artifact_text,
        rubric_name=rubric_name,
        related_doctrine=_extract_related_doctrine(artifact_text),
        code_context=_extract_code_context(artifact_text, context_paths or []),
        prior_grades=_load_prior_grades(path),
        doctrine_freshness=_doctrine_freshness(artifact_text),
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
    )
    if include_mcp_snippets:
        q = mcp_query or f"doctrine review context for {path.name}"
        bundle.mcp_snippets = _mcp_snippets(q)
    return bundle.to_dict()


def bundle_to_prompt(bundle: dict[str, Any]) -> str:
    """
    Render the bundle into a single human-readable prompt-ready string the
    reviewer model can ingest without further structuring.
    """
    parts: list[str] = []
    parts.append(f"### ARTIFACT UNDER REVIEW\nPath: `{bundle['artifact_path']}`\n")
    parts.append(f"Rubric: **{bundle['rubric_name']}**\n")
    parts.append("```")
    parts.append(bundle["artifact_content"])
    parts.append("```\n")

    if bundle.get("related_doctrine"):
        parts.append("\n### RELATED DOCTRINE EXCERPTS\n")
        for rel, excerpt in bundle["related_doctrine"].items():
            parts.append(f"#### {rel}\n```\n{excerpt}\n```\n")

    if bundle.get("code_context"):
        parts.append("\n### STRUCTURAL CODE CONTEXT\n")
        for entry in bundle["code_context"]:
            parts.append(f"#### {entry['path']}\n")
            if entry.get("docstring"):
                parts.append(f"**docstring:** {entry['docstring']}\n")
            parts.append(f"```\n{entry['first_lines']}\n```\n")

    if bundle.get("prior_grades"):
        parts.append("\n### PRIOR GRADES FOR THIS ARTIFACT\n")
        for pg in bundle["prior_grades"]:
            parts.append(
                f"- step `{pg['step_id']}` graded {pg['grade']} at {pg['timestamp']} via {pg['source']}\n"
            )

    fresh = bundle.get("doctrine_freshness") or {}
    if fresh.get("marker_present"):
        stale_flag = "**STALE** — " if fresh.get("stale") else ""
        parts.append(
            f"\n### DOCTRINE FRESHNESS\n{stale_flag}"
            f"last-research: {fresh['last_research']} ({fresh['age_days']} days ago, "
            f"threshold {fresh['stale_threshold_days']})\n"
        )

    if bundle.get("mcp_snippets"):
        parts.append("\n### SEMANTIC MEMORY SNIPPETS\n")
        for s in bundle["mcp_snippets"]:
            txt = s.get("text") or s.get("content") or json.dumps(s)[:400]
            parts.append(f"- {txt}\n")

    return "".join(parts)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Build a hybrid-retrieval bundle for grok_review")
    ap.add_argument("--artifact", required=True, help="path to doctrine/plan/spec file")
    ap.add_argument("--rubric", default="war-room-10d", help="rubric name (default: war-room-10d)")
    ap.add_argument("--context", default="", help="comma-separated extra code-context paths (lib/*.py, bin/*.sh)")
    ap.add_argument("--no-mcp", action="store_true", help="skip MCP search_memory call")
    ap.add_argument("--format", choices=["json", "prompt"], default="json")
    args = ap.parse_args()

    extra = [p.strip() for p in args.context.split(",") if p.strip()]
    bundle = build_bundle(
        args.artifact,
        args.rubric,
        context_paths=extra,
        include_mcp_snippets=(not args.no_mcp),
    )
    if args.format == "prompt":
        print(bundle_to_prompt(bundle))
    else:
        print(json.dumps(bundle, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
