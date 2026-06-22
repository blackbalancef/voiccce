import json
import tempfile
import unittest
from pathlib import Path

from agent_voice.installer.codex import MARKER, install_codex_personal


class CodexInstallerTests(unittest.TestCase):
    def test_installer_preserves_existing_hooks_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hooks_path = root / "codex" / "hooks.json"
            config_path = root / "config.toml"
            wrapper_path = root / "bin" / "hook"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text(
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
                                            "command": "/usr/bin/env AGENT_CHIME=1 /old/agent-chime-codex-hook Stop",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            first = install_codex_personal(
                repo_root=Path.cwd(),
                hooks_path=hooks_path,
                config_path=config_path,
                wrapper_path=wrapper_path,
                python_executable=root / "venv" / "bin" / "python",
            )
            second = install_codex_personal(
                repo_root=Path.cwd(),
                hooks_path=hooks_path,
                config_path=config_path,
                wrapper_path=wrapper_path,
                python_executable=root / "venv" / "bin" / "python",
            )

            data = json.loads(hooks_path.read_text(encoding="utf-8"))
            stop_entries = data["hooks"]["Stop"]
            commands = [
                hook["command"]
                for entry in stop_entries
                for hook in entry.get("hooks", [])
            ]
            self.assertIn("bash existing.sh", commands)
            self.assertFalse(any("AGENT_CHIME=1" in command for command in commands))
            self.assertEqual(sum(MARKER in command for command in commands), 1)
            agent_chime_command = next(command for command in commands if MARKER in command)
            self.assertTrue(agent_chime_command.startswith("/usr/bin/env "))
            self.assertIn("PermissionRequest", data["hooks"])
            self.assertIn("SubagentStop", data["hooks"])
            self.assertTrue(first.backup_path.exists())
            self.assertTrue(second.backup_path.exists())
            self.assertTrue(wrapper_path.exists())
            self.assertTrue(config_path.exists())
            wrapper = wrapper_path.read_text(encoding="utf-8")
            python_executable = (root / "venv" / "bin" / "python").resolve()
            self.assertIn(f"PYTHON_BIN={python_executable}", wrapper)
            self.assertIn("collect codex", wrapper)


if __name__ == "__main__":
    unittest.main()
