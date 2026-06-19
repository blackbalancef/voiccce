"""Shared helpers for turning a raw assistant message into a short, speakable summary.

Both the Claude Code and Codex collectors use these helpers, so the truncation
rules live in one place and cannot drift between agents.
"""

from __future__ import annotations

import re
from typing import Any

GENERIC_DONE_PREFIX_RE = re.compile(
    r"^(done|completed|finished)\.?\s*",
    re.IGNORECASE,
)

# A sentence terminator followed by whitespace or end-of-text.
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")

# Below this many characters a "sentence" or "word" cut is not worth it; we would
# rather keep the whole truncated window than emit a two-word fragment.
_MIN_USEFUL_CUT = 60


def shorten(value: Any, max_chars: int = 120) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def summary_source_text(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    return text or None


def clean_assistant_message(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = " ".join(text.strip().split()).strip(" -:;")
    return text.rstrip(".") or None


def summarize_assistant_message(value: Any, max_chars: int = 220) -> str | None:
    text = clean_assistant_message(value)
    if not text:
        return None

    summary = GENERIC_DONE_PREFIX_RE.sub("", text).strip(" -:;")
    if not summary:
        return None
    if len(summary) <= max_chars:
        return summary.rstrip(".")

    # Prefer ending on a complete sentence inside the limit.
    sentence_cut = _last_sentence_end(summary, max_chars)
    if sentence_cut >= _MIN_USEFUL_CUT:
        return summary[:sentence_cut].rstrip(".")

    # Otherwise stop on a word boundary. A mid-word hard cut only happens for text
    # that has no whitespace at all (a single huge token or a space-free script).
    return _cut_on_word_boundary(summary, max_chars)


def _last_sentence_end(text: str, max_chars: int) -> int:
    end = -1
    for match in _SENTENCE_END_RE.finditer(text, 0, max_chars):
        end = match.end()
    return end


def _cut_on_word_boundary(text: str, max_chars: int) -> str:
    # Reserve room for the trailing ellipsis so the result stays within max_chars.
    window = text[: max(1, max_chars - 3)]
    last_space = window.rfind(" ")
    head = window[:last_space] if last_space > 0 else window
    return head.rstrip(" ,;:.") + "..."
