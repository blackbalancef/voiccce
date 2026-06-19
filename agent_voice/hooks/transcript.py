"""Read the full final assistant turn from an agent transcript file.

Hook payloads often carry only a truncated ``last_assistant_message``. When a
``transcript_path`` is available we read the whole final assistant turn from the
JSONL transcript instead, so the summarizer gets the complete text rather than a
clipped preview.

A single logical turn is split across several JSONL lines (text block, tool_use,
tool_result, more text). We accumulate every assistant text block since the last
real user prompt; tool-result lines (stored with role ``user``) do not start a new
turn. Everything here is best-effort: any parsing or IO failure returns ``None``
and the caller falls back to the payload value.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Guard against pathological transcripts; a single assistant turn is tiny.
_MAX_TRANSCRIPT_BYTES = 64 * 1024 * 1024


def read_last_assistant_text(transcript_path: str | None) -> str | None:
    if not transcript_path:
        return None
    try:
        path = Path(transcript_path).expanduser()
        if not path.is_file() or path.stat().st_size > _MAX_TRANSCRIPT_BYTES:
            return None
        turn_texts: list[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError, RecursionError):
                    continue
                if not isinstance(entry, dict):
                    continue
                if _is_turn_boundary(entry):
                    turn_texts = []
                    continue
                if _is_assistant_entry(entry):
                    text = _entry_text(entry)
                    if text:
                        turn_texts.append(text)
        joined = "\n".join(turn_texts).strip()
        return joined or None
    except Exception:
        # Best-effort: never let transcript parsing crash the collector/hook.
        return None


def _role(entry: dict[str, Any]) -> str | None:
    role = entry.get("role") or entry.get("type")
    message = entry.get("message")
    if not role and isinstance(message, dict):
        role = message.get("role")
    return role


def _raw_content(entry: dict[str, Any]) -> Any:
    message = entry.get("message")
    if isinstance(message, dict) and message.get("content") is not None:
        return message.get("content")
    return entry.get("content")


def _is_assistant_entry(entry: dict[str, Any]) -> bool:
    return _role(entry) == "assistant"


def _is_turn_boundary(entry: dict[str, Any]) -> bool:
    """A genuine user prompt starts a new turn; tool-result echoes do not."""
    if _role(entry) not in {"user", "human"}:
        return False
    content = _raw_content(entry)
    if isinstance(content, list) and content and all(
        isinstance(block, dict) and block.get("type") == "tool_result" for block in content
    ):
        return False
    return True


def _entry_text(entry: dict[str, Any]) -> str | None:
    text = _content_text(_raw_content(entry))
    if text:
        return text
    message = entry.get("message")
    direct = entry.get("text") or (message.get("text") if isinstance(message, dict) else None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    return None


def _content_text(content: Any) -> str | None:
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") in {None, "text", "output_text"}:
            value = block.get("text")
            if isinstance(value, str):
                parts.append(value)
    joined = "\n".join(part for part in parts if part.strip())
    return joined.strip() or None
