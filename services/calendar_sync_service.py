"""行事曆同步服務：讀取 Outlook 發佈的 ICS，事件進行時自動進入／離開休假模式。"""
import logging
import threading
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.events import Events
from core.url_validator import is_safe_url
from services.config_service import ConfigManager
from services.pause_manager import PauseManager
from strategies.calendar_strategy import CalendarVacationStrategy

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_SECONDS = 20
_MAX_ICS_BYTES = 5 * 1024 * 1024
_LOOKBACK = timedelta(days=1)
_LOOKAHEAD = timedelta(days=7)
_IDLE_WAIT_SECONDS = 60
_VACATION_SOURCE = 'calendar'


def normalize_ics_url(url: str) -> str:
    """去除空白，並把 `webcal://` 轉為 `https://`。"""
    cleaned = (url or "").strip()
    if cleaned.lower().startswith("webcal://"):
        cleaned = "https://" + cleaned[len("webcal://"):]
    return cleaned


def is_valid_ics_url(url: str) -> bool:
    """ICS 連線含密鑰，僅接受 https。"""
    return is_safe_url(url) and urlparse(url).scheme.lower() == "https"


def _to_local_naive(value: date | datetime) -> datetime:
    """將 ICS 的日期／時間轉成本地無時區 datetime（全天事件取當日 00:00）。"""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone().replace(tzinfo=None)
    return datetime.combine(value, time.min)


class CalendarSyncService:
    """週期性抓取 ICS 並依事件時間自動切換休假模式。

    - 背景執行緒只負責下載與解析，結果存入記憶體快取；不碰 UI、不發通知。
    - `check()` 於主執行緒每個 tick 呼叫，負責切換休假與發出通知。
    - 只接管來源為 `calendar` 的休假，不影響手動或排程休假。
    - 抓取失敗時沿用上次快取，不改變休假狀態。
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        notify_callback: Callable[[str, Any], None],
        pause_manager: PauseManager,
    ) -> None:
        """
        初始化行事曆同步服務。

        Args:
            config_manager: 設定管理器
            notify_callback: 通知回調函數 (event, *args)
            pause_manager: 暫停管理器，用來查詢/切換休假狀態
        """
        self.config_manager = config_manager
        self.notify = notify_callback
        self.pause_manager = pause_manager
        self.strategy = CalendarVacationStrategy()

        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] | None = None
        self._url = ""
        self._refresh_seconds = 15 * 60
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

        # 主執行緒狀態
        self._entered_key: str | None = None
        self._notified_upcoming_key: str | None = None

    # --- 設定 ---

    def get_settings(self) -> dict[str, Any]:
        """回傳目前行事曆同步設定的拷貝。"""
        cfg = self.config_manager.load_config(read_only=True).get('calendar_sync', {})
        return {
            'enabled': bool(cfg.get('enabled', False)),
            'ics_url': str(cfg.get('ics_url', '') or ''),
            'refresh_minutes': self._clamp(cfg.get('refresh_minutes'), 15, 1, 1440),
            'lead_minutes': self._clamp(cfg.get('lead_minutes'), 10, 0, 120),
        }

    def update_settings(
        self,
        enabled: bool,
        ics_url: str,
        refresh_minutes: int,
        lead_minutes: int,
    ) -> None:
        """
        儲存設定並立即重新同步。

        Raises:
            ValueError: 啟用時 URL 不是有效的 https 連結。
        """
        url = normalize_ics_url(ics_url)
        if enabled and not is_valid_ics_url(url):
            raise ValueError("ICS 連結必須是有效的 https 網址")

        config = self.config_manager.load_config()
        config['calendar_sync'] = {
            'enabled': bool(enabled),
            'ics_url': url,
            'refresh_minutes': self._clamp(refresh_minutes, 15, 1, 1440),
            'lead_minutes': self._clamp(lead_minutes, 10, 0, 120),
        }
        self.config_manager.save_config(config)
        with self._lock:
            self._events = None
        self._apply_settings()
        self._wake.set()

    @staticmethod
    def _clamp(value: Any, default: int, low: int, high: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))

    def _apply_settings(self) -> None:
        """把設定同步給背景執行緒使用（停用或無效 URL 時 URL 清空）。"""
        settings = self.get_settings()
        url = normalize_ics_url(settings['ics_url'])
        if not settings['enabled'] or not is_valid_ics_url(url):
            url = ""
        with self._lock:
            self._url = url
            self._refresh_seconds = settings['refresh_minutes'] * 60

    # --- 背景同步 ---

    def start(self) -> None:
        """啟動背景同步執行緒（重複呼叫無效）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._apply_settings()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="calendar-sync", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """停止背景同步執行緒。"""
        self._stop.set()
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                url = self._url
                wait_seconds = self._refresh_seconds
            if url:
                self._sync(url)
            self._wake.wait(timeout=wait_seconds if url else _IDLE_WAIT_SECONDS)
            self._wake.clear()

    def _sync(self, url: str) -> None:
        """抓取並解析一次；失敗時保留舊快取。日誌不含完整 URL（含密鑰）。"""
        host = urlparse(url).hostname or "?"
        try:
            events = self.fetch_events(url)
        except Exception as e:
            logger.warning("Calendar sync failed (host=%s): %s", host, type(e).__name__)
            return
        with self._lock:
            if url == self._url:
                self._events = events
        logger.info("Calendar synced (host=%s): %d events", host, len(events))

    def fetch_events(self, url: str, now: datetime | None = None) -> list[dict[str, Any]]:
        """
        下載 ICS 並展開近期事件（含週期性事件）。

        Args:
            url: https ICS 連結
            now: 可選的基準時間（本地 naive），預設為目前時間

        Returns:
            事件清單，每筆含 `start`/`end`（本地 naive datetime）與 `summary`。

        Raises:
            ValueError: URL 無效或內容過大。
            ImportError: 未安裝 icalendar / recurring-ical-events。
        """
        url = normalize_ics_url(url)
        if not is_valid_ics_url(url):
            raise ValueError("ICS 連結必須是有效的 https 網址")
        request = Request(url, headers={"User-Agent": "DigitalClock/1.0"})
        with urlopen(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310 - 已限定 https
            data = response.read(_MAX_ICS_BYTES + 1)
        if len(data) > _MAX_ICS_BYTES:
            raise ValueError("ICS 內容過大")
        return self.parse_events(data, now)

    @staticmethod
    def parse_events(data: bytes | str, now: datetime | None = None) -> list[dict[str, Any]]:
        """解析 ICS 內容為事件清單（略過已取消的事件）。"""
        import icalendar
        import recurring_ical_events

        base = (now or datetime.now()).astimezone()
        calendar = icalendar.Calendar.from_ical(data)
        components = recurring_ical_events.of(calendar).between(
            base - _LOOKBACK, base + _LOOKAHEAD
        )

        events: list[dict[str, Any]] = []
        for component in components:
            if str(component.get('STATUS', '')).upper() == 'CANCELLED':
                continue
            start = component.start
            end = component.end
            if start is None or end is None:
                continue
            events.append({
                'start': _to_local_naive(start),
                'end': _to_local_naive(end),
                'summary': str(component.get('SUMMARY', '') or ''),
            })
        return events

    def test_connection(self, url: str) -> int:
        """測試連線，回傳解析到的事件數；失敗時拋出例外。"""
        return len(self.fetch_events(url))

    # --- 主執行緒檢查 ---

    def check(self, now: datetime | None = None) -> None:
        """依快取事件切換休假模式並發出通知（僅限主執行緒呼叫）。"""
        current_time = now or datetime.now()
        # 每次重新讀取：同一 tick 前面的服務可能已改變休假狀態
        config = self.config_manager.load_config(read_only=True)
        settings = self.get_settings()
        on_vacation = self.pause_manager.get_pause_state('vacation', config=config)
        owns_vacation = (
            on_vacation
            and self.pause_manager.get_vacation_source(config=config) == _VACATION_SOURCE
        )

        if not settings['enabled']:
            self._entered_key = None
            if owns_vacation:
                self._exit_vacation()
            return

        with self._lock:
            events = None if self._events is None else list(self._events)
        if events is None:
            return

        result = self.strategy.check(events, current_time, settings['lead_minutes'])
        current = result['current']

        if current is not None:
            key = current['start'].isoformat()
            if not on_vacation and key != self._entered_key:
                self._entered_key = key
                self.pause_manager.toggle_vacation(source=_VACATION_SOURCE)
                self.notify(Events.CALENDAR_EVENT_STARTED, current['summary'])
            return

        self._entered_key = None
        if owns_vacation:
            self._exit_vacation()
            return

        upcoming = result['upcoming']
        if upcoming is not None and not on_vacation:
            key = upcoming['start'].isoformat()
            if key != self._notified_upcoming_key:
                self._notified_upcoming_key = key
                minutes = max(1, int((upcoming['start'] - current_time).total_seconds() // 60))
                self.notify(Events.CALENDAR_EVENT_UPCOMING, upcoming['summary'], minutes)

    def _exit_vacation(self) -> None:
        self.pause_manager.toggle_vacation(source=_VACATION_SOURCE)
        self.notify(Events.CALENDAR_EVENT_ENDED)
