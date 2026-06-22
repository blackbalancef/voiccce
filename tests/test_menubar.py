import unittest
from pathlib import Path

from agent_voice.menubar import (
    ACTIVITY_FRAME_INTERVAL_SECONDS,
    ACTIVITY_ICON_STATES,
    LEFT_MOUSE_DOWN_EVENT_TYPE,
    LEFT_MOUSE_DRAGGED_EVENT_TYPE,
    VOICE_SPEED_PRESETS,
    format_countdown,
    format_speed_preset,
    format_voice_speed,
    is_slider_commit_event_type,
    menu_voice_speed_value,
    mute_countdown,
    speed_to_tag,
    tag_to_speed,
    voice_speed_label,
)


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

    def test_menu_voice_speed_value_clamps_and_steps(self) -> None:
        self.assertEqual(menu_voice_speed_value(0.1), 0.25)
        self.assertEqual(menu_voice_speed_value(4.5), 4.0)
        self.assertEqual(menu_voice_speed_value(1.234), 1.25)
        self.assertEqual(menu_voice_speed_value(1.224), 1.2)

    def test_format_voice_speed(self) -> None:
        self.assertEqual(format_voice_speed(1), "1.00x")
        self.assertEqual(format_voice_speed(1.2), "1.20x")

    def test_voice_speed_label(self) -> None:
        self.assertEqual(voice_speed_label(1), "Speed: 1.00x")
        self.assertEqual(voice_speed_label(1.234), "Speed: 1.25x")

    def test_slider_commits_on_mouse_up_and_keyboard_not_mid_drag(self) -> None:
        # Mid-drag ticks (mouse-down/dragged) must not persist the value.
        self.assertFalse(is_slider_commit_event_type(LEFT_MOUSE_DOWN_EVENT_TYPE))
        self.assertFalse(is_slider_commit_event_type(LEFT_MOUSE_DRAGGED_EVENT_TYPE))
        # Mouse-up (2), keyboard (10), and "no event" settle the value.
        self.assertTrue(is_slider_commit_event_type(2))
        self.assertTrue(is_slider_commit_event_type(10))
        self.assertTrue(is_slider_commit_event_type(None))

    def test_format_speed_preset_strips_trailing_zeros(self) -> None:
        self.assertEqual(format_speed_preset(1.0), "1×")
        self.assertEqual(format_speed_preset(1.5), "1.5×")
        self.assertEqual(format_speed_preset(2.0), "2×")

    def test_preset_tag_round_trip(self) -> None:
        for preset in VOICE_SPEED_PRESETS:
            self.assertEqual(tag_to_speed(speed_to_tag(preset)), preset)

    def test_speaking_animation_uses_nested_frame_sequence(self) -> None:
        self.assertGreaterEqual(ACTIVITY_FRAME_INTERVAL_SECONDS, 0.18)
        self.assertLessEqual(ACTIVITY_FRAME_INTERVAL_SECONDS, 0.25)
        self.assertEqual(
            ACTIVITY_ICON_STATES,
            ("speaking-1", "speaking-2", "speaking-3", "speaking-2"),
        )
        self.assertEqual(
            tuple(ACTIVITY_ICON_STATES[index % len(ACTIVITY_ICON_STATES)] for index in range(7)),
            (
                "speaking-1",
                "speaking-2",
                "speaking-3",
                "speaking-2",
                "speaking-1",
                "speaking-2",
                "speaking-3",
            ),
        )

    def test_speaking_wave_paths_are_nested_rotated_wifi_arcs(self) -> None:
        asset_dir = Path(__file__).resolve().parents[1] / "agent_voice" / "assets" / "menubar"
        expected_wave_counts = {
            "bat-speaking-1.svg": 1,
            "bat-speaking-2.svg": 2,
            "bat-speaking-3.svg": 3,
        }
        full_frame_paths = None
        previous_midpoint = None
        previous_radius = None
        origin = (14.55, 9.45)
        normalized_reference = None
        for filename, expected_count in expected_wave_counts.items():
            text = (asset_dir / filename).read_text(encoding="utf-8")
            wave_paths = [
                line.split('d="', 1)[1].split('"', 1)[0]
                for line in text.splitlines()
                if 'stroke-width="0.52"' in line
            ]
            self.assertEqual(len(wave_paths), expected_count)
            if full_frame_paths is None and filename == "bat-speaking-3.svg":
                full_frame_paths = wave_paths

        full_frame_text = (asset_dir / "bat-speaking-3.svg").read_text(encoding="utf-8")
        full_frame_paths = [
            line.split('d="', 1)[1].split('"', 1)[0]
            for line in full_frame_text.splitlines()
            if 'stroke-width="0.52"' in line
        ]
        for filename, expected_count in expected_wave_counts.items():
            text = (asset_dir / filename).read_text(encoding="utf-8")
            wave_paths = [
                line.split('d="', 1)[1].split('"', 1)[0]
                for line in text.splitlines()
                if 'stroke-width="0.52"' in line
            ]
            self.assertEqual(wave_paths, full_frame_paths[:expected_count])

        for path in full_frame_paths:
            start_text, rest = path.removeprefix("M").split(" C", 1)
            values = [float(value) for value in f"{start_text} {rest}".split()]
            points = tuple(zip(values[0::2], values[1::2], strict=True))
            radius = ((points[0][0] - origin[0]) ** 2 + (points[0][1] - origin[1]) ** 2) ** 0.5
            normalized = tuple(
                (
                    round((point[0] - origin[0]) / radius, 2),
                    round((point[1] - origin[1]) / radius, 2),
                )
                for point in points
            )
            if normalized_reference is None:
                normalized_reference = normalized
            else:
                for point, reference_point in zip(normalized, normalized_reference, strict=True):
                    self.assertAlmostEqual(point[0], reference_point[0], delta=0.02)
                    self.assertAlmostEqual(point[1], reference_point[1], delta=0.02)
            midpoint = self._cubic_midpoint(points)
            if previous_midpoint is not None and previous_radius is not None:
                self.assertGreater(radius, previous_radius)
                self.assertGreater(midpoint[0], previous_midpoint[0])
                self.assertLess(midpoint[1], previous_midpoint[1])
            previous_radius = radius
            previous_midpoint = midpoint

    @staticmethod
    def _cubic_midpoint(points: tuple[tuple[float, float], ...]) -> tuple[float, float]:
        start, control_1, control_2, end = points
        return (
            0.125 * start[0] + 0.375 * control_1[0] + 0.375 * control_2[0] + 0.125 * end[0],
            0.125 * start[1] + 0.375 * control_1[1] + 0.375 * control_2[1] + 0.125 * end[1],
        )


if __name__ == "__main__":
    unittest.main()
