import json
import tempfile
import unittest
from pathlib import Path

from agent_voice.hooks.codex_event_collector import normalize_codex_event
from agent_voice.models import EventType


class CodexCollectorTests(unittest.TestCase):
    def test_stop_event_prefers_full_transcript_over_truncated_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "transcript.jsonl"
            full = "The complete final Codex answer with all details kept intact for the summary."
            transcript.write_text(
                json.dumps({"role": "assistant", "content": full}) + "\n",
                encoding="utf-8",
            )
            payload = {
                "session_id": "session-1",
                "turn_id": "turn-1",
                "cwd": "/tmp/voiccce",
                "hook_event_name": "Stop",
                "transcript_path": str(transcript),
                "last_assistant_message": "clipped preview...",
            }

            event = normalize_codex_event(payload)

        self.assertEqual(event.summary_source_text, full)

    def test_stop_event_falls_back_to_payload_when_transcript_missing(self) -> None:
        payload = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": "/tmp/voiccce",
            "hook_event_name": "Stop",
            "transcript_path": "/nonexistent/transcript.jsonl",
            "last_assistant_message": "codex payload message",
        }

        event = normalize_codex_event(payload)

        self.assertEqual(event.summary_source_text, "codex payload message")

    def test_permission_request_summarizes_and_sanitizes_tool_input(self) -> None:
        event = normalize_codex_event(
            {
                "session_id": "session-1",
                "turn_id": "turn-1",
                "cwd": "/tmp/private-project",
                "hook_event_name": "PermissionRequest",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "npm install private-package",
                    "secret": "do-not-store",
                },
                "prompt": "full user prompt should not be stored",
                "last_assistant_message": "full assistant message should not be stored",
            }
        )

        self.assertEqual(event.agent_name, "codex")
        self.assertEqual(event.event_type, EventType.PERMISSION_NEEDED)
        self.assertEqual(event.run_id, "turn-1")
        self.assertEqual(event.ask_summary, "Bash: npm install private-package")
        self.assertIsNone(event.summary_source_text)
        self.assertEqual(event.raw_payload["hook_name"], "PermissionRequest")
        self.assertEqual(event.raw_payload["cwd"], "/tmp/private-project")
        self.assertEqual(event.raw_payload["session_id"], "session-1")
        self.assertEqual(event.raw_payload["turn_id"], "turn-1")
        self.assertEqual(event.raw_payload["tool_name"], "Bash")
        self.assertNotIn("tool_input", event.raw_payload)
        self.assertNotIn("prompt", event.raw_payload)
        self.assertNotIn("last_assistant_message", event.raw_payload)

    def test_stop_event_summarizes_last_assistant_message(self) -> None:
        payload = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": "/tmp/voiccce",
            "hook_event_name": "Stop",
            "last_assistant_message": (
                "Done.\n\n"
                "**Changes:**\n"
                "- added Codex voice notifications.\n"
                "- updated tests."
            ),
        }
        event = normalize_codex_event(payload)

        self.assertEqual(event.event_type, EventType.TASK_FINISHED)
        self.assertEqual(
            event.ask_summary,
            "Changes: added Codex voice notifications. updated tests",
        )
        self.assertEqual(event.summary_source_text, payload["last_assistant_message"])
        self.assertNotIn("**", event.ask_summary or "")


if __name__ == "__main__":
    unittest.main()
