from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agent_voice.hooks.text_extract import shorten, summary_source_text
from agent_voice.models import EventType, NormalizedEvent, stable_hash


def normalize_pi_event(payload: dict[str, Any], hook_name: str) -> NormalizedEvent:
    cwd = payload.get("cwd") or payload.get("workspace") or payload.get("project_dir")
    project_name = payload.get("project_name") or (Path(cwd).name if cwd else None)
    session_id = (
        payload.get("session_id")
        or payload.get("sessionId")
        or payload.get("conversation_id")
        or payload.get("id")
    )
    run_id = payload.get("run_id") or payload.get("runId") or session_id
    last_message = payload.get("last_assistant_message") or payload.get("message")

    if hook_name in {"StopFailure", "AgentError"}:
        event_type = EventType.TASK_FAILED
    elif hook_name == "SubagentStop":
        event_type = EventType.SUBAGENT_FINISHED
    else:
        event_type = EventType.TASK_FINISHED

    ask_summary = shorten(str(last_message)) if last_message else None
    key_payload = {
        "agent": "pi",
        "hook": hook_name,
        "event_type": event_type.value,
        "session_id": session_id,
        "run_id": run_id,
        "payload_key": payload.get("event_key") or payload.get("id"),
        "message": ask_summary,
    }
    event_key = payload.get("event_key") or f"pi:{stable_hash(key_payload)}"

    terminal = event_type in {EventType.TASK_FINISHED, EventType.TASK_FAILED}
    return NormalizedEvent.build(
        event_key=event_key,
        agent_name="pi",
        event_type=event_type,
        project_name=project_name,
        cwd=cwd,
        session_id=session_id,
        run_id=run_id,
        raw_payload={"hook_name": hook_name, "session_id": session_id, "cwd": cwd},
        ask_summary=ask_summary,
        summary_source_text=summary_source_text(str(last_message)) if (terminal and last_message) else None,
        terminal_state=event_type.value if terminal else None,
    )


def read_event_from_stdin(hook_name: str) -> NormalizedEvent:
    raw = sys.stdin.read()
    payload = json.loads(raw or "{}")
    return normalize_pi_event(payload, hook_name)
