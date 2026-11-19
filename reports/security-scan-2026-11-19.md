# 安全掃描報告 — digital_clock

> **掃描日期**：2026-11-19  
> **掃描模式**：快速模式 (Quick Scan)  
> **結論**：未發現已知依賴 CVE、機密洩漏或 Bandit 高嚴重度問題；保留 3 項低殘餘風險與數項防護設計確認。

---

## 安全掃描摘要

- **掃描範圍**：`core/`、`services/`、`strategies/`、`ui/`、`main.py`
- **掃描規模**：69 個 Python 檔案，Bandit 統計 10,113 LOC（不含測試、打包產物與報告）
- **主要語言／執行環境**：Python 3.13.2、Tkinter 桌面應用
- **進入點**：`main.py`
- **專案直接依賴**：`pynput`、`tkinterdnd2`、`icalendar`、`recurring-ical-events`、Windows 條件式 `tzdata`
- **執行工具與版本**：
  - `bandit` 1.9.4 — 靜態安全分析（SAST）
  - `pip-audit` 2.10.0 — 僅掃描 `requirements.txt` 及其解析後依賴
  - 正則表達式機密掃描 — 私鑰、常見雲端憑證、GitHub/OpenAI token、API key／secret 指派模式
- **涵蓋範圍缺口**：
  - `gitleaks`／`trufflehog` 未安裝；未掃描 Git 歷史，使用工作樹正則掃描作為備援。
  - 未執行 DAST、外部程式實際執行驗證或 ICS 遠端服務驗證。
  - 快速模式未逐一審查所有第三方套件原始碼。

---

## 發現事項（嚴重 → 低）

### 無高或嚴重風險

Bandit 未回報高嚴重度項目，pip-audit 未發現已知 CVE。

### 1. 嚴重度：低 — Windows `icacls` 使用部分可執行檔路徑

- **問題描述**：Windows 權限限制以未含完整路徑的 `icacls` 啟動外部程序。若 Windows 搜尋路徑或目前目錄遭植入同名惡意程式，該程式可能以使用者權限執行。
- **證據**：`core/file_security.py` 第 42–47 行；Bandit B607、B603。
- **影響說明**：需要攻擊者能預先控制目前工作目錄或 PATH；一般安裝與正常啟動情境下利用條件較高。呼叫未使用 shell，參數採 argv，並設有 10 秒 timeout。
- **建議修復方式**：優先改用 `%SystemRoot%\System32\icacls.exe`，解析後再執行；找不到標準路徑時明確失敗，不回退 PATH。
- **風險接受條件**：若桌面啟動固定工作目錄且僅目前使用者可控制，可暫列低風險；建議下一次重構一併處理。

### 2. 嚴重度：低 — 整點啟動可執行使用者設定的外部程式

- **問題描述**：功能設計允許使用者以設定檔指定程式、參數與工作目錄，並以 `subprocess.Popen` 啟動。
- **證據**：`core/program_launcher.py` 第 30–59 行；`services/hourly_web_service.py` 第 137–145 行；Bandit B603。
- **影響說明**：這是預期功能。手動啟用時 UI 顯示完整命令並要求確認，XML 匯入的程式規則預設停用；但自動規則執行時不會再次顯示確認，若同一使用者帳號或具有設定目錄寫入權的程式竄改 config，仍可觸發任意程式。
- **既有防護**：不經 shell；驗證可執行檔、Windows 副檔名、工作目錄、控制字元、參數長度與時段；程式規則不對腳本內容作安全判定。
- **建議修復方式**：維持目前使用者確認流程，避免放寬為自動接受任意來源；若引入遠端設定同步或多使用者設定，需增加簽章、允許清單與來源信任模型。

### 3. 嚴重度：低 — Tk 相容性分支吞掉例外

- **問題描述**：`ui/main_window.py` 第 1176–1179 行對相容性呼叫 `label.place_forget()` 捕捉所有例外且不記錄。
- **證據**：Bandit B110。
- **影響說明**：沒有直接提權或資料洩漏路徑，主要影響除錯可觀察性。
- **建議修復方式**：縮小例外為 `tk.TclError`，並視需要以 `logger.debug()` 記錄。

---

## 已驗證的 Bandit 提示（非可利用弱點）

### XML 解析（B314／B405）

- Bandit 針對 `xml.etree.ElementTree` 與 `ET.fromstring` 分別回報中、低嚴重度。
- `core/task_xml_importer.py` 第 50–58 行先拒絕含 `DOCTYPE` 的 XML；匯入前另限制 1 MiB，且 Python `ElementTree` 不會主動取回外部實體。
- **判定**：在目前本機檔案、大小限制與拒絕 DTD 的條件下，殘餘風險較低。若要完全消除工具告警，可評估改用 `defusedxml`，但不是本次高優先修復。

### ICS 網路開啟（B310）

- Bandit 提示 `urlopen` 應檢查 scheme。
- `services/calendar_sync_service.py` 第 205–209 行在開啟前再次呼叫 `is_valid_ics_url()`；該函式僅接受 `http/https` 安全 URL 且 ICS 另限制為 `https`。下載有 20 秒 timeout 與 5 MiB 上限。
- **判定**：已有明確前置控制，視為誤報。

### 非密碼學隨機數（B311）

- `ui/theme_utils.py` 第 83–91 行使用標準 `random` 產生配色。
- 配色不是 token、密鑰、識別碼或權限控制值。
- **判定**：不需要改用 `secrets`。

### `subprocess` 模組匯入（B404）

- 為 `icacls` 與使用者授權程式啟動所需，實際風險已分別列入上述低風險與誤報判定。

---

## 依賴套件弱點掃描

`pip-audit` 僅解析 `requirements.txt`，共解析 9 個套件（含 4 個傳遞依賴）。

- **結果**：`No known vulnerabilities found`
- **已解析套件**：
  - `pynput` 1.8.2
  - `tkinterdnd2` 0.7.0
  - `icalendar` 7.3.0
  - `recurring-ical-events` 3.8.2
  - `python-dateutil` 2.9.0.post0
  - `x-wr-timezone` 2.0.1
  - `tzdata` 2026.6
  - `six` 1.17.0
  - `click` 8.5.1
- **結論**：本次掃描資料庫未發現這些版本的已知 CVE。

---

## 機密與憑證曝露檢查

**結果：未發現疑似機密洩漏。**

掃描包含：
- PEM／OpenSSH 私鑰
- AWS access key
- GitHub／OpenAI token
- Google API key
- Slack token
- `password`、`secret`、`api_key` 的高信號明文指派
- 專案 `.gitignore` 與已追蹤檔案清單

倉庫衛生：
- `.gitignore` 已排除 `.venv/`、`__pycache__/`、`build/`、`dist/`、`*.log`、`config.json`、`todos.json*` 與 `tasks.json`。
- 工作目錄的 `digital_clock.log` 未被 Git 追蹤。
- `config.json`、`todos.json` 與 ICS URL 仍是本機敏感資料；不可加入版本控制或發送到外部服務。

---

## 速效改善

1. 以 `%SystemRoot%\System32\icacls.exe` 取代部分路徑 `icacls`。
2. 將 `main_window.py` 的相容性 `except Exception: pass` 縮小為 `tk.TclError` 並記錄 debug 日誌。
3. 對 Bandit XML 告警加入精確說明，或在下一次依賴更新時評估 `defusedxml`。
4. 維持整點啟動程式規則的逐項確認，不自動啟用 XML／JSON 匯入的程式規則。
5. CI 中固定執行 `bandit` 與 `pip-audit -r requirements.txt`，避免再次掃描無關共用環境。

---

## 建議重現指令

```bash
# Bandit 靜態掃描
python -m bandit -r core services strategies ui main.py -ll

# 僅審核專案宣告依賴
python -m pip_audit -r requirements.txt --desc

# 測試安全驗證相關行為
python -m unittest tests.test_url_validator tests.test_program_safety tests.test_task_xml_importer tests.test_config_manager
```

---

## 與舊報告差異

2026-03-24 報告已過時；其中 URL scheme、日誌位置、檔案權限、`.gitignore`、依賴清單等項目已在現有程式中修正或建立。本報告以目前 69 個來源檔案與專案 manifest 為準。
