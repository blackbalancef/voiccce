import tempfile
import unittest
from pathlib import Path
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
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path)
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
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path)
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
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path)
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
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path)
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
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path, duplicate_cooldown_seconds=300)
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
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path)
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

    def test_idle_notification_after_completion_becomes_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path)

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
            process_once(conn, config, deliver=False, current_time=100)

            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="idle",
                    agent_name="codex",
                    event_type=EventType.INPUT_NEEDED,
                    project_name="api",
                    session_id="s1",
                    ask_summary="Here is the full result I already produced.",
                ),
            )
            process_once(conn, config, deliver=False, current_time=110)

            rows = conn.execute("SELECT message FROM notifications ORDER BY id").fetchall()
            self.assertEqual(len(rows), 2)
            reminder = rows[-1]["message"]
            self.assertIn("reminder", reminder.lower())
            self.assertIn("10 minutes", reminder)  # codex cache window
            self.assertNotIn("full result I already produced", reminder)
            conn.close()

    def test_input_needed_is_gated_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(
                config_path=Path(tmp) / "config.toml",
                database_path=db_path,
                notify_input_needed=False,
            )
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="idle",
                    agent_name="claude-code",
                    event_type=EventType.INPUT_NEEDED,
                    project_name="api",
                    session_id="s1",
                ),
            )

            result = process_once(conn, config, deliver=False, current_time=100)

            self.assertEqual(result.processed_events, 1)
            self.assertEqual(result.notifications_created, 0)
            conn.close()

    def test_voice_is_throttled_within_min_seconds_between_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path, min_seconds_between_voice_messages=8)
            seen_voice_enabled: list[bool] = []

            class FakeDeliveryRouter:
                def __init__(self, config, *, terminal_only: bool = False) -> None:
                    seen_voice_enabled.append(config.voice_enabled)

                def deliver(self, message: str) -> list[DeliveryResult]:
                    if seen_voice_enabled[-1]:
                        return [DeliveryResult(channel="openai_tts", delivered=True, spoken=True, audio_generated=True)]
                    return [DeliveryResult(channel="macos_notification", delivered=True)]

            def enqueue(event_key: str) -> None:
                enqueue_event(
                    conn,
                    NormalizedEvent.build(
                        event_key=event_key,
                        agent_name="codex",
                        event_type=EventType.TASK_FINISHED,
                        project_name="api",
                        session_id=event_key,
                    ),
                )

            with patch("agent_voice.daemon.DeliveryRouter", FakeDeliveryRouter):
                enqueue("first")
                process_once(conn, config, deliver=True, current_time=100)
                enqueue("second")
                process_once(conn, config, deliver=True, current_time=105)
                enqueue("third")
                process_once(conn, config, deliver=True, current_time=120)

            # First spoken; second suppressed (within 8s); third allowed again (20s later).
            self.assertEqual(seen_voice_enabled, [True, False, True])
            rows = conn.execute("SELECT channel, spoken FROM notifications ORDER BY id").fetchall()
            self.assertEqual(rows[0]["channel"], "openai_tts")
            self.assertEqual(rows[1]["channel"], "macos_notification")
            self.assertEqual(rows[1]["spoken"], 0)
            self.assertEqual(rows[2]["channel"], "openai_tts")
            conn.close()

    def test_completed_notification_is_summarized_before_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path, summary_enabled=True)
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

    def test_pipeline_log_records_source_and_spoken_text(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(
                config_path=Path(tmp) / "config.toml",
                database_path=db_path,
                summary_enabled=True,
            )
            enqueue_event(
                conn,
                NormalizedEvent.build(
                    event_key="finished",
                    agent_name="codex",
                    event_type=EventType.TASK_FINISHED,
                    project_name="api",
                    session_id="s1",
                    summary_source_text="Full raw final message from the assistant.",
                ),
            )

            class FakeDeliveryRouter:
                def __init__(self, config, *, terminal_only: bool = False) -> None:
                    pass

                def deliver(self, message: str) -> list[DeliveryResult]:
                    return [DeliveryResult(channel="terminal_log", delivered=True, spoken=False)]

            def fake_summarize(config: AgentVoiceConfig, candidate) -> SummaryResult:
                return SummaryResult(
                    message="Done summarizing.",
                    cost_usd=0.0001,
                    prompt="PROMPT BODY",
                    raw_text="Done summarizing",
                )

            with (
                patch("agent_voice.daemon.DeliveryRouter", FakeDeliveryRouter),
                patch("agent_voice.daemon.summarize_notification", fake_summarize),
            ):
                process_once(conn, config, deliver=True, current_time=100)
            conn.close()

            log_path = Path(tmp) / "summary.log"
            self.assertTrue(log_path.exists())
            record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(record["source_text"], "Full raw final message from the assistant.")
            self.assertEqual(record["prompt"], "PROMPT BODY")
            self.assertEqual(record["gpt_raw_output"], "Done summarizing")
            self.assertEqual(record["gpt_clean_output"], "Done summarizing.")
            self.assertIn("Done summarizing.", record["spoken_text"])
            self.assertTrue(record["gpt_used"])

    def test_pipeline_log_marks_grouped_notifications(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = connect(db_path)
            init_db(conn)
            config = AgentVoiceConfig(config_path=Path(tmp) / "config.toml", database_path=db_path)
            for key, session in (("a", "s1"), ("b", "s2")):
                enqueue_event(
                    conn,
                    NormalizedEvent.build(
                        event_key=key,
                        agent_name="codex",
                        event_type=EventType.TASK_FINISHED,
                        project_name=key,
                        session_id=session,
                    ),
                )

            process_once(conn, config, deliver=False, current_time=100)
            conn.close()

            record = json.loads((Path(tmp) / "summary.log").read_text(encoding="utf-8").splitlines()[-1])
            self.assertTrue(record["grouped"])
            self.assertFalse(record["gpt_used"])


if __name__ == "__main__":
    unittest.main()
