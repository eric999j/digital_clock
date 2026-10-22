import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from core.events import Events
from services import timezone_service
from services.timezone_service import PRESET_ZONES, TimezoneService


class TestTimezoneService(unittest.TestCase):
    def setUp(self):
        self.config = {'timezones': {'selected': []}}
        self.config_mgr = MagicMock()
        self.config_mgr.load_config.side_effect = lambda read_only=False: self.config
        self.notify = MagicMock()
        self.service = TimezoneService(self.config_mgr, self.notify)

    def test_get_selected_filters_invalid_duplicate_and_overflow(self):
        self.config['timezones']['selected'] = [
            "Asia/Tokyo", "Asia/Tokyo", "Mars/Base", 42, "Europe/London",
            "America/New_York", "UTC",
        ]
        self.assertEqual(
            self.service.get_selected(),
            ["Asia/Tokyo", "Europe/London", "America/New_York"],
        )

    def test_get_selected_tolerates_missing_or_malformed_config(self):
        for bad in ({}, {'timezones': None}, {'timezones': {'selected': 'Asia/Tokyo'}}):
            with self.subTest(config=bad):
                self.assertEqual(self.service.get_selected(bad), [])

    def test_toggle_adds_saves_and_notifies(self):
        self.assertTrue(self.service.toggle_zone("Asia/Tokyo"))

        self.assertEqual(self.config['timezones']['selected'], ["Asia/Tokyo"])
        self.config_mgr.save_config.assert_called_once_with(self.config)
        self.notify.assert_called_once_with(Events.TIMEZONES_UPDATED, ["Asia/Tokyo"])

    def test_toggle_removes_existing_zone(self):
        self.config['timezones']['selected'] = ["Asia/Tokyo", "UTC"]
        self.assertFalse(self.service.toggle_zone("Asia/Tokyo"))
        self.assertEqual(self.config['timezones']['selected'], ["UTC"])

    def test_toggle_rejects_unknown_zone(self):
        self.assertFalse(self.service.toggle_zone("Mars/Base"))
        self.config_mgr.save_config.assert_not_called()
        self.notify.assert_not_called()

    def test_toggle_respects_max_zones(self):
        self.config['timezones']['selected'] = ["Asia/Tokyo", "Europe/London", "America/New_York"]
        self.assertFalse(self.service.toggle_zone("UTC"))
        self.assertEqual(len(self.config['timezones']['selected']), TimezoneService.MAX_ZONES)
        self.config_mgr.save_config.assert_not_called()

    def test_toggle_creates_missing_timezones_section(self):
        self.config.pop('timezones')
        self.assertTrue(self.service.toggle_zone("UTC"))
        self.assertEqual(self.config['timezones']['selected'], ["UTC"])

    def test_zone_times_convert_and_report_day_offset(self):
        self.config['timezones']['selected'] = ["Asia/Tokyo", "America/Los_Angeles"]
        # 2026-01-15 23:30 UTC：東京已是隔天 08:30，洛杉磯則是同日 15:30
        now = datetime(2026, 1, 15, 23, 30, tzinfo=ZoneInfo("UTC"))

        tokyo, la = self.service.get_zone_times(now)

        self.assertEqual((tokyo.label, tokyo.local_time.hour, tokyo.local_time.minute), ("東京", 8, 30))
        self.assertEqual(tokyo.day_offset, 1)
        self.assertEqual((la.label, la.local_time.hour), ("洛杉磯", 15))
        self.assertEqual(la.day_offset, 0)

    def test_zone_times_handle_dst(self):
        self.config['timezones']['selected'] = ["America/New_York"]
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC"))
        summer = datetime(2026, 7, 15, 12, 0, tzinfo=ZoneInfo("UTC"))

        self.assertEqual(self.service.get_zone_times(winter)[0].local_time.hour, 7)
        self.assertEqual(self.service.get_zone_times(summer)[0].local_time.hour, 8)

    def test_zone_times_accept_naive_local_time(self):
        self.config['timezones']['selected'] = ["UTC"]
        result = self.service.get_zone_times(datetime(2026, 3, 1, 12, 0))
        self.assertEqual(len(result), 1)

    def test_missing_tz_database_is_skipped_gracefully(self):
        self.config['timezones']['selected'] = ["Asia/Tokyo", "UTC"]
        real_load = timezone_service._load_zone
        with patch.object(
            timezone_service, "_load_zone",
            side_effect=lambda key: None if key == "Asia/Tokyo" else real_load(key),
        ):
            result = self.service.get_zone_times(datetime(2026, 3, 1, 12, 0))
            self.assertEqual([z.key for z in result], ["UTC"])
            self.assertNotIn("Asia/Tokyo", self.service.available_zones())
            self.assertFalse(self.service.toggle_zone("Asia/Tokyo"))

    def test_available_zones_lists_presets(self):
        available = self.service.available_zones()
        self.assertEqual(set(available), set(PRESET_ZONES))


if __name__ == "__main__":
    unittest.main()
