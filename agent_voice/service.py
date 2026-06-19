from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .config import AgentVoiceConfig


@dataclass(frozen=True, slots=True)
class ServicePaths:
    pid_path: Path
    log_path: Path


def service_paths(config: AgentVoiceConfig) -> ServicePaths:
    home = config.config_path.parent
    return ServicePaths(pid_path=home / "daemon.pid", log_path=home / "daemon.log")


def menubar_service_paths(config: AgentVoiceConfig) -> ServicePaths:
    home = config.config_path.parent
    return ServicePaths(pid_path=home / "menubar.pid", log_path=home / "menubar.log")


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def start_daemon(config: AgentVoiceConfig) -> int:
    return _start_background_process(
        config,
        paths=service_paths(config),
        command=["daemon"],
    )


def start_menubar(config: AgentVoiceConfig) -> int:
    return _start_background_process(
        config,
        paths=menubar_service_paths(config),
        command=["menubar"],
    )


def _start_background_process(config: AgentVoiceConfig, *, paths: ServicePaths, command: list[str]) -> int:
    existing_pid = read_pid(paths.pid_path)
    if existing_pid and is_pid_running(existing_pid):
        return existing_pid

    paths.pid_path.parent.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}:{env.get('PYTHONPATH', '')}"
    log_file = paths.log_path.open("ab")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent_voice",
            "--config",
            str(config.config_path),
            *command,
        ],
        cwd=str(repo_root),
        env=env,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
    )
    paths.pid_path.write_text(str(process.pid), encoding="utf-8")
    time.sleep(0.2)
    if not is_pid_running(process.pid):
        raise RuntimeError(f"background process exited immediately; see {paths.log_path}")
    return process.pid


def stop_daemon(config: AgentVoiceConfig) -> int | None:
    return _stop_background_process(service_paths(config))


def stop_menubar(config: AgentVoiceConfig) -> int | None:
    return _stop_background_process(menubar_service_paths(config))


def _stop_background_process(paths: ServicePaths) -> int | None:
    pid = read_pid(paths.pid_path)
    if not pid:
        return None
    if is_pid_running(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not is_pid_running(pid):
                break
            time.sleep(0.1)
    paths.pid_path.unlink(missing_ok=True)
    return pid


def daemon_status(config: AgentVoiceConfig) -> tuple[int | None, bool]:
    paths = service_paths(config)
    pid = read_pid(paths.pid_path)
    return pid, bool(pid and is_pid_running(pid))


def menubar_status(config: AgentVoiceConfig) -> tuple[int | None, bool]:
    paths = menubar_service_paths(config)
    pid = read_pid(paths.pid_path)
    return pid, bool(pid and is_pid_running(pid))
