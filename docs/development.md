# 開發指南

```bash
python -m unittest discover -s tests      # 執行全部測試
pip install -e ".[dev]"                   # 安裝 ruff、coverage
python -m ruff check .
```

- CI（`.github/workflows/ci.yml`）：ruff 檢查，以及 Ubuntu（xvfb）、Windows、macOS 上的 unittest + coverage。
- 非 Windows 平台不支援 `-transparentcolor` 等 Windows 視窗屬性，程式會略過或回退；少數測試依賴 Windows 行為（如 `shutdown.exe`），在其他平台自動略過。
- `pynput` 後端可能被 macOS 輔助使用權限、Linux Wayland/沙箱或無顯示器環境阻擋。啟動失敗時只停用全域截圖快捷鍵，不影響時鐘、提醒與其他功能。
- 測試使用標準庫 `unittest`；涉及 `ConfigManager` 時應 mock `Path.home()`，避免讀寫使用者設定。
- 部分 UI 測試需要可用的顯示器，無顯示器時會自動略過。
- 更多開發約定見 [AGENTS.md](../AGENTS.md)。

## 目前架構邊界

### UI 層

- `ui/main_window.py`：Tkinter 組裝 façade、Observer 事件入口、主要互動與設定命令。
- `ui/clock_renderer.py`：Canvas 時鐘文字、動畫、字元快取與圓角背景。
- `ui/info_band_presenter.py`：番茄鐘、倒數、待辦、多時區資訊列的組合與繪製。
- `ui/window_controller.py`：功能視窗建立與單例帶回。
- `ui/event_router.py`：事件名稱至 `DigitalClock` handler 的集中映射。

### Core 與 Service 層

- `ClockLogic` 為 Composition Root / Mediator，建立 Service 並統一關閉生命週期。
- `typed_events.py` 提供型別化事件封包；既有 Observer 呼叫仍相容。
- `ConfigStore` 提供 `ConfigSnapshot`、`WindowConfig`、`AppearanceConfig`。
- `ConfigManager` 保存記憶體快取與檔案版本；所有設定儲存進入 `ConfigWriter` 的單一背景佇列。
- `pomodoro_service.py` 使用 `PomodoroStrategy` 決定下一階段，避免測試與執行規則分離。

### 修改慣例

- UI 繪圖邏輯優先放在 Presenter/Renderer，不再持續增加 `DigitalClock` 的畫布細節。
- 新 Service 以 callback 發事件，不直接操作 Tk。
- 事件名稱仍集中於 `Events`；新 payload 可使用 `TypedEvent`。
- 設定寫入使用 `persist_config()` 或 `ClockLogic.schedule_save()`，不要建立另一條直接背景寫入路徑。
- Thread 產生的結果必須透過 `root.after()` 回到 Tk 主執行緒。

## 設定與資料檔版本

- `config.json`：整數 `schema_version`（目前為 1）。載入時缺欄位視為 0，依 `services/config_service.py` 的 `_MIGRATIONS` 逐版升級；舊 `version: "1.0"` 欄位保留相容。檔案版本高於程式支援時只記錄警告，不降級。
- 設定記憶體快取由 `RLock` 保護；UI 延遲儲存與 Service 即時儲存共用同一個 `ConfigWriter`，避免 temp file 與完整快照互相競爭。
- `todos.json`：`version`（目前為 1）。檔案版本高於程式支援時，載入顯示提示且拒絕覆寫，避免降級後遺失資料。
- 設定結構有不相容變更時：遞增 `CONFIG_SCHEMA_VERSION`，並新增對應的 migration 函式與測試。

## 授權與第三方套件

本專案原始碼（`core/`、`services/`、`strategies/`、`ui/`、`tests/`、`main.py`）一律以 [MIT License](../LICENSE) 授權。執行時相依的第三方套件各自遵循自己的授權，未隨原始碼散佈，也不改變本專案的授權：

| 套件 | 授權 |
|------|------|
| `pynput` | LGPL-3.0 |
| `recurring-ical-events`、`x-wr-timezone`（間接相依） | LGPL-3.0-or-later |
| `icalendar` | BSD-2-Clause |
| `tkinterdnd2` | MIT |
| `tzdata` | Apache-2.0 |
| `python-dateutil`、`tzlocal`、`six`（間接相依） | BSD / Apache-2.0、MIT、MIT |

- 以 `pip` 安裝、由使用者自行取得這些套件時，MIT 與 LGPL 相容，無需額外處理。
- **散佈 PyInstaller 打包的執行檔時**，會一併包含上述 LGPL 套件，須隨附各套件的授權文字，並讓使用者可取得該套件原始碼且能替換其版本（本專案以 onefile 打包，若要分發請特別注意）。
