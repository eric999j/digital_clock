"""ClockLogic Observer 派發例外隔離測試。"""
import unittest
from unittest.mock import MagicMock

from core.observer import Observer


class _FaultyObserver(Observer):
    """每次都拋例外的 observer。"""
    def __init__(self):
        self.calls = 0

    def update(self, event, *args, **kwargs):
        self.calls += 1
        raise RuntimeError("observer boom")


class _GoodObserver(Observer):
    def __init__(self):
        self.events = []

    def update(self, event, *args, **kwargs):
        self.events.append((event, args, kwargs))


class _FakeUiScheduler:
    """測試 ClockLogic 延遲排程用的精簡 UI stub。"""

    def __init__(self):
        self.after_calls = []
        self.cancelled_ids = []

    def after(self, delay_ms, callback):
        self.after_calls.append((delay_ms, callback))
        return f"after-{len(self.after_calls)}"

    def after_cancel(self, after_id):
        self.cancelled_ids.append(after_id)


class TestObserverIsolation(unittest.TestCase):
    """確保 ClockLogic.notify_observers 不因單一 observer 失敗而中斷派發。"""

    def _make_logic_stub(self):
        """建立最精簡的 logic stub，只測 notify_observers 的隔離邏輯。"""
        from core.clock_logic import ClockLogic

        # 透過 __new__ 跳過 __init__（避免實際初始化所有 service）
        logic = ClockLogic.__new__(ClockLogic)
        logic._observers = []
        return logic

    def test_observer_exception_does_not_block_others(self):
        logic = self._make_logic_stub()
        faulty = _FaultyObserver()
        good = _GoodObserver()
        logic.add_observer(faulty)
        logic.add_observer(good)

        # 即使 faulty 拋例外，good 仍應被通知
        logic.notify_observers("test_event", "arg1", key="value")

        self.assertEqual(faulty.calls, 1)
        self.assertEqual(good.events, [("test_event", ("arg1",), {"key": "value"})])

    def test_observer_can_be_removed(self):
        logic = self._make_logic_stub()
        good = _GoodObserver()
        logic.add_observer(good)
        logic.remove_observer(good)
        logic.notify_observers("test_event")
        self.assertEqual(good.events, [])

    def test_observer_must_implement_update(self):
        """Observer 是 abstract class，缺 update 應無法實例化。"""
        with self.assertRaises(TypeError):
            Observer()  # type: ignore[abstract]


class TestClockLogicScheduledSave(unittest.TestCase):
    """ClockLogic 延遲儲存流程測試。"""

    def _make_logic_stub(self):
        """建立只包含儲存排程狀態的 ClockLogic stub。"""
        from core.clock_logic import ClockLogic

        logic = ClockLogic.__new__(ClockLogic)
        logic.ui = _FakeUiScheduler()
        logic.config_manager = MagicMock()
        logic._save_delay_ms = 250
        logic._save_after_id = None
        logic._pending_config = None
        logic._pending_window_position = None
        return logic

    def test_window_position_save_loads_config_only_when_flushed(self):
        """拖曳排程時不應立即載入 config，flush 時才合併最新設定。"""
        logic = self._make_logic_stub()
        latest_config = {
            'window': {'x': 1, 'y': 2},
            'reminders': [{'message': 'keep'}],
        }
        logic.config_manager.load_config.return_value = latest_config

        logic.schedule_window_position_save(10, 20)
        logic.schedule_window_position_save(30, 40)

        logic.config_manager.load_config.assert_not_called()
        self.assertEqual(logic.ui.cancelled_ids, ['after-1'])
        self.assertEqual(logic.ui.after_calls[-1][0], 250)

        logic._do_save()

        logic.config_manager.load_config.assert_called_once()
        logic.config_manager.save_config.assert_called_once()
        saved_config = logic.config_manager.save_config.call_args[0][0]
        self.assertEqual(saved_config['window']['x'], 30)
        self.assertEqual(saved_config['window']['y'], 40)
        self.assertEqual(saved_config['reminders'], [{'message': 'keep'}])

    def test_flush_pending_save_cancels_callback_and_writes_immediately(self):
        """關閉前沖刷延遲儲存，避免最後一次設定變更遺失。"""
        logic = self._make_logic_stub()
        latest_config = {'window': {'x': 1, 'y': 2}}
        logic.config_manager.load_config.return_value = latest_config

        logic.schedule_window_position_save(30, 40)
        logic.flush_pending_save()

        self.assertEqual(logic.ui.cancelled_ids, ['after-1'])
        logic.config_manager.load_config.assert_called_once()
        logic.config_manager.save_config.assert_called_once_with(latest_config)
        self.assertEqual(latest_config['window'], {'x': 30, 'y': 40})


class TestClockLogicScreenshotDispatch(unittest.TestCase):
    """確保背景鍵盤執行緒只排程 UI 事件，不直接操作觀察者。"""

    def test_screenshot_event_is_dispatched_via_ui_scheduler(self):
        from core.clock_logic import ClockLogic
        from core.events import Events

        logic = ClockLogic.__new__(ClockLogic)
        logic.ui = MagicMock()
        logic.notify_observers = MagicMock()

        logic._on_screenshot_triggered()

        logic.ui.root.after.assert_called_once()
        delay, callback = logic.ui.root.after.call_args.args
        self.assertEqual(delay, 0)
        callback()
        logic.notify_observers.assert_called_once_with(Events.SCREENSHOT_TRIGGERED)


if __name__ == '__main__':
    unittest.main()
