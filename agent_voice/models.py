from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TASK_FINISHED = "task_finished"
    INPUT_NEEDED = "input_needed"
    PERMISSION_NEEDED = "permission_needed"
    TASK_FAILED = "task_failed"
    SUBAGENT_FINISHED = "subagent_finished"
    TOOL_FAILED = "tool_failed"
    LONG_RUNNING_STARTED = "long_running_started"
    LONG_RUNNING_FINISHED = "long_running_finished"
    SESSION_IDLE = "session_idle"
    UNKNOWN = "unknown"


class SessionStatus(StrEnum):
    RUNNING = "running"
    ATTENTION_REQUIRED = "attention_required"
    PERMISSION_NEEDED = "permission_needed"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"


class NotificationCategory(StrEnum):
    NEEDS_ATTENTION = "needs_attention"
    COMPLETED = "completed"
    FAILED = "failed"
    GROUPED_SUMMARY = "grouped_summary"


EVENT_PRIORITIES: dict[EventType, int] = {
    EventType.TASK_FAILED: 10,
    EventType.PERMISSION_NEEDED: 20,
    EventType.INPUT_NEEDED: 30,
    EventType.SESSION_IDLE: 35,
    EventType.TOOL_FAILED: 50,
    EventType.TASK_FINISHED: 70,
    EventType.LONG_RUNNING_FINISHED: 75,
    EventType.SUBAGENT_FINISHED: 90,
    EventType.LONG_RUNNING_STARTED: 100,
    EventType.UNKNOWN: 100,
}


def now_ts() -> int:
    return int(time.time())


def parse_event_type(value: str | EventType | None) -> EventType:
    if isinstance(value, EventType):
        return value
    if value:
        try:
            return EventType(value)
        except ValueError:
            return EventType.UNKNOWN
    return EventType.UNKNOWN


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:24]


@dataclass(slots=True)
class NormalizedEvent:
    event_key: str
    agent_name: str
    event_type: EventType
    project_name: str | None = None
    cwd: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    transcript_path: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    priority: int | None = None
    created_at: int = field(default_factory=now_ts)
    attention_reason: str | None = None
    ask_summary: str | None = None
    summary_source_text: str | None = None
    terminal_state: str | None = None
    supersedes_event_key: str | None = None

    def __post_init__(self) -> None:
        self.event_type = parse_event_type(self.event_type)
        if self.priority is None:
            self.priority = EVENT_PRIORITIES[self.event_type]
        if not self.session_id:
            self.session_id = self.cwd or self.project_name or "default"
        if not self.run_id:
            self.run_id = self.session_id

    @classmethod
    def build(
        cls,
        *,
        agent_name: str,
        event_type: str | EventType,
        project_name: str | None = None,
        cwd: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        transcript_path: str | None = None,
        raw_payload: dict[str, Any] | None = None,
        event_key: str | None = None,
        priority: int | None = None,
        created_at: int | None = None,
        attention_reason: str | None = None,
        ask_summary: str | None = None,
        summary_source_text: str | None = None,
        terminal_state: str | None = None,
        supersedes_event_key: str | None = None,
    ) -> "NormalizedEvent":
        parsed_type = parse_event_type(event_type)
        payload = raw_payload or {}
        key = event_key or stable_hash(
            {
                "agent_name": agent_name,
                "event_type": parsed_type.value,
                "project_name": project_name,
                "cwd": cwd,
                "session_id": session_id,
                "run_id": run_id,
                "attention_reason": attention_reason,
                "ask_summary": ask_summary,
                "raw_payload": payload,
            }
        )
        return cls(
            event_key=key,
            agent_name=agent_name,
            event_type=parsed_type,
            project_name=project_name,
            cwd=cwd,
            session_id=session_id,
            run_id=run_id,
            transcript_path=transcript_path,
            raw_payload=payload,
            priority=priority,
            created_at=created_at or now_ts(),
            attention_reason=attention_reason,
            ask_summary=ask_summary,
            summary_source_text=summary_source_text,
            terminal_state=terminal_state,
            supersedes_event_key=supersedes_event_key,
        )

    def subject(self) -> str:
        if self.project_name:
            return self.project_name
        if self.cwd:
            return self.cwd.rstrip("/").split("/")[-1] or self.cwd
        return "session"
