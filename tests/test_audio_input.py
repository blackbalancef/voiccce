import unittest
from unittest.mock import patch

from agent_voice import audio_input
from agent_voice.audio_input import microphone_in_use


class MicrophoneInUseTests(unittest.TestCase):
    def test_returns_bool_without_raising(self) -> None:
        # Real call: returns the actual system state on macOS, False elsewhere.
        # Either way it must be a bool and never raise.
        self.assertIsInstance(microphone_in_use(), bool)

    def test_fails_open_on_error(self) -> None:
        # A detection glitch must never silence notifications: return False, not raise.
        with patch.object(audio_input, "_load", side_effect=RuntimeError("boom")):
            self.assertFalse(microphone_in_use())

    def test_false_when_framework_unavailable(self) -> None:
        with patch.object(audio_input, "_load", return_value=None):
            self.assertFalse(microphone_in_use())

    def test_true_when_any_input_device_running(self) -> None:
        sentinel = object()
        with (
            patch.object(audio_input, "_load", return_value=sentinel),
            patch.object(audio_input, "_input_device_ids", return_value=[10, 20, 30]),
            patch.object(audio_input, "_is_running_somewhere", side_effect=lambda lib, dev: dev == 20),
        ):
            self.assertTrue(microphone_in_use())

    def test_false_when_no_input_device_running(self) -> None:
        sentinel = object()
        with (
            patch.object(audio_input, "_load", return_value=sentinel),
            patch.object(audio_input, "_input_device_ids", return_value=[10, 20]),
            patch.object(audio_input, "_is_running_somewhere", return_value=False),
        ):
            self.assertFalse(microphone_in_use())

    def test_false_when_no_input_devices(self) -> None:
        sentinel = object()
        with (
            patch.object(audio_input, "_load", return_value=sentinel),
            patch.object(audio_input, "_input_device_ids", return_value=[]),
        ):
            self.assertFalse(microphone_in_use())


if __name__ == "__main__":
    unittest.main()
