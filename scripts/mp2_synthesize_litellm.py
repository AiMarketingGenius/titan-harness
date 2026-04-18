#!/usr/bin/env python3
"""MP-2 Solon OS synthesis — LiteLLM gateway port.

Rewrites mp2-synthesize.py (original at /opt/amg-titan/solon-corpus/mp2-synthesize.py)
to route through LiteLLM (127.0.0.1:4000) instead of direct anthropic SDK.

WHY: direct anthropic SDK hit workspace usage cap on 2026-04-16T02:04Z; regains
2026-05-01. LiteLLM gateway routes through Bedrock / Vertex bearer tokens
(AWS_BEARER_TOKEN_BEDROCK + GCP SA in /opt/amg-titan/.env) which are per-vendor,
not per-workspace, and are uncapped relative to the direct path.

Both claude-haiku-4-5 and claude-sonnet-4-6 verified live via LiteLLM on
2026-04-18T03:47Z (returned "alive" on 10-token probe).

Same 34-chunk logic, same prompts, same output structure as the original.
Output goes to /opt/amg-docs/SOLON_OS_v2.0.md (NOT v1.0 — superseding v1.1
bridge per FOCUS v2 Item #1 completion spec).

Usage:
  ssh 170.205.37.148
  source /root/.titan-env
  python3 /opt/titan-harness/scripts/mp2_synthesize_litellm.py
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import httpx

THREADS_DIR = Path("/opt/amg-titan/solon-corpus/claude-threads")
PROJECTS_DIR = Path("/opt/amg-titan/solon-corpus/claude-projects")
OUTPUT = Path("/opt/amg-docs/SOLON_OS_v2.0.md")
LOG = Path("/opt/amg-titan/solon-corpus/mp2-synthesis-litellm.log")

LITELLM_BASE = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "").strip()
MODEL = os.environ.get("MP2_MODEL", "claude-haiku-4-5")
TIMEOUT = 120
MAX_CHUNK_TOKENS = 4000
MAX_SYNTH_TOKENS = 8192


def log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def litellm_call(prompt: str, max_tokens: int) -> str:
    """Single LiteLLM chat completion. Returns assistant text or raises."""
    if not LITELLM_KEY:
        raise RuntimeError("LITELLM_MASTER_KEY not set in environment")
    payload = {
        "model": MODEL,
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
                "conversation": conv_json.get("name", conv_json.get("title", "untitled")),
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
        if current_len + len(text) > max_chars:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(m)
        current_len += len(text)
    if current:
        chunks.append(current)
    return chunks


def analyze_chunk(chunk: list[dict], chunk_num: int, total_chunks: int) -> str:
    messages_text = "\n\n---\n\n".join(
        f"[Conv: {m['conversation']}]\n{m['text'][:2000]}"
        for m in chunk
    )
    prompt = f"""You are analyzing messages written by a CEO named Solon Zafiropoulos. This is chunk {chunk_num}/{total_chunks} of his communication corpus from Claude.ai conversations.

Analyze these messages and extract:

1. **Communication patterns**: How does he write? Sentence structure, vocabulary level, directness, use of metaphor, humor style, profanity patterns, emoji usage.
2. **Decision frameworks**: How does he make decisions? What does he weigh? Speed vs quality? Revenue vs brand? Short-term vs long-term?
3. **Values and principles**: What does he clearly care about? What makes him excited? What makes him frustrated?
4. **Anti-patterns / pet peeves**: What does he hate? What triggers corrections? What does he never want to see?
5. **Strategic vision**: What is he building? Where does he see the company going? What's the end-game?
6. **Personal context**: Any personal details, background, quirks, or preferences that shape how he works.
7. **Burned corrections**: Times he explicitly corrected an AI or team member — what was wrong and what was the rule going forward?

Be specific. Use direct quotes where illuminating (max 10 words each). Focus on PATTERNS not individual messages.

Here are his messages:

{messages_text}"""
    try:
        return litellm_call(prompt, MAX_CHUNK_TOKENS)
    except Exception as e:
        log(f"  Chunk {chunk_num} LiteLLM error: {e}")
        return f"[Analysis failed for chunk {chunk_num}: {e}]"


def synthesize_final(analyses: list[str]) -> str | None:
    combined = "\n\n===== CHUNK ANALYSIS =====\n\n".join(analyses)
    prompt = f"""You have {len(analyses)} chunk-level analyses of Solon Zafiropoulos's communication corpus from Claude.ai (1000+ conversations, 50+ projects). Your job is to synthesize these into a single, definitive document: **SOLON_OS_v2.0.md** — the operating system for any AI that works with Solon.

The document should be structured as:

# SOLON_OS v2.0 — The Solon Zafiropoulos Operating Manual for AI Agents

## 1. Who Is Solon
Background, role, what he does, how he thinks about himself and his company.

## 2. Communication Style
How he writes, speaks, and expects to be spoken to. Include: vocabulary, directness level, humor, profanity comfort, emoji usage, sentence patterns, opener preferences, closer preferences.

## 3. Decision Framework
How he weighs trade-offs. Speed vs. quality. Revenue vs. brand. Short-term vs. long-term. Build vs. buy. What data does he need? How much analysis before action?

## 4. Values and Principles
What he deeply cares about. What drives him. What he's building toward. The non-negotiables.

## 5. Anti-Patterns and Pet Peeves
What makes him frustrated. What he corrects. What he never wants to see from an AI or team member. Specific phrases to avoid. Behaviors to avoid.

## 6. Burned Corrections (The Don't-Repeat-These List)
Specific corrections he's made, synthesized into rules. Each should be: what was wrong, what the rule is, and why.

## 7. Strategic Vision
Where AMG is headed. The product roadmap implicit in his decisions. What the end state looks like.

## 8. Personal Context
Anything personal that shapes how he works — schedule preferences, energy patterns, communication channel preferences, stress responses.

## 9. How to Work With Solon (The Meta-Rules)
The top 10-15 behavioral rules for any AI agent working with him. This is the TL;DR that gets injected as a system prompt for every AI interaction.

## 10. Voice Cloning Guide
If an AI needed to write AS Solon (not TO Solon), what would the style guide be? Sentence structure templates, vocabulary choices, tone calibration.

Rules:
- Be SPECIFIC. No generic CEO advice. Everything should be uniquely Solon.
- Use evidence from the analyses. Reference specific patterns, not speculation.
- This document will be used as a system prompt injection for AI agents. Make it actionable.
- Target 5,000-8,000 words. Comprehensive but not bloated.
- Write in the third person ("Solon prefers..." not "You prefer...").

Here are the chunk analyses:

{combined}"""
    try:
        return litellm_call(prompt, MAX_SYNTH_TOKENS)
    except Exception as e:
        log(f"FATAL: synthesis failed: {e}")
        return None


def main() -> int:
    if not LITELLM_KEY:
        log("FATAL: LITELLM_MASTER_KEY not in env. source /root/.titan-env first.")
        return 1
    log(f"=== MP-2 Synthesis starting (LiteLLM port, model={MODEL}) ===")

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

    analyses: list[str] = []
    for i, chunk in enumerate(chunks):
        log(f"Analyzing chunk {i+1}/{len(chunks)} ({len(chunk)} messages)...")
        result = analyze_chunk(chunk, i + 1, len(chunks))
        analyses.append(result)
        time.sleep(0.5)

    log(f"All {len(analyses)} chunks analyzed. Synthesizing final document...")

    final = synthesize_final(analyses)
    if not final:
        log("FATAL: synthesis returned None")
        return 2

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(final)
    log(f"WROTE {OUTPUT} ({len(final)} chars)")
    log("=== MP-2 Synthesis complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
