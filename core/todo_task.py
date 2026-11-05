"""待辦事項資料模型。"""
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

PRIORITY_LOW = "low"
PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"
PRIORITIES = (PRIORITY_LOW, PRIORITY_NORMAL, PRIORITY_HIGH)


def _parse_date(value: Any) -> date | None:
    """容錯解析日期；接受 YYYY-MM-DD 或含時間的 ISO 字串，失敗回傳 None。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_date_input(text: str, today: date | None = None) -> date | None:
    """
    解析使用者輸入的日期。

    接受「今天」「明天」「下週」（今天起 7 天後）、YYYY-MM-DD 與 YYYY/MM/DD；空字串回傳 None。

    Raises:
        ValueError: 格式無法辨識
    """
    value = text.strip()
    if not value:
        return None
    base = today or date.today()
    shortcuts = {"今天": 0, "明天": 1, "下週": 7}
    if value in shortcuts:
        return base + timedelta(days=shortcuts[value])
    try:
        return date.fromisoformat(value.replace("/", "-"))
    except ValueError as e:
        raise ValueError(f"日期格式錯誤：{value}（請輸入 YYYY-MM-DD）") from e


def _parse_creation_time(value: Any) -> datetime:
    """解析建立時間為帶 UTC 時區的 datetime；失敗時以現在時間取代。"""
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


class TodoTask:
    """單一待辦事項，可含子任務。"""

    def __init__(
        self,
        text: str,
        task_id: str | None = None,
        children: list["TodoTask"] | None = None,
        link: str | None = None,
        creation_time: datetime | None = None,
        is_done: bool = False,
        priority: str = PRIORITY_NORMAL,
        due_date: date | None = None,
        start_date: date | None = None,
        project: str | None = None,
    ) -> None:
        """
        初始化待辦事項。

        Args:
            text: 任務內容
            task_id: 唯一識別碼；缺省時自動產生 UUID
            children: 子任務清單
            link: 外部連結
            creation_time: 建立時間；缺省為現在（UTC）
            is_done: 是否已完成
            priority: 優先度 low/normal/high
            due_date: 截止日
            start_date: 開始日；缺省為建立日
            project: 所屬專案
        """
        if creation_time is None:
            creation_time = datetime.now(UTC)
        elif creation_time.tzinfo is None:
            creation_time = creation_time.replace(tzinfo=UTC)
        self.id: str = task_id or str(uuid.uuid4())
        self.text: str = text
        self.children: list[TodoTask] = children if children is not None else []
        self.link: str | None = link
        self.creation_time: datetime = creation_time
        self.is_done: bool = is_done
        self.priority: str = priority if priority in PRIORITIES else PRIORITY_NORMAL
        self.due_date: date | None = due_date
        self.start_date: date | None = start_date or creation_time.astimezone().date()
        self.project: str | None = project

    def to_dict(self) -> dict[str, Any]:
        """遞迴轉為可 JSON 序列化的字典。"""
        created = self.creation_time.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return {
            "id": self.id,
            "text": self.text,
            "link": self.link,
            "project": self.project,
            "creation_time": created,
            "is_done": self.is_done,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "children": [child.to_dict() for child in self.children],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "TodoTask":
        """由字典還原（容錯：缺欄位用預設值，日期無法解析時為 None）。"""
        creation_time = _parse_creation_time(data.get("creation_time"))
        children_raw = data.get("children")
        children = [
            TodoTask.from_dict(child)
            for child in (children_raw if isinstance(children_raw, list) else [])
            if isinstance(child, dict)
        ]
        return TodoTask(
            text=str(data.get("text", "")),
            task_id=data.get("id") or None,
            children=children,
            link=data.get("link") or None,
            creation_time=creation_time,
            is_done=bool(data.get("is_done", False)),
            priority=data.get("priority", PRIORITY_NORMAL),
            due_date=_parse_date(data.get("due_date")),
            start_date=_parse_date(data.get("start_date")),
            project=data.get("project") or None,
        )
