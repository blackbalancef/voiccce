import json
import tempfile
import unittest
from pathlib import Path

from agent_voice.config import AgentVoiceConfig
from agent_voice.intelligence.pipeline_log import (
    log_summary_pipeline,
    pipeline_log_path,
    truncate_pipeline_log,
)


class PipelineLogTests(unittest.TestCase):
    def test_appends_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            log_summary_pipeline(config, {"source_text": "raw", "spoken_text": "spoken"})
            log_summary_pipeline(config, {"source_text": "raw2", "spoken_text": "spoken2"})

            lines = pipeline_log_path(config).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertEqual(first["source_text"], "raw")
            self.assertEqual(first["spoken_text"], "spoken")

    def test_non_serializable_record_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            # A set is not JSON serializable; logging must swallow the error.
            log_summary_pipeline(config, {"bad": {1, 2, 3}})

            self.assertFalse(pipeline_log_path(config).exists())

    def test_logging_is_noop_when_pipeline_log_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(
                config_path=Path(tmp) / "config.toml",
                summary_pipeline_log=False,
            )

            log_summary_pipeline(config, {"source_text": "raw", "spoken_text": "spoken"})

            self.assertFalse(pipeline_log_path(config).exists())

    def test_logging_writes_when_pipeline_log_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(
                config_path=Path(tmp) / "config.toml",
                summary_pipeline_log=True,
            )

            log_summary_pipeline(config, {"source_text": "raw", "spoken_text": "spoken"})

            self.assertTrue(pipeline_log_path(config).exists())
            lines = pipeline_log_path(config).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

    def test_truncate_clears_log_and_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")

            log_summary_pipeline(config, {"a": 1})
            path = pipeline_log_path(config)
            rotated = path.with_suffix(path.suffix + ".1")
            rotated.write_text("old rotated content\n", encoding="utf-8")
            self.assertTrue(path.exists())
            self.assertTrue(rotated.exists())

            truncate_pipeline_log(config)

            self.assertFalse(path.exists())
            self.assertFalse(rotated.exists())

    def test_truncate_is_safe_when_nothing_to_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml")
            # Must not raise even though no log file exists yet.
            truncate_pipeline_log(config)
            self.assertFalse(pipeline_log_path(config).exists())


if __name__ == "__main__":
    unittest.main()
