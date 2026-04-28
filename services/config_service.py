"""設定檔管理器，負責載入、儲存和合併設定。"""
import copy
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """管理應用程式的設定檔，包括載入、儲存和合併。單例模式。"""

    _instance: Optional['ConfigManager'] = None

    def __new__(cls, config_filename: str = "config.json") -> 'ConfigManager':
        """
        單例模式建構子。

        Args:
            config_filename: 設定檔名稱

        Returns:
            ConfigManager 實例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_filename: str = "config.json") -> None:
        """
        初始化設定管理器。

        Args:
            config_filename: 設定檔名稱
        """
        if getattr(self, '_initialized', False):
            return

        self.config_dir = Path.home() / '.digital_clock'
        self.config_file = self.config_dir / config_filename
        self.default_config: dict[str, Any] = {
            "version": "1.0",
            "window": {
                "x": None,  # None 代表自動置中
                "y": 0,
                "width": 200,
                "height": 70,
                "alpha_focused": 1.0,
                "alpha_unfocused": 0.5
            },
            "appearance": {
                "font_family": "Arial",
                "font_size": 56,
                "theme": "blue",
                "time_format": "24h",
                "corner_radius": 30,
                "recommended_fonts": [
                    "Arial", "Consolas", "Courier New", "Microsoft JhengHei",
                    "Microsoft YaHei", "Segoe UI", "Tahoma", "Verdana"
                ],
                "time_formats": {
                    "24h": "%H:%M",
                    "12h": "%I:%M %p"
                },
                "date_formats": {
                    "full": "%Y年%m月%d日 ",
                    "short": "%Y-%m-%d"
                }
            },
            "ui_behavior": {
                "width_calc_text": {
                    "24h": "23:59",
                    "12h": "11:59 下午"
                },
                "width_safety_factor": 1.1,
                "width_padding": 30,
                "min_width": 150,
                "animation": {
                    "duration_ms": 300,
                    "fps": 60,
                    "idle_refresh_ms": 250,
                    "relaxed_idle_refresh_ms": 500,
                    "relax_after_ms": 1500
                },
                "reminder_window_geometry": "400x530",
                "hourly_web_window_geometry": "500x320"
            },
            "system": {
                "save_delay_ms": 1000,
                "hide_duration_ms": 2000,
                "screenshot_keys": ["win", "shift", "s"],
                "performance_monitor": {
                    "enabled": False,
                    "log_interval_sec": 60
                },
                "key_map": {
                    "cmd": "win",
                    "shift": "shift",
                    "print_screen": "print_screen"
                }
            },
            "themes": {
                "green": {"bg": "#C7EDCC", "fg": "#2F4F2F", "name": "護眼綠"},
                "blue": {"bg": "#1E3A5F", "fg": "#A8D8FF", "name": "紳士藍"},
                "dusk": {"bg": "#2C3E50", "fg": "#BDC3C7", "name": "暮色灰"},
                "earth": {"bg": "#FDF2E9", "fg": "#8B4513", "name": "大地棕"},
                "amber": {"bg": "#1C1C1C", "fg": "#FFBF00", "name": "琥珀色"},
                "caramel": {"bg": "#3A1A08", "fg": "#CC9933", "name": "經典焦糖"},
                "walnut": {"bg": "#2D1B10", "fg": "#C4956A", "name": "深邃胡桃"},
                "milk_tea": {"bg": "#6B4226", "fg": "#F5EAD8", "name": "柔和奶茶"}
            },
            "reminders": [],
            "hourly_web_reminder": {
                "enabled": False,
                "url": "",
                "start_hour": 8,
                "end_hour": 17,
                "work_days_only": True  # 是否僅在上班日（週一至週五）觸發
            },
            "pomodoro": {
                "focus_minutes": 25,
                "short_break": 5,
                "long_break": 15,
                "cycles_before_long_break": 4
            }
        }
        self._config_cache: dict[str, Any] | None = None
        self._cache_mtime_ns: int | None = None
        self._initialized = True

    def _get_default_config_copy(self) -> dict[str, Any]:
        """回傳預設設定的深拷貝，避免共享可變巢狀物件。"""
        return copy.deepcopy(self.default_config)

    def _get_file_mtime_ns(self) -> int | None:
        """取得設定檔 mtime (ns)，若無法取得則回傳 None。"""
        try:
            return self.config_file.stat().st_mtime_ns
        except OSError:
            return None

    def save_config(self, config: dict[str, Any]) -> None:
        """
        儲存設定到檔案。

        Args:
            config: 設定字典
        """
        try:
            # 確保目錄存在
            self.config_dir.mkdir(parents=True, exist_ok=True)

            config_to_save = copy.deepcopy(config)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)

            # 寫入成功後同步更新快取，避免下一次 load 立即重讀檔案
            self._config_cache = config_to_save
            self._cache_mtime_ns = self._get_file_mtime_ns()
        except (OSError, TypeError, ValueError) as e:
            logger.error("Error saving config: %s", e)

    def load_config(self, read_only: bool = False) -> dict[str, Any]:
        """
        載入設定檔，若檔案不存在或損毀，則使用預設值。

        Args:
            read_only: True 時回傳「快取參考」（不做最終 deepcopy），呼叫端
                必須保證不會就地修改回傳的 dict；用於每秒主迴圈等熱路徑以
                降低重複 deepcopy 開銷。預設 False 仍回傳獨立深拷貝。

        Returns:
            設定字典
        """
        if not self.config_file.exists():
            # 檔案不存在時回傳預設值，並建立記憶體快取
            if self._config_cache is None or self._cache_mtime_ns is not None:
                self._config_cache = self._get_default_config_copy()
                self._cache_mtime_ns = None
            return self._config_cache if read_only else copy.deepcopy(self._config_cache)

        current_mtime = self._get_file_mtime_ns()
        if (
            self._config_cache is not None
            and current_mtime is not None
            and self._cache_mtime_ns == current_mtime
        ):
            # 檔案未改變，直接回傳快取（依 read_only 決定是否 deepcopy）
            return self._config_cache if read_only else copy.deepcopy(self._config_cache)

        try:
            with open(self.config_file, encoding='utf-8') as f:
                user_config = json.load(f)
            merged = self._merge_config(user_config)
            self._config_cache = merged
            self._cache_mtime_ns = current_mtime
            return merged if read_only else copy.deepcopy(merged)
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.error("Error loading config: %s. Using default config.", e)
            default_config = self._get_default_config_copy()
            self._config_cache = default_config
            self._cache_mtime_ns = None
            return default_config if read_only else copy.deepcopy(default_config)

    def _merge_config(self, user_config: dict[str, Any]) -> dict[str, Any]:
        """
        遞迴合併使用者設定與預設值，確保所有鍵都存在。

        Args:
            user_config: 使用者設定

        Returns:
            合併後的設定
        """
        if not isinstance(user_config, dict):
            logger.warning("Config file root is not a JSON object. Falling back to defaults.")
            return self._get_default_config_copy()

        def merge(default: Any, user: Any) -> Any:
            if isinstance(default, dict) and isinstance(user, dict):
                merged: dict[str, Any] = {}
                for key, default_value in default.items():
                    if key in user:
                        merged[key] = merge(default_value, user[key])
                    else:
                        merged[key] = copy.deepcopy(default_value)
                for key, user_value in user.items():
                    if key not in default:
                        merged[key] = copy.deepcopy(user_value)
                return merged
            if user is None:
                return copy.deepcopy(default)
            return copy.deepcopy(user)

        return merge(self.default_config, user_config)
