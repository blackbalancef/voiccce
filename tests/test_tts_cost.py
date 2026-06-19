import unittest

from agent_voice.tts_cost import (
    DEFAULT_TTS_AUDIO_OUTPUT_PRICE_PER_MILLION_TOKENS_USD,
    DEFAULT_TTS_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD,
    estimate_openai_tts_cost,
)


class TTSCostTests(unittest.TestCase):
    def test_estimate_includes_text_and_audio_costs(self) -> None:
        estimate = estimate_openai_tts_cost(
            input_text="Build completed.",
            instructions="Speak calmly.",
            duration_seconds=60,
            model="gpt-4o-mini-tts",
            text_input_price_per_million_tokens_usd=DEFAULT_TTS_TEXT_INPUT_PRICE_PER_MILLION_TOKENS_USD,
            audio_output_price_per_million_tokens_usd=DEFAULT_TTS_AUDIO_OUTPUT_PRICE_PER_MILLION_TOKENS_USD,
            audio_tokens_per_second=20.833333,
        )

        self.assertGreater(estimate.input_text_tokens, 0)
        self.assertEqual(estimate.output_audio_tokens, 1250)
        self.assertAlmostEqual(estimate.output_cost_usd, 0.015)
        self.assertAlmostEqual(estimate.total_cost_usd, estimate.input_cost_usd + estimate.output_cost_usd)

    def test_estimate_counts_instructions_as_text_input(self) -> None:
        without_instructions = estimate_openai_tts_cost(
            input_text="Build completed.",
            instructions=None,
            duration_seconds=0,
            model="gpt-4o-mini-tts",
            text_input_price_per_million_tokens_usd=0.60,
            audio_output_price_per_million_tokens_usd=12.0,
            audio_tokens_per_second=20.833333,
        )
        with_instructions = estimate_openai_tts_cost(
            input_text="Build completed.",
            instructions="Speak calmly.",
            duration_seconds=0,
            model="gpt-4o-mini-tts",
            text_input_price_per_million_tokens_usd=0.60,
            audio_output_price_per_million_tokens_usd=12.0,
            audio_tokens_per_second=20.833333,
        )

        self.assertGreater(with_instructions.input_text_tokens, without_instructions.input_text_tokens)


if __name__ == "__main__":
    unittest.main()
