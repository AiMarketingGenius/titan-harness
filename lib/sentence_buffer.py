"""
lib/sentence_buffer.py — Hermes Phase A Step 7

Streaming sentence buffer for Claude -> TTS pipeline. Yields complete sentences
as they materialise from a token stream, so the first Kokoro TTS chunk can fire
before the LLM finishes its full response.

Doctrine reference: plans/DOCTRINE_VOICE_AI_STACK_v1.0.md §"Step 7 — Sentence
Buffering + First-Chunk Streaming".

Design rules (from doctrine + plan §5 Step 7):
- Split only on `.`, `!`, or `?` followed by whitespace AND an uppercase letter
  (or end-of-string), to avoid false splits inside URLs, phone numbers, and
  decimal numbers.
- Do not split mid-URL or mid-phone-number.
- Emit the trailing fragment if the stream ends without a terminal punctuation.
- Accept either a sync iterable (list of str chunks) or a generator.

Public API:
    sentence_buffer(stream) -> Iterator[str]

Self-test:
    python3 -m lib.sentence_buffer --self-test
"""

from __future__ import annotations

import re
import sys
from typing import Iterable, Iterator

# A sentence boundary is a [.!?] followed by whitespace and either an uppercase
# letter OR the end of buffer. We use a lookahead so the terminator stays with
# the sentence we are yielding.
_BOUNDARY = re.compile(r'([.!?])\s+(?=[A-Z"“\'(\[])')

# Patterns that must not be split even if they contain a period.
_URL = re.compile(r'https?://\S+|www\.\S+')
_PHONE = re.compile(r'\+?\d[\d .\-()]{7,}\d')
_DECIMAL = re.compile(r'\d+\.\d+')
_ABBREV = re.compile(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|Inc|Ltd|etc|vs|e\.g|i\.e|St|Mt|Ave|Blvd)\.')


def _mask_non_splitting(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Replace URLs / phones / decimals / abbreviations with placeholder tokens
    so the sentence-boundary regex cannot split inside them. Returns the masked
    text and a list of (index, original) tuples to reverse the mask."""
    replacements: list[tuple[int, str]] = []
    idx = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal idx
        original = match.group(0)
        placeholder = f"\x00{idx}\x00"
        replacements.append((idx, original))
        idx += 1
        return placeholder

    masked = _URL.sub(_sub, text)
    masked = _PHONE.sub(_sub, masked)
    masked = _DECIMAL.sub(_sub, masked)
    masked = _ABBREV.sub(_sub, masked)
    return masked, replacements


def _unmask(text: str, replacements: list[tuple[int, str]]) -> str:
    for idx, original in replacements:
        text = text.replace(f"\x00{idx}\x00", original)
    return text


def _split_sentences(buffer: str) -> tuple[list[str], str]:
    """Return (complete_sentences, leftover_fragment). Only yields sentences
    that have a confirmed boundary; the leftover fragment stays in the buffer
    until more tokens arrive."""
    masked, replacements = _mask_non_splitting(buffer)
    # Find all boundary positions in the masked text.
    boundaries: list[int] = []
    for m in _BOUNDARY.finditer(masked):
        # End index of the captured punctuation — we split AFTER that point
        # (plus following whitespace).
        end = m.end()
        boundaries.append(end)

    if not boundaries:
        return [], buffer

    sentences_masked: list[str] = []
    start = 0
    for end in boundaries:
        segment = masked[start:end].strip()
        if segment:
            sentences_masked.append(segment)
        start = end

    leftover_masked = masked[start:]
    sentences = [_unmask(s, replacements) for s in sentences_masked]
    leftover = _unmask(leftover_masked, replacements)
    return sentences, leftover


def sentence_buffer(stream: Iterable[str]) -> Iterator[str]:
    """Yield complete sentences as they materialise from *stream*.

    *stream* can be any iterable of str chunks (e.g. a Claude streaming
    generator that yields delta tokens). The final non-empty fragment is
    yielded after the stream ends even if it lacks a terminator — this
    ensures the caller never loses the tail of a response.
    """
    buffer = ""
    for chunk in stream:
        if not chunk:
            continue
        buffer += chunk
        complete, buffer = _split_sentences(buffer)
        for sentence in complete:
            if sentence.strip():
                yield sentence
    if buffer.strip():
        yield buffer.strip()


# ─── self-test ────────────────────────────────────────────────────────────────

def _self_test() -> int:
    cases: list[tuple[str, list[str], list[str]]] = [
        (
            "simple two-sentence stream",
            ["Hello world. ", "This is Hermes."],
            ["Hello world.", "This is Hermes."],
        ),
        (
            "sentence split across token boundary",
            ["Hel", "lo wo", "rld. Now ", "Hermes speaks."],
            ["Hello world.", "Now Hermes speaks."],
        ),
        (
            "URL must not split",
            ["Visit https://example.com/path for details. Then reply."],
            ["Visit https://example.com/path for details.", "Then reply."],
        ),
        (
            "phone number must not split",
            ["Call me at 555.123.4567 today. I will answer."],
            ["Call me at 555.123.4567 today.", "I will answer."],
        ),
        (
            "decimal number must not split",
            ["The cost is 3.14 dollars. That is low."],
            ["The cost is 3.14 dollars.", "That is low."],
        ),
        (
            "tail fragment without terminator is still yielded",
            ["This is complete. ", "This is a tail"],
            ["This is complete.", "This is a tail"],
        ),
    ]

    failures = 0
    for name, stream, expected in cases:
        got = list(sentence_buffer(stream))
        if got == expected:
            print(f"  PASS  {name}")
        else:
            failures += 1
            print(f"  FAIL  {name}")
            print(f"        expected: {expected}")
            print(f"        got:      {got}")

    print(f"\n{len(cases) - failures}/{len(cases)} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print("Usage: python3 -m lib.sentence_buffer --self-test", file=sys.stderr)
    sys.exit(2)
