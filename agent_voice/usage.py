from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .db import connect, init_db


def start_of_day_epoch(timezone: str, *, now: float | None = None) -> int:
    """Epoch seconds of the most recent local midnight in ``timezone``."""
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        tz = datetime.now().astimezone().tzinfo
    current = datetime.fromtimestamp(time.time() if now is None else now, tz)
    midnight = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())


@dataclass(frozen=True, slots=True)
class UsageStats:
    audio_cost_usd: float
    audio_duration_seconds: float
    audio_generated_count: int
    audio_input_text_tokens: int
    audio_output_audio_tokens: int
    audio_input_cost_usd: float
    audio_output_cost_usd: float
    audio_billed_cost_usd: float
    audio_billed_count: int
    summary_cost_usd: float
    reports_listened_count: int


def read_usage_stats(db_path: str | Path, *, since: int | None = None) -> UsageStats:
    conn = connect(db_path)
    try:
        return fetch_usage_stats(conn, since=since)
    finally:
        conn.close()


def fetch_usage_stats(conn: sqlite3.Connection, *, since: int | None = None) -> UsageStats:
    init_db(conn)
    where = "WHERE created_at >= ?" if since is not None else ""
    params: tuple[int, ...] = (since,) if since is not None else ()
    row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(audio_cost_usd), 0) AS audio_cost_usd,
            COALESCE(SUM(audio_duration_seconds), 0) AS audio_duration_seconds,
            COALESCE(SUM(CASE WHEN audio_generated THEN 1 ELSE 0 END), 0) AS audio_generated_count,
            COALESCE(SUM(audio_input_text_tokens), 0) AS audio_input_text_tokens,
            COALESCE(SUM(audio_output_audio_tokens), 0) AS audio_output_audio_tokens,
            COALESCE(SUM(audio_input_cost_usd), 0) AS audio_input_cost_usd,
            COALESCE(SUM(audio_output_cost_usd), 0) AS audio_output_cost_usd,
            COALESCE(SUM(audio_billed_cost_usd), 0) AS audio_billed_cost_usd,
            COALESCE(SUM(CASE WHEN audio_billed_cost_usd IS NOT NULL THEN 1 ELSE 0 END), 0) AS audio_billed_count,
            COALESCE(SUM(summary_cost_usd), 0) AS summary_cost_usd,
            COALESCE(SUM(CASE WHEN spoken THEN 1 ELSE 0 END), 0) AS reports_listened_count
        FROM notifications
        {where}
        """,
        params,
    ).fetchone()
    return UsageStats(
        audio_cost_usd=float(_row_value(row, "audio_cost_usd", 0.0)),
        audio_duration_seconds=float(_row_value(row, "audio_duration_seconds", 0.0)),
        audio_generated_count=int(_row_value(row, "audio_generated_count", 0)),
        audio_input_text_tokens=int(_row_value(row, "audio_input_text_tokens", 0)),
        audio_output_audio_tokens=int(_row_value(row, "audio_output_audio_tokens", 0)),
        audio_input_cost_usd=float(_row_value(row, "audio_input_cost_usd", 0.0)),
        audio_output_cost_usd=float(_row_value(row, "audio_output_cost_usd", 0.0)),
        audio_billed_cost_usd=float(_row_value(row, "audio_billed_cost_usd", 0.0)),
        audio_billed_count=int(_row_value(row, "audio_billed_count", 0)),
        summary_cost_usd=float(_row_value(row, "summary_cost_usd", 0.0)),
        reports_listened_count=int(_row_value(row, "reports_listened_count", 0)),
    )


SPARKLINE_BLOCKS = "▁▂▃▄▅▆▇█"


@dataclass(frozen=True, slots=True)
class DashboardData:
    today: UsageStats
    last_7d: UsageStats
    last_30d: UsageStats
    all_time: UsageStats
    by_agent: list[tuple[str, float, int]]
    by_channel: list[tuple[str, float, int]]
    spark_7d: list[float]


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    peak = max(values)
    if peak <= 0:
        return SPARKLINE_BLOCKS[0] * len(values)
    last = len(SPARKLINE_BLOCKS) - 1
    return "".join(SPARKLINE_BLOCKS[min(last, int(value / peak * last))] for value in values)


def fetch_spend_by_agent(conn: sqlite3.Connection, *, since: int | None = None) -> list[tuple[str, float, int]]:
    """Spend grouped by agent (attributed to the first event of each notification)."""
    where = "WHERE n.created_at >= ?" if since is not None else ""
    params: tuple[int, ...] = (since,) if since is not None else ()
    try:
        rows = conn.execute(
            f"""
            SELECT COALESCE(e.agent_name, 'other') AS agent,
                   COALESCE(SUM(n.audio_cost_usd + n.summary_cost_usd), 0) AS spend,
                   COALESCE(SUM(CASE WHEN n.spoken THEN 1 ELSE 0 END), 0) AS spoken
            FROM notifications n
            LEFT JOIN events e ON e.event_key = json_extract(n.event_ids_json, '$[0]')
            {where}
            GROUP BY agent
            HAVING spoken > 0 OR spend > 0
            ORDER BY spend DESC
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [(_row_value(r, "agent", "other"), float(_row_value(r, "spend", 0.0)), int(_row_value(r, "spoken", 0))) for r in rows]


def fetch_spend_by_channel(conn: sqlite3.Connection, *, since: int | None = None) -> list[tuple[str, float, int]]:
    clauses = ["channel IN ('openai_tts', 'macos_say')"]
    params: list[int] = []
    if since is not None:
        clauses.append("created_at >= ?")
        params.append(since)
    where = "WHERE " + " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT channel,
               COALESCE(SUM(audio_cost_usd + summary_cost_usd), 0) AS spend,
               COALESCE(SUM(CASE WHEN spoken THEN 1 ELSE 0 END), 0) AS spoken
        FROM notifications
        {where}
        GROUP BY channel
        ORDER BY spend DESC
        """,
        tuple(params),
    ).fetchall()
    return [(_row_value(r, "channel", ""), float(_row_value(r, "spend", 0.0)), int(_row_value(r, "spoken", 0))) for r in rows]


def fetch_daily_spend(conn: sqlite3.Connection, day_starts: list[int]) -> list[float]:
    """Spend per day for each [start, start+24h) window (day_starts ascending)."""
    result: list[float] = []
    for start in day_starts:
        row = conn.execute(
            "SELECT COALESCE(SUM(audio_cost_usd + summary_cost_usd), 0) FROM notifications "
            "WHERE created_at >= ? AND created_at < ?",
            (start, start + 86400),
        ).fetchone()
        result.append(float(row[0] if not isinstance(row, sqlite3.Row) else row[0]))
    return result


def read_dashboard(db_path: str | Path, timezone: str, *, now: float | None = None) -> DashboardData:
    conn = connect(db_path)
    try:
        init_db(conn)
        today_start = start_of_day_epoch(timezone, now=now)
        return DashboardData(
            today=fetch_usage_stats(conn, since=today_start),
            last_7d=fetch_usage_stats(conn, since=today_start - 6 * 86400),
            last_30d=fetch_usage_stats(conn, since=today_start - 29 * 86400),
            all_time=fetch_usage_stats(conn),
            by_agent=fetch_spend_by_agent(conn, since=today_start),
            by_channel=fetch_spend_by_channel(conn, since=today_start),
            spark_7d=fetch_daily_spend(conn, [today_start - k * 86400 for k in range(6, -1, -1)]),
        )
    finally:
        conn.close()


def read_last_voice_channel(db_path: str | Path) -> str | None:
    """Return the channel of the most recent voice delivery (openai_tts or macos_say)."""
    conn = connect(db_path)
    try:
        init_db(conn)
        row = conn.execute(
            """
            SELECT channel FROM notifications
            WHERE channel IN ('openai_tts', 'macos_say')
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return row["channel"] if isinstance(row, sqlite3.Row) else row[0]
    finally:
        conn.close()


def format_usd(amount: float) -> str:
    if amount <= 0:
        return "$0.0000"
    if amount < 0.0001:
        return "<$0.0001"
    if amount < 1:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _row_value(row: sqlite3.Row | tuple[object, ...] | None, key: str, default: object) -> object:
    if row is None:
        return default
    if isinstance(row, sqlite3.Row):
        return row[key]
    keys = {
        "audio_cost_usd": 0,
        "audio_duration_seconds": 1,
        "audio_generated_count": 2,
        "audio_input_text_tokens": 3,
        "audio_output_audio_tokens": 4,
        "audio_input_cost_usd": 5,
        "audio_output_cost_usd": 6,
        "audio_billed_cost_usd": 7,
        "audio_billed_count": 8,
        "summary_cost_usd": 9,
        "reports_listened_count": 10,
    }
    return row[keys[key]]
