from __future__ import annotations

import os
import shlex
import stat
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_voice.config import DEFAULT_CONFIG_PATH, load_config, write_default_config
from agent_voice.db import connect, init_db
from agent_voice.installer import verify_wrapper_imports


DEFAULT_PI_HOME = Path.home() / ".pi"
AGENT_CHIME_HOME = Path.home() / ".agent-chime"
WRAPPER_PATH = AGENT_CHIME_HOME / "bin" / "agent-chime-pi-hook"
MARKER = "AGENT_CHIME=1"

# pi auto-discovers global extensions from ~/.pi/agent/extensions/*.ts
PI_HOOKS = ("Stop", "UserPromptSubmit")


@dataclass(frozen=True, slots=True)
class PiInstallResult:
    extension_path: Path
    wrapper_path: Path
    config_path: Path
    database_path: Path
    installed_events: tuple[str, ...]


def install_pi_personal(
    *,
    repo_root: Path | None = None,
    pi_home: Path | None = None,
    extension_path: Path | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
    wrapper_path: Path = WRAPPER_PATH,
    python_executable: str | Path | None = None,
    verify: bool = False,
) -> PiInstallResult:
    repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    config_path = config_path.expanduser().resolve()
    pi_home = (pi_home or _default_pi_home()).expanduser().resolve()
    extension_path = (extension_path or pi_home / "agent" / "extensions" / "agent-chime.ts").expanduser().resolve()
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
    if verify:
        verify_wrapper_imports(python_executable, repo_root)
    _write_extension(extension_path, wrapper_path)
    return PiInstallResult(
        extension_path=extension_path,
        wrapper_path=wrapper_path,
        config_path=config_path,
        database_path=config.database_path,
        installed_events=PI_HOOKS,
    )


def _default_pi_home() -> Path:
    return Path(os.environ.get("PI_HOME") or DEFAULT_PI_HOME)


def _write_wrapper(wrapper_path: Path, repo_root: Path, config_path: Path, python_executable: Path) -> None:
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = AGENT_CHIME_HOME / "hook.log"
    content = f"""#!/usr/bin/env bash
set -u

HOOK_NAME="${{1:-Stop}}"
REPO_ROOT={shlex.quote(str(repo_root))}
CONFIG_PATH={shlex.quote(str(config_path))}
LOG_PATH={shlex.quote(str(log_path))}
PYTHON_BIN={shlex.quote(str(python_executable))}

mkdir -p "$(dirname "$LOG_PATH")"
cd "$REPO_ROOT" || exit 0
PYTHONPATH="$REPO_ROOT:${{PYTHONPATH:-}}" "$PYTHON_BIN" -m agent_voice --config "$CONFIG_PATH" collect pi --hook "$HOOK_NAME" >> "$LOG_PATH" 2>&1 || true
exit 0
"""
    wrapper_path.write_text(content, encoding="utf-8")
    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_extension(extension_path: Path, wrapper_path: Path) -> None:
    extension_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    wrapper_js = _js_string(str(wrapper_path))
    content = f"""// {MARKER} Agent Chime — pi integration (generated {stamp})
// Bridges pi lifecycle events to the agent-chime notification daemon.
// Auto-discovered from ~/.pi/agent/extensions/. Safe to delete to uninstall.
import {{ spawn }} from "node:child_process";

const WRAPPER = {wrapper_js};
let currentSessionId = null;

function pick(...values) {{
  for (const value of values) if (value) return value;
  return null;
}}

function sessionId(event, ctx) {{
  return pick(
    currentSessionId,
    event && (event.sessionId || event.session_id || (event.session && event.session.id)),
    ctx && ctx.sessionManager && (ctx.sessionManager.id || (ctx.sessionManager.session && ctx.sessionManager.session.id)),
    ctx && ctx.cwd,
  );
}}

function lastAssistantText(event) {{
  try {{
    const raw = (event && (event.messages || (event.message && [event.message]) || event.result)) || [];
    const arr = Array.isArray(raw) ? raw : [raw];
    for (let i = arr.length - 1; i >= 0; i--) {{
      const m = arr[i];
      if (!m) continue;
      if (m.role && m.role !== "assistant") continue;
      const c = m.content;
      if (typeof c === "string") return c;
      if (Array.isArray(c)) {{
        const text = c
          .filter((p) => p && (p.type === "text" || typeof p.text === "string"))
          .map((p) => p.text || "")
          .join(" ")
          .trim();
        if (text) return text;
      }}
    }}
  }} catch (e) {{ /* best effort */ }}
  return null;
}}

function fire(hook, payload) {{
  try {{
    const child = spawn(WRAPPER, [hook], {{ stdio: ["pipe", "ignore", "ignore"], detached: true }});
    child.on("error", () => {{}});
    child.stdin.end(JSON.stringify(payload));
    child.unref();
  }} catch (e) {{ /* never block the agent */ }}
}}

export default function (pi) {{
  pi.on("session_start", async (event, ctx) => {{
    currentSessionId = sessionId(event, ctx) || currentSessionId;
  }});
  pi.on("before_agent_start", async (event, ctx) => {{
    fire("UserPromptSubmit", {{ session_id: sessionId(event, ctx), cwd: ctx && ctx.cwd }});
  }});
  pi.on("agent_end", async (event, ctx) => {{
    fire("Stop", {{
      session_id: sessionId(event, ctx),
      cwd: ctx && ctx.cwd,
      last_assistant_message: lastAssistantText(event),
    }});
  }});
}}
"""
    extension_path.write_text(content, encoding="utf-8")
    extension_path.chmod(0o600)


def _js_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
