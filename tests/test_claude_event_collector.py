import json
import tempfile
import unittest
from pathlib import Path

from agent_voice.hooks.claude_event_collector import normalize_claude_event
from agent_voice.models import EventType


class ClaudeEventCollectorTests(unittest.TestCase):
    def test_stop_event_prefers_full_transcript_over_truncated_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "transcript.jsonl"
            full = "This is the complete final assistant answer with every detail preserved intact."
            transcript.write_text(
                json.dumps(
                    {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": full}]}}
                )
                + "\n",
                encoding="utf-8",
            )
            payload = {
                "cwd": "/tmp/agent-chime",
                "session_id": "s1",
                "transcript_path": str(transcript),
                "last_assistant_message": "clipped preview...",
            }

            event = normalize_claude_event(payload, "Stop")

        self.assertEqual(event.summary_source_text, full)

    def test_stop_event_falls_back_to_payload_when_transcript_missing(self) -> None:
        payload = {
            "cwd": "/tmp/agent-chime",
            "session_id": "s1",
            "transcript_path": "/nonexistent/transcript.jsonl",
            "last_assistant_message": "payload message text",
        }

        event = normalize_claude_event(payload, "Stop")

        self.assertEqual(event.summary_source_text, "payload message text")

    def test_stop_event_summarizes_last_assistant_message(self) -> None:
        payload = {
            "cwd": "/tmp/agent-chime",
            "session_id": "s1",
            "last_assistant_message": (
                "Done.\n\n"
                "**Changes:**\n"
                "- added voice notifications after completion.\n"
                "- updated tests."
            ),
        }
        event = normalize_claude_event(payload, "Stop")

        self.assertEqual(event.event_type, EventType.TASK_FINISHED)
        self.assertEqual(
            event.ask_summary,
            "Changes: added voice notifications after completion. updated tests",
        )
        self.assertEqual(event.summary_source_text, payload["last_assistant_message"])
        self.assertNotIn("**", event.ask_summary or "")

if __name__ == "__main__":
    unittest.main()
