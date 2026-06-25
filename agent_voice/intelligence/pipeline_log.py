"""Append a structured record of the notification pipeline to ``summary.log``.

This makes the whole path observable: the raw last message, the prompt sent to
the model, the model's raw and cleaned output, and the final spoken text. Writing
is best-effort and never raises, so logging can never break notification delivery.

The log can contain the full assistant message in plaintext, so it is created with
owner-only permissions (0600), matching the rest of ``~/.voiccce``, and is
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


def _max_log_bytes(config: AgentVoiceConfig) -> int:
    """Resolve the rotation threshold, honouring [daemon].max_log_bytes when set."""
    configured = getattr(config, "max_log_bytes", None)
    if isinstance(configured, int) and configured > 0:
        return configured
    return MAX_LOG_BYTES


def log_summary_pipeline(config: AgentVoiceConfig, record: dict[str, Any]) -> None:
    # Gated by [summary].pipeline_log; a no-op (writes nothing) when disabled.
    if not getattr(config, "summary_pipeline_log", True):
        return
    try:
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        path = pipeline_log_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(path, _max_log_bytes(config))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        path.chmod(0o600)
    except (OSError, TypeError, ValueError):
        # Observability must never take down the daemon.
        pass


def truncate_pipeline_log(config: AgentVoiceConfig) -> None:
    """Clear ``summary.log`` and its rotated ``summary.log.1`` file.

    Best-effort like the writer: any I/O error is swallowed so clearing the log can
    never take down the caller.
    """
    path = pipeline_log_path(config)
    for target in (path, path.with_suffix(path.suffix + ".1")):
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


def _rotate_if_needed(path: Path, max_bytes: int) -> None:
    try:
        if path.exists() and path.stat().st_size > max_bytes:
            path.replace(path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass
