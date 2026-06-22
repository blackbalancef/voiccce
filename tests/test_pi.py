import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agent_voice.cli import main
from agent_voice.config import load_config, write_default_config
from agent_voice.db import connect, init_db
from agent_voice.hooks.pi_event_collector import normalize_pi_event
from agent_voice.installer.pi import MARKER, install_pi_personal
from agent_voice.models import EventType


class PiCollectorTests(unittest.TestCase):
    def test_agent_end_maps_to_task_finished(self) -> None:
        event = normalize_pi_event(
            {"session_id": "s1", "cwd": "/work/myproj", "last_assistant_message": "All tests pass."},
            "Stop",
        )
        self.assertEqual(event.agent_name, "pi")
        self.assertEqual(event.event_type, EventType.TASK_FINISHED)
        self.assertEqual(event.session_id, "s1")
        self.assertEqual(event.project_name, "myproj")
        self.assertEqual(event.terminal_state, "task_finished")
        self.assertTrue(event.ask_summary)

    def test_failure_hook_maps_to_task_failed(self) -> None:
        event = normalize_pi_event({"session_id": "s2", "message": "boom"}, "StopFailure")
        self.assertEqual(event.event_type, EventType.TASK_FAILED)


class PiInstallerTests(unittest.TestCase):
    def test_install_writes_extension_and_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = install_pi_personal(
                repo_root=Path.cwd(),
                pi_home=root / "pi-home",
                config_path=root / "config.toml",
                wrapper_path=root / "bin" / "voiccce-pi-hook",
                python_executable=sys.executable,
                verify=True,
            )
            self.assertTrue(result.wrapper_path.exists())
            self.assertTrue(result.extension_path.exists())
            self.assertEqual(
                result.extension_path,
                (root / "pi-home" / "agent" / "extensions" / "voiccce.ts").resolve(),
            )

            ext = result.extension_path.read_text(encoding="utf-8")
            self.assertIn(MARKER, ext)
            self.assertIn(str(result.wrapper_path), ext)
            self.assertIn('pi.on("agent_end"', ext)
            self.assertIn('pi.on("before_agent_start"', ext)

            wrapper = result.wrapper_path.read_text(encoding="utf-8")
            self.assertIn("collect pi --hook", wrapper)

    def test_install_removes_legacy_generated_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pi_home = root / "pi-home"
            legacy_extension = pi_home / "agent" / "extensions" / "agent-chime.ts"
            legacy_extension.parent.mkdir(parents=True)
            legacy_extension.write_text("// AGENT_CHIME=1 old generated extension\n", encoding="utf-8")

            install_pi_personal(
                repo_root=Path.cwd(),
                pi_home=pi_home,
                config_path=root / "config.toml",
                wrapper_path=root / "bin" / "voiccce-pi-hook",
                python_executable=sys.executable,
                verify=True,
            )

            self.assertFalse(legacy_extension.exists())
            self.assertTrue((pi_home / "agent" / "extensions" / "voiccce.ts").exists())


class PiCollectCliTests(unittest.TestCase):
    def test_collect_pi_enqueues_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"
            write_default_config(config_path)
            config = load_config(config_path)

            payload = json.dumps({"session_id": "pi-1", "cwd": str(Path(tmp)), "last_assistant_message": "Done."})
            with patch("sys.stdin", StringIO(payload)), redirect_stdout(StringIO()):
                main(["--config", str(config_path), "collect", "pi", "--hook", "Stop"])

            conn = connect(config.database_path)
            init_db(conn)
            row = conn.execute("SELECT agent_name, event_type, session_id FROM events").fetchone()
            self.assertEqual(row["agent_name"], "pi")
            self.assertEqual(row["event_type"], "task_finished")
            self.assertEqual(row["session_id"], "pi-1")
            conn.close()


if __name__ == "__main__":
    unittest.main()
