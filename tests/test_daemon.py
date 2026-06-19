import tempfile
import unittest
from unittest.mock import patch

from agent_voice.config import AgentVoiceConfig
from agent_voice.daemon import process_once
from agent_voice.db import connect, init_db
from agent_voice.delivery import DeliveryResult
from agent_voice.intelligence.summarizer import SummaryResult
from agent_voice.models import EventType, NormalizedEvent
from agent_voice.queue import enqueue_event


class DaemonTests(unittest.TestCase):
    def test_multiple_events_are_grouped_into_one_notification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(database_path=db_path)
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                ),
            )
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="attention",
                    agent_name="codex",
                    event_type=EventType.PERMISSION_NEEDED,
                    project_name="web",
                    session_id="s2",
                    ask_summary="npm install",
                ),
            )

            result = process_once(conn, config, deliver=False, current_time=100)

            self.assertEqual(result.processed_events, 2)
            self.assertEqual(result.notifications_created, 1)
            row = conn.execute("SELECT * FROM notifications").fetchone()
            self.assertEqual(row["category"], "grouped_summary")
            self.assertIn("web needs attention", row["message"])
            self.assertIn("api completed", row["message"])

    def test_later_completion_suppresses_stale_attention_in_same_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(database_path=db_path)
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="attention",
                    agent_name="codex",
                    event_type=EventType.INPUT_NEEDED,
                    project_name="api",
                    session_id="s1",
                    ask_summary="choose an approach",
                    created_at=100,
                ),
            )
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                    created_at=101,
                ),
            )

            result = process_once(conn, config, deliver=False, current_time=200)

            self.assertEqual(result.processed_events, 2)
            row = conn.execute("SELECT * FROM notifications").fetchone()
            self.assertEqual(row["category"], "completed")
            self.assertEqual(row["message"], "Session api is fully complete.")

    def test_later_failure_replaces_completion_in_same_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(database_path=db_path)
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                    created_at=100,
                ),
            )
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="failed",
                    agent_name="codex",
                    event_type=EventType.TASK_FAILED,
                    project_name="api",
                    session_id="s1",
                    ask_summary="tests did not pass",
                    created_at=101,
                ),
            )

            result = process_once(conn, config, deliver=False, current_time=200)

            self.assertEqual(result.processed_events, 2)
            row = conn.execute("SELECT * FROM notifications").fetchone()
            self.assertEqual(row["category"], "failed")
            self.assertIn("tests did not pass", row["message"])

    def test_later_completion_in_same_session_still_notifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(database_path=db_path)
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="first-finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                    ask_summary="first step is ready",
                ),
            )

            first_result = process_once(conn, config, deliver=False, current_time=100)
            self.assertEqual(first_result.notifications_created, 1)

            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="second-finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                    ask_summary="second step is ready",
                ),
            )

            second_result = process_once(conn, config, deliver=False, current_time=110)

            self.assertEqual(second_result.processed_events, 1)
            self.assertEqual(second_result.notifications_created, 1)
            rows = conn.execute("SELECT * FROM notifications ORDER BY id").fetchall()
            self.assertEqual(len(rows), 2)
            self.assertIn("second step is ready", rows[-1]["message"])

    def test_repeated_permission_in_cooldown_is_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(database_path=db_path, duplicate_cooldown_seconds=300)
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="permission-generic",
                    agent_name="codex",
                    event_type=EventType.PERMISSION_NEEDED,
                    project_name="api",
                    session_id="s1",
                ),
            )

            first_result = process_once(conn, config, deliver=False, current_time=100)
            self.assertEqual(first_result.notifications_created, 1)

            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="permission-detail",
                    agent_name="codex",
                    event_type=EventType.PERMISSION_NEEDED,
                    project_name="api",
                    session_id="s1",
                    ask_summary="Claude needs your permission",
                ),
            )

            second_result = process_once(conn, config, deliver=False, current_time=108)

            self.assertEqual(second_result.processed_events, 1)
            self.assertEqual(second_result.notifications_created, 0)
            count = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
            self.assertEqual(count, 1)

    def test_delivery_usage_metrics_are_stored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(database_path=db_path)
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                ),
            )

            class FakeDeliveryRouter:
                def __init__(self, config, *, terminal_only: bool = False) -> None:
                    pass

                def deliver(self, message: str) -> list[DeliveryResult]:
                    return [
                        DeliveryResult(
                            channel="openai_tts",
                            delivered=True,
                            spoken=True,
                            audio_generated=True,
                            audio_duration_seconds=4.5,
                            audio_cost_usd=0.001125,
                            audio_request_id="req_123",
                            audio_client_request_id="client_123",
                            audio_input_text_tokens=11,
                            audio_output_audio_tokens=94,
                            audio_input_cost_usd=0.0000066,
                            audio_output_cost_usd=0.001128,
                            audio_token_count_method="tiktoken:o200k_base",
                        )
                    ]

            with patch("agent_voice.daemon.DeliveryRouter", FakeDeliveryRouter):
                result = process_once(conn, config, deliver=True, current_time=100)

            self.assertEqual(result.notifications_delivered, 1)
            row = conn.execute("SELECT * FROM notifications").fetchone()
            self.assertEqual(row["channel"], "openai_tts")
            self.assertEqual(row["spoken"], 1)
            self.assertEqual(row["audio_generated"], 1)
            self.assertAlmostEqual(row["audio_duration_seconds"], 4.5)
            self.assertAlmostEqual(row["audio_cost_usd"], 0.001125)
            self.assertEqual(row["audio_request_id"], "req_123")
            self.assertEqual(row["audio_client_request_id"], "client_123")
            self.assertEqual(row["audio_input_text_tokens"], 11)
            self.assertEqual(row["audio_output_audio_tokens"], 94)
            self.assertAlmostEqual(row["audio_input_cost_usd"], 0.0000066)
            self.assertAlmostEqual(row["audio_output_cost_usd"], 0.001128)
            self.assertEqual(row["audio_token_count_method"], "tiktoken:o200k_base")
            conn.close()

    def test_completed_notification_is_summarized_before_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(database_path=db_path, summary_enabled=True)
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                    summary_source_text="Done.\n\n**Changes:** added voice notification summarization.",
                ),
            )
            seen_source_text = None

            class FakeDeliveryRouter:
                def __init__(self, config, *, terminal_only: bool = False) -> None:
                    pass

                def deliver(self, message: str) -> list[DeliveryResult]:
                    return [DeliveryResult(channel="terminal_log", delivered=True)]

            def fake_summarize(config: AgentVoiceConfig, candidate) -> SummaryResult:
                nonlocal seen_source_text
                seen_source_text = candidate.summary_source_text
                return SummaryResult(message="Voice notification summaries are ready.", cost_usd=0.000123)

            with (
                patch("agent_voice.daemon.DeliveryRouter", FakeDeliveryRouter),
                patch("agent_voice.daemon.summarize_notification", fake_summarize),
            ):
                result = process_once(conn, config, deliver=True, current_time=100)

            self.assertEqual(result.notifications_delivered, 1)
            self.assertEqual(seen_source_text, "Done.\n\n**Changes:** added voice notification summarization.")
            row = conn.execute("SELECT * FROM notifications").fetchone()
            self.assertEqual(row["message"], "Voice notification summaries are ready.")
            self.assertAlmostEqual(row["summary_cost_usd"], 0.000123)
            event_row = conn.execute("SELECT summary_source_text FROM events WHERE event_key = 'finished'").fetchone()
            self.assertIsNone(event_row["summary_source_text"])
            conn.close()


if __name__ == "__main__":
    unittest.main()
