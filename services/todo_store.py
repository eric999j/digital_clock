"""待辦事項持久化：原子寫入、損毀備份、舊版匯入與 Markdown 匯出。"""
import json
import logging
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from core.file_security import restrict_to_owner
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
    讀取 JSON 或 Markdown 任務檔。

    Raises:
        OSError: 無法讀取
        ValueError: 檔案格式不正確
    """
    if path.suffix.lower() == ".md":
        return parse_markdown(path.read_text(encoding="utf-8-sig"))
    with open(path, encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式損毀：{e}") from e
    return parse_tasks(payload)


def parse_markdown(content: str) -> list[TodoTask]:
    """解析 Markdown 核取方塊清單及其縮排階層。"""
    tasks: list[TodoTask] = []
    parents: list[tuple[int, TodoTask]] = []
    for line in content.splitlines():
        match = re.match(r"^([ \t]*)[-*+]\s+\[([ xX])\]\s+(.*\S)\s*$", line)
        if not match:
            continue
        indentation = len(match.group(1).expandtabs(4))
        body = match.group(3)
        link_match = re.fullmatch(r"\[((?:\\.|[^\]\\])*)\]\((.+)\)", body)
        if link_match:
            text = re.sub(r"\\([\[\]])", r"\1", link_match.group(1))
            link = link_match.group(2)
        else:
            text, link = body, None
        task = TodoTask(text, link=link, is_done=match.group(2).lower() == "x")
        while parents and parents[-1][0] >= indentation:
            parents.pop()
        if parents:
            parents[-1][1].children.append(task)
        else:
            tasks.append(task)
        parents.append((indentation, task))
    if content.strip() and not tasks:
        raise ValueError("Markdown 檔案不含待辦核取方塊清單")
    return tasks


def file_version(path: Path) -> int:
    """讀取檔案的 ``version``；Markdown、舊版純陣列或無欄位視為 1。"""
    if path.suffix.lower() == ".md":
        return FILE_VERSION
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError):
        return FILE_VERSION
    version = payload.get("version") if isinstance(payload, dict) else None
    return version if isinstance(version, int) and not isinstance(version, bool) else FILE_VERSION


def export_json(tasks: Iterable[TodoTask]) -> str:
    """將任務樹輸出為完整 JSON（含優先度、日期、專案、id），可無損還原。"""
    payload = {"version": FILE_VERSION, "tasks": [task.to_dict() for task in tasks]}
    return json.dumps(payload, indent=4, ensure_ascii=False) + "\n"


class TodoStore:
    """待辦事項檔案存取。"""

    def __init__(self, path: Path) -> None:
        """
        Args:
            path: todos.json 路徑
        """
        self.path = path
        self._newer_version_message = ""

    def load(self) -> tuple[list[TodoTask], str]:
        """
        載入任務。

        Returns:
            (任務清單, 訊息)；訊息為空字串表示正常。檔案損毀時會改名為 ``.bak`` 並回傳空清單。
        """
        self._newer_version_message = ""
        if not self.path.exists():
            return [], ""
        try:
            tasks = read_tasks_file(self.path)
            version = self._peek_version()
            if version > FILE_VERSION:
                self._newer_version_message = (
                    f"待辦檔案版本 {version} 比本程式支援的 {FILE_VERSION} 新，"
                    "為避免資料遺失，本次不會覆寫該檔案"
                )
                return [], self._newer_version_message
            return tasks, ""
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

    def _peek_version(self) -> int:
        return file_version(self.path)

    def save(self, tasks: Iterable[TodoTask]) -> str:
        """
        原子寫入任務。

        Returns:
            空字串表示成功，否則為錯誤訊息
        """
        if self._newer_version_message:
            return self._newer_version_message
        temp_file = self.path.with_name(f"{self.path.name}.tmp")
        payload = {"version": FILE_VERSION, "tasks": [task.to_dict() for task in tasks]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            restrict_to_owner(temp_file)  # 待辦內容僅限本人讀寫
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
