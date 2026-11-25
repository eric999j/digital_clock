# 桌面數位時鐘 (Digital Clock)

![示範](docs/assets/demo.gif)

## 緣起
當應用程式最大化時，自動隱藏的工具列雖然釋放了螢幕空間，卻也讓我們無法隨時看到時間。此專案旨在解決這個問題，提供一個簡潔、不干擾且永遠在最上層的桌面時鐘，並整合番茄鐘、倒數計時、提醒、整點啟動、待辦事項、通知中心與行事曆勿擾等小工具。

- 環境：Python 3.13+（tkinter）
- 依賴（皆列於 `requirements.txt`）：`pynput`（全域鍵盤監聽）；`tkinterdnd2`（選用，整點啟動視窗拖入 XML 匯入，未安裝時改用按鈕匯入）；`icalendar` + `recurring-ical-events`（Outlook 行事曆 ICS 同步，缺少時停用該功能）；Windows 另需 `tzdata`（多時區）
- 架構：Tkinter UI、Observer/Mediator、Service、Strategy、Command；設定透過 `ConfigStore` 提供型別化快照，磁碟寫入由單一背景 writer 排程。

## 架構重點

- `main.py` 僅負責日誌、DPI、設定管理器與應用程式組裝。
- `ClockLogic` 是 Mediator 與 Composition Root，協調服務並透過事件通知 UI。
- `DigitalClock` 是 Tkinter façade；Canvas 渲染與資訊列分別由 `ClockRenderer`、`InfoBandPresenter` 處理。
- `strategies/` 提供可替換的時間與階段判斷；`PomodoroService` 已實際使用 `PomodoroStrategy`。
- 設定寫入統一排入背景佇列，Service 與 UI 不再各自對同一個 JSON 競爭寫入；關閉時會同步 flush。
- 重要事件支援型別化封包，同時保留既有 `event, *args, **kwargs` Observer 相容介面。

---

## 啟動

### 跨平台雙擊啟動
啟動檔會自動建立 `.venv`、安裝 `requirements.txt` 並啟動 `main.py`。

| 平台 | 做法 |
|------|------|
| Windows | 雙擊 `start_windows.bat` |
| macOS | 雙擊 `start_macos.command`（需要 Python 3.13+；若系統移除執行權限則先執行 `chmod +x start_macos.command`） |
| Linux | 執行 `./start_linux.sh` 或在檔案管理器以「執行」開啟（需要 Python 3.13+ 與 Tkinter） |

macOS 上若要使用「截圖時自動隱藏」，第一次啟動後須在「系統設定 › 隱私權與安全性 › 輔助使用」授權 Python；未授權時其餘功能仍可正常使用。Linux Wayland 或沙箱化桌面若限制全域鍵盤事件，也只會停用截圖快捷鍵，不影響主程式。

### 手動執行
```bash
pip install -r requirements.txt
python main.py
```

---

## 文件

- [功能說明](docs/features.md)：完整功能清單與穩定性設計
- [使用手冊](docs/usage.md)：右鍵選單、自訂 BAT 啟動、正式打包
- [架構設計](docs/architecture.md)：分層架構、生命週期、資料流、目錄結構與設計模式
- [開發指南](docs/development.md)：測試、CI、授權與第三方套件

---


## 授權

本專案以 [MIT License](LICENSE) 授權。第三方套件授權見 [開發指南](docs/development.md#授權與第三方套件)。
