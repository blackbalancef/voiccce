import sqlite3
import tempfile
import unittest

from agent_voice.db import connect, init_db
from agent_voice.usage import fetch_usage_stats, format_duration, format_usd


class UsageTests(unittest.TestCase):
    def test_fetch_usage_stats_aggregates_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(f"{tmp}/events.sqlite3")
            init_db(conn)
            conn.execute(
                """
                INSERT INTO notifications (
                    event_ids_json,
                    category,
                    channel,
                    message,
                    notification_hash,
                    spoken,
                    audio_generated,
                    audio_duration_seconds,
                    audio_cost_usd,
                    audio_input_text_tokens,
                    audio_output_audio_tokens,
                    audio_input_cost_usd,
                    audio_output_cost_usd,
                    audio_billed_cost_usd,
                    summary_cost_usd,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "[]",
                    "completed",
                    "openai_tts",
                    "Done.",
                    "n1",
                    1,
                    1,
                    7.5,
                    0.001875,
                    9,
                    156,
                    0.0000054,
                    0.001872,
                    0.0019,
                    0.0002,
                    100,
                ),
            )
            conn.execute(
                """
                INSERT INTO notifications (
                    event_ids_json,
                    category,
                    channel,
                    message,
                    notification_hash,
                    spoken,
                    audio_generated,
                    audio_duration_seconds,
                    audio_cost_usd,
                    summary_cost_usd,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("[]", "failed", "macos_notification", "Failed.", "n2", 0, 0, 0, 0, 0.0003, 110),
            )
            conn.commit()

            stats = fetch_usage_stats(conn)

            self.assertEqual(stats.audio_generated_count, 1)
            self.assertEqual(stats.reports_listened_count, 1)
            self.assertAlmostEqual(stats.audio_duration_seconds, 7.5)
            self.assertAlmostEqual(stats.audio_cost_usd, 0.001875)
            self.assertEqual(stats.audio_input_text_tokens, 9)
            self.assertEqual(stats.audio_output_audio_tokens, 156)
            self.assertAlmostEqual(stats.audio_input_cost_usd, 0.0000054)
            self.assertAlmostEqual(stats.audio_output_cost_usd, 0.001872)
            self.assertAlmostEqual(stats.audio_billed_cost_usd, 0.0019)
            self.assertEqual(stats.audio_billed_count, 1)
            self.assertAlmostEqual(stats.summary_cost_usd, 0.0005)
            conn.close()

    def test_init_db_migrates_old_notification_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_ids_json TEXT NOT NULL,
                    category TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    message TEXT NOT NULL,
                    notification_hash TEXT,
                    spoken BOOLEAN NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    delivered_at INTEGER,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO notifications (
                    event_ids_json,
                    category,
                    channel,
                    message,
                    notification_hash,
                    spoken,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("[]", "completed", "openai_tts", "Done.", "n1", 1, 100),
            )
            conn.commit()

            init_db(conn)
            stats = fetch_usage_stats(conn)

            self.assertEqual(stats.audio_generated_count, 1)
            self.assertEqual(stats.reports_listened_count, 1)
            self.assertGreater(stats.audio_duration_seconds, 0)
            self.assertGreater(stats.audio_cost_usd, 0)
            self.assertGreater(stats.audio_output_audio_tokens, 0)
            self.assertGreater(stats.audio_output_cost_usd, 0)
            conn.close()

    def test_init_db_backfills_existing_audio_cost_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/events.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_ids_json TEXT NOT NULL,
                    category TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    message TEXT NOT NULL,
                    notification_hash TEXT,
                    spoken BOOLEAN NOT NULL DEFAULT 0,
                    audio_generated BOOLEAN NOT NULL DEFAULT 0,
                    audio_duration_seconds REAL NOT NULL DEFAULT 0,
                    audio_cost_usd REAL NOT NULL DEFAULT 0,
                    summary_cost_usd REAL NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    delivered_at INTEGER,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO notifications (
                    event_ids_json,
                    category,
                    channel,
                    message,
                    notification_hash,
                    spoken,
                    audio_generated,
                    audio_duration_seconds,
                    audio_cost_usd,
                    summary_cost_usd,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("[]", "completed", "openai_tts", "Done.", "n1", 1, 1, 7.5, 0.001875, 0, 100),
            )
            conn.commit()

            init_db(conn)
            stats = fetch_usage_stats(conn)
            row = conn.execute("SELECT audio_token_count_method FROM notifications").fetchone()

            self.assertAlmostEqual(stats.audio_cost_usd, 0.001875)
            self.assertAlmostEqual(stats.audio_output_cost_usd, 0.001875)
            self.assertGreater(stats.audio_output_audio_tokens, 0)
            self.assertEqual(row[0], "legacy_per_minute")
            conn.close()

    def test_format_helpers_keep_small_values_visible(self) -> None:
        self.assertEqual(format_usd(0), "$0.0000")
        self.assertEqual(format_usd(0.00005), "<$0.0001")
        self.assertEqual(format_usd(0.001875), "$0.0019")
        self.assertEqual(format_duration(65), "1m 05s")
        self.assertEqual(format_duration(3661), "1h 01m")


if __name__ == "__main__":
    unittest.main()
