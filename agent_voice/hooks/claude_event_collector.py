from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agent_voice.hooks.text_extract import (
    shorten,
    summarize_assistant_message,
    summary_source_text,
)
from agent_voice.hooks.transcript import read_last_assistant_text
from agent_voice.models import EventType, NormalizedEvent, stable_hash


def normalize_claude_event(payload: dict[str, Any], hook_name: str) -> NormalizedEvent:
    cwd = payload.get("cwd") or payload.get("workspace") or payload.get("project_dir")
    project_name = payload.get("project_name") or _project_from_cwd(cwd)
    session_id = payload.get("session_id") or payload.get("sessionId") or payload.get("conversation_id")
    run_id = payload.get("run_id") or payload.get("runId") or session_id
    transcript_path = payload.get("transcript_path") or payload.get("transcriptPath")
    payload_message = payload.get("last_assistant_message") or payload.get("message")
    # Prefer the complete final assistant turn from the transcript; hook payloads
    # often carry only a clipped preview of the message.
    last_message = read_last_assistant_text(transcript_path) or payload_message
    notification_type = str(payload.get("notification_type") or payload.get("type") or "").lower()

    if hook_name == "StopFailure":
        event_type = EventType.TASK_FAILED
        ask_summary = _summary_from_payload(payload, last_message)
    elif hook_name == "PermissionRequest":
        event_type = EventType.PERMISSION_NEEDED
        ask_summary = _summary_from_payload(payload, last_message)
    elif hook_name == "PermissionDenied":
        event_type = EventType.INPUT_NEEDED
        ask_summary = _summary_from_payload(payload, last_message)
    elif hook_name == "Notification":
        if "permission" in notification_type or "permission" in str(last_message).lower():
            event_type = EventType.PERMISSION_NEEDED
        else:
            event_type = EventType.INPUT_NEEDED
        ask_summary = _summary_from_payload(payload, last_message)
    elif hook_name == "SubagentStop":
        event_type = EventType.SUBAGENT_FINISHED
        ask_summary = _summary_from_payload(payload, last_message)
    else:
        background_tasks = payload.get("background_tasks") or []
        if background_tasks:
            event_type = EventType.SESSION_IDLE
            ask_summary = "active background tasks are still running"
        else:
            event_type = EventType.TASK_FINISHED
            ask_summary = _summary_from_payload(payload, last_message)

    key_payload = {
        "agent": "claude-code",
        "hook": hook_name,
        "event_type": event_type.value,
        "session_id": session_id,
        "run_id": run_id,
        "transcript_path": transcript_path,
        "payload_key": payload.get("event_key") or payload.get("id"),
        "message": ask_summary,
    }
    event_key = payload.get("event_key") or f"claude-code:{stable_hash(key_payload)}"

    return NormalizedEvent.build(
        event_key=event_key,
        agent_name="claude-code",
        event_type=event_type,
        project_name=project_name,
        cwd=cwd,
        session_id=session_id,
        run_id=run_id,
        transcript_path=transcript_path,
        raw_payload=_metadata_payload(payload, hook_name, ask_summary),
        attention_reason=notification_type or None,
        ask_summary=ask_summary,
        summary_source_text=summary_source_text(last_message)
        if event_type in {EventType.TASK_FINISHED, EventType.TASK_FAILED}
        else None,
        terminal_state=event_type.value if event_type in {EventType.TASK_FINISHED, EventType.TASK_FAILED} else None,
    )


def read_event_from_stdin(hook_name: str) -> NormalizedEvent:
    raw = sys.stdin.read()
    payload = json.loads(raw or "{}")
    return normalize_claude_event(payload, hook_name)


def _project_from_cwd(cwd: str | None) -> str | None:
    if not cwd:
        return None
    return Path(cwd).name


def _metadata_payload(payload: dict[str, Any], hook_name: str, ask_summary: str | None) -> dict[str, Any]:
    allowed_keys = (
        "cwd",
        "workspace",
        "project_dir",
        "project_name",
        "session_id",
        "sessionId",
        "conversation_id",
        "run_id",
        "runId",
        "transcript_path",
        "transcriptPath",
        "notification_type",
        "type",
        "tool_name",
        "toolName",
        "event_key",
        "id",
    )
    sanitized: dict[str, Any] = {"hook_name": hook_name}
    for key in allowed_keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, str | int | float | bool) or value is None:
            sanitized[key] = value
    if ask_summary:
        sanitized["ask_summary"] = ask_summary
    return sanitized


def _summary_from_payload(payload: dict[str, Any], fallback: Any) -> str | None:
    tool_name = payload.get("tool_name") or payload.get("toolName")
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or tool_input.get("cmd")
        description = tool_input.get("description")
        file_path = tool_input.get("file_path") or tool_input.get("path")
        if command:
            return shorten(f"{tool_name or 'command'}: {command}")
        if description:
            return shorten(f"{tool_name or 'action'}: {description}")
        if file_path:
            return shorten(f"{tool_name or 'file'}: {file_path}")
    reason = payload.get("reason") or payload.get("permission_reason") or payload.get("prompt")
    if reason:
        return shorten(reason)
    return summarize_assistant_message(fallback)
