#!/usr/bin/env python3
"""
hercules_onboarding_paste.py — generate ONE single paste-block at
~/AMG/HERCULES_ONBOARDING.md that Solon can use to fully onboard a fresh
Hercules tab in a single paste.

Combines:
  - Perplexity's recommended onboarding prompt (architecture review +
    operating model internalization)
  - Full inline doctrine (DOCTRINE_AMG_FACTORY_ARCHITECTURE_v1_0.md)
  - Full inline current bootstrap brief (HERCULES_BOOTSTRAP.md)

Solon's workflow:
  1. Open ~/AMG/HERCULES_ONBOARDING.md
  2. Cmd-A, Cmd-C
  3. Paste into fresh Kimi K2.6 tab
  4. Send

That's it. No terminal commands, no file paths to remember, no copy-from-
multiple-files. One file, one paste.

Auto-regenerates via launchd com.amg.hercules-onboarding (5-min interval)
so the bootstrap brief part stays current.

Run modes:
    hercules_onboarding_paste.py            one-shot, exit
    hercules_onboarding_paste.py --watch    regen every 5 min
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time
from datetime import datetime, timezone

HOME = pathlib.Path.home()
DOCTRINE_PATH = HOME / "titan-harness" / "plans" / "DOCTRINE_AMG_FACTORY_ARCHITECTURE_v1_0.md"
BOOTSTRAP_PATH = HOME / "AMG" / "HERCULES_BOOTSTRAP.md"
OUT_PATH = HOME / "Downloads" / "HERCULES_ONBOARDING.md"
LEGACY_PATH = HOME / "AMG" / "HERCULES_ONBOARDING.md"  # also write here for back-compat

PROMPT_HEADER = """ROLE: You are Hercules, Chief Executive Operations Manager for AMG AI Factory.

CONTEXT: An external expert (Perplexity Deep Research) just completed a deep architecture review of our 40-agent system after today's production failures (CT-0426-36 phantom-agent stall, CT-0426-37 Mercury hallucinated completion). The review identified four structural gaps and provided a hardening roadmap.

Solon's subordinate builder (Titan, Claude Opus 4.7 in ~/titan-harness/) has already shipped:
- Mercury V4 Pro routing (qwen2.5-coder:7b banned for orchestration)
- Aletheia tightening (artifact-existence checks beyond status flags)
- Notifier dedupe (3-layer: content-hash + per-task cooldown + global rate limit)
- Hercules daemon LIVE (PID 45623, polls MCP every 30s, calls Kimi K2.6 API direct)
- Agent Capability Manifest (Perplexity P0 #1 — phantom agents now rejected at queue time)
- 3 atlas agents upgraded to V4 Pro (atlas_titan, atlas_einstein, atlas_hallucinometer)
- Hercules Bootstrap Brief auto-updater (THIS document)
- Hercules powerdown protocol (conversation snapshots survive restart)

The Perplexity report is now filed as binding canonical doctrine. The full doctrine and current factory state are inlined below.

TASK: Read both documents, internalize the architectural principles, and update your internal operating model. Specifically:

1. Confirm you understand the executor-validator separation pattern and why self-attestation failed (CT-0426-37: Mercury via qwen2.5-coder:7b wrote /tmp/notifier.txt and returned ok=true with no real work; Aletheia v1 only checked status flag, missed it).

2. Confirm the agent capability manifest pattern (no dispatching to phantom agents like atlas_hercules — that's YOU, you can't claim queue tasks; redirect to mercury or specific specialist).

3. Confirm the tool receipt + artifact grounding pattern for Aletheia v2 (Pydantic-schema tool calls return {ok, artifact_path, artifact_hash, exit_code}; Aletheia verifies sha256(file)==receipt.hash; mechanically unforgeable).

4. Confirm the priority execution order (P0–P3 in the report). Telnyx tollfree verification is P0 (5-min Solon portal action). VPS systemd migration is P1. Tool receipts is P1. Redis Streams is P1.

Then: brief Solon in 3-5 sentences on what changes to your dispatch logic this requires going forward (e.g., always check capability manifest before dispatching, prefer primitive ssh_run over LLM mode for high-stakes tasks, request artifact-hash receipts in acceptance_criteria, etc.).

After that, acknowledge in your one-line greeting (per the bootstrap brief format) that you are hydrated AND have internalized the doctrine.

═══════════════════════════════════════════════════════════
ATTACHMENT 1 — BINDING DOCTRINE (Perplexity Architecture Review 2026-04-26)
═══════════════════════════════════════════════════════════

"""

DIVIDER = """

═══════════════════════════════════════════════════════════
ATTACHMENT 2 — CURRENT BOOTSTRAP BRIEF (live factory state, regenerates every 5 min)
═══════════════════════════════════════════════════════════

"""


def build_onboarding() -> str:
    try:
        doctrine = DOCTRINE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        doctrine = f"(ERROR reading doctrine at {DOCTRINE_PATH}: {e!r})"
    try:
        bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    except Exception as e:
        bootstrap = f"(ERROR reading bootstrap brief at {BOOTSTRAP_PATH}: {e!r})"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    header = f"<!-- HERCULES ONBOARDING PASTE-BLOCK — generated {now_iso} -->\n<!-- Source: hercules_onboarding_paste.py — auto-regen 5 min via launchd -->\n<!-- Solon workflow: Cmd-A, Cmd-C, paste into fresh Kimi K2.6 tab, send. -->\n\n"

    return header + PROMPT_HEADER + doctrine + DIVIDER + bootstrap


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--watch", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=300)
    args = p.parse_args()

    if not (args.watch or args.once):
        args.once = True

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.once:
        text = build_onboarding()
        OUT_PATH.write_text(text, encoding="utf-8")
        try:
            LEGACY_PATH.parent.mkdir(parents=True, exist_ok=True)
            LEGACY_PATH.write_text(text, encoding="utf-8")
        except Exception:
            pass
        print(f"OK wrote {OUT_PATH} ({len(text)} bytes)")
        return 0

    while True:
        try:
            text = build_onboarding()
            OUT_PATH.write_text(text, encoding="utf-8")
            try:
                LEGACY_PATH.parent.mkdir(parents=True, exist_ok=True)
                LEGACY_PATH.write_text(text, encoding="utf-8")
            except Exception:
                pass
        except Exception as e:
            sys.stderr.write(f"regen error: {e!r}\n")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
