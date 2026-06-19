from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping

from agent_voice.models import NotificationCategory, SessionStatus


_GENERIC_DONE_PREFIX_RE = re.compile(
    r"^(done|completed|finished)\.?\s*",
    re.IGNORECASE,
)


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    value = str(text)
    value = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", value)
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-*+]\s+", "", value, flags=re.MULTILINE)
    collapsed = " ".join(value.strip().split()).strip(" -:;")
    return collapsed.rstrip(".")


def _summarize_reason(reason: str | None, *, max_chars: int = 180) -> str | None:
    cleaned = _clean(reason)
    if not cleaned:
        return None

    cleaned = _GENERIC_DONE_PREFIX_RE.sub("", cleaned).strip(" -:;")
    if not cleaned:
        return None
    if len(cleaned) <= max_chars:
        return cleaned.rstrip(".")

    cut = cleaned.rfind(". ", 0, max_chars)
    if cut >= 60:
        return cleaned[:cut].rstrip(".")
    return cleaned[: max_chars - 3].rstrip(" ,;:.") + "..."


def build_single_message(
    *,
    agent_name: str,
    project_name: str,
    status: SessionStatus,
    ask_summary: str | None = None,
    attention_reason: str | None = None,
    language: str = "en",
    templates: Mapping[str, str] | None = None,
) -> str:
    subject = project_name or "session"
    agent = agent_name or "Agent"
    reason = ask_summary or attention_reason
    cleaned_reason = _clean(reason)
    values = {
        "agent": agent,
        "project": subject,
        "reason": cleaned_reason or "",
        "reason_clause": f": {cleaned_reason}" if cleaned_reason else "",
    }

    if status == SessionStatus.FAILED:
        return _message(templates, "failed", "{agent} in {project} failed{reason_clause}.", values)
    if status == SessionStatus.PERMISSION_NEEDED:
        return _message(templates, "permission_needed", "{agent} in {project} needs permission{reason_clause}.", values)
    if status == SessionStatus.ATTENTION_REQUIRED:
        return _message(templates, "attention_required", "{agent} in {project} needs attention{reason_clause}.", values)
    if status == SessionStatus.COMPLETED:
        summary = _summarize_reason(reason)
        if summary:
            return _message(
                templates,
                "completed_with_summary",
                "Session {project} is fully complete. Summary: {summary}.",
                values | {"summary": summary},
            )
        return _message(templates, "completed", "Session {project} is fully complete.", values)
    return _message(templates, "handled", "Event in {project} was handled.", values)


def build_grouped_message(
    candidates: list[object],
    *,
    language: str = "en",
    templates: Mapping[str, str] | None = None,
) -> str:
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0].message

    by_status = Counter(candidate.status for candidate in candidates)
    fragments: list[str] = []
    for candidate in candidates[:3]:
        subject = candidate.project_name or "session"
        if candidate.category == NotificationCategory.FAILED:
            fragments.append(_message(templates, "grouped_failed_fragment", "{project} failed", {"project": subject}))
        elif candidate.category == NotificationCategory.NEEDS_ATTENTION:
            fragments.append(_message(templates, "grouped_attention_fragment", "{project} needs attention", {"project": subject}))
        elif candidate.category == NotificationCategory.COMPLETED:
            fragments.append(_message(templates, "grouped_completed_fragment", "{project} completed", {"project": subject}))
        else:
            fragments.append(subject)

    if len(candidates) <= 3:
        return _message(templates, "grouped_prefix", "Updates: {items}.", {"items": "; ".join(fragments)})

    failed = by_status[SessionStatus.FAILED]
    attention = by_status[SessionStatus.ATTENTION_REQUIRED] + by_status[SessionStatus.PERMISSION_NEEDED]
    completed = by_status[SessionStatus.COMPLETED]
    summary_parts = []
    if attention:
        summary_parts.append(_message(templates, "grouped_attention_count", "{count} need attention", {"count": attention}))
    if failed:
        summary_parts.append(_message(templates, "grouped_failed_count", "{count} failed", {"count": failed}))
    if completed:
        summary_parts.append(_message(templates, "grouped_completed_count", "{count} completed", {"count": completed}))
    if not summary_parts:
        summary_parts.append(_message(templates, "grouped_updates_count", "{count} updates", {"count": len(candidates)}))
    return _message(
        templates,
        "grouped_many",
        "{count} sessions: {summary}.",
        {"count": len(candidates), "summary": ", ".join(summary_parts)},
    )


def _message(
    templates: Mapping[str, str] | None,
    key: str,
    fallback: str,
    values: Mapping[str, object],
) -> str:
    template = templates.get(key) if templates else None
    if not template:
        template = fallback
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return fallback.format(**values)
