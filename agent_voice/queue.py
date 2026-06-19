from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .db import init_db
from .models import NormalizedEvent, stable_hash


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    inserted: bool
    event_key: str


def enqueue_event(conn: sqlite3.Connection, event: NormalizedEvent) -> EnqueueResult:
    init_db(conn)
    try:
        conn.execute(
            """
            INSERT INTO events (
                event_key,
                agent_name,
                event_type,
                project_name,
                cwd,
                session_id,
                run_id,
                transcript_path,
                raw_payload_json,
                status,
                priority,
                created_at,
                attention_reason,
                ask_summary,
                summary_source_text,
                terminal_state,
                supersedes_event_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_key,
                event.agent_name,
                event.event_type.value,
                event.project_name,
                event.cwd,
                event.session_id,
                event.run_id,
                event.transcript_path,
                json.dumps(event.raw_payload, ensure_ascii=False, sort_keys=True),
                event.priority,
                event.created_at,
                event.attention_reason,
                event.ask_summary,
                event.summary_source_text,
                event.terminal_state,
                event.supersedes_event_key,
            ),
        )
        conn.commit()
        return EnqueueResult(inserted=True, event_key=event.event_key)
    except sqlite3.IntegrityError:
        conn.rollback()
        return EnqueueResult(inserted=False, event_key=event.event_key)


def event_key_for_payload(payload: object) -> str:
    return stable_hash(payload)
