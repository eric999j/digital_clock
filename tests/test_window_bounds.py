import unittest
from unittest.mock import MagicMock, patch

from ui.window_bounds import clamp_position, get_screen_bounds, position_popup_outside

BOUNDS = (0, 0, 1920, 1080)


class TestClampPosition(unittest.TestCase):
    def test_inside_bounds_is_unchanged(self):
        self.assertEqual(clamp_position(100, 50, 200, 70, BOUNDS), (100, 50))

    def test_negative_coordinates_are_clamped_to_top_left(self):
        self.assertEqual(clamp_position(-500, -30, 200, 70, BOUNDS), (0, 0))

    def test_overflow_is_clamped_so_whole_window_stays_visible(self):
        self.assertEqual(clamp_position(5000, 5000, 200, 70, BOUNDS), (1720, 1010))

    def test_exact_edges_are_allowed(self):
        self.assertEqual(clamp_position(1720, 1010, 200, 70, BOUNDS), (1720, 1010))

    def test_window_larger_than_bounds_aligns_top_left(self):
        self.assertEqual(clamp_position(300, 300, 3000, 2000, BOUNDS), (0, 0))

    def test_negative_origin_monitor_is_supported(self):
        # 副螢幕位於主螢幕左側時，虛擬桌面的 left 為負值
        bounds = (-1920, 0, 1920, 1080)
        self.assertEqual(clamp_position(-3000, 10, 200, 70, bounds), (-1920, 10))
        self.assertEqual(clamp_position(-100, 10, 200, 70, bounds), (-100, 10))


class TestPositionPopupOutside(unittest.TestCase):
    def test_prefers_space_to_the_nearest_side_of_clock(self):
        obstacle = (500, 300, 900, 450)

        self.assertEqual(
            position_popup_outside(700, 375, 180, 300, obstacle, BOUNDS),
            (700, 451),
        )

    def test_uses_left_when_right_edge_has_no_space(self):
        obstacle = (1700, 300, 1900, 450)

        self.assertEqual(
            position_popup_outside(1800, 375, 180, 300, obstacle, BOUNDS),
            (1740, 451),
        )

    def test_uses_space_below_when_horizontal_space_is_insufficient(self):
        bounds = (0, 0, 500, 800)
        obstacle = (50, 250, 450, 400)

        self.assertEqual(
            position_popup_outside(250, 325, 180, 200, obstacle, bounds),
            (250, 401),
        )

    def test_uses_space_above_clock_near_bottom_edge(self):
        obstacle = (100, 900, 400, 1050)

        self.assertEqual(
            position_popup_outside(250, 975, 180, 300, obstacle, BOUNDS),
            (401, 780),
        )


class TestGetScreenBounds(unittest.TestCase):
    def test_non_windows_uses_primary_screen(self):
        root = MagicMock()
        root.winfo_screenwidth.return_value = 1440
        root.winfo_screenheight.return_value = 900
        with patch("ui.window_bounds.sys.platform", "linux"):
            self.assertEqual(get_screen_bounds(root), (0, 0, 1440, 900))

    def test_windows_uses_virtual_screen(self):
        metrics = {76: -1920, 77: 0, 78: 3840, 79: 1080}
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetSystemMetrics.side_effect = lambda i: metrics[i]
        with patch("ui.window_bounds.sys.platform", "win32"), patch("ui.window_bounds.ctypes", fake_ctypes):
            self.assertEqual(get_screen_bounds(MagicMock()), (-1920, 0, 1920, 1080))

    def test_windows_falls_back_when_metrics_unavailable(self):
        root = MagicMock()
        root.winfo_screenwidth.return_value = 1280
        root.winfo_screenheight.return_value = 720
        fake_ctypes = MagicMock()
        fake_ctypes.windll.user32.GetSystemMetrics.return_value = 0
        with patch("ui.window_bounds.sys.platform", "win32"), patch("ui.window_bounds.ctypes", fake_ctypes):
            self.assertEqual(get_screen_bounds(root), (0, 0, 1280, 720))


if __name__ == "__main__":
    unittest.main()
