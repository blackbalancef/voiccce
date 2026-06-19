import json
import tempfile
import unittest
from pathlib import Path

from agent_voice.hooks.transcript import read_last_assistant_text


class TranscriptReaderTests(unittest.TestCase):
    def _write(self, tmp: str, lines: list[dict]) -> str:
        path = Path(tmp) / "transcript.jsonl"
        path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
        return str(path)

    def test_reads_full_text_of_last_assistant_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                [
                    {"type": "user", "message": {"role": "user", "content": "go"}},
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "first reply"}]},
                    },
                    {"type": "user", "message": {"role": "user", "content": "continue"}},
                    {
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "Final answer part one."},
                                {"type": "tool_use", "name": "Bash", "input": {}},
                                {"type": "text", "text": "Final answer part two."},
                            ],
                        },
                    },
                ],
            )

            text = read_last_assistant_text(path)

        self.assertEqual(text, "Final answer part one.\nFinal answer part two.")

    def test_concatenates_assistant_text_across_a_multi_line_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                [
                    {"type": "user", "message": {"role": "user", "content": "fix the bug"}},
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "Let me check the file."}]},
                    },
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Read", "input": {}}]},
                    },
                    # tool_result is stored with role=user but must NOT start a new turn
                    {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}},
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "Found and fixed it."}]},
                    },
                ],
            )

            text = read_last_assistant_text(path)

        self.assertEqual(text, "Let me check the file.\nFound and fixed it.")

    def test_a_new_user_prompt_resets_to_only_the_final_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                [
                    {"role": "assistant", "content": "old turn answer"},
                    {"role": "user", "content": "another question"},
                    {"role": "assistant", "content": "new turn answer"},
                ],
            )

            self.assertEqual(read_last_assistant_text(path), "new turn answer")

    def test_supports_string_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                [{"role": "assistant", "content": "plain string answer"}],
            )

            self.assertEqual(read_last_assistant_text(path), "plain string answer")

    def test_missing_or_empty_path_returns_none(self) -> None:
        self.assertIsNone(read_last_assistant_text(None))
        self.assertIsNone(read_last_assistant_text("/nonexistent/transcript.jsonl"))

    def test_malformed_lines_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            path.write_text(
                "not json\n"
                + json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "ok"}})
                + "\n{broken",
                encoding="utf-8",
            )

            self.assertEqual(read_last_assistant_text(str(path)), "ok")


if __name__ == "__main__":
    unittest.main()
