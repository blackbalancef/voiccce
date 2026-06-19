import unittest

from agent_voice.hooks.text_extract import (
    clean_assistant_message,
    shorten,
    summarize_assistant_message,
    summary_source_text,
)


class TextExtractTests(unittest.TestCase):
    def test_short_message_is_returned_without_truncation(self) -> None:
        result = summarize_assistant_message("All checks pass and the build is green.")

        self.assertEqual(result, "All checks pass and the build is green")

    def test_long_message_without_sentence_end_cuts_on_word_boundary(self) -> None:
        words = " ".join(f"word{i:02d}" for i in range(60))  # ~420 chars, no sentence end

        result = summarize_assistant_message(words, max_chars=220)

        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 220)  # ellipsis kept inside the budget
        head = result[:-3].rstrip()
        # The retained text is a whole-word prefix of the source: we never split a word.
        self.assertTrue(words.startswith(head))
        self.assertEqual(words[len(head)], " ")

    def test_a_sentence_end_below_the_threshold_is_rejected(self) -> None:
        # "Hi." ends at char 3 (< 60), so the tiny sentence must not be used; the long
        # remainder is cut on a word boundary instead.
        text = "Hi. " + " ".join(f"token{i:02d}" for i in range(60))

        result = summarize_assistant_message(text, max_chars=220)

        self.assertTrue(result.endswith("..."))
        self.assertNotEqual(result, "Hi")
        self.assertLessEqual(len(result), 220)

    def test_single_huge_token_with_no_space_is_hard_cut_within_budget(self) -> None:
        result = summarize_assistant_message("a" * 300, max_chars=50)

        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 50)

    def test_long_message_prefers_a_complete_sentence(self) -> None:
        first = "The first fact is fully and completely stated right here in this opening sentence."
        text = first + " " + ("more padding words " * 20)

        result = summarize_assistant_message(text, max_chars=220)

        self.assertFalse(result.endswith("..."))
        self.assertEqual(result, first.rstrip("."))

    def test_clean_strips_markdown_and_done_prefix(self) -> None:
        cleaned = clean_assistant_message("Done.\n\n**Result:** `code` works.")

        self.assertNotIn("**", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertIn("Result: code works", cleaned)

    def test_shorten_and_summary_source_text_handle_empty(self) -> None:
        self.assertIsNone(shorten(""))
        self.assertIsNone(summary_source_text("   "))
        self.assertEqual(summary_source_text("  keep this  "), "keep this")


if __name__ == "__main__":
    unittest.main()
