import unittest

from agent_voice.hooks.claude_event_collector import normalize_claude_event
from agent_voice.models import EventType


class ClaudeEventCollectorTests(unittest.TestCase):
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
