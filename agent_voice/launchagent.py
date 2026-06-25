"""Opt-in macOS launchd autostart for the Voiccce daemon and menu bar app.

Autostart is *always opt-in*: nothing in this module is wired up automatically.
The user (via the CLI) decides whether to enable it, and the CLI — not this
module — owns flipping the ``[autostart].managed`` config flag. Here we only
render per-user LaunchAgent plists and drive ``launchctl`` to (un)load them.

All ``launchctl`` invocations go through an injectable ``runner`` (defaulting to
:func:`subprocess.run`) so tests never need a real ``launchctl``.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from .config import AgentVoiceConfig
from . import service


DAEMON_LABEL = "com.voiccce.daemon"
MENUBAR_LABEL = "com.voiccce.menubar"

# A subprocess.run-compatible callable. Kept loose on purpose so tests can pass a
# lightweight stub that merely records the argv it was handed.
Runner = Callable[..., "subprocess.CompletedProcess[object]"]


def launch_agents_dir() -> Path:
    """Return the per-user ``~/Library/LaunchAgents`` directory."""
    return Path.home() / "Library" / "LaunchAgents"


def plist_path(label: str) -> Path:
    """Return the on-disk plist path for ``label`` inside the LaunchAgents dir."""
    return launch_agents_dir() / f"{label}.plist"


def render_plist(
    label: str,
    program_args: Sequence[str],
    *,
    stdout_path: str | os.PathLike[str],
    stderr_path: str | os.PathLike[str],
    run_at_load: bool = True,
    keep_alive: bool = True,
) -> str:
    """Render a launchd LaunchAgent plist as XML text.

    ``program_args`` is the full argv (typically from
    :func:`service.service_python_invocation`). ``run_at_load`` starts the job as
    soon as it is loaded; ``keep_alive`` asks launchd to restart it if it exits.
    """
    spec: dict[str, object] = {
        "Label": label,
        "ProgramArguments": [str(arg) for arg in program_args],
        "RunAtLoad": bool(run_at_load),
        "KeepAlive": bool(keep_alive),
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
    }
    return plistlib.dumps(spec).decode("utf-8")


def daemon_spec(config: AgentVoiceConfig) -> tuple[str, list[str], Path, Path]:
    """Return ``(label, program_args, stdout, stderr)`` for the daemon agent."""
    paths = service.service_paths(config)
    return (
        DAEMON_LABEL,
        service.service_python_invocation(config, ["daemon"]),
        paths.log_path,
        paths.log_path,
    )


def menubar_spec(config: AgentVoiceConfig) -> tuple[str, list[str], Path, Path]:
    """Return ``(label, program_args, stdout, stderr)`` for the menu bar agent."""
    paths = service.menubar_service_paths(config)
    return (
        MENUBAR_LABEL,
        service.service_python_invocation(config, ["menubar"]),
        paths.log_path,
        paths.log_path,
    )


def _gui_domain() -> str:
    """Return the launchd ``gui/<uid>`` domain target for the current user."""
    return f"gui/{os.getuid()}"


def _run_ok(runner: Runner, args: list[str]) -> bool:
    """Run ``args`` through ``runner`` and report whether it succeeded.

    Any non-zero exit or raised :class:`OSError` (e.g. ``launchctl`` missing) is
    treated as failure so callers can fall back to the legacy verb.
    """
    try:
        result = runner(args, capture_output=True, text=True)
    except OSError:
        return False
    return getattr(result, "returncode", 1) == 0


def _bootstrap(runner: Runner, path: Path) -> bool:
    """Load ``path`` via modern ``bootstrap``, falling back to ``load -w``."""
    if _run_ok(runner, ["launchctl", "bootstrap", _gui_domain(), str(path)]):
        return True
    return _run_ok(runner, ["launchctl", "load", "-w", str(path)])


def _bootout(runner: Runner, label: str, path: Path) -> bool:
    """Unload ``label`` via modern ``bootout``, falling back to ``unload -w``."""
    if _run_ok(runner, ["launchctl", "bootout", f"{_gui_domain()}/{label}"]):
        return True
    return _run_ok(runner, ["launchctl", "unload", "-w", str(path)])


def enable_autostart(
    config: AgentVoiceConfig,
    *,
    menubar: bool = True,
    runner: Runner = subprocess.run,
) -> list[str]:
    """Write LaunchAgent plists and load them through ``launchctl``.

    Always installs the daemon agent; the menu bar agent is installed only when
    ``menubar`` is true. Returns the labels that were successfully loaded. This
    does *not* touch the ``[autostart].managed`` config flag — the CLI owns that.
    """
    specs = [daemon_spec(config)]
    if menubar:
        specs.append(menubar_spec(config))

    launch_agents_dir().mkdir(parents=True, exist_ok=True)
    enabled: list[str] = []
    for label, program_args, stdout_path, stderr_path in specs:
        path = plist_path(label)
        path.write_text(
            render_plist(
                label,
                program_args,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            ),
            encoding="utf-8",
        )
        if _bootstrap(runner, path):
            enabled.append(label)
    return enabled


def disable_autostart(
    config: AgentVoiceConfig,
    *,
    runner: Runner = subprocess.run,
) -> list[str]:
    """Unload both LaunchAgents and remove their plist files (idempotent).

    Returns the labels whose plist files were present and removed. Safe to call
    when nothing is installed: missing plists are simply skipped.
    """
    removed: list[str] = []
    for label in (DAEMON_LABEL, MENUBAR_LABEL):
        path = plist_path(label)
        # Always attempt to unload, even if the plist file was already deleted, so
        # a job loaded into launchd is not orphaned.
        _bootout(runner, label, path)
        if path.exists():
            path.unlink(missing_ok=True)
            removed.append(label)
    return removed


def _is_loaded(runner: Runner, label: str) -> bool:
    """Report whether ``label`` is currently loaded in launchd.

    Tries modern ``launchctl print gui/<uid>/<label>`` first, then the legacy
    ``launchctl list <label>``. A missing ``launchctl`` reports "not loaded".
    """
    if _run_ok(runner, ["launchctl", "print", f"{_gui_domain()}/{label}"]):
        return True
    return _run_ok(runner, ["launchctl", "list", label])


def autostart_status(
    config: AgentVoiceConfig,
    *,
    runner: Runner = subprocess.run,
) -> dict[str, dict[str, bool]]:
    """Return per-label ``{plist_present, loaded}`` autostart status.

    ``plist_present`` checks the on-disk file; ``loaded`` queries ``launchctl``.
    """
    status: dict[str, dict[str, bool]] = {}
    for label in (DAEMON_LABEL, MENUBAR_LABEL):
        status[label] = {
            "plist_present": plist_path(label).exists(),
            "loaded": _is_loaded(runner, label),
        }
    return status
