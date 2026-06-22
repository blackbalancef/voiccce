import tempfile
import unittest

from agent_voice.db import connect, init_db
from agent_voice.models import EventType, NormalizedEvent
from agent_voice.queue import enqueue_event


class QueueTests(unittest.TestCase):
    def test_duplicate_event_key_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)
            event = NormalizedEvent.build(
                event_key="same-key",
                agent_name="codex",
                event_type=EventType.TASK_FINISHED,
                project_name="voiccce",
                session_id="s1",
            )

            first = enqueue_event(conn, event)
            second = enqueue_event(conn, event)

            self.assertTrue(first.inserted)
            self.assertFalse(second.inserted)
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
