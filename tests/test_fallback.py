import unittest
from types import SimpleNamespace

from agent_voice.intelligence.fallback import build_grouped_message, build_single_message
from agent_voice.models import NotificationCategory, SessionStatus


class FallbackTests(unittest.TestCase):
    def test_attention_message_is_short_and_actionable(self) -> None:
        message = build_single_message(
            agent_name="Codex",
            project_name="agent-chime",
            status=SessionStatus.ATTENTION_REQUIRED,
            ask_summary="choose implementation",
        )

        self.assertEqual(
            message,
            "Codex in agent-chime needs attention: choose implementation.",
        )

    def test_completed_message_says_fully_completed(self) -> None:
        message = build_single_message(
            agent_name="Codex",
            project_name="agent-chime",
            status=SessionStatus.COMPLETED,
        )

        self.assertEqual(message, "Session agent-chime is fully complete.")

    def test_completed_message_includes_final_summary(self) -> None:
        message = build_single_message(
            agent_name="Codex",
            project_name="agent-chime",
            status=SessionStatus.COMPLETED,
            ask_summary="Done. **Changes:** added voice notifications after completion.",
        )

        self.assertEqual(
            message,
            "Session agent-chime is fully complete. Summary: Changes: added voice notifications after completion.",
        )

    def test_english_attention_message(self) -> None:
        message = build_single_message(
            agent_name="Codex",
            project_name="agent-chime",
            status=SessionStatus.ATTENTION_REQUIRED,
            ask_summary="choose implementation",
            language="en",
        )

        self.assertEqual(
            message,
            "Codex in agent-chime needs attention: choose implementation.",
        )

    def test_custom_attention_template(self) -> None:
        message = build_single_message(
            agent_name="Claude",
            project_name="api",
            status=SessionStatus.ATTENTION_REQUIRED,
            ask_summary="approve command",
            templates={
                "attention_required": "Human input needed for {project}{reason_clause}.",
            },
        )

        self.assertEqual(message, "Human input needed for api: approve command.")

    def test_invalid_custom_template_falls_back_to_default(self) -> None:
        message = build_single_message(
            agent_name="Claude",
            project_name="api",
            status=SessionStatus.ATTENTION_REQUIRED,
            ask_summary="approve command",
            templates={
                "attention_required": "Need {missing}.",
            },
        )

        self.assertEqual(message, "Claude in api needs attention: approve command.")

    def test_custom_grouped_template(self) -> None:
        message = build_grouped_message(
            [
                SimpleNamespace(
                    project_name="api",
                    status=SessionStatus.ATTENTION_REQUIRED,
                    category=NotificationCategory.NEEDS_ATTENTION,
                    message="ignored",
                ),
                SimpleNamespace(
                    project_name="web",
                    status=SessionStatus.COMPLETED,
                    category=NotificationCategory.COMPLETED,
                    message="ignored",
                ),
            ],
            templates={
                "grouped_prefix": "Summary: {items}.",
                "grouped_attention_fragment": "{project}: waiting",
                "grouped_completed_fragment": "{project}: done",
            },
        )

        self.assertEqual(message, "Summary: api: waiting; web: done.")


if __name__ == "__main__":
    unittest.main()
