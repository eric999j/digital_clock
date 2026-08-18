# Agent Instructions — Digital Clock

## 快速指令

```bash
# 啟動應用程式
python main.py

# 執行全部測試
python -m unittest discover -s tests

# 安裝唯一外部依賴
pip install pynput
```

## 專案概覽

桌面數位時鐘（tkinter），支援番茄鐘、提醒、整點網頁開啟、截圖自動隱藏等功能。
Python 3.13 + `pynput`，無其他外部依賴。

## 架構

分層設計，所有 UI ↔ 業務邏輯透過 **Observer pattern** 解耦：

| 層 | 目錄 | 說明 |
|---|---|---|
| Entry | `main.py` | 建立 DI Container → `DigitalClock.run()` |
| UI | `ui/` | tkinter 視窗，實作 `Observer`。**所有 UI 操作必須在主線程** |
| Core | `core/` | `ClockLogic`（Mediator）、`Observer`（ABC）、`Events`（常數）、`ServiceContainer`（DI） |
| Services | `services/` | 各功能引擎，透過 `notify_callback` 與 `ClockLogic` 通訊 |
| Strategies | `strategies/` | `BaseStrategy`（ABC）→ 可替換演算法（提醒、整點網頁、番茄鐘） |

詳細架構圖見 [README.md](README.md)。

## 關鍵慣例

- **絕對 import**：`from services.config_service import ConfigManager`
- **命名**：snake_case 方法/變數、PascalCase 類別、UPPER_CASE 常數
- **Type hints**：所有方法簽名與回傳值必須標註
- **Docstring**：Google-style（繁體中文）
- **事件名稱**：必須使用 `core/events.py` 的 `Events` 常數，禁止 magic string
- **私有方法**：單底線 `_method_name`
- **日誌**：`logging.getLogger(__name__)`，不用 print

## 設計模式注意事項

| 模式 | 檔案 | 注意 |
|---|---|---|
| Singleton | `services/config_service.py` | 測試中須重設 `ConfigManager._instance = None` |
| Observer | `core/observer.py` | UI 實作 `update(event, *args, **kwargs)` |
| Strategy | `strategies/base.py` | 新策略必須繼承 `BaseStrategy` 並實作 `check()` |
| DI Container | `core/container.py` | name-based `register`/`get` |

### Strategy 回傳型別規範

| Strategy | `check()` 回傳 | 說明 |
|---|---|---|
| `ReminderStrategy` | `tuple[list[dict], str]` | `(triggered, updated_minute_key)`；去重狀態由 `ReminderService._last_weekly_minute_key` 持有 |
| `HourlyWebReminderStrategy` | `str \| None` | 要開啟的 URL，或 None；支援 `url_rules` 時段路由 |
| `PomodoroStrategy` | `str` | 下一個階段名稱 |
| `VacationScheduleStrategy` | `dict` | 含 `active/expired/future/invalid` 分類 |

## 測試

- 框架：**unittest**（標準庫）
- 執行：`python -m unittest discover -s tests`
- ConfigManager 測試需先 `ConfigManager._instance = None` 重設 Singleton
- Strategy 有狀態（如 `last_triggered_hour`），測試間需確保隔離
- 設定檔路徑 `~/.digital_clock/config.json`，測試時 mock `Path.home()`
- Strategy mock 回傳值須符合型別：`ReminderStrategy` → `([], "")` tuple；`HourlyWebReminderStrategy` → `None`（非 `False`）

## 關鍵模組補充

| 模組 | 說明 |
|---|---|
| `services/pause_manager.py` | 統一管理 reminder/hourly_web/vacation 暫停狀態，勿在 service 直接讀寫 paused 欄位。**`toggle_vacation()` 不再接收 pomodoro_stop 參數**——須先呼叫 `set_pomodoro_stop(callback)` 注入 |
| `services/reminder_service.py` | 持有 `_last_weekly_minute_key`（週期提醒去重狀態）；呼叫 Strategy 時傳入並接收 tuple |
| `services/pomodoro_service.py` | `__init__` 接收 `Callable[[], dict]` getter，每次 `start_focus/break` 才讀取最新設定 |
| `ui/popup_utils.py` | 提供非阻塞提醒彈窗，**支援 Markdown 行內語法渲染**（粗體、斜體、code、連結、URL）。**禁止直接使用 `tkinter.messagebox`**——所有確認、錯誤、通知彈窗均須呼叫此模組函數，確保主題配色一致 |
| `ui/menus/` | `context_menu.py`、`reminder_menu.py`、`vacation_menu.py`，右鍵選單子元件 |

### 整點網頁 Config 結構

```json
"hourly_web_reminder": {
  "url_rules": [{"url": "https://...", "start_hour": 9, "end_hour": 12}],
  "paused": false,
  "work_days_only": true,
  "url": "",        // 舊版相容欄位，Strategy 在 url_rules 為空時使用
  "start_hour": 8,
  "end_hour": 17
}
```

- 新增規則：加入 `url_rules` 清單；`update_config(url_rules)` 同時更新舊版欄位保持相容。
- Strategy 優先用 `url_rules`，逐條比對 `start_hour ≤ now.hour ≤ end_hour`，回傳第一個命中的 URL。

## 常見陷阱

- **循環引用**：`ClockLogic` ↔ `DigitalClock` 互相引用，新模組引用 UI 時須使用 `TYPE_CHECKING` guard
- **tkinter 線程安全**：背景線程不可直接操作 UI，用 `root.after()` 排程
- **Windows 專用程式碼**：`ctypes.windll` 在非 Windows 會失敗，需 platform check
- **schedule_save() 時序**：`schedule_save()` 僅延遲磁碟寫入，記憶體狀態立即生效。開子視窗或更新選單時必須從記憶體讀取，**絕不可**再呼叫 `get_config()` 從磁碟快取——否則會拿到未儲存的舊值（主題、提醒清單等）
- **ttk 樣式命名**：`ttk.LabelFrame` 對應樣式 key 為 `TLabelframe`（小寫 `f`），誤用 `TLabelFrame` 會導致 layout 找不到
- **暫停狀態**：所有暫停/休假判斷必須透過 `PauseManager`，不可直接讀取 config 欄位
- **tkinter pack 順序**：視窗底部元件（按鈕列）必須**先** `pack(side=BOTTOM)`，再 pack 可展開的中間區塊（`expand=True`），否則按鈕會被推出可視範圍
