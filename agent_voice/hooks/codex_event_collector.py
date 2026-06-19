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


def normalize_codex_event(payload: dict[str, Any], hook_name: str | None = None) -> NormalizedEvent:
    resolved_hook = hook_name or payload.get("hook_event_name") or payload.get("hookEventName") or "Stop"
    cwd = payload.get("cwd")
    project_name = payload.get("project_name") or _project_from_cwd(cwd)
    session_id = payload.get("session_id") or payload.get("sessionId")
    turn_id = payload.get("turn_id") or payload.get("turnId")
    run_id = payload.get("run_id") or payload.get("runId") or turn_id or session_id
    transcript_path = payload.get("transcript_path") or payload.get("transcriptPath")
    payload_message = payload.get("last_assistant_message") or payload.get("lastAssistantMessage")
    # Prefer the complete final assistant turn from the transcript when available.
    last_message = read_last_assistant_text(transcript_path) or payload_message

    if resolved_hook == "PermissionRequest":
        event_type = EventType.PERMISSION_NEEDED
        ask_summary = _summary_from_payload(payload, last_message)
        attention_reason = shorten(payload.get("tool_name") or payload.get("toolName"))
    elif resolved_hook == "SubagentStop":
        event_type = EventType.SUBAGENT_FINISHED
        ask_summary = _summary_from_payload(payload, last_message)
        attention_reason = shorten(payload.get("agent_type") or payload.get("agentType"))
    elif resolved_hook == "Stop":
        event_type = EventType.TASK_FINISHED
        ask_summary = _summary_from_payload(payload, last_message)
        attention_reason = None
    else:
        event_type = EventType.UNKNOWN
        ask_summary = _summary_from_payload(payload, last_message)
        attention_reason = shorten(resolved_hook)

    key_payload = {
        "agent": "codex",
        "hook": resolved_hook,
        "event_type": event_type.value,
        "session_id": session_id,
        "run_id": run_id,
        "turn_id": turn_id,
        "transcript_path": transcript_path,
        "tool_name": payload.get("tool_name") or payload.get("toolName"),
        "agent_id": payload.get("agent_id") or payload.get("agentId"),
        "message": ask_summary,
    }
    event_key = payload.get("event_key") or payload.get("id") or f"codex:{stable_hash(key_payload)}"

    return NormalizedEvent.build(
        event_key=event_key,
        agent_name="codex",
        event_type=event_type,
        project_name=project_name,
        cwd=cwd,
        session_id=session_id,
        run_id=run_id,
        transcript_path=transcript_path,
        raw_payload=_metadata_payload(payload, str(resolved_hook), ask_summary),
        attention_reason=attention_reason,
        ask_summary=ask_summary,
        summary_source_text=summary_source_text(last_message) if event_type == EventType.TASK_FINISHED else None,
        terminal_state=event_type.value if event_type == EventType.TASK_FINISHED else None,
    )


def read_event_from_stdin(hook_name: str | None = None) -> NormalizedEvent:
    raw = sys.stdin.read()
    payload = json.loads(raw or "{}")
    return normalize_codex_event(payload, hook_name)


def _project_from_cwd(cwd: str | None) -> str | None:
    if not cwd:
        return None
    return Path(cwd).name


def _metadata_payload(payload: dict[str, Any], hook_name: str, ask_summary: str | None) -> dict[str, Any]:
    allowed_keys = (
        "session_id",
        "sessionId",
        "turn_id",
        "turnId",
        "cwd",
        "transcript_path",
        "transcriptPath",
        "agent_transcript_path",
        "agentTranscriptPath",
        "hook_event_name",
        "hookEventName",
        "model",
        "permission_mode",
        "permissionMode",
        "tool_name",
        "toolName",
        "agent_id",
        "agentId",
        "agent_type",
        "agentType",
        "stop_hook_active",
        "stopHookActive",
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

    reason = payload.get("reason") or payload.get("permission_reason") or payload.get("prompt_summary")
    if reason:
        return shorten(reason)
    return summarize_assistant_message(fallback)
