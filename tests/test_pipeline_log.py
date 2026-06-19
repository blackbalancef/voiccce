import json
import tempfile
import unittest
from pathlib import Path

from agent_voice.config import AgentVoiceConfig
from agent_voice.intelligence.pipeline_log import log_summary_pipeline, pipeline_log_path


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


if __name__ == "__main__":
    unittest.main()
