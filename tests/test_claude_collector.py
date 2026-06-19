import unittest

from agent_voice.hooks.claude_event_collector import normalize_claude_event
from agent_voice.models import EventType


class ClaudeCollectorTests(unittest.TestCase):
    def test_collector_stores_sanitized_payload_metadata(self) -> None:
        event = normalize_claude_event(
            {
                "cwd": "/tmp/private-project",
                "session_id": "session-1",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "npm install private-package",
                    "secret": "do-not-store",
                },
                "message": "full assistant message should not be stored",
                "prompt": "full user prompt should not be stored",
            },
            "PermissionRequest",
        )

        self.assertEqual(event.event_type, EventType.PERMISSION_NEEDED)
        self.assertEqual(event.ask_summary, "Bash: npm install private-package")
        self.assertEqual(event.raw_payload["hook_name"], "PermissionRequest")
        self.assertEqual(event.raw_payload["cwd"], "/tmp/private-project")
        self.assertEqual(event.raw_payload["session_id"], "session-1")
        self.assertEqual(event.raw_payload["tool_name"], "Bash")
        self.assertEqual(event.raw_payload["ask_summary"], "Bash: npm install private-package")
        self.assertNotIn("tool_input", event.raw_payload)
        self.assertNotIn("message", event.raw_payload)
        self.assertNotIn("prompt", event.raw_payload)


if __name__ == "__main__":
    unittest.main()
