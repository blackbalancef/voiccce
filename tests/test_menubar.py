import unittest

from agent_voice.menubar import format_countdown, mute_countdown


class MenuBarTests(unittest.TestCase):
    def test_format_countdown(self) -> None:
        self.assertEqual(format_countdown(0), "0:00")
        self.assertEqual(format_countdown(9), "0:09")
        self.assertEqual(format_countdown(65), "1:05")
        self.assertEqual(format_countdown(3605), "1:00:05")

    def test_mute_countdown_uses_remaining_seconds(self) -> None:
        self.assertEqual(mute_countdown(700, now=100), "10:00")
        self.assertEqual(mute_countdown(700, now=640), "1:00")
        self.assertEqual(mute_countdown(700, now=701), "0:00")
        self.assertIsNone(mute_countdown(None, now=100))


if __name__ == "__main__":
    unittest.main()
