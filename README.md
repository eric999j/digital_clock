# 桌面數位時鐘 (Digital Clock)

![示範](docs/assets/demo.gif)

## 緣起
當應用程式最大化時，自動隱藏的工具列雖然釋放了螢幕空間，卻也讓我們無法隨時看到時間。此專案旨在解決這個問題，提供一個簡潔、不干擾且永遠在最上層的桌面時鐘，並整合番茄鐘、倒數計時、提醒、整點啟動、待辦事項等小工具。

- 環境：Python 3.13+（tkinter）
- 依賴（皆列於 `requirements.txt`）：`pynput`（全域鍵盤監聽）；`tkinterdnd2`（選用，整點啟動視窗拖入 XML 匯入，未安裝時改用按鈕匯入）；`icalendar` + `recurring-ical-events`（Outlook 行事曆 ICS 同步，缺少時停用該功能）；Windows 另需 `tzdata`（多時區）

---

## 啟動

### 跨平台雙擊啟動
啟動檔會自動建立 `.venv`、安裝 `requirements.txt` 並啟動 `main.py`。

| 平台 | 做法 |
|------|------|
| Windows | 雙擊 `start_windows.bat` |
| macOS | 首次執行 `chmod +x start_macos.command`，之後在 Finder 雙擊 |
| Linux | 首次執行 `chmod +x start_linux.sh`，之後在檔案管理器雙擊（詢問時選 Run） |

### 手動執行
```bash
pip install -r requirements.txt
python main.py
```

---

## 文件

- [功能說明](docs/features.md)：完整功能清單與穩定性設計
- [使用手冊](docs/usage.md)：右鍵選單、自訂 BAT 啟動、正式打包
- [架構設計](docs/architecture.md)：分層架構、目錄結構、設計模式、程式碼慣例
- [開發指南](docs/development.md)：測試、CI、授權與第三方套件

---


## 授權

本專案以 [MIT License](LICENSE) 授權。第三方套件授權見 [開發指南](docs/development.md#授權與第三方套件)。
