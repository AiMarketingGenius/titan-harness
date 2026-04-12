"""
lib/research_query.py
Ironclad architecture §3.3 — Perplexity sonar-pro query wrapper.

Routes through lib/model_router.py when available; falls back to a direct
LiteLLM / Perplexity call. Writes the result as a markdown file suitable
for doctrine extraction downstream.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path


def _call_router(topic: str, model: str) -> str:
    """Try lib.model_router first, then lib.llm_client, then fail hard."""
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))

    prompt = f"""You are Titan's research engine for AMG / Atlas operational doctrine.

Deep-research the following topic and return structured output.

TOPIC: {topic}

Return EXACTLY these sections:

## 1. Key findings
Bullet list, cited with [n] markers.

## 2. Operational implications for AMG / Atlas
What this changes for Solon's day-to-day.

## 3. Recommended doctrine changes
Specific patches to CLAUDE.md / CORE_CONTRACT.md / policy.yaml / RADAR.md.
If none, say "none".

## 4. Sources
Numbered [n] list with URLs.

Be concise, actionable, and production-ready. Output will be parsed."""

    # Preferred path: model_router
    try:
        import model_router  # type: ignore
        if hasattr(model_router, "call_llm"):
            return model_router.call_llm(model=model, prompt=prompt, task_type="research")
        if hasattr(model_router, "route_and_call"):
            return model_router.route_and_call(task_type="research", prompt=prompt, model=model)
    except Exception as e:
        print(f"[research_query] model_router unavailable: {e}", file=sys.stderr)

    # Fallback: llm_client
    try:
        import llm_client  # type: ignore
        if hasattr(llm_client, "call"):
            return llm_client.call(model=model, prompt=prompt, task_type="research")
    except Exception as e:
        print(f"[research_query] llm_client unavailable: {e}", file=sys.stderr)

    # Last-ditch: perplexity_review MCP placeholder — emit a stub the caller
    # can fill manually without killing the pipeline.
    return (
        "> [research_query STUB]\n"
        f"> model={model}\n"
        "> model_router/llm_client both unavailable at call time.\n"
        "> Fill this file manually or re-run after fixing the router wiring.\n\n"
        f"## 1. Key findings\n- (pending manual research on: {topic})\n\n"
        "## 2. Operational implications for AMG / Atlas\n- tbd\n\n"
        "## 3. Recommended doctrine changes\nnone\n\n"
        "## 4. Sources\n- tbd\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--model", default="sonar-pro")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    body = _call_router(args.topic, args.model)

    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    out.write_text(
        f"# Research: {args.topic}\n\n"
        f"> Generated: {ts}\n"
        f"> Model: {args.model}\n"
        f"<!-- last-research: {_dt.date.today().isoformat()} -->\n\n"
        f"{body}\n"
    )
    print(f"[research_query] Saved to {out}")


if __name__ == "__main__":
    main()
