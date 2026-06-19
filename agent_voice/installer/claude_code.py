from __future__ import annotations

import json
import os
import shlex
import stat
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_voice.config import DEFAULT_CONFIG_PATH, write_default_config
from agent_voice.db import connect, init_db
from agent_voice.config import load_config


PERSONAL_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
AGENT_CHIME_HOME = Path.home() / ".agent-chime"
WRAPPER_PATH = AGENT_CHIME_HOME / "bin" / "agent-chime-claude-hook"
MARKER = "AGENT_CHIME=1"

CLAUDE_HOOKS = {
    "Stop": {"matcher": None},
    "Notification": {"matcher": "*"},
    "PermissionRequest": {"matcher": "*"},
    "StopFailure": {"matcher": None},
    "SubagentStop": {"matcher": None},
}


@dataclass(frozen=True, slots=True)
class ClaudeInstallResult:
    settings_path: Path
    backup_path: Path
    wrapper_path: Path
    config_path: Path
    database_path: Path
    installed_events: tuple[str, ...]


def install_claude_code_personal(
    *,
    repo_root: Path | None = None,
    settings_path: Path = PERSONAL_SETTINGS_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    wrapper_path: Path = WRAPPER_PATH,
    python_executable: str | Path | None = None,
) -> ClaudeInstallResult:
    repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    config_path = config_path.expanduser().resolve()
    settings_path = settings_path.expanduser().resolve()
    wrapper_path = wrapper_path.expanduser().resolve()
    python_executable = Path(python_executable or sys.executable).expanduser().resolve()

    write_default_config(config_path)
    config = load_config(config_path)
    conn = connect(config.database_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    _write_wrapper(wrapper_path, repo_root, config_path, python_executable)
    settings = _read_settings(settings_path)
    backup_path = _backup_settings(settings_path)
    settings.setdefault("hooks", {})

    for hook_name, hook_config in CLAUDE_HOOKS.items():
        command = f"{MARKER} {wrapper_path} {hook_name}"
        entry: dict[str, object] = {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                }
            ]
        }
        if hook_config["matcher"] is not None:
            entry["matcher"] = hook_config["matcher"]

        existing_entries = settings["hooks"].setdefault(hook_name, [])
        settings["hooks"][hook_name] = _without_agent_chime_entries(existing_entries)
        settings["hooks"][hook_name].append(entry)

    _write_settings(settings_path, settings)
    return ClaudeInstallResult(
        settings_path=settings_path,
        backup_path=backup_path,
        wrapper_path=wrapper_path,
        config_path=config_path,
        database_path=config.database_path,
        installed_events=tuple(CLAUDE_HOOKS.keys()),
    )


def _read_settings(settings_path: Path) -> dict[str, object]:
    if not settings_path.exists():
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        return {}
    return json.loads(settings_path.read_text(encoding="utf-8"))


def _backup_settings(settings_path: Path) -> Path:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    backup_path = settings_path.with_name(f"{settings_path.name}.agent-chime-backup.{stamp}")
    if settings_path.exists():
        backup_path.write_text(settings_path.read_text(encoding="utf-8"), encoding="utf-8")
        backup_path.chmod(settings_path.stat().st_mode & 0o777)
    else:
        backup_path.write_text("{}\n", encoding="utf-8")
        backup_path.chmod(0o600)
    return backup_path


def _write_settings(settings_path: Path, settings: dict[str, object]) -> None:
    tmp_path = settings_path.with_suffix(settings_path.suffix + ".agent-chime-tmp")
    tmp_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    existing_mode = settings_path.stat().st_mode & 0o777 if settings_path.exists() else 0o600
    tmp_path.chmod(existing_mode)
    os.replace(tmp_path, settings_path)


def _without_agent_chime_entries(entries: object) -> list[object]:
    if not isinstance(entries, list):
        return []
    kept = []
    for entry in entries:
        if _entry_contains_marker(entry):
            continue
        kept.append(entry)
    return kept


def _entry_contains_marker(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks", [])
    if not isinstance(hooks, list):
        return False
    for hook in hooks:
        if isinstance(hook, dict) and MARKER in str(hook.get("command", "")):
            return True
    return False


def _write_wrapper(
    wrapper_path: Path,
    repo_root: Path,
    config_path: Path,
    python_executable: Path,
) -> None:
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = AGENT_CHIME_HOME / "hook.log"
    repo_root_value = shlex.quote(str(repo_root))
    config_path_value = shlex.quote(str(config_path))
    log_path_value = shlex.quote(str(log_path))
    python_executable_value = shlex.quote(str(python_executable))
    content = f"""#!/usr/bin/env bash
set -u

HOOK_NAME="${{1:-Stop}}"
REPO_ROOT={repo_root_value}
CONFIG_PATH={config_path_value}
LOG_PATH={log_path_value}
PYTHON_BIN={python_executable_value}

mkdir -p "$(dirname "$LOG_PATH")"
cd "$REPO_ROOT" || exit 0
PYTHONPATH="$REPO_ROOT:${{PYTHONPATH:-}}" "$PYTHON_BIN" -m agent_voice --config "$CONFIG_PATH" collect claude-code --hook "$HOOK_NAME" >> "$LOG_PATH" 2>&1 || true
exit 0
"""
    wrapper_path.write_text(content, encoding="utf-8")
    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
