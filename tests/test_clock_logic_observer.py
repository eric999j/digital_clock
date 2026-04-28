"""ClockLogic Observer 派發例外隔離測試。"""
import unittest

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


if __name__ == '__main__':
    unittest.main()
