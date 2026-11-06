"""CalendarSyncService 測試（不連網、不使用真實 ICS 連結）。"""
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from core.events import Events
from services.calendar_sync_service import CalendarSyncService, is_valid_ics_url

NOW = datetime(2026, 5, 1, 10, 30)


class FakeConfig:
    """最小化的 ConfigManager 替身。"""

    def __init__(self, enabled: bool = True) -> None:
        self.data = {
            'on_vacation': False,
            'reminder_paused': False,
            'hourly_web_reminder': {},
            'calendar_sync': {'enabled': enabled, 'ics_url': 'https://example.invalid/x.ics',
                              'refresh_minutes': 15, 'lead_minutes': 10},
        }

    def load_config(self, read_only: bool = False) -> dict:
        return self.data

    def save_config(self, config: dict) -> None:
        self.data = config


class FakePause:
    """依 FakeConfig 運作的 PauseManager 替身。"""

    def __init__(self, cfg: FakeConfig) -> None:
        self.cfg = cfg
        self.toggles: list[str] = []

    def get_pause_state(self, key: str, config=None) -> bool:
        return bool(self.cfg.data.get('on_vacation'))

    def get_vacation_source(self, config=None):
        return self.cfg.data.get('on_vacation_source') if self.cfg.data.get('on_vacation') else None

    def has_vacation_source(self, source: str, config=None) -> bool:
        return source in self.cfg.data.get('vacation_sources', [self.cfg.data.get('on_vacation_source')])

    def set_vacation_source(self, source: str, active: bool) -> None:
        sources = set(self.cfg.data.get('vacation_sources', []))
        if not sources and self.cfg.data.get('on_vacation_source'):
            sources.add(self.cfg.data['on_vacation_source'])
        if active:
            sources.add(source)
        else:
            sources.discard(source)
        self.cfg.data['vacation_sources'] = sorted(sources)
        self.cfg.data['on_vacation'] = bool(sources)
        if sources:
            self.cfg.data['on_vacation_source'] = sorted(sources)[0]
        else:
            self.cfg.data.pop('on_vacation_source', None)

    def toggle_vacation(self, source: str = 'manual') -> None:
        self.toggles.append(source)
        sources = set(self.cfg.data.get('vacation_sources', []))
        if not sources and self.cfg.data.get('on_vacation_source'):
            sources.add(self.cfg.data['on_vacation_source'])
        if source == 'manual' and source not in sources and sources:
            for held_source in tuple(sources):
                self.set_vacation_source(held_source, False)
        else:
            self.set_vacation_source(source, source not in sources)


def _ev(start: str, end: str, summary: str = "會議") -> dict:
    return {'start': datetime.fromisoformat(start), 'end': datetime.fromisoformat(end), 'summary': summary}


class CalendarSyncServiceTests(unittest.TestCase):
    def _make(self, enabled: bool = True):
        cfg = FakeConfig(enabled)
        pause = FakePause(cfg)
        notify = MagicMock()
        service = CalendarSyncService(cfg, notify, pause)
        return service, cfg, pause, notify

    def test_enters_and_exits_vacation(self) -> None:
        service, cfg, pause, notify = self._make()
        service._events = [_ev("2026-05-01T10:00", "2026-05-01T11:00")]
        service.check(now=NOW)
        self.assertTrue(cfg.data['on_vacation'])
        self.assertEqual(cfg.data['on_vacation_source'], 'calendar')
        notify.assert_any_call(Events.CALENDAR_EVENT_STARTED, "會議")

        service.check(now=datetime(2026, 5, 1, 11, 0))
        self.assertFalse(cfg.data['on_vacation'])
        notify.assert_any_call(Events.CALENDAR_EVENT_ENDED)

    def test_manual_vacation_coexists_with_calendar_source(self) -> None:
        service, cfg, pause, notify = self._make()
        cfg.data['on_vacation'] = True
        cfg.data['on_vacation_source'] = 'manual'
        service._events = [_ev("2026-05-01T10:00", "2026-05-01T11:00")]
        service.check(now=NOW)
        service.check(now=datetime(2026, 5, 1, 12, 0))
        self.assertTrue(pause.has_vacation_source('manual'))
        self.assertFalse(pause.has_vacation_source('calendar'))
        self.assertTrue(cfg.data['on_vacation'])

    def test_manual_exit_during_event_releases_calendar_source(self) -> None:
        service, cfg, pause, notify = self._make()
        service._events = [_ev("2026-05-01T10:00", "2026-05-01T11:00")]
        service.check(now=NOW)
        pause.toggle_vacation('manual')  # 使用者手動結束
        service.check(now=datetime(2026, 5, 1, 10, 40))
        self.assertFalse(cfg.data['on_vacation'])
        self.assertFalse(pause.has_vacation_source('calendar'))

    def test_no_data_keeps_state(self) -> None:
        service, cfg, pause, notify = self._make()
        cfg.data['on_vacation'] = True
        cfg.data['on_vacation_source'] = 'calendar'
        service._events = None  # 尚未成功同步（或失敗）
        service.check(now=NOW)
        self.assertTrue(cfg.data['on_vacation'])
        notify.assert_not_called()

    def test_disabled_releases_calendar_vacation(self) -> None:
        service, cfg, pause, notify = self._make(enabled=False)
        cfg.data['on_vacation'] = True
        cfg.data['on_vacation_source'] = 'calendar'
        service.check(now=NOW)
        self.assertFalse(cfg.data['on_vacation'])

    def test_upcoming_notice_deduped(self) -> None:
        service, cfg, pause, notify = self._make()
        service._events = [_ev("2026-05-01T10:40", "2026-05-01T11:00")]
        service.check(now=NOW)
        service.check(now=datetime(2026, 5, 1, 10, 31))
        upcoming = [c for c in notify.call_args_list if c.args[0] == Events.CALENDAR_EVENT_UPCOMING]
        self.assertEqual(len(upcoming), 1)

    def test_https_only(self) -> None:
        self.assertTrue(is_valid_ics_url("https://example.invalid/a.ics"))
        self.assertFalse(is_valid_ics_url("http://example.invalid/a.ics"))
        self.assertFalse(is_valid_ics_url("file:///etc/passwd"))

    def test_update_settings_rejects_http(self) -> None:
        service, *_ = self._make()
        with self.assertRaises(ValueError):
            service.update_settings(True, "http://example.invalid/a.ics", 15, 10)

    def test_parse_outlook_style_ics(self) -> None:
        ics = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
            "BEGIN:VTIMEZONE\r\nTZID:Taipei Standard Time\r\n"
            "BEGIN:STANDARD\r\nDTSTART:16010101T000000\r\nTZOFFSETFROM:+0800\r\nTZOFFSETTO:+0800\r\nEND:STANDARD\r\n"
            "END:VTIMEZONE\r\n"
            # 每週五 10:00-12:00（Windows TZID + RRULE）
            "BEGIN:VEVENT\r\nUID:weekly\r\nSUMMARY:週會\r\n"
            "DTSTART;TZID=Taipei Standard Time:20260102T100000\r\n"
            "DTEND;TZID=Taipei Standard Time:20260102T120000\r\n"
            "RRULE:FREQ=WEEKLY;BYDAY=FR\r\nEND:VEVENT\r\n"
            # UTC 單次事件
            "BEGIN:VEVENT\r\nUID:once\r\nSUMMARY:單次\r\n"
            "DTSTART:20260501T020000Z\r\nDTEND:20260501T030000Z\r\nEND:VEVENT\r\n"
            # 已取消
            "BEGIN:VEVENT\r\nUID:cancel\r\nSUMMARY:取消\r\nSTATUS:CANCELLED\r\n"
            "DTSTART:20260501T040000Z\r\nDTEND:20260501T050000Z\r\nEND:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        try:
            events = CalendarSyncService.parse_events(ics, datetime(2026, 5, 1, 9, 0))
        except ImportError:
            self.skipTest("icalendar / recurring-ical-events 未安裝")
        summaries = [e['summary'] for e in events]
        self.assertIn("單次", summaries)
        self.assertNotIn("取消", summaries)
        self.assertGreaterEqual(summaries.count("週會"), 1)  # 5/1 為週五
        self.assertTrue(all(isinstance(e['start'], datetime) and e['start'].tzinfo is None for e in events))


if __name__ == '__main__':
    unittest.main()
