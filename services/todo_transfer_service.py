"""待辦匯入、匯出與備份還原。"""
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from core.file_security import restrict_to_owner
from core.todo_commands import (
    ImportTasksCommand,
    ReplaceTasksCommand,
    iter_subtree,
)
from services.todo_store import (
    FILE_VERSION,
    export_json,
    export_markdown,
    file_version,
    read_tasks_file,
)

if TYPE_CHECKING:
    from services.todo_service import TodoService


class TodoTransferService:
    """在既有 ``TodoService`` 命令邊界內處理檔案傳輸。"""

    def __init__(self, service: "TodoService") -> None:
        self.service = service

    def import_file(self, path: str | Path) -> int:
        """匯入 JSON 或 Markdown 待辦，附加到最上層。"""
        imported = read_tasks_file(Path(path))
        existing = {task.id for task in self.service.iter_tasks()}
        for top in imported:
            for task in iter_subtree(top):
                if task.id in existing:
                    task.id = str(uuid.uuid4())
                existing.add(task.id)
        return (
            len(imported)
            if self.service._run(ImportTasksCommand(self.service, imported))
            else 0
        )

    def export_markdown(self) -> str:
        """輸出可讀 Markdown 待辦清單。"""
        return export_markdown(self.service.tasks)

    def export_json(self) -> str:
        """輸出完整 JSON 備份。"""
        return export_json(self.service.tasks)

    def export_to_file(self, path: str | Path) -> str:
        """依副檔名輸出 JSON 或 Markdown。"""
        target = Path(path)
        suffix = target.suffix.lower()
        if suffix == ".json":
            target.write_text(self.export_json(), encoding="utf-8")
            restrict_to_owner(target)
            return "json"
        if suffix == ".md":
            target.write_text(self.export_markdown(), encoding="utf-8")
            return "md"
        raise ValueError("僅支援匯出為 .json 或 .md")

    def restore_backup(self, path: str | Path) -> int:
        """以 JSON 備份取代目前任務樹，並保留可復原命令。"""
        source = Path(path)
        if source.suffix.lower() != ".json":
            raise ValueError("還原僅支援 JSON 備份；Markdown 請使用匯入")
        if file_version(source) > FILE_VERSION:
            raise ValueError("備份版本比本程式支援的新，請先更新程式")
        restored = read_tasks_file(source)
        seen: set[str] = set()
        for top in restored:
            for task in iter_subtree(top):
                if task.id in seen:
                    task.id = str(uuid.uuid4())
                seen.add(task.id)
        return (
            len(restored)
            if self.service._run(ReplaceTasksCommand(self.service, restored))
            else 0
        )
