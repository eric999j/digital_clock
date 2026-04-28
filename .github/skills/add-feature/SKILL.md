---
name: add-feature
description: "新增功能到 Digital Clock 專案。依循分層架構（Events → Strategy → Service → ClockLogic → UI）逐步實作，確保 Observer 解耦與設計慣例。Use when: 新增功能、add feature、implement feature、新增服務、新增策略。"
argument-hint: "描述要新增的功能，例如：自動亮度調整、專注統計報表"
---

# 新增功能 — Digital Clock

依循專案的分層架構，按以下順序新增功能。每一步完成後執行測試確認無破壞。

## 步驟

### 1. 定義事件常數

在 [core/events.py](../../../core/events.py) 的 `Events` 類別新增事件常數。

```python
# 範例：新增 MY_FEATURE 相關事件
MY_FEATURE_UPDATED = 'my_feature_updated'
MY_FEATURE_TRIGGERED = 'my_feature_triggered'
```

**規則**：禁止 magic string，所有事件名稱必須在此集中定義。

### 2. 建立 Strategy（僅限需要可替換判定邏輯時）

> 簡單功能可跳過此步驟，直接進入步驟 3。
> 需要 Strategy 的信號：判定邏輯可能有多種實作、需要獨立測試觸發條件、或涉及時間/狀態去重。

在 `strategies/` 新增繼承 `BaseStrategy` 的策略類別：

```python
from strategies.base import BaseStrategy

class MyFeatureStrategy(BaseStrategy):
    def check(self, *args, **kwargs) -> Any:
        """實作判定邏輯。"""
        ...
```

**注意**：Strategy 可能有實例狀態（如 `last_triggered_hour`），測試時需確保隔離。

### 3. 建立 Service

在 `services/` 新增服務，遵循既有模式：

```python
from services.config_service import ConfigManager
from strategies.my_feature_strategy import MyFeatureStrategy
from core.events import Events

class MyFeatureService:
    def __init__(self, config_manager: ConfigManager, notify_callback: Callable[[str, Any], None]):
        self.config_manager = config_manager
        self.notify = notify_callback
        self.strategy = MyFeatureStrategy()

    @property
    def config(self) -> Dict[str, Any]:
        return self.config_manager.load_config()
```

**關鍵**：
- 接收 `config_manager` 與 `notify_callback` 兩個依賴
- 透過 `self.notify(Events.XXX, ...)` 通知 `ClockLogic`，不直接操作 UI
- 設定存取統一透過 `config_manager`，寫入使用 `schedule_save()` 延遲儲存

### 4. 整合到 ClockLogic

在 [core/clock_logic.py](../../../core/clock_logic.py) 中：

1. **Import** 新 Service
2. 在 `__init__` 中實例化，注入 `config_manager` 和 `self.notify_observers`
3. 若需要 UI 排程，用 `self.ui.after()` 而非直接操作 UI

```python
from services.my_feature_service import MyFeatureService

# 在 __init__ 中
self.my_feature_service = MyFeatureService(config_manager, self.notify_observers)
```

### 5. 新增 UI 回應（如需要）

在 [ui/main_window.py](../../../ui/main_window.py) 的 `update()` 方法新增事件處理分支：

```python
def update(self, event: str, *args, **kwargs) -> None:
    if event == Events.MY_FEATURE_TRIGGERED:
        self._handle_my_feature(*args, **kwargs)
```

若需要設定視窗，在 `ui/` 新增 Toplevel 視窗（參考 `reminder_window.py` 或 `hourly_web_window.py`）。

### 6. 撰寫測試

在 `tests/` 新增 `test_my_feature_service.py`：

```python
class TestMyFeatureService(unittest.TestCase):
    def setUp(self):
        self.mock_config_mgr = MagicMock()
        self.config_data = { ... }
        self.mock_config_mgr.load_config.return_value = self.config_data
        self.mock_notify = MagicMock()
        self.service = MyFeatureService(self.mock_config_mgr, self.mock_notify)
```

**測試要點**：
- Mock `ConfigManager` 和 `notify_callback`
- Strategy 有狀態時，每個 test 需建立新的 Service 實例
- 確認事件以正確的 `Events` 常數發送

### 7. 驗證

```bash
python -m unittest discover -s tests
```

## 必須遵守的慣例

| 項目 | 規則 |
|------|------|
| Import | 絕對 import（`from services.xxx import Xxx`） |
| 命名 | snake_case 方法/變數、PascalCase 類別、UPPER_CASE 常數 |
| Type hints | 所有方法簽名與回傳值必須標註 |
| Docstring | Google-style，繁體中文 |
| 私有方法 | 單底線 `_method_name` |
| 日誌 | `logging.getLogger(__name__)`，不用 print |
| 循環引用 | 引用 UI 類型時使用 `TYPE_CHECKING` guard |
| 線程安全 | 背景線程不可直接操作 UI，用 `root.after()` |

## 常見錯誤

- **忘記在 Events 定義常數** → 出現 magic string，違反慣例
- **Service 直接操作 UI** → 破壞 Observer 解耦，應透過 `notify_callback`
- **跳過 Strategy 層** → 硬編碼邏輯在 Service，日後難以替換
- **測試未隔離 Singleton** → `ConfigManager` 需重設 `_instance = None`
- **Windows 專用 API 無 platform check** → `ctypes.windll` 在非 Windows 會失敗
