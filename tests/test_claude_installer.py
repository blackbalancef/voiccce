import json
import sys
import tempfile
import unittest
from pathlib import Path

from agent_voice.installer import WrapperImportError
from agent_voice.installer.claude_code import MARKER, install_claude_code_personal


class ClaudeInstallerTests(unittest.TestCase):
    def test_installer_preserves_existing_hooks_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / "settings.json"
            config_path = root / "config.toml"
            wrapper_path = root / "bin" / "hook"
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "bash existing.sh",
                                        }
                                    ]
                                },
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "AGENT_CHIME=1 /old/agent-chime-claude-hook Stop",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            first = install_claude_code_personal(
                repo_root=Path.cwd(),
                settings_path=settings_path,
                config_path=config_path,
                wrapper_path=wrapper_path,
                python_executable=root / "venv" / "bin" / "python",
            )
            second = install_claude_code_personal(
                repo_root=Path.cwd(),
                settings_path=settings_path,
                config_path=config_path,
                wrapper_path=wrapper_path,
                python_executable=root / "venv" / "bin" / "python",
            )

            data = json.loads(settings_path.read_text(encoding="utf-8"))
            stop_entries = data["hooks"]["Stop"]
            commands = [
                hook["command"]
                for entry in stop_entries
                for hook in entry.get("hooks", [])
            ]
            self.assertIn("bash existing.sh", commands)
            self.assertFalse(any("AGENT_CHIME=1" in command for command in commands))
            self.assertEqual(sum(MARKER in command for command in commands), 1)
            self.assertTrue(first.backup_path.exists())
            self.assertTrue(second.backup_path.exists())
            self.assertTrue(wrapper_path.exists())
            self.assertTrue(config_path.exists())
            wrapper = wrapper_path.read_text(encoding="utf-8")
            python_executable = (root / "venv" / "bin" / "python").resolve()
            self.assertIn(f"PYTHON_BIN={python_executable}", wrapper)
            self.assertNotIn("/usr/bin/env python3 -m agent_voice", wrapper)

    def test_verify_raises_when_interpreter_cannot_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(WrapperImportError):
                install_claude_code_personal(
                    repo_root=root,  # empty dir → agent_voice not importable
                    settings_path=root / "settings.json",
                    config_path=root / "config.toml",
                    wrapper_path=root / "bin" / "hook",
                    python_executable=sys.executable,
                    verify=True,
                )

    def test_verify_passes_for_valid_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = install_claude_code_personal(
                repo_root=Path.cwd(),  # repo root has the agent_voice package
                settings_path=root / "settings.json",
                config_path=root / "config.toml",
                wrapper_path=root / "bin" / "hook",
                python_executable=sys.executable,
                verify=True,
            )
            self.assertTrue(result.wrapper_path.exists())


if __name__ == "__main__":
    unittest.main()
