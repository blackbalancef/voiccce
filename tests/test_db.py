import tempfile
import unittest

from agent_voice.db import (
    clear_events,
    clear_notifications,
    clear_session_states,
    connect,
    count_prunable_events,
    db_size_bytes,
    init_db,
    mark_events_processed,
    prune_processed_events,
    vacuum_db,
)
from agent_voice.models import EventType, NormalizedEvent
from agent_voice.queue import enqueue_event


def _seed_event(conn, *, key: str, created_at: int) -> NormalizedEvent:
    event = NormalizedEvent.build(
        event_key=key,
        agent_name="codex",
        event_type=EventType.TASK_FINISHED,
        project_name="voiccce",
        session_id=key,
        created_at=created_at,
    )
    enqueue_event(conn, event)
    return event


class DbRetentionTests(unittest.TestCase):
    def test_prune_only_old_processed_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)

            _seed_event(conn, key="old-processed", created_at=100)
            _seed_event(conn, key="new-processed", created_at=5000)
            _seed_event(conn, key="old-pending", created_at=100)
            mark_events_processed(conn, ["old-processed", "new-processed"], processed_at=6000)
            conn.commit()

            cutoff = 1000
            self.assertEqual(
                count_prunable_events(conn, older_than_epoch=cutoff), 1
            )

            deleted = prune_processed_events(conn, older_than_epoch=cutoff)
            self.assertEqual(deleted, 1)

            remaining = {
                row["event_key"]
                for row in conn.execute("SELECT event_key FROM events").fetchall()
            }
            self.assertEqual(remaining, {"new-processed", "old-pending"})

    def test_count_prunable_respects_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)

            _seed_event(conn, key="old-pending", created_at=100)
            self.assertEqual(count_prunable_events(conn, older_than_epoch=1000), 0)
            self.assertEqual(
                count_prunable_events(conn, older_than_epoch=1000, status="pending"), 1
            )

    def test_prune_at_cutoff_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)

            _seed_event(conn, key="boundary", created_at=1000)
            mark_events_processed(conn, ["boundary"], processed_at=2000)
            conn.commit()

            # created_at == cutoff is NOT pruned (strict less-than)
            self.assertEqual(prune_processed_events(conn, older_than_epoch=1000), 0)
            self.assertEqual(prune_processed_events(conn, older_than_epoch=1001), 1)

    def test_clear_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)

            _seed_event(conn, key="e1", created_at=100)
            _seed_event(conn, key="e2", created_at=200)

            self.assertEqual(clear_events(conn), 2)
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertEqual(count, 0)

    def test_clear_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)

            conn.execute(
                """
                INSERT INTO notifications (event_ids_json, category, channel, message, created_at)
                VALUES ('[]', 'completed', 'log', 'hi', 100)
                """
            )
            conn.commit()

            self.assertEqual(clear_notifications(conn), 1)
            count = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
            self.assertEqual(count, 0)

    def test_clear_session_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)

            conn.execute(
                """
                INSERT INTO session_states (session_id, agent_name, status, last_event_at)
                VALUES ('s1', 'codex', 'running', 100)
                """
            )
            conn.commit()

            self.assertEqual(clear_session_states(conn), 1)
            count = conn.execute("SELECT COUNT(*) FROM session_states").fetchone()[0]
            self.assertEqual(count, 0)

    def test_vacuum_db_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)

            _seed_event(conn, key="e1", created_at=100)
            clear_events(conn)

            self.assertIsNone(vacuum_db(conn))
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertEqual(count, 0)

    def test_db_size_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            self.assertEqual(db_size_bytes(db_path), 0)

            conn = connect(db_path)
            init_db(conn)
            _seed_event(conn, key="e1", created_at=100)

            self.assertGreater(db_size_bytes(db_path), 0)

    def test_db_size_bytes_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(db_size_bytes(f"{tmp}/does-not-exist.sqlite3"), 0)


if __name__ == "__main__":
    unittest.main()
