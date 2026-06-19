from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, replace

from .config import AgentVoiceConfig
from .db import connect, fetch_pending_events, init_db, mark_events_processed
from .delivery import DeliveryRouter
from .intelligence.fallback import build_grouped_message
from .intelligence.summarizer import summarize_notification
from .models import NotificationCategory, now_ts, stable_hash
from .session_state import NotificationCandidate, SessionStateManager


@dataclass(frozen=True, slots=True)
class ProcessResult:
    processed_events: int
    notifications_created: int
    notifications_delivered: int


def process_once(
    conn: sqlite3.Connection,
    config: AgentVoiceConfig,
    *,
    deliver: bool = True,
    terminal_only: bool = False,
    current_time: int | None = None,
) -> ProcessResult:
    init_db(conn)
    events = fetch_pending_events(conn)
    if not events:
        return ProcessResult(processed_events=0, notifications_created=0, notifications_delivered=0)

    current_time = current_time or now_ts()
    manager = SessionStateManager(
        conn,
        duplicate_cooldown_seconds=config.duplicate_cooldown_seconds,
        language=config.language,
        message_templates=config.message_templates,
    )
    candidates_by_session: dict[str, NotificationCandidate] = {}
    processed_keys: list[str] = []

    for event in events:
        candidate = manager.apply_event(event, now=current_time)
        if candidate:
            candidates_by_session[candidate.session_id] = candidate
        processed_keys.append(event.event_key)

    mark_events_processed(conn, processed_keys, current_time)

    notifications_created = 0
    notifications_delivered = 0
    if candidates_by_session:
        candidates = list(candidates_by_session.values())
        candidates.sort(key=lambda candidate: (candidate.priority, candidate.created_at))
        summary_cost_usd = 0.0
        if deliver and not terminal_only and config.voice_enabled and len(candidates) == 1:
            summary_result = summarize_notification(config, candidates[0])
            summary_cost_usd = summary_result.cost_usd
            if summary_result.message:
                candidates[0] = replace(candidates[0], message=summary_result.message)
        message = build_grouped_message(
            candidates,
            language=config.language,
            templates=config.message_templates.get(config.language),
        )
        category = (
            NotificationCategory.GROUPED_SUMMARY
            if len(candidates) > 1
            else candidates[0].category
        )
        notification_hash = stable_hash([candidate.notification_hash for candidate in candidates])
        event_ids = [candidate.event_key for candidate in candidates]
        channel = "none"
        spoken = False
        audio_generated = False
        audio_duration_seconds = 0.0
        audio_cost_usd = 0.0
        audio_request_id = None
        audio_client_request_id = None
        audio_input_text_tokens = 0
        audio_output_audio_tokens = 0
        audio_input_cost_usd = 0.0
        audio_output_cost_usd = 0.0
        audio_billed_cost_usd = None
        audio_token_count_method = None
        delivered_at = None
        error = None

        if deliver:
            router = DeliveryRouter(config, terminal_only=terminal_only)
            results = router.deliver(message)
            audio_generated = any(result.audio_generated for result in results)
            audio_duration_seconds = sum(result.audio_duration_seconds for result in results)
            audio_cost_usd = sum(result.audio_cost_usd for result in results)
            request_ids = [result.audio_request_id for result in results if result.audio_request_id]
            client_request_ids = [
                result.audio_client_request_id for result in results if result.audio_client_request_id
            ]
            token_methods = [
                result.audio_token_count_method for result in results if result.audio_token_count_method
            ]
            audio_request_id = ",".join(request_ids) if request_ids else None
            audio_client_request_id = ",".join(client_request_ids) if client_request_ids else None
            audio_input_text_tokens = sum(result.audio_input_text_tokens for result in results)
            audio_output_audio_tokens = sum(result.audio_output_audio_tokens for result in results)
            audio_input_cost_usd = sum(result.audio_input_cost_usd for result in results)
            audio_output_cost_usd = sum(result.audio_output_cost_usd for result in results)
            audio_token_count_method = ",".join(dict.fromkeys(token_methods)) if token_methods else None
            successful = next((result for result in results if result.delivered), None)
            if successful:
                channel = successful.channel
                spoken = successful.spoken
                delivered_at = current_time
                notifications_delivered = 1
            elif results:
                channel = results[-1].channel
                error = "; ".join(result.error or "delivery failed" for result in results if not result.delivered)

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
                audio_request_id,
                audio_client_request_id,
                audio_input_text_tokens,
                audio_output_audio_tokens,
                audio_input_cost_usd,
                audio_output_cost_usd,
                audio_billed_cost_usd,
                audio_token_count_method,
                summary_cost_usd,
                created_at,
                delivered_at,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                json.dumps(event_ids, ensure_ascii=False),
                category.value,
                channel,
                message,
                notification_hash,
                int(spoken),
                int(audio_generated),
                audio_duration_seconds,
                audio_cost_usd,
                audio_request_id,
                audio_client_request_id,
                audio_input_text_tokens,
                audio_output_audio_tokens,
                audio_input_cost_usd,
                audio_output_cost_usd,
                audio_billed_cost_usd,
                audio_token_count_method,
                summary_cost_usd,
                current_time,
                delivered_at,
                error,
            ),
        )
        notifications_created = 1

    conn.commit()
    return ProcessResult(
        processed_events=len(processed_keys),
        notifications_created=notifications_created,
        notifications_delivered=notifications_delivered,
    )


def run_daemon(config: AgentVoiceConfig, *, once: bool = False, deliver: bool = True, terminal_only: bool = False) -> None:
    conn = connect(config.database_path)
    init_db(conn)
    try:
        while True:
            process_once(conn, config, deliver=deliver, terminal_only=terminal_only)
            if once:
                return
            time.sleep(config.poll_interval_ms / 1000)
    finally:
        conn.close()
