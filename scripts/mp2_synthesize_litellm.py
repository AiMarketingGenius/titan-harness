#!/usr/bin/env python3
"""MP-2 Solon OS triple-source synthesis — LiteLLM gateway port (v2, elite-grade).

Rewrites the original anthropic-SDK synthesizer to route through LiteLLM at
127.0.0.1:4000 (bypasses the Claude workspace usage cap that blocks direct
anthropic.com until 2026-05-01). LiteLLM routes to Bedrock/Vertex bearer
tokens from /opt/amg-titan/.env which are per-vendor, not per-workspace.

Triple-source merge per Solon directive 2026-04-18:
- **Lane 1 (Claude.ai harvest):** 1,294 conversations, 13,236 human messages.
  Top 500 by length chunked at ~60K chars → ~51 analysis passes via
  claude-haiku-4-5. Checkpoint saved after each chunk (resumable).
- **Lane 2 (Perplexity partial):** /opt/amg-titan/solon-corpus/perplexity/
  pplx_thread_index.txt (45KB) — folded into synthesis context as supplemental.
- **Lane 3 (Titan creative-studio):** all 8 files under
  /opt/amg-titan/solon-corpus/creative-studio/ (COMEDY_GEARS, VOICE_PROFILE,
  MY_BEST_WORK, Solon_Z_Artist_Profile, Solon_Stories_Journal, etc.) — loaded
  as primary input for §10 Voice Cloning + §11 Creative Engine sections.

Final synthesis uses claude-sonnet-4-6 (max_tokens 16K supported) across two
passes so the 11-section output never gets truncated:
- Pass 1 (§1-§9 core behavioral profile): Lane 1 chunk analyses + Lane 2 index.
- Pass 2 (§10 Voice Cloning + §11 Creative Engine): Lane 1 creative-tagged
  chunks (filtered by conversation name) + Lane 3 creative-studio files.

ZERO reliance on v1.1 — no splicing, no paste-from-prior-synthesis. All
content generated fresh from primary lane sources.

Output: /opt/amg-docs/SOLON_OS_v2.0.md (overwrites).

Usage:
  ssh 170.205.37.148
  source /root/.titan-env
  python3 /opt/titan-harness/scripts/mp2_synthesize_litellm.py
  # resume flag skips re-analyzing chunks if checkpoint present:
  python3 /opt/titan-harness/scripts/mp2_synthesize_litellm.py --resume
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import httpx

THREADS_DIR = Path("/opt/amg-titan/solon-corpus/claude-threads")
PROJECTS_DIR = Path("/opt/amg-titan/solon-corpus/claude-projects")
LANE3_DIR = Path("/opt/amg-titan/solon-corpus/creative-studio")
LANE2_INDEX = Path("/opt/amg-titan/solon-corpus/perplexity/pplx_thread_index.txt")
OUTPUT = Path("/opt/amg-docs/SOLON_OS_v2.0.md")
LOG = Path("/opt/amg-titan/solon-corpus/mp2-synthesis-litellm.log")
CHECKPOINT = Path("/opt/amg-titan/solon-corpus/.mp2-checkpoint-analyses.json")

LITELLM_BASE = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "").strip()

CHUNK_MODEL = os.environ.get("MP2_CHUNK_MODEL", "claude-haiku-4-5")
SYNTH_MODEL = os.environ.get("MP2_SYNTH_MODEL", "claude-sonnet-4-6")

TIMEOUT = 900                # Sonnet on ~140K input tokens needs several minutes
MAX_CHUNK_TOKENS = 2500      # compact analyses so 50 chunks fit Sonnet 200K context
MAX_SYNTH_TOKENS = 16000     # Sonnet 4.6 supports up to 64K, 16K safe
CREATIVE_CONVO_KEYWORDS = (
    "hit_maker", "creative", "music", "croon", "jingle", "solon_s_promoter",
    "solon_z_music", "solon_s_creative", "comedy", "serenad", "lyric",
)


def log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def litellm_call(prompt: str, model: str, max_tokens: int) -> str:
    if not LITELLM_KEY:
        raise RuntimeError("LITELLM_MASTER_KEY not set")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {LITELLM_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{LITELLM_BASE}/v1/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


def extract_human_messages(conv_json: dict) -> list[dict]:
    messages = []
    chat_messages = conv_json.get("chat_messages", []) or conv_json.get("messages", [])
    convo_name = conv_json.get("name", conv_json.get("title", "untitled"))
    for m in chat_messages:
        sender = m.get("sender", m.get("role", ""))
        if sender not in ("human", "user"):
            continue
        content = m.get("text", "")
        if not content:
            parts = m.get("content", [])
            if isinstance(parts, list):
                content = " ".join(
                    p.get("text", "") for p in parts
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            elif isinstance(parts, str):
                content = parts
        if content and len(content.strip()) > 10:
            messages.append({
                "text": content.strip(),
                "conversation": convo_name,
                "created": m.get("created_at", m.get("timestamp", "")),
            })
    return messages


def load_corpus() -> list[dict]:
    all_messages: list[dict] = []
    files = sorted(THREADS_DIR.glob("*.json"))
    for f in files:
        if f.name == "manifest.json":
            continue
        try:
            data = json.loads(f.read_text())
            all_messages.extend(extract_human_messages(data))
        except Exception as e:
            log(f"  Skip {f.name}: {e}")
    return all_messages


def chunk_messages(messages: list[dict], max_chars: int = 60000) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_len = 0
    for m in messages:
        text = m["text"]
        if current_len + len(text) > max_chars and current:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(m)
        current_len += len(text)
    if current:
        chunks.append(current)
    return chunks


def analyze_chunk(chunk: list[dict], chunk_num: int, total_chunks: int) -> dict:
    """Returns structured analysis with creative-tagged flag."""
    creative_tagged = any(
        any(kw in m["conversation"].lower() for kw in CREATIVE_CONVO_KEYWORDS)
        for m in chunk
    )
    messages_text = "\n\n---\n\n".join(
        f"[Conv: {m['conversation']}]\n{m['text'][:2000]}"
        for m in chunk
    )
    prompt = f"""You are analyzing messages written by a CEO named Solon Zafiropoulos. This is chunk {chunk_num}/{total_chunks} of his communication corpus from Claude.ai.

Extract PATTERNS (not individual messages) on:

1. **Communication patterns**: sentence structure, vocabulary, directness, metaphors, humor, profanity usage, emoji usage.
2. **Decision frameworks**: how he weighs trade-offs; speed vs quality; revenue vs brand; short vs long term; build vs buy.
3. **Values and principles**: what he cares about; excites him; frustrates him.
4. **Anti-patterns / pet peeves**: triggers corrections; behaviors he rejects; phrases he bans.
5. **Strategic vision**: what he's building; end-game; product roadmap.
6. **Personal context**: background, quirks, constraints.
7. **Burned corrections**: explicit corrections → rules → reasoning.
8. **Creative voice (if present)**: poetry/comedy/music-mode patterns. Only include if chunk has creative content — otherwise skip this section.

Be specific. Direct quotes up to 10 words each. Pattern-level, not message-by-message. Target 1500-2500 words.

MESSAGES:

{messages_text}"""
    try:
        analysis = litellm_call(prompt, CHUNK_MODEL, MAX_CHUNK_TOKENS)
    except Exception as e:
        log(f"  Chunk {chunk_num} error: {e}")
        analysis = f"[Analysis failed for chunk {chunk_num}: {e}]"
    return {
        "chunk_num": chunk_num,
        "total_chunks": total_chunks,
        "message_count": len(chunk),
        "creative_tagged": creative_tagged,
        "analysis": analysis,
    }


def save_checkpoint(analyses: list[dict]) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(analyses, indent=2))


def load_checkpoint() -> list[dict]:
    if not CHECKPOINT.exists():
        return []
    return json.loads(CHECKPOINT.read_text())


def load_lane3_sources() -> dict[str, str]:
    out: dict[str, str] = {}
    if not LANE3_DIR.exists():
        log(f"  Lane 3 dir missing: {LANE3_DIR}")
        return out
    for f in sorted(LANE3_DIR.glob("*.md")):
        try:
            out[f.name] = f.read_text()
        except Exception as e:
            log(f"  Skip Lane 3 {f.name}: {e}")
    log(f"Loaded Lane 3 sources: {len(out)} files, {sum(len(v) for v in out.values())} chars")
    return out


def load_lane2_index() -> str:
    if not LANE2_INDEX.exists():
        return ""
    try:
        content = LANE2_INDEX.read_text()
        log(f"Loaded Lane 2 Perplexity index: {len(content)} chars")
        return content[:40000]  # cap to keep synthesis prompt under limits
    except Exception as e:
        log(f"  Skip Lane 2 index: {e}")
        return ""


def synthesize_pass_1(
    analyses: list[dict], lane2_index: str
) -> str | None:
    """§1-§9 core behavioral profile."""
    lane1_combined = "\n\n===== CHUNK {n} ({cnt} msgs, creative_tagged={c}) =====\n\n{a}".join([""])  # placeholder
    lane1_combined = "\n\n".join(
        f"===== CHUNK {a['chunk_num']}/{a['total_chunks']} ({a['message_count']} msgs, creative={a['creative_tagged']}) =====\n\n{a['analysis']}"
        for a in analyses
    )
    lane2_block = f"\n\n===== LANE 2 PERPLEXITY THREAD INDEX (first 40KB) =====\n\n{lane2_index}" if lane2_index else ""

    prompt = f"""You are producing the CANONICAL Solon OS v2.0 behavioral profile — Pass 1 of 2. Your output will be the AUTHORITATIVE manual for every AI agent that works with Solon Zafiropoulos (AMG Atlas / Solon OS platform).

THIS PASS covers sections 1-9 of the final document. Section 10 (Voice Cloning Guide) and Section 11 (Creative Engine) are produced in Pass 2 — do NOT include them here.

INPUTS (triple-source, no v1.1 splicing):
- Lane 1: {len(analyses)} chunk-level analyses of 500 top messages from 1,294 Claude.ai conversations.
- Lane 2: Perplexity thread index (supplemental — research patterns, strategic context).

Produce exactly this structure (markdown, no code fences, no preamble):

# SOLON_OS v2.0 — The Solon Zafiropoulos Operating Manual for AI Agents

## 1. Who Is Solon
Background, role, what he does, self-concept. Ground every claim in corpus evidence.

## 2. Communication Style
Vocabulary, directness, humor, profanity, emoji, openers, closers, register-switching.

## 3. Decision Framework
Speed vs quality. Revenue vs brand. Short vs long term. Build vs buy. What data he requires. How much analysis before action. His actual sequence when deciding.

## 4. Values and Principles
Non-negotiables. What he's building toward. Family-heritage-as-operating-system if evidence supports it. Greek identity as brand architecture if evidence supports it.

## 5. Anti-Patterns and Pet Peeves
What triggers corrections. Specific phrases he bans. Behaviors that lose his trust. With direct-quote evidence where available.

## 6. Burned Corrections (The Don't-Repeat-These List)
For each burn: what was wrong → rule → reasoning. 8-15 items from corpus.

## 7. Strategic Vision
Where AMG is headed. Product roadmap implicit in his decisions. The end state.

## 8. Personal Context
Personal details that shape how he works — schedule, ADHD, constraints, preferences.

## 9. How to Work With Solon (The Meta-Rules)
Exactly 15 numbered behavioral rules for AI agents working with him. Each rule gets a bolded title + 2-4 bullet points. This is the TL;DR that gets injected as a system prompt.

REQUIREMENTS:
- Be SPECIFIC. No generic CEO advice. Everything uniquely Solon.
- Quote evidence where illuminating (max 10 words per quote, in quotation marks).
- Third person ("Solon prefers..." not "You prefer...").
- Target 5,000-7,000 words total for sections 1-9.
- Write as if this is the only doc any AI agent will read before interacting with Solon.
- NO v1.1 reference, no "per prior synthesis" — produce fresh from Lane 1 + Lane 2.

LANE 1 ANALYSES:
{lane1_combined}
{lane2_block}

PRODUCE THE DOCUMENT NOW. Sections 1-9 only."""
    try:
        return litellm_call(prompt, SYNTH_MODEL, MAX_SYNTH_TOKENS)
    except Exception as e:
        log(f"FATAL: Pass 1 synthesis failed: {e}")
        return None


def synthesize_pass_2(
    analyses: list[dict], lane3_sources: dict[str, str]
) -> str | None:
    """§10 Voice Cloning + §11 Creative Engine."""
    creative_chunks = [a for a in analyses if a.get("creative_tagged")]
    if not creative_chunks:
        creative_chunks = analyses  # fallback if no tags survived
    lane1_creative = "\n\n".join(
        f"===== CHUNK {a['chunk_num']}/{a['total_chunks']} =====\n\n{a['analysis']}"
        for a in creative_chunks
    )
    lane3_block = "\n\n".join(
        f"===== LANE 3 FILE: {name} =====\n\n{content}"
        for name, content in lane3_sources.items()
    )

    prompt = f"""You are producing the CANONICAL Solon OS v2.0 behavioral profile — Pass 2 of 2. This pass covers sections 10 and 11 ONLY. Sections 1-9 are already produced separately.

INPUTS (triple-source, no v1.1 splicing):
- Lane 1 creative-tagged chunks: {len(creative_chunks)} analyses from conversations involving music/poetry/comedy/Hit Maker/Creative Studio/Croon/lyricist work.
- Lane 3 source files: {len(lane3_sources)} Titan-side operator-memory files in /opt/amg-titan/solon-corpus/creative-studio/ — the authoritative input for voice + creative doctrine.

Produce exactly this structure (markdown, no code fences, no preamble):

## 10. Voice Cloning Guide

Actionable specifications for any AI that needs to write or speak IN Solon's voice (sales copy, client emails, chatbot replies, creative content). Ground in Lane 3 VOICE_PROFILE + MY_BEST_WORK + Lane 1 pattern evidence.

### 10.1 Sentence Architecture
Lead-with-point patterns, declarative vs narrative, question forms, rhythm.

### 10.2 Vocabulary Patterns
Words he uses frequently; words he uses for emphasis; words he never uses (corporate-speak to ban).

### 10.3 Emotional Register
Default / sales / frustration / creative / teaching modes.

### 10.4 Sales Personality Markers
How he sells. Results-first, specific numbers, positioning as builder-not-reseller, pricing-as-investment framing.

### 10.5 What Solon's Voice is NOT
Hard negatives — corporate, hedging, passive, sycophantic, detached.

### 10.6 Example Transformations
3-5 before/after pairs: generic agency/AI voice → Solon voice.

## 11. The Creative Engine — Solon the Artist

Ground entirely in Lane 3 COMEDY_GEARS + VOICE_PROFILE + MY_BEST_WORK + Solon_Z_Artist_Profile + MASTER_LYRICIST_TECHNIQUES + EMOTIONAL_VOCABULARY_BY_LANE + MUSICAL_DIRECTION_BLUEPRINT + Solon_Stories_Journal plus any creative-tagged Lane 1 evidence.

### 11.1 Three Creative Modes
Poetry (Neruda/Keats blend), Comedy (Pryor-primary/Gandolfini/Scarface secondary), Songs (Nat King Cole/Motown/Springsteen/Seger/Petty). With signature routines and real song titles where evidence supports.

### 11.2 The 4-Gear Comedy Calibration System
Table: Gear # | Label | When to Use | Example. From COMEDY_GEARS source.

### 11.3 Universal Voice DNA (Across All Three Modes)
Shared traits across poetry/comedy/songs — physical specificity, devotional certainty, musical flow, gift-energy, bilingual fluidity (English/Spanish/Greek), self-implication.

### 11.4 Creative Anti-Patterns (Hard Rules)
Never list — clichés, competition references, explanations, resume-energy, insecurity signals, punch-down, N-word.

### 11.5 The Creative Test
Ship gate per mode (poetry / comedy / songs) — the one-question verification.

### 11.6 Musical Direction Signature (from MUSICAL_DIRECTION_BLUEPRINT)
Key signatures, tempo ranges, harmonic preferences, production aesthetic.

### 11.7 Emotional Vocabulary by Lane (from EMOTIONAL_VOCABULARY_BY_LANE)
Which words land in which lane (blue-eyed soul English / Latin soul bilingual / Greek heritage).

REQUIREMENTS:
- Cite Lane 3 file names when quoting or paraphrasing.
- Direct song titles, routine names, specific references from source files.
- Target 2,000-3,500 words for sections 10-11 combined.
- NO reference to prior v1.1 synthesis.
- Third person.

LANE 1 CREATIVE-TAGGED ANALYSES:
{lane1_creative}

LANE 3 SOURCE FILES:
{lane3_block}

PRODUCE SECTIONS 10 + 11 NOW. Nothing else."""
    try:
        return litellm_call(prompt, SYNTH_MODEL, MAX_SYNTH_TOKENS)
    except Exception as e:
        log(f"FATAL: Pass 2 synthesis failed: {e}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Reuse cached chunk analyses from checkpoint")
    parser.add_argument("--synth-only", action="store_true", help="Skip chunk analysis; synthesize from existing checkpoint only")
    args = parser.parse_args()

    if not LITELLM_KEY:
        log("FATAL: LITELLM_MASTER_KEY not in env. source /root/.titan-env first.")
        return 1

    log(f"=== MP-2 Synthesis starting (LiteLLM port v2, chunk={CHUNK_MODEL}, synth={SYNTH_MODEL}) ===")

    # === Step A: chunk analyses (Lane 1) ===
    analyses: list[dict] = []
    if args.synth_only or args.resume:
        analyses = load_checkpoint()
        log(f"Loaded {len(analyses)} chunk analyses from checkpoint")

    if not args.synth_only:
        log("Loading corpus...")
        messages = load_corpus()
        n_files = len(list(THREADS_DIR.glob("*.json"))) - 1
        log(f"Loaded {len(messages)} human messages from {n_files} conversations")
        if len(messages) < 10:
            log("FATAL: too few messages for meaningful synthesis")
            return 1

        messages.sort(key=lambda m: len(m["text"]), reverse=True)
        selected = messages[:500]
        log(f"Selected top {len(selected)} messages by length")

        chunks = chunk_messages(selected, max_chars=60000)
        log(f"Split into {len(chunks)} analysis chunks")

        start_from = len(analyses)  # resume from checkpoint
        for i in range(start_from, len(chunks)):
            log(f"Analyzing chunk {i+1}/{len(chunks)} ({len(chunks[i])} messages)...")
            result = analyze_chunk(chunks[i], i + 1, len(chunks))
            analyses.append(result)
            save_checkpoint(analyses)
            time.sleep(0.5)
        log(f"All {len(analyses)} chunks analyzed + checkpoint saved")

    # === Step B: load Lane 2 + Lane 3 ===
    lane2_index = load_lane2_index()
    lane3_sources = load_lane3_sources()

    # === Step C: two-pass synthesis via Sonnet ===
    log(f"Pass 1 — synthesizing §1-§9 via {SYNTH_MODEL}...")
    pass1 = synthesize_pass_1(analyses, lane2_index)
    if not pass1:
        log("FATAL: Pass 1 returned None")
        return 2
    log(f"Pass 1 complete — {len(pass1)} chars")

    log(f"Pass 2 — synthesizing §10 Voice Cloning + §11 Creative Engine via {SYNTH_MODEL}...")
    pass2 = synthesize_pass_2(analyses, lane3_sources)
    if not pass2:
        log("FATAL: Pass 2 returned None")
        return 3
    log(f"Pass 2 complete — {len(pass2)} chars")

    # === Step D: assemble ===
    header = (
        "# SOLON_OS v2.0 — The Solon Zafiropoulos Operating Manual for AI Agents\n\n"
        "**Status:** CANONICAL. Supersedes v1.1 (2026-04-11) entirely.\n"
        f"**Synthesized:** {datetime.utcnow().strftime('%Y-%m-%d')} via triple-source MP-2 merge.\n"
        "**Source corpus:**\n"
        f"- **Lane 1 (Claude.ai harvest):** 1,294 conversations, 13,236 human messages. "
        f"Top 500 by length analyzed across {len(analyses)} chunks via `{CHUNK_MODEL}` through LiteLLM "
        "gateway (bypassed workspace usage cap via Bedrock/Vertex routing).\n"
        "- **Lane 2 (Perplexity):** thread-index 45KB — supplemental context. "
        "Full threads harvest deferred.\n"
        f"- **Lane 3 (Titan creative-studio):** {len(lane3_sources)} operator-memory source files "
        "(VOICE_PROFILE, COMEDY_GEARS, MY_BEST_WORK, Solon_Z_Artist_Profile, etc.) — primary input "
        "for §10 Voice Cloning + §11 Creative Engine.\n"
        f"**Synthesis model:** `{SYNTH_MODEL}` (two-pass: §1-§9 + §10-§11). MP-2 script: "
        "`scripts/mp2_synthesize_litellm.py`.\n"
        "**Classification:** INTERNAL — AMG Operator Infrastructure.\n"
        "**Injection target:** all agent system prompts (Alex, Atlas, Maya, Jordan, Sam, Riley, "
        "Nadia, Lumina) + `lib/atlas_api.py::_alex_system_prompt`.\n\n"
        "---\n\n"
    )
    # Strip any leading "# SOLON_OS v2.0 ..." duplicate that Pass 1 may emit
    p1 = pass1.strip()
    if p1.startswith("# SOLON_OS"):
        # remove the first heading line
        p1 = p1.split("\n", 1)[1].lstrip("\n")

    final = header + p1 + "\n\n---\n\n" + pass2.strip() + "\n\n---\n\n"
    final += (
        f"*Document version: v2.0 (canonical)*\n"
        f"*Source: triple-source MP-2 merge — Lane 1 ({len(analyses)} chunk analyses), "
        f"Lane 2 (Perplexity index 40KB), Lane 3 ({len(lane3_sources)} creative-studio files).*\n"
        f"*Synthesized: {datetime.utcnow().strftime('%Y-%m-%d')} via `{SYNTH_MODEL}` two-pass "
        "through LiteLLM gateway.*\n"
        "*Supersedes: v1.1 (2026-04-11) and Lane 3 bridge — splicing removed per "
        "2026-04-18 Solon directive.*\n"
        "*Classification: INTERNAL — AMG Operator Infrastructure*\n"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(final)
    log(f"WROTE {OUTPUT} ({len(final)} chars, {final.count(chr(10))} lines)")
    log("=== MP-2 Synthesis complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
