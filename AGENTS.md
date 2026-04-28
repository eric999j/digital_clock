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

## 測試

- 框架：**unittest**（標準庫）
- 執行：`python -m unittest discover -s tests`
- ConfigManager 測試需先 `ConfigManager._instance = None` 重設 Singleton
- Strategy 有狀態（如 `last_triggered_hour`），測試間需確保隔離
- 設定檔路徑 `~/.digital_clock/config.json`，測試時 mock `Path.home()`

## 常見陷阱

- **循環引用**：`ClockLogic` ↔ `DigitalClock` 互相引用，新模組引用 UI 時須使用 `TYPE_CHECKING` guard
- **tkinter 線程安全**：背景線程不可直接操作 UI，用 `root.after()` 排程
- **Windows 專用程式碼**：`ctypes.windll` 在非 Windows 會失敗，需 platform check
- **設定檔寫入**：使用 `schedule_save()` 延遲儲存，避免頻繁 IO
