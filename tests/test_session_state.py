import tempfile
import unittest

from agent_voice.db import connect, init_db
from agent_voice.models import EventType, NormalizedEvent, SessionStatus
from agent_voice.session_state import SessionStateManager


class SessionStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(f"{self.tmp.name}/events.sqlite3")
        init_db(self.conn)
        self.manager = SessionStateManager(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_completion_then_failure_reports_failure(self) -> None:
        completed = NormalizedEvent.build(
            event_key="complete",
            agent_name="codex",
            event_type=EventType.TASK_FINISHED,
            project_name="voiccce",
            session_id="s1",
            run_id="r1",
        )
        failed = NormalizedEvent.build(
            event_key="failed",
            agent_name="codex",
            event_type=EventType.TASK_FAILED,
            project_name="voiccce",
            session_id="s1",
            run_id="r1",
            ask_summary="tests did not pass",
        )

        complete_candidate = self.manager.apply_event(completed, now=100)
        failed_candidate = self.manager.apply_event(failed, now=101)

        self.assertIsNotNone(complete_candidate)
        self.assertIsNotNone(failed_candidate)
        self.assertEqual(failed_candidate.status, SessionStatus.FAILED)
        self.assertIn("tests did not pass", failed_candidate.message)

    def test_failure_then_completion_suppresses_completion(self) -> None:
        failed = NormalizedEvent.build(
            event_key="failed",
            agent_name="codex",
            event_type=EventType.TASK_FAILED,
            project_name="voiccce",
            session_id="s1",
            run_id="r1",
        )
        completed = NormalizedEvent.build(
            event_key="complete",
            agent_name="codex",
            event_type=EventType.TASK_FINISHED,
            project_name="voiccce",
            session_id="s1",
            run_id="r1",
        )

        self.assertIsNotNone(self.manager.apply_event(failed, now=100))
        self.assertIsNone(self.manager.apply_event(completed, now=101))

    def test_same_attention_is_suppressed_but_changed_question_notifies(self) -> None:
        first = NormalizedEvent.build(
            event_key="ask-1",
            agent_name="codex",
            event_type=EventType.INPUT_NEEDED,
            project_name="voiccce",
            session_id="s1",
            run_id="r1",
            ask_summary="choose an approach",
        )
        duplicate = NormalizedEvent.build(
            event_key="ask-2",
            agent_name="codex",
            event_type=EventType.INPUT_NEEDED,
            project_name="voiccce",
            session_id="s1",
            run_id="r1",
            ask_summary="choose an approach",
        )
        changed = NormalizedEvent.build(
            event_key="ask-3",
            agent_name="codex",
            event_type=EventType.INPUT_NEEDED,
            project_name="voiccce",
            session_id="s1",
            run_id="r1",
            ask_summary="approve migration",
        )

        self.assertIsNotNone(self.manager.apply_event(first, now=100))
        self.assertIsNone(self.manager.apply_event(duplicate, now=101))
        changed_candidate = self.manager.apply_event(changed, now=102)
        self.assertIsNotNone(changed_candidate)
        self.assertIn("approve migration", changed_candidate.message)


if __name__ == "__main__":
    unittest.main()
