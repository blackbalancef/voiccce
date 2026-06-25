from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .config import AgentVoiceConfig


def _version() -> str:
    """Best-effort package version: prefer ``agent_voice.__version__``, fall back
    to :mod:`importlib.metadata`, and finally ``"unknown"``."""
    try:
        from . import __version__  # local import keeps the module import cheap

        if __version__:
            return str(__version__)
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        from importlib import metadata

        return metadata.version("voiccce")
    except Exception:  # pragma: no cover - metadata may be absent in source checkouts
        return "unknown"


def heartbeat_path(config: AgentVoiceConfig) -> Path:
    """Path to the daemon heartbeat file, a sibling of ``daemon.pid``."""
    return config.config_path.parent / "daemon.heartbeat"


def write_heartbeat(config: AgentVoiceConfig, *, now: float | None = None) -> None:
    """Persist the current epoch, pid, and version as JSON (best-effort).

    Written atomically so a reader never sees a half-written file. Any I/O error
    is swallowed: a missed heartbeat must never take the daemon down.
    """
    path = heartbeat_path(config)
    payload = {
        "ts": int(now if now is not None else time.time()),
        "pid": os.getpid(),
        "version": _version(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        tmp_path.chmod(0o600)
        os.replace(tmp_path, path)
    except OSError:
        return


def read_heartbeat(config: AgentVoiceConfig) -> dict | None:
    """Return the parsed heartbeat mapping, or ``None`` if missing/unreadable."""
    path = heartbeat_path(config)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def heartbeat_age_seconds(config: AgentVoiceConfig, *, now: float | None = None) -> float | None:
    """Seconds since the last heartbeat, or ``None`` when there is no usable timestamp."""
    heartbeat = read_heartbeat(config)
    if not heartbeat:
        return None
    ts = heartbeat.get("ts")
    if not isinstance(ts, (int, float)):
        return None
    current_time = now if now is not None else time.time()
    return max(0.0, current_time - float(ts))
