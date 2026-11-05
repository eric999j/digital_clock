"""待辦事項服務：任務樹、CRUD、復原／重做、持久化與整點到期提醒。"""
import logging
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from core.events import Events
from core.todo_commands import (
    AddTaskCommand,
    CommandHistory,
    DeleteTasksCommand,
    ImportTasksCommand,
    MoveTaskCommand,
    RemoveLinkCommand,
    TodoCommand,
    ToggleDoneCommand,
    UpdateTaskCommand,
    iter_subtree,
)
from core.todo_filter import TodoFilter
from core.todo_task import PRIORITIES, PRIORITY_NORMAL, TodoTask
from services.config_service import ConfigManager
from services.todo_store import TodoStore, export_markdown, read_tasks_file
from strategies.todo_due_strategy import TodoDueStrategy

logger = logging.getLogger(__name__)

TODO_FILE_NAME = "todos.json"


class TodoService:
    """管理待辦事項樹。所有變更皆經 Command 執行並立即原子存檔。"""

    def __init__(
        self,
        config_manager: ConfigManager,
        notify_callback: Callable[..., None],
        store: TodoStore | None = None,
    ) -> None:
        """
        Args:
            config_manager: 設定管理器（提供資料目錄與 ``todo`` 設定）
            notify_callback: 通知回調 (event, *args)
            store: 檔案存取物件；缺省使用設定目錄下的 todos.json
        """
        self.config_manager = config_manager
        self.notify = notify_callback
        self.store = store or TodoStore(Path(config_manager.config_dir) / TODO_FILE_NAME)
        self.strategy = TodoDueStrategy()
        self.history = CommandHistory()
        self.tasks: list[TodoTask] = []
        self.last_message: str = ""
        self.load()

    # ---- 載入／存檔 ----

    def load(self) -> str:
        """從檔案載入任務並清空歷史；回傳載入訊息（空字串表示正常）。"""
        self.tasks, message = self.store.load()
        self.history.clear()
        self.last_message = message
        return message

    def _persist(self) -> None:
        self.last_message = self.store.save(self.tasks)

    # ---- 樹狀查詢（供 Command 使用）----

    def _scan(self) -> dict[str, tuple[TodoTask, str | None, int]]:
        """前序掃描：{id: (任務, 父項 id, 在父層的索引)}，插入順序即文件順序。"""
        found: dict[str, tuple[TodoTask, str | None, int]] = {}

        def walk(items: list[TodoTask], parent_id: str | None) -> None:
            for index, task in enumerate(items):
                found[task.id] = (task, parent_id, index)
                walk(task.children, task.id)

        walk(self.tasks, None)
        return found

    def find_task(self, task_id: str | None) -> TodoTask | None:
        if task_id is None:
            return None
        entry = self._scan().get(task_id)
        return entry[0] if entry else None

    def locate(self, task_id: str) -> tuple[str | None, int] | None:
        """回傳 (父項 id, 索引)；找不到回傳 None。"""
        entry = self._scan().get(task_id)
        return (entry[1], entry[2]) if entry else None

    def parent_id_of(self, task_id: str) -> str | None:
        located = self.locate(task_id)
        return located[0] if located else None

    def container(self, parent_id: str | None) -> list[TodoTask] | None:
        """回傳父項的子任務清單（parent_id 為 None 代表頂層）；父項不存在回傳 None。"""
        if parent_id is None:
            return self.tasks
        parent = self.find_task(parent_id)
        return parent.children if parent else None

    def ancestors_of(self, task_id: str) -> list[TodoTask]:
        """回傳祖先清單，由最近的父項到最上層。"""
        scan = self._scan()
        result: list[TodoTask] = []
        entry = scan.get(task_id)
        while entry and entry[1] is not None:
            entry = scan.get(entry[1])
            if entry:
                result.append(entry[0])
        return result

    def is_descendant(self, ancestor_id: str, task_id: str) -> bool:
        """task_id 是否位於 ancestor_id 的子樹內（不含自身）。"""
        return any(a.id == ancestor_id for a in self.ancestors_of(task_id))

    def document_order(self) -> dict[str, int]:
        """前序走訪順序：{id: 序號}。"""
        return {tid: i for i, tid in enumerate(self._scan())}

    def iter_tasks(self) -> Iterator[TodoTask]:
        """前序走訪所有任務。"""
        for task in self.tasks:
            yield from iter_subtree(task)

    def detach(self, task_id: str) -> tuple[TodoTask, str | None, int] | None:
        """從樹中移除任務，回傳 (任務, 原父項 id, 原索引)；不存在回傳 None。"""
        entry = self._scan().get(task_id)
        if entry is None:
            return None
        task, parent_id, index = entry
        siblings = self.container(parent_id)
        if siblings is None:
            return None
        del siblings[index]
        return task, parent_id, index

    def attach(self, task: TodoTask, parent_id: str | None, index: int | None = None) -> None:
        """把任務插入父項（None 為頂層）；index 為 None 或越界時附加到最後。"""
        siblings = self.container(parent_id)
        if siblings is None:
            siblings = self.tasks
        if index is None or index > len(siblings):
            siblings.append(task)
        else:
            siblings.insert(max(index, 0), task)

    def apply_done(self, task: TodoTask, value: bool) -> dict[str, bool]:
        """設定完成狀態並連鎖（子孫同值；取消完成時祖先也取消）；回傳 {id: 原狀態}。"""
        original: dict[str, bool] = {}
        affected = list(iter_subtree(task))
        if not value:
            affected.extend(self.ancestors_of(task.id))
        for item in affected:
            if item.is_done != value:
                original[item.id] = item.is_done
                item.is_done = value
        return original

    def restore_done(self, states: dict[str, bool]) -> None:
        """依 {id: 狀態} 還原完成狀態。"""
        scan = self._scan()
        for tid, state in states.items():
            if tid in scan:
                scan[tid][0].is_done = state

    # ---- 命令執行 ----

    def _run(self, command: TodoCommand) -> bool:
        if not command.execute():
            return False
        self.history.record(command)
        self._changed()
        return True

    def _changed(self) -> None:
        self._persist()
        self.notify(Events.TODO_UPDATED, self.pending_count())

    @staticmethod
    def _clean(fields: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(fields)
        if 'text' in cleaned:
            cleaned['text'] = str(cleaned['text']).strip()
        for key in ('project', 'link'):
            if key in cleaned:
                cleaned[key] = (str(cleaned[key]).strip() or None) if cleaned[key] else None
        if 'priority' in cleaned and cleaned['priority'] not in PRIORITIES:
            cleaned['priority'] = PRIORITY_NORMAL
        return cleaned

    def add_task(self, text: str, parent_id: str | None = None, **fields: Any) -> TodoTask | None:
        """新增任務；內容為空或父項不存在時回傳 None。"""
        fields = self._clean({'text': text, **fields})
        if not fields['text']:
            return None
        command = AddTaskCommand(self, fields.pop('text'), parent_id, **fields)
        return command.task if self._run(command) else None

    def update_task(self, task_id: str, **changes: Any) -> bool:
        """更新任務欄位（text/link/priority/due_date/start_date/is_done/project）。"""
        changes = self._clean(changes)
        if 'text' in changes and not changes['text']:
            return False
        return self._run(UpdateTaskCommand(self, task_id, **changes))

    def delete_tasks(self, task_ids: list[str]) -> bool:
        return self._run(DeleteTasksCommand(self, task_ids))

    def toggle_done(self, task_ids: list[str]) -> bool:
        return self._run(ToggleDoneCommand(self, task_ids))

    def move_task(self, task_id: str, target_id: str | None, position: str) -> bool:
        """移動任務；position 見 ``core.todo_commands.POSITION_*``。"""
        return self._run(MoveTaskCommand(self, task_id, target_id, position))

    def remove_link(self, task_id: str) -> bool:
        return self._run(RemoveLinkCommand(self, task_id))

    def undo(self) -> bool:
        command = self.history.undo()
        if command is None:
            return False
        command.undo()
        self._changed()
        return True

    def redo(self) -> bool:
        command = self.history.redo()
        if command is None:
            return False
        command.execute()
        self._changed()
        return True

    # ---- 匯入／匯出／統計 ----

    def import_file(self, path: str | Path) -> int:
        """
        匯入 todo_list 的 tasks.json（或本程式的 todos.json），附加到頂層。

        Returns:
            匯入的頂層任務數

        Raises:
            OSError: 無法讀取
            ValueError: 格式不正確
        """
        imported = read_tasks_file(Path(path))
        existing = {task.id for task in self.iter_tasks()}
        for top in imported:
            for task in iter_subtree(top):
                if task.id in existing:
                    task.id = str(uuid.uuid4())
                existing.add(task.id)
        return len(imported) if self._run(ImportTasksCommand(self, imported)) else 0

    def export_markdown(self) -> str:
        return export_markdown(self.tasks)

    def stats(self) -> tuple[int, int, int]:
        """回傳 (總數, 待辦數, 完成數)。"""
        return TodoFilter.count_tasks(self.tasks)

    def pending_count(self) -> int:
        return self.stats()[1]

    # ---- 設定與提醒 ----

    def is_remind_enabled(self) -> bool:
        return bool(self.config_manager.load_config(read_only=True).get('todo', {}).get('remind_enabled', True))

    def set_remind_enabled(self, enabled: bool) -> None:
        """寫入「整點提醒到期待辦」開關。"""
        config = self.config_manager.load_config()
        config.setdefault('todo', {})['remind_enabled'] = bool(enabled)
        self.config_manager.save_config(config)

    def check(self, now: datetime | None = None, config: dict[str, Any] | None = None) -> None:
        """整點時提醒今日到期／逾期的待辦；勿擾或整點啟動暫停時略過。"""
        current = now if now is not None else datetime.now()
        config_data = config if config is not None else self.config_manager.load_config(read_only=True)
        if config_data.get('on_vacation', False):
            return
        if config_data.get('hourly_web_reminder', {}).get('paused', False):
            return
        due = self.strategy.check(config_data.get('todo', {}), self.tasks, current)
        if due:
            self.notify(Events.TODO_DUE, due)
