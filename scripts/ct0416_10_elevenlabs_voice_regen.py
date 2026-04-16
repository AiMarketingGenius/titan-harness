#!/usr/bin/env python3
"""
titan-harness/scripts/ct0416_10_elevenlabs_voice_regen.py

CT-0416-10 — ElevenLabs voice library regeneration (v2).

Supersedes ct0415_17_voice_library_gen.py (Kokoro v1) per MCP decision #14
(2026-04-16 12:45Z). Solon's canonical voice mapping (Section 3A) is locked
and pre-authorized — no guess-mapping, no Solon ack required at runtime.

Voice map (canonical, locked 2026-04-16):
  Alex    → DZifC2yzJiQrdYzF21KH  (Solon OS clone)
  Maya    → uYXf8XasLslADfZ2MB4u  (Hope)
  Jordan  → UgBBYS2sOqTuMpoF3BR0  (Mark)
  Sam     → Yg7C1g7suzNt5TisIqkZ  (Jude British)
  Riley   → DODLEQrClDo8wCz460ld  (Lauren)
  Nadia   → vZzlAds9NzvLsFSWp0qk  (Maria Mysh)
  Lumina  → X03mvPuTfprif8QBAVeJ  (Christina)

Pipeline:
  1. For each (agent, message_type) pair (7 × 6 = 42 total):
     a. Skip if MP3 exists and --force not set (idempotent)
     b. Check cost_kill_switch (vendor='elevenlabs') — fail-closed at cap
     c. POST to ElevenLabs streaming TTS
     d. Save MP3 to /opt/titan-harness-work/services/atlas-web/voices/{agent}/{type}.mp3
     e. Record cost in ledger
  2. Emit manifest.json + summary report
  3. Print SQL to insert/upsert agent_voice_library rows (operator runs)

Run modes:
  python3 ct0416_10_elevenlabs_voice_regen.py --dry-run   # print plan, no API
  python3 ct0416_10_elevenlabs_voice_regen.py             # full regen (skip existing)
  python3 ct0416_10_elevenlabs_voice_regen.py --force     # regen all even if exists
  python3 ct0416_10_elevenlabs_voice_regen.py --agent maya # one agent only
  python3 ct0416_10_elevenlabs_voice_regen.py --client levar # interpolate client name

Cost: ~150 chars per message × 42 messages × ~$0.30/1K chars ≈ $1.89 total at
ElevenLabs Premium tier. Cost kill-switch caps at $5/day for elevenlabs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError


# ---------------------------------------------------------------------------
# Cost kill-switch (mandatory — refuse to call if missing)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
try:
    from cost_kill_switch import KillSwitch
except ImportError as e:
    print(f"FATAL: cost_kill_switch.py not importable: {e}", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ELEVENLABS_API_BASE = 'https://api.elevenlabs.io/v1'
ELEVENLABS_MODEL = 'eleven_turbo_v2_5'  # fast + good for production agent voices

# Canonical voice map per MCP decision #14 (2026-04-16 12:45Z)
VOICE_MAP = {
    'alex':   {'voice_id': 'DZifC2yzJiQrdYzF21KH', 'voice_name': 'Solon OS clone',
               'role': 'Account Manager'},
    'maya':   {'voice_id': 'uYXf8XasLslADfZ2MB4u', 'voice_name': 'Hope',
               'role': 'Content Lead'},
    'jordan': {'voice_id': 'UgBBYS2sOqTuMpoF3BR0', 'voice_name': 'Mark',
               'role': 'Reputation Manager'},
    'sam':    {'voice_id': 'Yg7C1g7suzNt5TisIqkZ', 'voice_name': 'Jude British',
               'role': 'SEO Lead'},
    'riley':  {'voice_id': 'DODLEQrClDo8wCz460ld', 'voice_name': 'Lauren',
               'role': 'Strategy Lead'},
    'nadia':  {'voice_id': 'vZzlAds9NzvLsFSWp0qk', 'voice_name': 'Maria Mysh',
               'role': 'Onboarding Specialist'},
    'lumina': {'voice_id': 'X03mvPuTfprif8QBAVeJ', 'voice_name': 'Christina',
               'role': 'CRO Expert'},
}

MESSAGE_TYPES = ['intro', 'status_update', 'question', 'deliverable',
                 'escalation', 'closing']

# Reused verbatim from ct0415_17_voice_library_gen.py for transcript stability
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


# ElevenLabs Premium pricing per character (rough estimate — actual depends on tier)
# Source: elevenlabs.io/pricing — assume Premium at ~$0.30/1k chars
ELEVENLABS_COST_PER_CHAR = 0.0003  # USD


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or \
               (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k.strip()] = v
    except OSError:
        pass
    return out


def _resolve_elevenlabs_key() -> str:
    candidates = [
        Path('/etc/amg/elevenlabs.env'),
        Path.home() / '.titan-env',
    ]
    for p in candidates:
        env = _load_env_file(p)
        if 'ELEVENLABS_API_KEY' in env:
            return env['ELEVENLABS_API_KEY']
    return os.environ.get('ELEVENLABS_API_KEY', '')


# ---------------------------------------------------------------------------
# ElevenLabs TTS call
# ---------------------------------------------------------------------------

def synthesize(api_key: str, voice_id: str, text: str) -> tuple[Optional[bytes], Optional[str]]:
    """POST text to ElevenLabs streaming TTS. Returns (audio_bytes, error_msg)."""
    url = f'{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}'
    body = json.dumps({
        'text': text,
        'model_id': ELEVENLABS_MODEL,
        'voice_settings': {
            'stability': 0.45,
            'similarity_boost': 0.95,
            'style': 0.0,
            'use_speaker_boost': True,
        },
    }).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'xi-api-key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'audio/mpeg',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read(), None
    except HTTPError as e:
        return None, f'http {e.code}: {e.read().decode("utf-8", errors="replace")[:300]}'
    except (URLError, OSError) as e:
        return None, f'network-error: {e}'


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true',
                   help='print plan, do not call API')
    p.add_argument('--force', action='store_true',
                   help='regenerate even if MP3 exists')
    p.add_argument('--agent', help='only this agent (alex|maya|jordan|sam|riley|nadia|lumina)')
    p.add_argument('--client', default='your business',
                   help='client name to interpolate into transcripts')
    p.add_argument('--out-dir', default='/opt/titan-harness-work/services/atlas-web/voices',
                   help='output directory for MP3s + manifest')
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    agents_to_gen = [args.agent] if args.agent else list(VOICE_MAP.keys())
    if args.agent and args.agent not in VOICE_MAP:
        print(f'FATAL: unknown agent {args.agent!r}. Choose from: {list(VOICE_MAP.keys())}',
              file=sys.stderr)
        return 2

    api_key = _resolve_elevenlabs_key()
    if not api_key and not args.dry_run:
        print('FATAL: ELEVENLABS_API_KEY not found in /etc/amg/elevenlabs.env or env',
              file=sys.stderr)
        return 2

    # Cost kill-switch
    ks = KillSwitch(vendor='elevenlabs', daily_cap_usd=5.0,
                    scope='voice_library_regen')

    # Plan + estimate cost
    total_chars = 0
    plan: list[dict] = []
    for agent in agents_to_gen:
        for mtype in MESSAGE_TYPES:
            text = MESSAGES[agent][mtype].format(client_name=args.client)
            mp3_path = out_dir / agent / f'{mtype}.mp3'
            skip = mp3_path.is_file() and not args.force
            plan.append({
                'agent': agent,
                'mtype': mtype,
                'text': text,
                'chars': len(text),
                'voice_id': VOICE_MAP[agent]['voice_id'],
                'voice_name': VOICE_MAP[agent]['voice_name'],
                'mp3_path': str(mp3_path),
                'skip': skip,
            })
            if not skip:
                total_chars += len(text)

    estimated_cost = total_chars * ELEVENLABS_COST_PER_CHAR
    to_gen = sum(1 for x in plan if not x['skip'])
    skipped = sum(1 for x in plan if x['skip'])

    print(f'\n=== CT-0416-10 ElevenLabs Voice Regen ===')
    print(f'Agents:        {len(agents_to_gen)}')
    print(f'Messages:      {len(plan)} total, {to_gen} to generate, {skipped} skipped (exist)')
    print(f'Total chars:   {total_chars:,}')
    print(f'Est. cost:     ${estimated_cost:.4f} (cap ${ks.daily_cap_usd} — today spent ${ks.today_spend_usd():.4f})')
    print(f'Output dir:    {out_dir}')
    print(f'Client name:   {args.client}')
    print()

    if args.dry_run:
        for entry in plan:
            tag = '[SKIP existing]' if entry['skip'] else '[GEN]'
            print(f'  {tag} {entry["agent"]:8s} {entry["mtype"]:14s} '
                  f'voice={entry["voice_name"]:18s} {entry["chars"]:3d}ch')
        return 0

    if not ks.allow_call(estimated_cost_usd=estimated_cost):
        print(f'COST CAP HIT — refusing to proceed. '
              f'Today: ${ks.today_spend_usd():.4f} / cap ${ks.daily_cap_usd}',
              file=sys.stderr)
        return 1

    # Execute
    succeeded = 0
    failed: list[dict] = []
    actual_cost = 0.0

    for entry in plan:
        if entry['skip']:
            print(f'  SKIP   {entry["agent"]:8s} {entry["mtype"]:14s} (exists)')
            continue

        print(f'  GEN... {entry["agent"]:8s} {entry["mtype"]:14s} '
              f'({entry["chars"]:3d}ch, voice={entry["voice_name"]})', end=' ', flush=True)

        audio, err = synthesize(api_key, entry['voice_id'], entry['text'])
        if err:
            print(f'FAIL: {err}')
            failed.append({**entry, 'error': err})
            continue

        out_path = Path(entry['mp3_path'])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio)
        size_kb = len(audio) / 1024
        cost = entry['chars'] * ELEVENLABS_COST_PER_CHAR
        actual_cost += cost
        # Record per-message in ledger for granular dedupe
        ks.record_call(
            artifact_text=f'{entry["agent"]}|{entry["mtype"]}|{entry["text"]}',
            actual_cost_usd=cost,
            result={'voice_id': entry['voice_id'], 'mp3_path': str(out_path), 'size_kb': size_kb},
        )
        print(f'OK ({size_kb:.1f}KB, ${cost:.4f})')
        succeeded += 1
        time.sleep(0.4)  # be nice to the API

    # Manifest
    manifest = {
        'version': '2.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'client_name': args.client,
        'engine': 'elevenlabs',
        'model': ELEVENLABS_MODEL,
        'voice_map': VOICE_MAP,
        'agents': {},
    }
    for agent in agents_to_gen:
        manifest['agents'][agent] = {
            'voice_id': VOICE_MAP[agent]['voice_id'],
            'voice_name': VOICE_MAP[agent]['voice_name'],
            'role': VOICE_MAP[agent]['role'],
            'messages': {
                mtype: {
                    'transcript': MESSAGES[agent][mtype].format(client_name=args.client),
                    'mp3_url': f'/atlas/voices/{agent}/{mtype}.mp3',
                    'mp3_local': str(out_dir / agent / f'{mtype}.mp3'),
                    'exists': (out_dir / agent / f'{mtype}.mp3').is_file(),
                } for mtype in MESSAGE_TYPES
            },
        }
    manifest_path = out_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print()
    print(f'=== SUMMARY ===')
    print(f'  Succeeded: {succeeded}')
    print(f'  Skipped:   {skipped}')
    print(f'  Failed:    {len(failed)}')
    print(f'  Actual cost: ${actual_cost:.4f}')
    print(f'  Manifest: {manifest_path}')
    if failed:
        print(f'  Failures:')
        for f in failed:
            print(f'    {f["agent"]}/{f["mtype"]}: {f["error"]}')

    # SQL upsert hints
    print()
    print(f'=== SQL UPSERT (run on Supabase to update agent_voice_library) ===')
    print(f'-- Add elevenlabs_voice_id column if not present:')
    print(f"ALTER TABLE public.agent_voice_library ADD COLUMN IF NOT EXISTS elevenlabs_voice_id text;")
    print(f'-- Update existing rows OR insert new:')
    print(f'-- (per-row UPSERTs would go here; use ct0416_10_insert_voice_rows.py if you wrote one)')

    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
