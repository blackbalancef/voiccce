import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_voice.config import AgentVoiceConfig
from agent_voice.runtime import (
    clear_active_voice_sessions,
    clear_voice_mute,
    clear_voice_activity,
    parse_age_seconds,
    parse_duration_seconds,
    read_voice_activity_started_at,
    set_active_voice_sessions,
    set_voice_mute,
    start_voice_activity,
    voice_mute_status,
    voice_session_active,
    write_voice_pid,
    stop_speaking,
    request_voice_stop,
    voice_stop_requested_after,
    voice_pid_path,
)


class RuntimeTests(unittest.TestCase):
    def test_active_voice_sessions_tracking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(
                config_path=Path(tmp) / "config.toml",
                database_path=Path(tmp) / "events.sqlite3",
            )
            self.assertFalse(voice_session_active(config, "s1", now=1000.0))
            set_active_voice_sessions(config, ["s1", "s2"], now=1000.0)
            self.assertTrue(voice_session_active(config, "s1", now=1000.0))
            self.assertTrue(voice_session_active(config, "s2", now=1001.0))
            self.assertFalse(voice_session_active(config, "s3", now=1000.0))
            # stale window -> not active
            self.assertFalse(voice_session_active(config, "s1", now=1000.0 + 10**6))
            clear_active_voice_sessions(config)
            self.assertFalse(voice_session_active(config, "s1", now=1000.0))

    def test_parse_duration_seconds(self) -> None:
        self.assertEqual(parse_duration_seconds("30s"), 30)
        self.assertEqual(parse_duration_seconds("10m"), 600)
        self.assertEqual(parse_duration_seconds("1h"), 3600)
        self.assertEqual(parse_duration_seconds("2"), 120)

    def test_parse_age_seconds(self) -> None:
        self.assertEqual(parse_age_seconds("45s"), 45)
        self.assertEqual(parse_age_seconds("30m"), 1800)
        self.assertEqual(parse_age_seconds("12h"), 43200)
        self.assertEqual(parse_age_seconds("30d"), 2592000)
        # bare integer == seconds (differs from parse_duration_seconds minutes)
        self.assertEqual(parse_age_seconds("90"), 90)
        self.assertEqual(parse_age_seconds(90), 90)

    def test_parse_age_seconds_rejects_bad_input(self) -> None:
        for bad in ("", "  ", "abc", "1.5d", "-5d", "0d", "10x", "d"):
            with self.assertRaises(ValueError):
                parse_age_seconds(bad)

    def test_voice_mute_status_expires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            set_voice_mute(config, 10, now=100)
            self.assertTrue(voice_mute_status(config, now=105).muted)
            self.assertFalse(voice_mute_status(config, now=111).muted)

    def test_clear_voice_mute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            set_voice_mute(config, 10, now=100)
            clear_voice_mute(config)

            self.assertFalse(voice_mute_status(config, now=105).muted)

    def test_stop_speaking_clears_stale_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            write_voice_pid(config, 99999999)
            stopped_pid = stop_speaking(config)

            self.assertEqual(stopped_pid, 99999999)
            self.assertFalse(voice_pid_path(config).exists())

    def test_stop_speaking_terminates_running_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")
            process = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                start_new_session=True,
            )
            try:
                write_voice_pid(config, process.pid)

                stopped_pid = stop_speaking(config)
                return_code = process.wait(timeout=2)

                self.assertEqual(stopped_pid, process.pid)
                self.assertNotEqual(return_code, 0)
                self.assertFalse(voice_pid_path(config).exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)

    def test_voice_stop_request_is_time_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            request_voice_stop(config, now=101.5)

            self.assertTrue(voice_stop_requested_after(config, 100.0))
            self.assertFalse(voice_stop_requested_after(config, 102.0))

    def test_voice_activity_is_time_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            started_at = start_voice_activity(config, now=101.5)

            self.assertEqual(read_voice_activity_started_at(config, now=102.0), started_at)

            clear_voice_activity(config, started_at + 1)
            self.assertEqual(read_voice_activity_started_at(config, now=103.0), started_at)

            clear_voice_activity(config, started_at)
            self.assertIsNone(read_voice_activity_started_at(config, now=104.0))

    def test_voice_activity_stale_value_is_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            start_voice_activity(config, now=100.0)

            self.assertIsNone(read_voice_activity_started_at(config, now=120.0, max_age_seconds=10))


if __name__ == "__main__":
    unittest.main()
