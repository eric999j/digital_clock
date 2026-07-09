"""VacationScheduleService 測試。"""
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from core.events import Events
from services.vacation_schedule_service import VacationScheduleService


class TestVacationScheduleService(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_config_mgr = MagicMock()
        self.mock_notify = MagicMock()
        self.mock_pause_manager = MagicMock()
        self.mock_pomodoro_stop = MagicMock()
        self.service = VacationScheduleService(
            self.mock_config_mgr,
            self.mock_notify,
            self.mock_pause_manager,
            self.mock_pomodoro_stop,
        )

    # --- add_schedule ---

    def test_add_schedule_persists_and_notifies(self) -> None:
        config: dict = {'vacation_schedules': []}
        self.mock_config_mgr.load_config.return_value = config

        result = self.service.add_schedule('2026-07-10', '2026-07-15', '暑假')

        self.mock_config_mgr.save_config.assert_called_once_with(config)
        self.assertEqual(len(config['vacation_schedules']), 1)
        stored = config['vacation_schedules'][0]
        self.assertEqual(stored['start'], '2026-07-10')
        self.assertEqual(stored['end'], '2026-07-15')
        self.assertEqual(stored['note'], '暑假')
        self.assertFalse(stored['auto_started'])
        self.mock_notify.assert_called_once_with(Events.VACATION_SCHEDULE_ADDED, result)

    def test_add_schedule_rejects_end_before_start(self) -> None:
        with self.assertRaises(ValueError):
            self.service.add_schedule('2026-07-15', '2026-07-10')
        self.mock_config_mgr.save_config.assert_not_called()

    def test_add_schedule_rejects_invalid_date(self) -> None:
        with self.assertRaises(ValueError):
            self.service.add_schedule('not-a-date', '2026-07-10')

    def test_add_schedule_sorts_by_start(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-08-01', 'end': '2026-08-05', 'note': ''},
            ]
        }
        self.mock_config_mgr.load_config.return_value = config

        self.service.add_schedule('2026-07-10', '2026-07-15', 'a')

        starts = [s['start'] for s in config['vacation_schedules']]
        self.assertEqual(starts, sorted(starts))

    # --- delete_schedule ---

    def test_delete_schedule_removes_first_match(self) -> None:
        schedule = {'start': '2026-07-10', 'end': '2026-07-15', 'note': '暑假'}
        config: dict = {'vacation_schedules': [schedule]}
        self.mock_config_mgr.load_config.return_value = config

        self.service.delete_schedule(schedule)

        self.assertEqual(config['vacation_schedules'], [])
        self.mock_notify.assert_called_once_with(Events.VACATION_SCHEDULE_DELETED, schedule)

    def test_delete_schedule_no_op_when_missing(self) -> None:
        self.mock_config_mgr.load_config.return_value = {'vacation_schedules': []}
        self.service.delete_schedule({'start': '2026-07-10', 'end': '2026-07-15', 'note': ''})
        self.mock_config_mgr.save_config.assert_not_called()
        self.mock_notify.assert_not_called()

    # --- check: 快速跳出 ---

    def test_check_returns_when_snapshot_has_no_schedules(self) -> None:
        snapshot = {'vacation_schedules': []}
        self.service.check(now=datetime(2026, 7, 10, 9), config=snapshot)
        # 使用快照時完全跳出，不會再次 load
        self.mock_config_mgr.load_config.assert_not_called()

    # --- check: 自動進入休假 ---

    def test_check_auto_enters_vacation_when_active_and_not_on_vacation(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-10', 'end': '2026-07-15', 'note': '', 'auto_started': False},
            ],
            'on_vacation': False,
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = False
        self.mock_pause_manager.get_vacation_source.return_value = None

        self.service.check(now=datetime(2026, 7, 10, 9))

        # 標記 auto_started 並儲存
        self.assertTrue(config['vacation_schedules'][0]['auto_started'])
        self.mock_config_mgr.save_config.assert_called_once_with(config)
        self.mock_pause_manager.toggle_vacation.assert_called_once_with(
            self.mock_pomodoro_stop, source='schedule'
        )

    def test_check_does_not_re_enter_when_already_marked(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-10', 'end': '2026-07-15', 'note': '', 'auto_started': True},
            ],
            'on_vacation': False,
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = False

        self.service.check(now=datetime(2026, 7, 12, 9))

        # 使用者手動退出後不應再自動進入
        self.mock_pause_manager.toggle_vacation.assert_not_called()
        # 沒有變動也不寫入
        self.mock_config_mgr.save_config.assert_not_called()

    def test_check_does_not_enter_when_already_on_vacation_manual(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-10', 'end': '2026-07-15', 'note': '', 'auto_started': False},
            ],
            'on_vacation': True,
            'on_vacation_source': 'manual',
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = True
        self.mock_pause_manager.get_vacation_source.return_value = 'manual'

        self.service.check(now=datetime(2026, 7, 10, 9))

        # 已在休假中，不需要再 toggle
        self.mock_pause_manager.toggle_vacation.assert_not_called()
        # 但 auto_started 仍應被標記，避免使用者手動結束休假後又被觸發
        self.assertTrue(config['vacation_schedules'][0]['auto_started'])

    # --- check: 自動離開休假 ---

    def test_check_auto_exits_when_expired_and_source_is_schedule(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-01', 'end': '2026-07-05', 'note': '', 'auto_started': True},
            ],
            'on_vacation': True,
            'on_vacation_source': 'schedule',
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = True
        self.mock_pause_manager.get_vacation_source.return_value = 'schedule'

        self.service.check(now=datetime(2026, 7, 10, 9))

        # 過期排程被清除
        self.assertEqual(config['vacation_schedules'], [])
        self.mock_config_mgr.save_config.assert_called_once_with(config)
        # 自動離開休假
        self.mock_pause_manager.toggle_vacation.assert_called_once_with(
            self.mock_pomodoro_stop, source='schedule'
        )

    def test_check_does_not_exit_when_vacation_is_manual(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-01', 'end': '2026-07-05', 'note': '', 'auto_started': True},
            ],
            'on_vacation': True,
            'on_vacation_source': 'manual',
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = True
        self.mock_pause_manager.get_vacation_source.return_value = 'manual'

        self.service.check(now=datetime(2026, 7, 10, 9))

        # 手動觸發的休假不應被排程過期自動退出
        self.mock_pause_manager.toggle_vacation.assert_not_called()
        # 但過期排程仍應被清除
        self.assertEqual(config['vacation_schedules'], [])
        self.mock_config_mgr.save_config.assert_called_once_with(config)

    def test_check_does_not_exit_when_another_active_schedule_exists(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-01', 'end': '2026-07-05', 'note': '', 'auto_started': True},
                {'start': '2026-07-08', 'end': '2026-07-15', 'note': '', 'auto_started': True},
            ],
            'on_vacation': True,
            'on_vacation_source': 'schedule',
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = True
        self.mock_pause_manager.get_vacation_source.return_value = 'schedule'

        self.service.check(now=datetime(2026, 7, 10, 9))

        # 仍在另一個排程期間，不應退出
        self.mock_pause_manager.toggle_vacation.assert_not_called()
        # 但過期排程仍被清除，剩下 active
        self.assertEqual(len(config['vacation_schedules']), 1)
        self.assertEqual(config['vacation_schedules'][0]['start'], '2026-07-08')

    # --- check: 清理 ---

    def test_check_removes_expired_without_toggle_when_not_on_vacation(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-01', 'end': '2026-07-05', 'note': '', 'auto_started': True},
            ],
            'on_vacation': False,
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = False
        self.mock_pause_manager.get_vacation_source.return_value = None

        self.service.check(now=datetime(2026, 7, 10, 9))

        # 過期排程被清除，不 toggle
        self.assertEqual(config['vacation_schedules'], [])
        self.mock_pause_manager.toggle_vacation.assert_not_called()

    def test_check_removes_invalid_schedules(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-07-15', 'end': '2026-07-10', 'note': '結束早於開始'},
                {'start': 'bad-date', 'end': '2026-07-10', 'note': ''},
            ],
            'on_vacation': False,
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = False
        self.mock_pause_manager.get_vacation_source.return_value = None

        self.service.check(now=datetime(2026, 7, 10, 9))

        self.assertEqual(config['vacation_schedules'], [])
        self.mock_config_mgr.save_config.assert_called_once_with(config)

    def test_check_no_write_when_no_changes(self) -> None:
        config: dict = {
            'vacation_schedules': [
                {'start': '2026-08-01', 'end': '2026-08-05', 'note': '', 'auto_started': False},
            ],
            'on_vacation': False,
        }
        self.mock_config_mgr.load_config.return_value = config
        self.mock_pause_manager.get_pause_state.return_value = False
        self.mock_pause_manager.get_vacation_source.return_value = None

        self.service.check(now=datetime(2026, 7, 10, 9))

        # 只有未來排程，未進入 active，不應改變或寫入
        self.mock_config_mgr.save_config.assert_not_called()
        self.mock_pause_manager.toggle_vacation.assert_not_called()

    # --- list_schedules ---

    def test_list_schedules_returns_copy(self) -> None:
        schedules = [
            {'start': '2026-07-10', 'end': '2026-07-15', 'note': ''},
        ]
        self.mock_config_mgr.load_config.return_value = {'vacation_schedules': schedules}

        result = self.service.list_schedules()

        self.assertEqual(result, schedules)
        # 修改結果不應影響原資料
        result.append({})
        self.assertEqual(len(schedules), 1)


if __name__ == '__main__':
    unittest.main()
