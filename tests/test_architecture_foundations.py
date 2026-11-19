"""架構基礎元件測試：型別事件、設定快照與背景寫入。"""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.events import Events
from core.typed_events import as_typed_event
from services.config_service import ConfigManager
from services.config_store import ConfigStore
from services.config_writer import ConfigWriter


class TestTypedEvents(unittest.TestCase):
    """型別事件保留 legacy 呼叫形式並驗證 payload。"""

    def test_event_legacy_shape_is_stable(self) -> None:
        event = as_typed_event(Events.POMODORO_TICK, "FOCUS", 30)

        self.assertEqual(
            event.legacy(),
            (Events.POMODORO_TICK, ("FOCUS", 30), {}),
        )

    def test_known_event_rejects_invalid_payload_length(self) -> None:
        with self.assertRaises(ValueError):
            as_typed_event(Events.POMODORO_TICK, "FOCUS")

    def test_known_event_accepts_legacy_keyword_payload(self) -> None:
        event = as_typed_event(
            Events.POMODORO_TICK,
            phase="FOCUS",
            remaining_seconds=30,
        )

        self.assertEqual(
            event.legacy(),
            (
                Events.POMODORO_TICK,
                (),
                {'phase': 'FOCUS', 'remaining_seconds': 30},
            ),
        )


class TestConfigStore(unittest.TestCase):
    """ConfigStore 提供獨立快照與型別化外觀欄位。"""

    def setUp(self) -> None:
        self.manager = MagicMock()
        self.manager.load_config.return_value = {
            'window': {
                'x': 12,
                'y': 34,
                'width': 200,
                'height': 70,
                'alpha_focused': 1.0,
                'alpha_unfocused': 0.5,
            },
            'appearance': {
                'font_family': 'Arial',
                'font_size': 56,
                'theme': 'blue',
                'time_format': '24h',
                'date_format': 'full',
                'corner_radius': 30,
            },
        }
        self.store = ConfigStore(self.manager)

    def test_snapshot_exposes_typed_common_sections(self) -> None:
        snapshot = self.store.snapshot()

        self.assertEqual(snapshot.window.width, 200)
        self.assertEqual(snapshot.appearance.font_size, 56)

    def test_mutable_copy_does_not_share_nested_values(self) -> None:
        first = self.store.mutable()
        second = self.store.mutable()
        first['appearance']['font_size'] = 10

        self.assertEqual(second['appearance']['font_size'], 56)


class TestConfigWriter(unittest.TestCase):
    """背景 writer 在不同執行緒寫入且 flush 等待完成。"""

    def test_submit_writes_snapshot_on_worker(self) -> None:
        manager = MagicMock()
        thread_ids: list[int] = []

        def save(config: dict) -> None:
            thread_ids.append(threading.get_ident())

        manager.save_config.side_effect = save
        writer = ConfigWriter(manager)
        writer.submit({'window': {'x': 99}, 'service': 1})
        self.assertTrue(writer.flush(timeout=2))
        writer.close()

        self.assertNotEqual(thread_ids, [threading.get_ident()])
        saved = manager.save_config.call_args.args[0]
        self.assertEqual(saved['window']['x'], 99)
        self.assertEqual(saved['service'], 1)

    def test_real_manager_flush_persists_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            Path,
            "home",
            return_value=Path(temp_dir),
        ):
            manager = ConfigManager()
            writer = ConfigWriter(manager)
            config = manager.load_config()
            config['window']['x'] = 123
            writer.submit(config)
            writer.close()

            self.assertEqual(manager.load_config()['window']['x'], 123)

    def test_manager_serializes_app_and_service_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            Path,
            "home",
            return_value=Path(temp_dir),
        ):
            manager = ConfigManager()
            first = manager.load_config()
            first['window']['x'] = 1
            manager.schedule_config_save(first)
            second = manager.load_config()
            second['window']['x'] = 2
            second['appearance']['theme'] = 'green'
            manager.schedule_config_save(second)
            manager.close_config_writer()

            persisted = ConfigManager().load_config()
            self.assertEqual(persisted['window']['x'], 2)
            self.assertEqual(persisted['appearance']['theme'], 'green')


if __name__ == '__main__':
    unittest.main()
