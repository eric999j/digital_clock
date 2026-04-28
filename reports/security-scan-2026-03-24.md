# 安全掃描報告 — digital_clock

> **掃描日期**: 2026-03-24
> **掃描模式**: 快速模式 (Quick Scan)

---

## 安全掃描摘要

- **掃描範圍**: digital_clock 專案全部原始碼 (2,224 LOC, 20 個 Python 檔案)
- **主要語言**: Python 3.13
- **進入點**: `main.py`
- **非標準庫依賴**: `pynput` (鍵盤監聽)
- **執行工具與版本**:
  - `bandit` 1.9.4 — 靜態安全分析 (SAST)
  - `pip-audit` 2.10.0 — 依賴套件 CVE 掃描
  - regex 機密掃描 — 手動正則比對 (API key, token, private key, AWS/Azure/GCP credentials)
- **涵蓋範圍缺口**:
  - 未執行 `gitleaks`/`trufflehog` (未安裝)；以 regex 備援
  - pip-audit 掃描的是共用 venv (400+ 套件)，多數套件與本專案無直接關聯
  - 未執行動態測試 (DAST)

---

## 發現事項（嚴重 → 低）

### 1. 嚴重度：中 — URL 未驗證即透過 `webbrowser.open()` 開啟

- **問題描述**: `HourlyWebService.check()` 與 `HourlyWebWindow._test_open_url()` 會將使用者設定的 URL 直接傳給 `webbrowser.open()`，僅以 `showwarning` 建議使用 http/https 前綴，未強制驗證 URL scheme。惡意使用者如果能修改 config.json，可注入 `file://` 或 `javascript:` 等危險 scheme。
- **證據**:
  - `services/hourly_web_service.py` L65-69：`webbrowser.open(url, new=2)`
  - `ui/hourly_web_window.py` L171：`if url and not (url.startswith('http://') or url.startswith('https://'))` — 僅 warning，不阻止
  - `ui/hourly_web_window.py` L185：`webbrowser.open(url)`
  - `ui/popup_utils.py` L12：`_URL_PATTERN` regex 僅匹配 `http/https` 但開啟連結時無額外驗證
- **影響說明**: 本專案為桌面應用程式，URL 來自本機 config.json，攻擊面有限。但若 config 檔案被其他程式或惡意操作竄改，可導致開啟任意本機檔案或危險 URI。
- **建議修復方式**: 在 `webbrowser.open()` 呼叫前強制檢查 URL scheme 為 `http` 或 `https`，否則拒絕開啟。

### 2. 嚴重度：中 — config.json 無完整性驗證機制

- **問題描述**: `ConfigManager.load_config()` 從 `~/.digital_clock/config.json` 讀取設定檔，僅做 JSON 格式驗證與型別合併，無任何完整性或簽章檢查。設定檔中的欄位（如 `screenshot_keys`、`url`）直接影響程式行為。
- **證據**:
  - `services/config_service.py` L167-189：`load_config()` 直接信任 JSON 內容
  - `services/config_service.py` L145-157：`save_config()` 以明文 JSON 寫入
- **影響說明**: 桌面應用常見模式，風險取決於作業系統的檔案權限。在多使用者環境下可能被利用。
- **建議修復方式**: 可接受的風險等級（桌面應用），但建議確保檔案權限為使用者唯讀 (0600)。

### 3. 嚴重度：低 — 寬泛的 try-except-pass 模式 (B110 × 6)

- **問題描述**: bandit 偵測到 6 處 `try: ... except Exception: pass` 或 `except: pass` 的模式，可能靜默吞掉重要的安全例外。
- **證據**:
  - `core/clock_logic.py` L100：`except Exception: pass`
  - `services/hourly_web_service.py` L79, L81：`except Exception: pass` (ctypes 呼叫)
  - `ui/main_window.py` L539：`except Exception: pass`
  - `ui/main_window.py` L724：`except: pass` (bare except)
  - `ui/main_window.py` L747：`except: pass` (bare except)
- **影響說明**: 雖為防禦性程式碼慣例，但 bare `except` (無指定例外類型) 會捕獲 `SystemExit` 和 `KeyboardInterrupt`，可能影響程式正常終止。
- **建議修復方式**: 將 `except:` 改為 `except Exception:`，並加入 `logger.debug()` 以利除錯。

### 4. 嚴重度：低 — 日誌檔寫入於工作目錄

- **問題描述**: `main.py` L10 將日誌寫入 `digital_clock.log`（工作目錄），而非受保護的使用者目錄。
- **證據**: `main.py` L10：`logging.FileHandler('digital_clock.log', encoding='utf-8')`
- **影響說明**: 若工作目錄為可寫的共享位置，其他使用者可讀取日誌內容。
- **建議修復方式**: 將日誌檔放入 `~/.digital_clock/` 目錄，與 config.json 一致。

### 5. 嚴重度：資訊 — 共用 venv 存在多個已知 CVE（非專案直接依賴）

- **問題描述**: pip-audit 偵測到共用 venv 中多個套件含已知弱點，但這些套件（如 tornado, werkzeug, starlette, pdfminer.six 等）**非本專案的直接依賴**。
- **主要 CVE（僅列與 Python 生態系相關者）**：
  | 套件 | 版本 | CVE | 嚴重度 |
  |------|------|-----|-------|
  | tornado | 6.4.2 | CVE-2025-47287, CVE-2026-31958 | 中 |
  | werkzeug | 3.1.1 | CVE-2025-66221, CVE-2026-21860, CVE-2026-27199 | 中 |
  | urllib3 | 2.3.0 | CVE-2025-50182 等 5 個 | 中 |
  | pillow | 11.1.0 | CVE-2026-25990 | 中 |
  | setuptools | 78.1.0 | CVE-2025-47273 | 高 |
  | pdfminer.six | 20250506 | CVE-2025-64512, CVE-2025-70559 | 嚴重 |
- **影響說明**: 不影響本專案 runtime，但 venv 衛生狀況不佳。
- **建議修復方式**: 為本專案建立獨立的 venv，並建立 `requirements.txt` 僅包含 `pynput`。

---

## 機密與憑證曝露檢查

**結果：✅ 未發現任何機密洩漏**

掃描項目：
- API Key / Secret / Token / Password 模式 — 無匹配
- 私鑰格式 (PEM) — 無匹配
- AWS / Azure / GCP 認證字串 — 無匹配
- GitHub / OpenAI token 格式 — 無匹配
- `.env` 檔案 — 不存在
- `.gitignore` — 不存在（建議建立）

---

## 速效改善

1. **建立 `.gitignore`** — 排除 `.venv/`、`__pycache__/`、`*.log`、`config.json`
2. **建立 `requirements.txt`** — `pynput>=1.8.1` 並使用獨立 venv
3. **URL scheme 白名單** — 在 `webbrowser.open()` 前加入 `urlparse` 驗證
4. **bare except → except Exception** — 修改 `main_window.py` L724, L747
5. **日誌路徑** — 移至 `~/.digital_clock/digital_clock.log`

---

## 建議重現指令

```bash
# 1. bandit 靜態掃描
python -m bandit -r . --exclude ./.venv,./__pycache__,./tests -ll

# 2. pip-audit 依賴弱點掃描
python -m pip_audit --desc

# 3. regex 機密掃描 (PowerShell)
Select-String -Path *.py,**/*.py -Pattern "password|secret|api_key|token|private_key" -CaseSensitive:False
```
