from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path

from .config import AgentVoiceConfig

VOICE_ACTIVITY_STALE_SECONDS = 15 * 60


@dataclass(frozen=True, slots=True)
class VoiceMuteStatus:
    muted: bool
    muted_until: int | None = None


def runtime_state_path(config: AgentVoiceConfig) -> Path:
    return config.config_path.parent / "runtime.json"


def voice_pid_path(config: AgentVoiceConfig) -> Path:
    return config.config_path.parent / "voice.pid"


def read_runtime_state(config: AgentVoiceConfig) -> dict[str, object]:
    path = runtime_state_path(config)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_runtime_state(config: AgentVoiceConfig, state: dict[str, object]) -> None:
    path = runtime_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.chmod(0o600)
    os.replace(tmp_path, path)


def parse_duration_seconds(value: str) -> int:
    raw = value.strip().lower()
    if not raw:
        raise ValueError("Duration is empty")
    unit = raw[-1]
    number = raw[:-1] if unit.isalpha() else raw
    if not number.isdigit():
        raise ValueError(f"Invalid duration '{value}'")
    amount = int(number)
    if amount <= 0:
        raise ValueError("Duration must be positive")
    if unit == "s":
        return amount
    if unit == "m" or not unit.isalpha():
        return amount * 60
    if unit == "h":
        return amount * 60 * 60
    raise ValueError(f"Unsupported duration unit '{unit}'. Use s, m, or h")


def parse_age_seconds(value: str | int) -> int:
    raw = str(value).strip().lower()
    if not raw:
        raise ValueError("Age is empty")
    unit = raw[-1]
    number = raw[:-1] if unit.isalpha() else raw
    if not number.isdigit():
        raise ValueError(f"Invalid age '{value}'")
    amount = int(number)
    if amount <= 0:
        raise ValueError("Age must be positive")
    if unit == "s" or not unit.isalpha():
        return amount
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 60 * 60
    if unit == "d":
        return amount * 60 * 60 * 24
    raise ValueError(f"Unsupported age unit '{unit}'. Use s, m, h, or d")


def set_voice_mute(config: AgentVoiceConfig, duration_seconds: int, *, now: int | None = None) -> int:
    current_time = now or int(time.time())
    muted_until = current_time + duration_seconds
    state = read_runtime_state(config)
    state["voice_muted_until"] = muted_until
    write_runtime_state(config, state)
    return muted_until


def clear_voice_mute(config: AgentVoiceConfig) -> None:
    state = read_runtime_state(config)
    state.pop("voice_muted_until", None)
    write_runtime_state(config, state)


def voice_mute_status(config: AgentVoiceConfig, *, now: int | None = None) -> VoiceMuteStatus:
    current_time = now or int(time.time())
    state = read_runtime_state(config)
    muted_until = state.get("voice_muted_until")
    if not isinstance(muted_until, int):
        return VoiceMuteStatus(muted=False)
    if muted_until <= current_time:
        clear_voice_mute(config)
        return VoiceMuteStatus(muted=False)
    return VoiceMuteStatus(muted=True, muted_until=muted_until)


def is_voice_muted(config: AgentVoiceConfig) -> bool:
    return voice_mute_status(config).muted


def start_voice_activity(config: AgentVoiceConfig, *, now: float | None = None) -> float:
    started_at = now or time.time()
    state = read_runtime_state(config)
    state["voice_activity_started_at"] = started_at
    write_runtime_state(config, state)
    return started_at


def clear_voice_activity(config: AgentVoiceConfig, started_at: float | None = None) -> None:
    state = read_runtime_state(config)
    current_started_at = state.get("voice_activity_started_at")
    if (
        started_at is not None
        and isinstance(current_started_at, int | float)
        and float(current_started_at) != started_at
    ):
        return
    state.pop("voice_activity_started_at", None)
    write_runtime_state(config, state)


def read_voice_activity_started_at(
    config: AgentVoiceConfig,
    *,
    now: float | None = None,
    max_age_seconds: float = VOICE_ACTIVITY_STALE_SECONDS,
) -> float | None:
    current_time = now or time.time()
    state = read_runtime_state(config)
    started_at = state.get("voice_activity_started_at")
    if not isinstance(started_at, int | float):
        return None
    started_at = float(started_at)
    if started_at <= 0 or current_time - started_at > max_age_seconds:
        clear_voice_activity(config, started_at)
        return None
    return started_at


def set_active_voice_sessions(
    config: AgentVoiceConfig, sessions: list[str], *, now: float | None = None
) -> None:
    started_at = now or time.time()
    state = read_runtime_state(config)
    state["voice_active_sessions"] = [s for s in sessions if s]
    state["voice_active_sessions_at"] = started_at
    write_runtime_state(config, state)


def clear_active_voice_sessions(config: AgentVoiceConfig) -> None:
    state = read_runtime_state(config)
    state.pop("voice_active_sessions", None)
    state.pop("voice_active_sessions_at", None)
    write_runtime_state(config, state)


def voice_session_active(
    config: AgentVoiceConfig,
    session_id: str,
    *,
    now: float | None = None,
    max_age_seconds: float = VOICE_ACTIVITY_STALE_SECONDS,
) -> bool:
    current_time = now or time.time()
    state = read_runtime_state(config)
    started_at = state.get("voice_active_sessions_at")
    if not isinstance(started_at, int | float) or current_time - float(started_at) > max_age_seconds:
        return False
    sessions = state.get("voice_active_sessions")
    return isinstance(sessions, list) and session_id in sessions


def request_voice_stop(config: AgentVoiceConfig, *, now: float | None = None) -> float:
    stopped_at = now or time.time()
    state = read_runtime_state(config)
    state["voice_stop_requested_at"] = stopped_at
    write_runtime_state(config, state)
    return stopped_at


def voice_stop_requested_after(config: AgentVoiceConfig, started_at: float) -> bool:
    state = read_runtime_state(config)
    stopped_at = state.get("voice_stop_requested_at")
    return isinstance(stopped_at, int | float) and stopped_at >= started_at


def write_voice_pid(config: AgentVoiceConfig, pid: int) -> None:
    path = voice_pid_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")
    path.chmod(0o600)


def read_voice_pid(config: AgentVoiceConfig) -> int | None:
    try:
        return int(voice_pid_path(config).read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def clear_voice_pid(config: AgentVoiceConfig, pid: int | None = None) -> None:
    current_pid = read_voice_pid(config)
    if pid is not None and current_pid is not None and current_pid != pid:
        return
    voice_pid_path(config).unlink(missing_ok=True)


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_speaking(config: AgentVoiceConfig) -> int | None:
    request_voice_stop(config)
    pid = read_voice_pid(config)
    if not pid:
        return None
    if is_pid_running(pid):
        terminate_process_group(pid)
    clear_voice_pid(config, pid)
    return pid


def terminate_process_group(pid: int) -> None:
    use_process_group = False
    try:
        use_process_group = os.getpgid(pid) == pid
    except OSError:
        return

    try:
        if use_process_group:
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        return

    deadline = time.time() + 0.4
    while time.time() < deadline:
        if not is_pid_running(pid):
            return
        time.sleep(0.05)

    try:
        if use_process_group:
            os.killpg(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
