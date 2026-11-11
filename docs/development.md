# 開發指南

```bash
python -m unittest discover -s tests      # 執行全部測試
pip install -e ".[dev]"                   # 安裝 ruff、coverage
python -m ruff check .
```

- CI（`.github/workflows/ci.yml`）：ruff 檢查，以及 Ubuntu（xvfb）與 Windows 上的 unittest + coverage。
- 非 Windows 平台不支援 `-transparentcolor` 等 Windows 視窗屬性，程式會略過；少數測試依賴 Windows 行為（如 `shutdown.exe`），在其他平台自動略過。
- 測試使用標準庫 `unittest`；涉及 `ConfigManager` 時應 mock `Path.home()`，避免讀寫使用者設定。
- 部分 UI 測試需要可用的顯示器，無顯示器時會自動略過。
- 更多開發約定見 [AGENTS.md](../AGENTS.md)。

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
