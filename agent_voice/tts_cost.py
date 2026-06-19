from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_TTS_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD = 0.60
DEFAULT_TTS_AUDIO_OUTPUT_PRICE_PER_MILLION_TOKENS_USD = 12.00
DEFAULT_TTS_ESTIMATED_COST_PER_MINUTE_USD = 0.015
DEFAULT_TTS_AUDIO_TOKENS_PER_SECOND = (
    DEFAULT_TTS_ESTIMATED_COST_PER_MINUTE_USD
    * 1_000_000
    / DEFAULT_TTS_AUDIO_OUTPUT_PRICE_PER_MILLION_TOKENS_USD
    / 60
)


@dataclass(frozen=True, slots=True)
class TTSCostEstimate:
    input_text_tokens: int
    output_audio_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    token_count_method: str


def estimate_openai_tts_cost(
    *,
    input_text: str,
    instructions: str | None,
    duration_seconds: float,
    model: str,
    text_input_price_per_million_tokens_usd: float,
    audio_output_price_per_million_tokens_usd: float,
    audio_tokens_per_second: float,
) -> TTSCostEstimate:
    counted_text = "\n".join(part for part in (input_text, instructions or "") if part)
    input_text_tokens, token_count_method = count_text_tokens(counted_text, model=model)
    output_audio_tokens = int(round(max(0.0, duration_seconds) * max(0.0, audio_tokens_per_second)))
    input_cost_usd = input_text_tokens / 1_000_000 * max(0.0, text_input_price_per_million_tokens_usd)
    output_cost_usd = (
        output_audio_tokens
        / 1_000_000
        * max(0.0, audio_output_price_per_million_tokens_usd)
    )
    return TTSCostEstimate(
        input_text_tokens=input_text_tokens,
        output_audio_tokens=output_audio_tokens,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=input_cost_usd + output_cost_usd,
        token_count_method=token_count_method,
    )


def count_text_tokens(text: str, *, model: str) -> tuple[int, str]:
    if not text:
        return 0, "empty"
    try:
        import tiktoken  # type: ignore[import-not-found]
    except Exception:
        return heuristic_text_token_count(text), "heuristic:utf8"

    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text)), f"tiktoken:{getattr(encoding, 'name', 'unknown')}"


def heuristic_text_token_count(text: str) -> int:
    if not text:
        return 0
    byte_estimate = len(text.encode("utf-8")) / 4
    word_estimate = len(text.split()) * 1.3
    char_estimate = len(text) / 4
    return max(1, math.ceil(max(byte_estimate, word_estimate, char_estimate)))


def audio_tokens_per_second_from_minute_cost(
    cost_per_minute_usd: float,
    audio_output_price_per_million_tokens_usd: float,
) -> float:
    if cost_per_minute_usd <= 0 or audio_output_price_per_million_tokens_usd <= 0:
        return 0.0
    return cost_per_minute_usd * 1_000_000 / audio_output_price_per_million_tokens_usd / 60
