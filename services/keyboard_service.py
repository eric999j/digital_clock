"""鍵盤監聽服務。"""
from collections.abc import Callable
from typing import Any

from pynput import keyboard
from pynput.keyboard import Key

from services.config_service import ConfigManager


class KeyboardService:
    """處理全球鍵盤事件監聽。"""

    def __init__(self, config_manager: ConfigManager,
                 on_screenshot_callback: Callable[[], None]):
        """
        初始化鍵盤服務。

        Args:
            config_manager: 設定管理器
            on_screenshot_callback: 當截圖快捷鍵觸發時的回調
        """
        self.config_manager = config_manager
        self.on_screenshot = on_screenshot_callback
        self.pressed_keys: set[str] = set()
        self.KEY_MAP: dict[Any, str] = {}
        self.WIN_SCREENSHOT_KEYS: set[str] = set()
        self.listener: keyboard.Listener | None = None

        self._load_config()

    def _load_config(self) -> None:
        """載入鍵盤相關設定。"""
        config = self.config_manager.load_config()
        sys_conf = config['system']
        self.WIN_SCREENSHOT_KEYS = set(sys_conf['screenshot_keys'])

        # 建立鍵盤映射
        self.KEY_MAP = {}
        for key_attr, key_name in sys_conf.get('key_map', {}).items():
            if hasattr(Key, key_attr):
                self.KEY_MAP[getattr(Key, key_attr)] = key_name

    def start(self) -> None:
        """啟動鍵盤監聽。"""
        if self.listener is None:
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_key_release
            )
            self.listener.start()

    def stop(self) -> None:
        """停止鍵盤監聽。"""
        if self.listener:
            self.listener.stop()
            self.listener = None

    def _on_press(self, key: Any) -> None:
        """處理按鍵按下事件。"""
        try:
            key_name = self.KEY_MAP.get(key, getattr(key, 'char', None))
            if key_name:
                self.pressed_keys.add(key_name)
                self._check_key_combination()
        except AttributeError:
            pass

    def _on_key_release(self, key: Any) -> None:
        """處理按鍵釋放事件。"""
        key_name = self.KEY_MAP.get(key, getattr(key, 'char', None))
        if key_name:
            self.pressed_keys.discard(key_name)

    def _check_key_combination(self) -> None:
        """檢查是否觸發組合鍵。"""
        # 截圖組合鍵 (Win+Shift+S)
        if self.WIN_SCREENSHOT_KEYS.issubset(self.pressed_keys):
            self.on_screenshot()
