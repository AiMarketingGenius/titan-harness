"""Hermes Phase A Step 7 — sentence_buffer pytest suite.

Plan §5 Step 7 acceptance: `python3 -m pytest tests/test_sentence_buffer.py`
passes 6 cases (short sentence, long sentence, mid-URL, mid-phone, mid-decimal,
empty / tail fragment).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.sentence_buffer import sentence_buffer  # noqa: E402


def _run(stream):
    return list(sentence_buffer(stream))


def test_short_sentence():
    assert _run(["Hello world. This is Hermes."]) == ["Hello world.", "This is Hermes."]


def test_long_sentence_across_many_chunks():
    chunks = [
        "The quick brown fox jumps ",
        "over the lazy dog and then ",
        "continues running through the ",
        "forest until sunset. ",
        "Then the story ends.",
    ]
    result = _run(chunks)
    assert result[0] == (
        "The quick brown fox jumps over the lazy dog and then continues "
        "running through the forest until sunset."
    )
    assert result[1] == "Then the story ends."


def test_mid_url_is_not_split():
    result = _run(["Visit https://example.com/some.path for details. Then reply."])
    assert result == [
        "Visit https://example.com/some.path for details.",
        "Then reply.",
    ]


def test_mid_phone_number_is_not_split():
    result = _run(["Call me at 555.123.4567 today. I will answer soon."])
    assert result == [
        "Call me at 555.123.4567 today.",
        "I will answer soon.",
    ]


def test_mid_decimal_is_not_split():
    result = _run(["The cost is 3.14 dollars. That is low."])
    assert result == ["The cost is 3.14 dollars.", "That is low."]


def test_empty_and_tail_fragment():
    # Empty chunks should be ignored; tail without terminator should still fire.
    result = _run(["", "Complete sentence. ", "", "Tail fragment"])
    assert result == ["Complete sentence.", "Tail fragment"]
