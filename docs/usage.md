# 使用手冊

## 右鍵選單

```
勿擾模式 ›  立即開始勿擾 / 新增勿擾排程… / 行事曆同步設定… / 既有排程
提醒 ›      新增提醒… / 暫停 / 既有提醒（編輯、刪除）
整點啟動 ›  設定 / 暫停
待辦事項 ›  開啟待辦事項… / ☑ 整點提醒到期待辦
通知中心…   番茄鐘、提醒、倒數、待辦、行事曆的通知歷史（標題顯示未讀數）
效率提升 ›
    番茄鐘 ›    開始專注 / 暫停（繼續）/ 取消番茄鐘
    倒數計時 ›  暫停（繼續）/ 取消倒數 / 1·3·5·10·15·30 分鐘 / 自訂…
時鐘設定 ›  多時區 / 字型 / 字型大小 / 配色 / 時間格式 / 日期格式 / 透明度 / 圓角
離開
```

## 待辦事項匯出／匯入

| 格式 | 用途 | 內容 |
|------|------|------|
| Markdown（`.md`） | 閱讀、分享、跨工具 | 核取方塊清單與階層、連結；不含日期、優先級、專案 |
| JSON（`.json`） | 完整備份、還原、資料遷移 | 全部欄位（id、日期、優先級、專案…） |

- 「匯出…」依存檔副檔名選擇格式；「匯入…」兩種格式皆可，內容會附加到頂層。
- 「還原…」只接受 JSON 備份，會取代目前所有待辦，並可用「復原」取消。

## 自訂 BAT 雙擊啟動（Windows，無主控台視窗）

已自行安裝 Python 與相依套件時，可建立自己的 `.bat`，以 `pythonw.exe` 背景啟動（不會出現命令列視窗）；路徑請換成自己的環境：

```bat
@echo off
cd /d "<專案資料夾>"
start "" "<Python 安裝資料夾>\pythonw.exe" "main.py"
```

- `cd /d` 切換到專案資料夾，讓 `main.py` 與相對路徑正確。
- `start ""` 啟動後立即返回，BAT 視窗隨即關閉。
- 要開機自動啟動，可將此 BAT 的捷徑放入 `shell:startup` 資料夾。

## 正式打包（Release Build）

使用 PyInstaller 產生單一執行檔（onefile）。

| 平台 | 指令 | 產出 |
|------|------|------|
| Windows | 雙擊 `package_windows.bat` | `dist/DigitalClock.exe` |
| macOS | `chmod +x package_macos.sh && ./package_macos.sh` | `dist/DigitalClock` |
| Linux | `chmod +x package_linux.sh && ./package_linux.sh` | `dist/DigitalClock` |

注意事項：
- 建議在目標平台各自打包。
- onefile 每次啟動都需解壓縮，啟動較慢；分發給 macOS 使用者通常還需簽章與公證，Windows 未簽署的執行檔可能被 SmartScreen 警告。
