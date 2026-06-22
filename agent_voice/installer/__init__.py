"""Installers for supported agent integrations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class WrapperImportError(RuntimeError):
    """Raised when a generated hook wrapper cannot import ``agent_voice``."""


def verify_wrapper_imports(python_executable: Path, repo_root: Path) -> None:
    """Confirm the wrapper's interpreter can import ``agent_voice``.

    The hook wrapper runs ``$PYTHON_BIN -m agent_voice`` with ``REPO_ROOT`` on
    ``PYTHONPATH``. This reproduces that exact import so a broken install fails
    loudly at setup time instead of silently swallowing every notification (see
    ``hook.log`` filling with ``No module named agent_voice``).
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
    try:
        result = subprocess.run(
            [str(python_executable), "-c", "import agent_voice"],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - platform dependent
        raise WrapperImportError(
            f"Could not run {python_executable} to verify the hook wrapper: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise WrapperImportError(
            f"The hook interpreter {python_executable} cannot import agent_voice "
            f"with PYTHONPATH={repo_root}.\n{detail}\n\n"
            "Re-run setup with the interpreter that has voiccce installed, e.g. "
            "`python -m agent_voice ... setup` from the voiccce virtualenv, "
            "or `pipx run --spec voiccce voiccce setup`."
        )
