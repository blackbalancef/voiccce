"""Append a structured record of the notification pipeline to ``summary.log``.

This makes the whole path observable: the raw last message, the prompt sent to
the model, the model's raw and cleaned output, and the final spoken text. Writing
is best-effort and never raises, so logging can never break notification delivery.

The log can contain the full assistant message in plaintext, so it is created with
owner-only permissions (0600), matching the rest of ``~/.agent-chime``, and is
rotated once it grows past ``MAX_LOG_BYTES`` to avoid unbounded growth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_voice.config import AgentVoiceConfig

PIPELINE_LOG_NAME = "summary.log"
MAX_LOG_BYTES = 5 * 1024 * 1024


def pipeline_log_path(config: AgentVoiceConfig) -> Path:
    return config.config_path.parent / PIPELINE_LOG_NAME


def log_summary_pipeline(config: AgentVoiceConfig, record: dict[str, Any]) -> None:
    try:
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        path = pipeline_log_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        path.chmod(0o600)
    except (OSError, TypeError, ValueError):
        # Observability must never take down the daemon.
        pass


def _rotate_if_needed(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
            path.replace(path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass
