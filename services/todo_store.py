"""待辦事項持久化：原子寫入、損毀備份、舊版匯入與 Markdown 匯出。"""
import contextlib
import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from core.todo_task import TodoTask

logger = logging.getLogger(__name__)

FILE_VERSION = 1


def parse_tasks(payload: Any) -> list[TodoTask]:
    """
    解析 todos.json 內容；同時接受 ``{"tasks": [...]}`` 與 todo_list 舊版的純陣列。

    Raises:
        ValueError: 內容不是任務陣列或含 ``tasks`` 陣列的物件
    """
    items = payload.get("tasks") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("檔案格式不正確：需為任務陣列")
    return [TodoTask.from_dict(item) for item in items if isinstance(item, dict)]


def read_tasks_file(path: Path) -> list[TodoTask]:
    """
    讀取任務檔（用於匯入 todo_list 的 tasks.json）。

    Raises:
        OSError: 無法讀取
        ValueError: JSON 或格式不正確
    """
    with open(path, encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式損毀：{e}") from e
    return parse_tasks(payload)


class TodoStore:
    """待辦事項檔案存取。"""

    def __init__(self, path: Path) -> None:
        """
        Args:
            path: todos.json 路徑
        """
        self.path = path

    def load(self) -> tuple[list[TodoTask], str]:
        """
        載入任務。

        Returns:
            (任務清單, 訊息)；訊息為空字串表示正常。檔案損毀時會改名為 ``.bak`` 並回傳空清單。
        """
        if not self.path.exists():
            return [], ""
        try:
            return read_tasks_file(self.path), ""
        except ValueError as e:
            backup = self.path.with_name(f"{self.path.name}.bak")
            try:
                os.replace(self.path, backup)
            except OSError as backup_error:
                logger.error("Unable to back up corrupted todos file: %s", backup_error)
            logger.error("Corrupted todos file: %s", e)
            return [], f"待辦檔案損毀，已備份為 {backup.name} 並建立新清單"
        except OSError as e:
            logger.error("Error reading todos file: %s", e)
            return [], f"無法讀取待辦檔案：{e}"

    def save(self, tasks: Iterable[TodoTask]) -> str:
        """
        原子寫入任務。

        Returns:
            空字串表示成功，否則為錯誤訊息
        """
        temp_file = self.path.with_name(f"{self.path.name}.tmp")
        payload = {"version": FILE_VERSION, "tasks": [task.to_dict() for task in tasks]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            with contextlib.suppress(OSError):
                os.chmod(temp_file, 0o600)  # 待辦內容僅限本人讀寫
            os.replace(temp_file, self.path)
            return ""
        except (OSError, TypeError, ValueError) as e:
            logger.error("Error saving todos: %s", e)
            return f"無法儲存待辦檔案：{e}"
        finally:
            try:
                temp_file.unlink(missing_ok=True)
            except OSError:
                logger.debug("Unable to clean temporary todos file: %s", temp_file)


def export_markdown(tasks: Iterable[TodoTask]) -> str:
    """將任務樹輸出為 Markdown checkbox 清單；子項繼承父項的完成狀態。"""
    lines: list[str] = []

    def walk(items: Iterable[TodoTask], level: int, parent_done: bool) -> None:
        for task in items:
            done = parent_done or task.is_done
            box = "[x]" if done else "[ ]"
            text = task.text.replace("[", "\\[").replace("]", "\\]") if task.link else task.text
            body = f"[{text}]({task.link})" if task.link else text
            lines.append(f"{'  ' * level}- {box} {body}")
            walk(task.children, level + 1, done)

    walk(tasks, 0, False)
    return "\n".join(lines) + ("\n" if lines else "")
