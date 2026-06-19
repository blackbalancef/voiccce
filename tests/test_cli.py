import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_voice.cli import main


class CliTests(unittest.TestCase):
    def test_install_claude_code_accepts_config_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured: dict[str, Path] = {}

            def fake_install(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    settings_path=root / "claude-personal" / "settings.json",
                    backup_path=root / "backup.json",
                    wrapper_path=root / "bin" / "hook",
                    config_path=root / "config.toml",
                    database_path=root / "events.sqlite3",
                    installed_events=("Stop",),
                )

            with (
                patch("agent_voice.cli.install_claude_code_personal", fake_install),
                redirect_stdout(StringIO()),
            ):
                main(
                    [
                        "install",
                        "claude-code",
                        "--claude-config-dir",
                        str(root / "claude-personal"),
                    ]
                )

            self.assertEqual(
                captured["settings_path"],
                root / "claude-personal" / "settings.json",
            )

    def test_install_claude_code_accepts_settings_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "custom-settings.json"
            captured: dict[str, Path] = {}

            def fake_install(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    settings_path=settings_path,
                    backup_path=Path(tmp) / "backup.json",
                    wrapper_path=Path(tmp) / "bin" / "hook",
                    config_path=Path(tmp) / "config.toml",
                    database_path=Path(tmp) / "events.sqlite3",
                    installed_events=("Stop",),
                )

            with (
                patch("agent_voice.cli.install_claude_code_personal", fake_install),
                redirect_stdout(StringIO()),
            ):
                main(["install", "claude-code", "--settings-path", str(settings_path)])

            self.assertEqual(captured["settings_path"], settings_path)

    def test_install_codex_accepts_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured: dict[str, Path] = {}

            def fake_install(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    hooks_path=root / "codex-personal" / "hooks.json",
                    backup_path=root / "backup.json",
                    wrapper_path=root / "bin" / "hook",
                    config_path=root / "config.toml",
                    database_path=root / "events.sqlite3",
                    installed_events=("Stop",),
                )

            with (
                patch("agent_voice.cli.install_codex_personal", fake_install),
                redirect_stdout(StringIO()),
            ):
                main(["install", "codex", "--codex-home", str(root / "codex-personal")])

            self.assertEqual(captured["codex_home"], root / "codex-personal")

    def test_install_codex_accepts_hooks_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hooks_path = Path(tmp) / "custom-hooks.json"
            captured: dict[str, Path] = {}

            def fake_install(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    hooks_path=hooks_path,
                    backup_path=Path(tmp) / "backup.json",
                    wrapper_path=Path(tmp) / "bin" / "hook",
                    config_path=Path(tmp) / "config.toml",
                    database_path=Path(tmp) / "events.sqlite3",
                    installed_events=("Stop",),
                )

            with (
                patch("agent_voice.cli.install_codex_personal", fake_install),
                redirect_stdout(StringIO()),
            ):
                main(["install", "codex", "--hooks-path", str(hooks_path)])

            self.assertEqual(captured["hooks_path"], hooks_path)


if __name__ == "__main__":
    unittest.main()
