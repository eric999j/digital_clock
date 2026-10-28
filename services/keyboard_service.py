"""鍵盤監聽服務。"""
from collections.abc import Callable
from typing import Any

from pynput import keyboard
from pynput.keyboard import Key

from services.config_service import ConfigManager

# 同一個修飾鍵的左右版本要視為同一個名稱
_KEY_FAMILIES: tuple[tuple[str, ...], ...] = (
    ('cmd', 'cmd_l', 'cmd_r'),
    ('shift', 'shift_l', 'shift_r'),
)


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
        self.SINGLE_SCREENSHOT_KEYS: set[str] = set()
        self.listener: keyboard.Listener | None = None
        self._combination_triggered = False

        self._load_config()

    def _load_config(self) -> None:
        """載入鍵盤相關設定。"""
        config = self.config_manager.load_config()
        sys_conf = config['system']
        self.WIN_SCREENSHOT_KEYS = set(sys_conf['screenshot_keys'])
        self.SINGLE_SCREENSHOT_KEYS = set(sys_conf.get('screenshot_single_keys', ['print_screen']))

        # 建立鍵盤映射
        self.KEY_MAP = {}
        configured: dict[str, str] = {}
        for key_attr, key_name in sys_conf.get('key_map', {}).items():
            if hasattr(Key, key_attr):
                self.KEY_MAP[getattr(Key, key_attr)] = key_name
                configured[key_attr] = key_name

        # 設定只寫左邊（或通用）修飾鍵時，右邊的同名鍵也要能觸發
        for family in _KEY_FAMILIES:
            name = next((configured[attr] for attr in family if attr in configured), None)
            if name:
                for attr in family:
                    if hasattr(Key, attr):
                        self.KEY_MAP.setdefault(getattr(Key, attr), name)

        # 單鍵觸發的按鍵（如 print_screen）未明確映射時，直接以按鍵名稱映射
        for attr in self.SINGLE_SCREENSHOT_KEYS:
            if hasattr(Key, attr):
                self.KEY_MAP.setdefault(getattr(Key, attr), attr)

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
            key_name = self._key_name(key)
            if key_name:
                is_new = key_name not in self.pressed_keys
                self.pressed_keys.add(key_name)
                # 單鍵觸發（如 PrtScn）只在首次按下時觸發，長按的自動重複不再觸發
                if is_new and key_name in self.SINGLE_SCREENSHOT_KEYS:
                    self.on_screenshot()
                self._check_key_combination()
        except AttributeError:
            pass

    def _on_key_release(self, key: Any) -> None:
        """處理按鍵釋放事件。"""
        key_name = self._key_name(key)
        if key_name:
            self.pressed_keys.discard(key_name)
            if not self.WIN_SCREENSHOT_KEYS.issubset(self.pressed_keys):
                self._combination_triggered = False

    def _key_name(self, key: Any) -> str | None:
        """取得按鍵名稱；字元鍵統一為小寫（按住 Shift 時 pynput 會回報大寫）。"""
        name = self.KEY_MAP.get(key)
        if name:
            return name
        char = getattr(key, 'char', None)
        return char.lower() if isinstance(char, str) else char

    def _check_key_combination(self) -> None:
        """檢查是否觸發組合鍵。"""
        # 截圖組合鍵 (Win+Shift+S)
        is_pressed = self.WIN_SCREENSHOT_KEYS.issubset(self.pressed_keys)
        if is_pressed and not self._combination_triggered:
            self.on_screenshot()
            self._combination_triggered = True
        elif not is_pressed:
            self._combination_triggered = False
