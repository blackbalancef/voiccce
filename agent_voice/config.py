from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .tts_cost import (
    DEFAULT_TTS_AUDIO_OUTPUT_PRICE_PER_MILLION_TOKENS_USD,
    DEFAULT_TTS_AUDIO_TOKENS_PER_SECOND,
    DEFAULT_TTS_ESTIMATED_COST_PER_MINUTE_USD,
    DEFAULT_TTS_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD,
    audio_tokens_per_second_from_minute_cost,
)


DEFAULT_HOME = Path.home() / ".agent-chime"
DEFAULT_CONFIG_PATH = DEFAULT_HOME / "config.toml"
DEFAULT_DB_PATH = DEFAULT_HOME / "events.sqlite3"
SUPPORTED_LANGUAGES = ("en",)
SUMMARY_PRIVACY_LEVELS = ("metadata_only", "full_last_message")
SUMMARY_PROVIDERS = ("fallback", "openai")
DEFAULT_SUMMARY_MODEL = "gpt-5.4-nano"
DEFAULT_SUMMARY_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD = 0.20
DEFAULT_SUMMARY_CACHED_INPUT_PRICE_PER_MILLION_TOKENS_USD = 0.02
DEFAULT_SUMMARY_TEXT_OUTPUT_PRICE_PER_MILLION_TOKENS_USD = 1.25
DEFAULT_SUMMARY_MAX_INPUT_CHARS = 6000
DEFAULT_SUMMARY_PROMPT = """Rewrite the final assistant update into one natural spoken notification.
Write in the same language as the final assistant update below.
Project: {project}
Agent: {agent}
Status: {status}

Keep only what the user needs to know now. Write no more than {max_words} words, and always finish your sentence completely — never stop mid-thought or mid-word.
Sound natural and varied, not like a status template. Do not mention internal paths, commands, or tests unless they are essential.
Return only the text to speak.

Final assistant update:
{message}
"""
DEFAULT_SUMMARY_CONFIG: dict[str, str | int | float | bool] = {
    "enabled": False,
    "provider": "openai",
    "model": DEFAULT_SUMMARY_MODEL,
    "privacy_level": "full_last_message",
    "max_input_chars": DEFAULT_SUMMARY_MAX_INPUT_CHARS,
    "max_words": 40,
    "timeout_seconds": 5,
    "text_input_price_per_million_tokens_usd": DEFAULT_SUMMARY_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD,
    "cached_input_price_per_million_tokens_usd": DEFAULT_SUMMARY_CACHED_INPUT_PRICE_PER_MILLION_TOKENS_USD,
    "text_output_price_per_million_tokens_usd": DEFAULT_SUMMARY_TEXT_OUTPUT_PRICE_PER_MILLION_TOKENS_USD,
    "prompt": DEFAULT_SUMMARY_PROMPT,
}


DEFAULT_CONFIG_TOML_TEMPLATE = """[user]
language = "en"
timezone = "Europe/Belgrade"

[daemon]
database_path = "{database_path}"
poll_interval_ms = 500

[summary]
enabled = false
provider = "openai"
model = "gpt-5.4-nano"
privacy_level = "full_last_message"
max_input_chars = 6000
max_words = 40
timeout_seconds = 5
text_input_price_per_million_tokens_usd = 0.20
cached_input_price_per_million_tokens_usd = 0.02
text_output_price_per_million_tokens_usd = 1.25
prompt = '''
Rewrite the final assistant update into one natural spoken notification.
Write in the same language as the final assistant update below.
Project: {project}
Agent: {agent}
Status: {status}

Keep only what the user needs to know now. Write no more than {max_words} words, and always finish your sentence completely — never stop mid-thought or mid-word.
Sound natural and varied, not like a status template. Do not mention internal paths, commands, or tests unless they are essential.
Return only the text to speak.

Final assistant update:
{message}
'''

[messages.en]
failed = "{agent} in {project} failed{reason_clause}."
permission_needed = "{agent} in {project} needs permission{reason_clause}."
attention_required = "{agent} in {project} needs attention{reason_clause}."
completed = "Session {project} is fully complete."
completed_with_summary = "Session {project} is fully complete. Summary: {summary}."
handled = "Event in {project} was handled."
grouped_prefix = "Updates: {items}."
grouped_many = "{count} sessions: {summary}."
grouped_failed_fragment = "{project} failed"
grouped_attention_fragment = "{project} needs attention"
grouped_completed_fragment = "{project} completed"
grouped_attention_count = "{count} need attention"
grouped_failed_count = "{count} failed"
grouped_completed_count = "{count} completed"
grouped_updates_count = "{count} updates"

[voice]
enabled = true
backend = "macos_say"
voice = "Alex"
rate = 185
speed = 1.0
model = "gpt-4o-mini-tts"
format = "mp3"
estimated_cost_per_minute_usd = 0.015
text_input_price_per_million_tokens_usd = 0.60
audio_output_price_per_million_tokens_usd = 12.00
audio_tokens_per_second = 20.833333
api_key_env = "OPENAI_API_KEY"
api_key_keychain_service = "agent-chime"
api_key_keychain_account = "openai"
instructions = "Speak naturally, calmly, and briefly. This is a short developer notification."
timeout_seconds = 15

[desktop]
enabled = true

[terminal]
enabled = true

[events]
task_finished = true
permission_needed = true
input_needed = true
task_failed = true
subagent_finished = false

[limits]
min_seconds_between_voice_messages = 8
grouping_window_seconds = 20
max_events_per_minute = 6
duplicate_cooldown_seconds = 300

[quiet_hours]
enabled = true
from = "23:00"
to = "09:00"
voice = false
desktop = true
"""

DEFAULT_MESSAGE_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "failed": "{agent} in {project} failed{reason_clause}.",
        "permission_needed": "{agent} in {project} needs permission{reason_clause}.",
        "attention_required": "{agent} in {project} needs attention{reason_clause}.",
        "completed": "Session {project} is fully complete.",
        "completed_with_summary": "Session {project} is fully complete. Summary: {summary}.",
        "handled": "Event in {project} was handled.",
        "grouped_prefix": "Updates: {items}.",
        "grouped_many": "{count} sessions: {summary}.",
        "grouped_failed_fragment": "{project} failed",
        "grouped_attention_fragment": "{project} needs attention",
        "grouped_completed_fragment": "{project} completed",
        "grouped_attention_count": "{count} need attention",
        "grouped_failed_count": "{count} failed",
        "grouped_completed_count": "{count} completed",
        "grouped_updates_count": "{count} updates",
    },
}


@dataclass(slots=True)
class AgentVoiceConfig:
    config_path: Path = DEFAULT_CONFIG_PATH
    database_path: Path = DEFAULT_DB_PATH
    language: str = "en"
    poll_interval_ms: int = 500
    voice_enabled: bool = True
    voice_backend: str = "macos_say"
    voice_name: str = "Alex"
    voice_rate: int = 185
    voice_speed: float = 1.0
    voice_model: str = "gpt-4o-mini-tts"
    voice_format: str = "mp3"
    voice_estimated_cost_per_minute_usd: float = DEFAULT_TTS_ESTIMATED_COST_PER_MINUTE_USD
    voice_text_input_price_per_million_tokens_usd: float = DEFAULT_TTS_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD
    voice_audio_output_price_per_million_tokens_usd: float = DEFAULT_TTS_AUDIO_OUTPUT_PRICE_PER_MILLION_TOKENS_USD
    voice_audio_tokens_per_second: float = DEFAULT_TTS_AUDIO_TOKENS_PER_SECOND
    voice_api_key_env: str = "OPENAI_API_KEY"
    voice_api_key_keychain_service: str = "agent-chime"
    voice_api_key_keychain_account: str = "openai"
    voice_instructions: str = "Speak naturally, calmly, and briefly. This is a short developer notification."
    voice_timeout_seconds: int = 15
    summary_enabled: bool = False
    summary_provider: str = "openai"
    summary_model: str = DEFAULT_SUMMARY_MODEL
    summary_privacy_level: str = "full_last_message"
    summary_max_input_chars: int = DEFAULT_SUMMARY_MAX_INPUT_CHARS
    summary_max_words: int = 40
    summary_timeout_seconds: int = 5
    summary_prompt: str = DEFAULT_SUMMARY_PROMPT
    summary_text_input_price_per_million_tokens_usd: float = DEFAULT_SUMMARY_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD
    summary_cached_input_price_per_million_tokens_usd: float = DEFAULT_SUMMARY_CACHED_INPUT_PRICE_PER_MILLION_TOKENS_USD
    summary_text_output_price_per_million_tokens_usd: float = DEFAULT_SUMMARY_TEXT_OUTPUT_PRICE_PER_MILLION_TOKENS_USD
    message_templates: dict[str, dict[str, str]] = field(default_factory=lambda: copy_message_templates(DEFAULT_MESSAGE_TEMPLATES))
    desktop_enabled: bool = True
    terminal_enabled: bool = True
    min_seconds_between_voice_messages: int = 8
    grouping_window_seconds: int = 20
    max_events_per_minute: int = 6
    duplicate_cooldown_seconds: int = 300


def expand_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve()


def load_config(path: str | os.PathLike[str] | None = None) -> AgentVoiceConfig:
    config_path = expand_path(path or DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        return AgentVoiceConfig(
            config_path=config_path,
            database_path=default_database_path_for_config(config_path),
        )

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    daemon = data.get("daemon", {})
    user = data.get("user", {})
    voice = data.get("voice", {})
    summary = data.get("summary", {})
    desktop = data.get("desktop", {})
    terminal = data.get("terminal", {})
    limits = data.get("limits", {})

    voice_estimated_cost_per_minute_usd = float(
        voice.get("estimated_cost_per_minute_usd", DEFAULT_TTS_ESTIMATED_COST_PER_MINUTE_USD)
    )
    voice_audio_output_price_per_million_tokens_usd = float(
        voice.get(
            "audio_output_price_per_million_tokens_usd",
            DEFAULT_TTS_AUDIO_OUTPUT_PRICE_PER_MILLION_TOKENS_USD,
        )
    )
    configured_audio_tokens_per_second = voice.get("audio_tokens_per_second")
    if configured_audio_tokens_per_second is None:
        voice_audio_tokens_per_second = audio_tokens_per_second_from_minute_cost(
            voice_estimated_cost_per_minute_usd,
            voice_audio_output_price_per_million_tokens_usd,
        )
    else:
        voice_audio_tokens_per_second = float(configured_audio_tokens_per_second)

    return AgentVoiceConfig(
        config_path=config_path,
        database_path=expand_path(daemon.get("database_path", str(DEFAULT_DB_PATH))),
        language=normalize_language(user.get("language", "en")),
        poll_interval_ms=int(daemon.get("poll_interval_ms", 500)),
        voice_enabled=bool(voice.get("enabled", True)),
        voice_backend=voice.get("backend", "macos_say"),
        voice_name=voice.get("voice", "Alex"),
        voice_rate=int(voice.get("rate", 185)),
        voice_speed=float(voice.get("speed", 1.0)),
        voice_model=voice.get("model", "gpt-4o-mini-tts"),
        voice_format=voice.get("format", "mp3"),
        voice_estimated_cost_per_minute_usd=voice_estimated_cost_per_minute_usd,
        voice_text_input_price_per_million_tokens_usd=float(
            voice.get(
                "text_input_price_per_million_tokens_usd",
                DEFAULT_TTS_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD,
            )
        ),
        voice_audio_output_price_per_million_tokens_usd=voice_audio_output_price_per_million_tokens_usd,
        voice_audio_tokens_per_second=voice_audio_tokens_per_second,
        voice_api_key_env=voice.get("api_key_env", "OPENAI_API_KEY"),
        voice_api_key_keychain_service=voice.get("api_key_keychain_service", "agent-chime"),
        voice_api_key_keychain_account=voice.get("api_key_keychain_account", "openai"),
        voice_instructions=voice.get(
            "instructions",
            "Speak naturally, calmly, and briefly. This is a short developer notification.",
        ),
        voice_timeout_seconds=int(voice.get("timeout_seconds", 15)),
        summary_enabled=bool(summary.get("enabled", False)),
        summary_provider=normalize_summary_provider(summary.get("provider", "openai")),
        summary_model=summary.get("model", DEFAULT_SUMMARY_MODEL),
        summary_privacy_level=normalize_summary_privacy_level(summary.get("privacy_level", "full_last_message")),
        summary_max_input_chars=max(200, int(summary.get("max_input_chars", DEFAULT_SUMMARY_MAX_INPUT_CHARS))),
        summary_max_words=max(1, int(summary.get("max_words", 40))),
        summary_timeout_seconds=max(1, int(summary.get("timeout_seconds", 5))),
        summary_prompt=summary.get("prompt", DEFAULT_SUMMARY_PROMPT),
        summary_text_input_price_per_million_tokens_usd=float(
            summary.get(
                "text_input_price_per_million_tokens_usd",
                DEFAULT_SUMMARY_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD,
            )
        ),
        summary_cached_input_price_per_million_tokens_usd=float(
            summary.get(
                "cached_input_price_per_million_tokens_usd",
                DEFAULT_SUMMARY_CACHED_INPUT_PRICE_PER_MILLION_TOKENS_USD,
            )
        ),
        summary_text_output_price_per_million_tokens_usd=float(
            summary.get(
                "text_output_price_per_million_tokens_usd",
                DEFAULT_SUMMARY_TEXT_OUTPUT_PRICE_PER_MILLION_TOKENS_USD,
            )
        ),
        message_templates=load_message_templates(data.get("messages", {})),
        desktop_enabled=bool(desktop.get("enabled", True)),
        terminal_enabled=bool(terminal.get("enabled", True)),
        min_seconds_between_voice_messages=int(limits.get("min_seconds_between_voice_messages", 8)),
        grouping_window_seconds=int(limits.get("grouping_window_seconds", 20)),
        max_events_per_minute=int(limits.get("max_events_per_minute", 6)),
        duplicate_cooldown_seconds=int(limits.get("duplicate_cooldown_seconds", 300)),
    )


def write_default_config(path: str | os.PathLike[str] | None = None) -> Path:
    config_path = expand_path(path or DEFAULT_CONFIG_PATH)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        database_path = default_database_path_for_config(config_path)
        config_path.write_text(
            DEFAULT_CONFIG_TOML_TEMPLATE.replace("{database_path}", str(database_path)),
            encoding="utf-8",
        )
        config_path.chmod(0o600)
    else:
        ensure_default_summary_section(config_path)
        ensure_default_message_sections(config_path)
    return config_path


def default_database_path_for_config(config_path: Path) -> Path:
    if config_path == expand_path(DEFAULT_CONFIG_PATH):
        return DEFAULT_DB_PATH
    return config_path.parent / "events.sqlite3"


def normalize_language(language: str) -> str:
    value = language.strip().lower()
    aliases = {
        "english": "en",
        "en-us": "en",
        "en-gb": "en",
    }
    normalized = aliases.get(value, value)
    if normalized not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise ValueError(f"Unsupported language '{language}'. Supported: {supported}")
    return normalized


def copy_message_templates(templates: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {language: dict(values) for language, values in templates.items()}


def load_message_templates(value: object) -> dict[str, dict[str, str]]:
    templates = copy_message_templates(DEFAULT_MESSAGE_TEMPLATES)
    if not isinstance(value, dict):
        return templates
    for language, defaults in DEFAULT_MESSAGE_TEMPLATES.items():
        user_templates = value.get(language, {})
        if not isinstance(user_templates, dict):
            continue
        for key in defaults:
            user_value = user_templates.get(key)
            if isinstance(user_value, str) and user_value.strip():
                templates[language][key] = user_value
    return templates


def ensure_default_message_sections(config_path: Path) -> None:
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return

    messages = data.get("messages", {})
    missing_languages = [
        language
        for language in SUPPORTED_LANGUAGES
        if not isinstance(messages, dict) or not isinstance(messages.get(language), dict)
    ]
    if not missing_languages:
        return

    with config_path.open("a", encoding="utf-8") as file:
        file.write(default_message_sections_toml(missing_languages))
    config_path.chmod(0o600)


def ensure_default_summary_section(config_path: Path) -> None:
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return

    current = data.get("summary", {})
    missing = dict(DEFAULT_SUMMARY_CONFIG)
    if isinstance(current, dict):
        for key in current:
            missing.pop(key, None)
    if not missing:
        return
    ensure_config_section_values(config_path, "summary", missing)


def ensure_config_section_values(
    config_path: Path,
    section: str,
    values: dict[str, str | int | float | bool],
) -> None:
    lines = config_path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    in_section = False
    saw_section = False
    remaining = dict(values)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section:
                for key, value in remaining.items():
                    output.append(_toml_assignment(key, value))
                remaining.clear()
            in_section = stripped == f"[{section}]"
            saw_section = saw_section or in_section
            output.append(line)
            continue
        output.append(line)

    if in_section:
        for key, value in remaining.items():
            output.append(_toml_assignment(key, value))
        remaining.clear()

    if not saw_section:
        output.extend(["", f"[{section}]"])
        for key, value in remaining.items():
            output.append(_toml_assignment(key, value))

    config_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    config_path.chmod(0o600)


def default_message_sections_toml(languages: list[str]) -> str:
    lines = [""]
    for language in languages:
        lines.append(f"[messages.{language}]")
        for key, value in DEFAULT_MESSAGE_TEMPLATES[language].items():
            lines.append(_toml_assignment(key, value))
        lines.append("")
    return "\n".join(lines)


def set_config_language(path: str | os.PathLike[str] | None, language: str) -> Path:
    config_path = write_default_config(path)
    normalized = normalize_language(language)
    lines = config_path.read_text(encoding="utf-8").splitlines()

    output: list[str] = []
    in_user_section = False
    saw_user_section = False
    wrote_language = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_user_section and not wrote_language:
                output.append(f'language = "{normalized}"')
                wrote_language = True
            in_user_section = stripped == "[user]"
            saw_user_section = saw_user_section or in_user_section
            output.append(line)
            continue

        if in_user_section and stripped.startswith("language"):
            output.append(f'language = "{normalized}"')
            wrote_language = True
            continue

        output.append(line)

    if in_user_section and not wrote_language:
        output.append(f'language = "{normalized}"')
        wrote_language = True

    if not saw_user_section:
        output = ["[user]", f'language = "{normalized}"', ""] + output

    config_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    config_path.chmod(0o600)
    return config_path


def set_voice_config(
    path: str | os.PathLike[str] | None,
    *,
    backend: str | None = None,
    voice: str | None = None,
    rate: int | None = None,
    speed: float | None = None,
    model: str | None = None,
    audio_format: str | None = None,
    estimated_cost_per_minute_usd: float | None = None,
    text_input_price_per_million_tokens_usd: float | None = None,
    audio_output_price_per_million_tokens_usd: float | None = None,
    audio_tokens_per_second: float | None = None,
    instructions: str | None = None,
    api_key_env: str | None = None,
) -> Path:
    values: dict[str, str | int | float] = {}
    if backend is not None:
        values["backend"] = normalize_voice_backend(backend)
    if voice is not None:
        values["voice"] = voice
    if rate is not None:
        values["rate"] = rate
    if speed is not None:
        values["speed"] = normalize_voice_speed(speed)
    if model is not None:
        values["model"] = model
    if audio_format is not None:
        values["format"] = normalize_audio_format(audio_format)
    if estimated_cost_per_minute_usd is not None:
        values["estimated_cost_per_minute_usd"] = normalize_estimated_cost(estimated_cost_per_minute_usd)
    if text_input_price_per_million_tokens_usd is not None:
        values["text_input_price_per_million_tokens_usd"] = normalize_estimated_cost(
            text_input_price_per_million_tokens_usd
        )
    if audio_output_price_per_million_tokens_usd is not None:
        values["audio_output_price_per_million_tokens_usd"] = normalize_estimated_cost(
            audio_output_price_per_million_tokens_usd
        )
    if audio_tokens_per_second is not None:
        values["audio_tokens_per_second"] = normalize_estimated_cost(audio_tokens_per_second)
    if instructions is not None:
        values["instructions"] = instructions
    if api_key_env is not None:
        values["api_key_env"] = api_key_env
    return set_config_section_values(path, "voice", values)


def set_config_section_values(
    path: str | os.PathLike[str] | None,
    section: str,
    values: dict[str, str | int | float | bool],
) -> Path:
    config_path = write_default_config(path)
    lines = config_path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    in_section = False
    saw_section = False
    remaining = dict(values)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section:
                for key, value in remaining.items():
                    output.append(_toml_assignment(key, value))
                remaining.clear()
            in_section = stripped == f"[{section}]"
            saw_section = saw_section or in_section
            output.append(line)
            continue

        if in_section:
            key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
            if key in remaining:
                output.append(_toml_assignment(key, remaining.pop(key)))
                continue

        output.append(line)

    if in_section:
        for key, value in remaining.items():
            output.append(_toml_assignment(key, value))
        remaining.clear()

    if not saw_section:
        output.extend(["", f"[{section}]"])
        for key, value in remaining.items():
            output.append(_toml_assignment(key, value))

    config_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    config_path.chmod(0o600)
    return config_path


def normalize_voice_backend(backend: str) -> str:
    normalized = backend.strip().lower()
    supported = {"macos_say", "openai_tts"}
    if normalized not in supported:
        raise ValueError(f"Unsupported voice backend '{backend}'. Supported: {', '.join(sorted(supported))}")
    return normalized


def normalize_summary_provider(provider: str) -> str:
    normalized = str(provider).strip().lower()
    if normalized not in SUMMARY_PROVIDERS:
        supported = ", ".join(SUMMARY_PROVIDERS)
        raise ValueError(f"Unsupported summary provider '{provider}'. Supported: {supported}")
    return normalized


def normalize_summary_privacy_level(privacy_level: str) -> str:
    normalized = str(privacy_level).strip().lower()
    if normalized not in SUMMARY_PRIVACY_LEVELS:
        supported = ", ".join(SUMMARY_PRIVACY_LEVELS)
        raise ValueError(f"Unsupported summary privacy level '{privacy_level}'. Supported: {supported}")
    return normalized


def normalize_audio_format(audio_format: str) -> str:
    normalized = audio_format.strip().lower()
    supported = {"mp3", "opus", "aac", "flac", "wav", "pcm"}
    if normalized not in supported:
        raise ValueError(f"Unsupported audio format '{audio_format}'. Supported: {', '.join(sorted(supported))}")
    return normalized


def normalize_voice_speed(speed: float) -> float:
    if speed < 0.25 or speed > 4.0:
        raise ValueError("Voice speed must be between 0.25 and 4.0")
    return round(speed, 2)


def normalize_estimated_cost(cost: float) -> float:
    if cost < 0:
        raise ValueError("Estimated cost must be non-negative")
    return round(cost, 6)


def _toml_assignment(key: str, value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return f"{key} = {str(value).lower()}"
    if isinstance(value, int):
        return f"{key} = {value}"
    if isinstance(value, float):
        return f"{key} = {value:g}"
    if "\n" in value:
        return f"{key} = '''\n{value.rstrip()}\n'''"
    return f'{key} = "{_escape_toml_string(value)}"'


def _escape_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
