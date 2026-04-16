#!/usr/bin/env python3
"""
titan-harness/scripts/ct0415_17_voice_library_gen.py

CT-0415-17 — 7-agent voice library generator.

Generates one intro + five standard messages for each of 6 AMG agents
(Maya, Jordan, Sam, Riley, Nadia, Lumina) via the Kokoro TTS API running
on the VPS at http://127.0.0.1:8880/v1/audio/speech. Alex's voice is the
existing Solon ElevenLabs clone at ~/Downloads/amg-voice-demo/alex_SOLON_CLONE.mp3 —
we stage it + flag the extended Alex messages as 'pending ElevenLabs regen'.

Pipeline:
  1. Compose messages catalog (7 agents × (intro + 5 standard) = 42 rows)
  2. For each non-Alex agent, POST to Kokoro, save MP3 to local out dir
  3. Upload entire voice-library tree to VPS /opt/titan-harness/services/atlas-web/voices/
  4. Insert 42 rows into Supabase agent_voice_library table (schema created by
     scripts/ct0415_17_create_voice_table.sql, applied separately)
  5. Emit manifest.json for the portal to read

Kokoro voice assignments (from Solon's CT-0415-17 spec + voice inventory):
  Maya     → bf_emma          (warm female, content)
  Jordan   → am_michael       (direct male, reputation)
  Sam      → am_eric          (analytical male, SEO)
  Riley    → bf_alice         (strategic female, opus-tier)
  Nadia    → af_nicole        (welcoming female, onboarding)
  Lumina   → af_sarah         (expert female, CRO)
  Alex     → solon_clone      (existing ElevenLabs file, not regenerated tonight)

Run mode:
  python3 ct0415_17_voice_library_gen.py --dry-run      # print catalog + voice map only
  python3 ct0415_17_voice_library_gen.py                # full generate + manifest
  python3 ct0415_17_voice_library_gen.py --agent maya   # regenerate one agent only
  python3 ct0415_17_voice_library_gen.py --client levar # regenerate with client name interpolation

Output layout:
  ~/titan-harness/out/voice-library/
    manifest.json              # master index
    alex/intro.mp3             # existing Solon clone copy
    maya/intro.mp3
    maya/status-update.mp3
    maya/question.mp3
    ...
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

KOKORO_URL = os.environ.get("KOKORO_URL", "http://127.0.0.1:8880")
DEFAULT_OUT_DIR = Path.home() / "titan-harness" / "out" / "voice-library"
ALEX_SOURCE = Path.home() / "Downloads" / "amg-voice-demo" / "alex_SOLON_CLONE.mp3"

# ---------------------------------------------------------------------------
# Agent voice assignments
# ---------------------------------------------------------------------------

AGENTS = {
    "alex":   {"voice": "solon_clone",  "tts": "elevenlabs", "role": "account manager"},
    "maya":   {"voice": "bf_emma",      "tts": "kokoro",     "role": "content lead"},
    "jordan": {"voice": "am_michael",   "tts": "kokoro",     "role": "reputation manager"},
    "sam":    {"voice": "am_eric",      "tts": "kokoro",     "role": "SEO strategist"},
    "riley":  {"voice": "bf_alice",     "tts": "kokoro",     "role": "strategic lead"},
    "nadia":  {"voice": "af_nicole",    "tts": "kokoro",     "role": "onboarding specialist"},
    "lumina": {"voice": "af_sarah",     "tts": "kokoro",     "role": "CRO expert"},
}

# ---------------------------------------------------------------------------
# Message catalog
# ---------------------------------------------------------------------------
# Each agent gets 6 recordings: intro + 5 standard types.
# {client_name} placeholder interpolated at generation time for portal replay.
# Text is deliberately concise — ≤ 25 words — so delivery stays punchy.

STANDARD_MESSAGE_TYPES = ["intro", "status_update", "question", "deliverable", "escalation", "closing"]

MESSAGES = {
    "alex": {
        "intro":         "Hi, I'm Alex — your account manager for {client_name}. I'm the one making sure every piece of the AMG team hits for you.",
        "status_update": "Quick update for {client_name}. The team shipped three deliverables this week. Full breakdown is in your dashboard.",
        "question":      "One question before I close the loop — do you want me to route this through Maya for content, or keep it on my plate?",
        "deliverable":   "The deliverable is live. I reviewed it personally before it went out. Let me know your reaction — we iterate fast.",
        "escalation":    "Heads up on a timing risk. I flagged it with the team and we have a plan. I want you to hear it from me first.",
        "closing":       "Thanks for the trust. We earned this week. Next week the bar goes up again. Talk soon.",
    },
    "maya": {
        "intro":         "Hi, I'm Maya — your content lead for {client_name}. I turn your brand voice into posts that pull.",
        "status_update": "Content status for {client_name}: three articles live, two more in review, calendar loaded for next two weeks.",
        "question":      "Before I publish — are we still running the founder-voice angle, or shifting to customer-story mode this month?",
        "deliverable":   "New article is up. I matched your tone, pulled two case studies, and hit the target keyword naturally.",
        "escalation":    "One of the outlets flagged our angle. I have two backup pitches ready. Want me to send them over?",
        "closing":       "Content is in a good rhythm this week. I'll have the next calendar on your desk Monday morning.",
    },
    "jordan": {
        "intro":         "Jordan here — your reputation manager for {client_name}. I watch every review, every mention, every signal.",
        "status_update": "Reputation snapshot: Google rating up point two this month, seven new five-star reviews, zero unresolved complaints.",
        "question":      "Got a borderline review I want your call on — respond publicly, reach out privately, or let it ride?",
        "deliverable":   "New review management playbook is deployed. Every inbound gets acknowledged within four hours now. Automated.",
        "escalation":    "One review needs executive attention. Not a crisis, but the customer deserves a direct response from the top.",
        "closing":       "Rep is trending the right direction. I'll keep eyes on it this weekend. No surprises on Monday.",
    },
    "sam": {
        "intro":         "Sam here, SEO lead for {client_name}. I read search data the way musicians read sheet music.",
        "status_update": "SEO this week: four rankings climbed, two target keywords hit page one, site speed scored ninety-two on mobile.",
        "question":      "I see two paths — double down on what's working or test a new cluster. Which feels right for this quarter?",
        "deliverable":   "Technical SEO pass is complete. Core Web Vitals green across all pages, schema markup on every service.",
        "escalation":    "Google just shipped a ranking update. Your position held, but I want to walk you through the implications.",
        "closing":       "Numbers are moving. Slow and compounding, the way SEO wins. Full report in your inbox by end of day.",
    },
    "riley": {
        "intro":         "Riley here — strategy lead for {client_name}. My job is connecting this quarter's moves to next year's position.",
        "status_update": "Strategic snapshot: we're on track for the quarterly targets, ahead on two leading indicators, one risk to discuss.",
        "question":      "Before we commit this next cycle of spend — want to pressure-test the thesis with me, or move?",
        "deliverable":   "Q-plan is finalized. Three priorities, clear owners, weekly check-ins. You approve it, we execute.",
        "escalation":    "A competitive signal just shifted the landscape. I want twenty minutes to walk you through what changes.",
        "closing":       "Good cycle. The compounding is real. Next week we push on the second priority. You'll see it fast.",
    },
    "nadia": {
        "intro":         "Welcome — I'm Nadia, your onboarding specialist. I make sure {client_name} gets to value in the first fourteen days, not the first year.",
        "status_update": "Onboarding status: all five systems are live, team is trained, first reporting cycle ran clean. You're in flight.",
        "question":      "Quick check — is the weekly cadence working for you, or would you prefer bi-weekly touchpoints from here?",
        "deliverable":   "Your team handoff document is done. Every login, every process, every safety net, documented.",
        "escalation":    "Small hiccup worth surfacing — nothing blocking. I want you to know before it hits your radar.",
        "closing":       "You're officially past onboarding. The full AMG machine is at your disposal now. Proud of this kickoff.",
    },
    "lumina": {
        "intro":         "Hi, I'm Lumina, your conversion optimization expert. I turn website visitors into revenue for {client_name}.",
        "status_update": "CRO this cycle: three A-B tests running, one clear winner shipping Monday, conversion rate up eleven percent.",
        "question":      "Before we scale the winning variant — want to see the raw data, or trust the test and move?",
        "deliverable":   "New conversion funnel is live. Every page tested, every CTA measured, friction cut where it mattered.",
        "escalation":    "One variant hurt conversion by six percent. I killed it Tuesday. Still worth flagging so you know the process.",
        "closing":       "Revenue per visitor is up. That compounds. Next month I want to go after the checkout flow. We'll talk.",
    },
}


def _kokoro_generate(text: str, voice: str, out_path: Path, timeout_s: int = 60) -> dict:
    """POST to Kokoro /v1/audio/speech and save mp3.

    Returns {'ok': bool, 'bytes': int, 'duration_ms': int, 'error': str}."""
    t0 = time.time()
    body = json.dumps({
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "speed": 1.0,
    }).encode()
    req = urllib.request.Request(
        f"{KOKORO_URL}/v1/audio/speech",
        data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            data = r.read()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            return {"ok": True, "bytes": len(data), "duration_ms": int((time.time() - t0) * 1000), "error": ""}
    except Exception as e:
        return {"ok": False, "bytes": 0, "duration_ms": int((time.time() - t0) * 1000), "error": str(e)[:200]}


def _interp(text: str, client_name: str) -> str:
    return text.replace("{client_name}", client_name or "your business")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--agent", help="Regenerate only this agent (alex|maya|jordan|sam|riley|nadia|lumina)")
    p.add_argument("--client", default="your business", help="Client name interpolated into {client_name} placeholders")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--vps-host", default="root@170.205.37.148")
    p.add_argument("--vps-voice-dir", default="/opt/titan-harness/services/atlas-web/voices")
    p.add_argument("--skip-upload", action="store_true", help="Do not rsync to VPS")
    args = p.parse_args()

    # Remote kokoro requires SSH tunnel if script runs from Mac and Kokoro is on VPS
    # Default assumption: script runs ON VPS. On Mac, set KOKORO_URL via SSH tunnel first:
    #   ssh -L 8880:127.0.0.1:8880 root@170.205.37.148 &

    if args.dry_run:
        print("=== DRY RUN — voice library generation plan ===\n")
        print(f"Client interpolation: {args.client!r}")
        print(f"Out dir: {args.out_dir}")
        print(f"VPS upload: {args.vps_host}:{args.vps_voice_dir}")
        print()
        total_chars = 0
        for agent, meta in AGENTS.items():
            print(f"  {agent:8} voice={meta['voice']:15} tts={meta['tts']:11} role={meta['role']}")
            for mtype in STANDARD_MESSAGE_TYPES:
                msg = _interp(MESSAGES[agent][mtype], args.client)
                total_chars += len(msg)
                status = "(existing Solon clone)" if agent == "alex" and mtype == "intro" else ""
                print(f"      {mtype:15} ({len(msg):3} chars) {msg[:60]}... {status}")
        print(f"\nTotal chars to synthesize: {total_chars}")
        print(f"Estimated Kokoro runtime: ~{total_chars * 0.02:.1f} seconds at 50ch/s")
        return 0

    # Filter agents if --agent specified
    agent_list = [args.agent] if args.agent else list(AGENTS.keys())
    if args.agent and args.agent not in AGENTS:
        sys.stderr.write(f"ERR: unknown agent {args.agent}. Known: {list(AGENTS.keys())}\n")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "client_name": args.client,
        "kokoro_url": KOKORO_URL,
        "agents": {},
    }

    # Alex: copy existing Solon clone
    if "alex" in agent_list:
        alex_dir = args.out_dir / "alex"
        alex_dir.mkdir(parents=True, exist_ok=True)
        if ALEX_SOURCE.is_file():
            shutil.copy(ALEX_SOURCE, alex_dir / "intro.mp3")
            print(f"[alex] intro.mp3 copied from {ALEX_SOURCE} ({ALEX_SOURCE.stat().st_size} bytes)")
            manifest["agents"]["alex"] = {
                "voice": "solon_clone",
                "tts": "elevenlabs",
                "files": {"intro": {"ok": True, "bytes": ALEX_SOURCE.stat().st_size, "source": "existing_clone"}},
            }
        else:
            print(f"[alex] WARN: {ALEX_SOURCE} not found — intro skipped", file=sys.stderr)
            manifest["agents"]["alex"] = {"voice": "solon_clone", "tts": "elevenlabs", "files": {}}
        # Extended Alex messages flagged for ElevenLabs regen (not synthesized tonight)
        for mtype in STANDARD_MESSAGE_TYPES[1:]:
            manifest["agents"]["alex"].setdefault("files", {})[mtype] = {
                "ok": False,
                "pending": "ElevenLabs Solon voice clone regen required",
                "transcript": _interp(MESSAGES["alex"][mtype], args.client),
            }

    # Non-Alex agents: Kokoro synthesize all 6 messages
    for agent in agent_list:
        if agent == "alex":
            continue
        meta = AGENTS[agent]
        voice = meta["voice"]
        agent_entry = {"voice": voice, "tts": "kokoro", "files": {}}
        for mtype in STANDARD_MESSAGE_TYPES:
            text = _interp(MESSAGES[agent][mtype], args.client)
            out = args.out_dir / agent / f"{mtype}.mp3"
            result = _kokoro_generate(text, voice, out)
            if result["ok"]:
                print(f"[{agent}] {mtype:15} → {result['bytes']:>6} bytes in {result['duration_ms']}ms")
            else:
                print(f"[{agent}] {mtype:15} FAILED: {result['error']}", file=sys.stderr)
            agent_entry["files"][mtype] = {
                "ok": result["ok"],
                "bytes": result["bytes"],
                "duration_ms": result["duration_ms"],
                "error": result["error"],
                "transcript": text,
                "voice": voice,
            }
        manifest["agents"][agent] = agent_entry

    # Write manifest
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n[manifest] {manifest_path} ({manifest_path.stat().st_size} bytes)")

    # Upload to VPS
    if not args.skip_upload:
        print(f"\n[upload] rsync → {args.vps_host}:{args.vps_voice_dir}/ ...")
        rc = os.system(
            f"rsync -avz --delete-after {args.out_dir}/ {args.vps_host}:{args.vps_voice_dir}/"
        )
        if rc == 0:
            print("[upload] OK")
        else:
            print(f"[upload] FAILED (rc={rc})", file=sys.stderr)
            return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
