"""待辦事項 Command 模式：每個操作皆可執行與復原，由 TodoService 記錄於歷史堆疊。"""
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from core.todo_task import TodoTask

if TYPE_CHECKING:
    from services.todo_service import TodoService

POSITION_BEFORE = "before"
POSITION_AFTER = "after"
POSITION_INTO = "into"
POSITION_PROMOTE = "promote"
POSITION_ROOT = "root"
POSITIONS = (POSITION_BEFORE, POSITION_AFTER, POSITION_INTO, POSITION_PROMOTE, POSITION_ROOT)

# UpdateTaskCommand 允許變更的欄位
UPDATABLE_FIELDS = frozenset({"text", "link", "priority", "due_date", "start_date", "is_done", "project"})


def iter_subtree(task: TodoTask) -> Iterator[TodoTask]:
    """前序走訪任務與其所有子孫。"""
    yield task
    for child in task.children:
        yield from iter_subtree(child)


class TodoCommand(ABC):
    """可復原的待辦操作。"""

    def __init__(self, service: "TodoService") -> None:
        self.service = service

    @abstractmethod
    def execute(self) -> bool:
        """執行操作；回傳 False 表示無實際變更（不記入歷史）。"""
        raise NotImplementedError

    @abstractmethod
    def undo(self) -> None:
        """還原 execute 造成的變更。"""
        raise NotImplementedError


class CommandHistory:
    """復原／重做堆疊。"""

    MAX_HISTORY_SIZE = 50

    def __init__(self) -> None:
        self.undo_stack: list[TodoCommand] = []
        self.redo_stack: list[TodoCommand] = []

    def record(self, command: TodoCommand) -> None:
        """記錄新執行的命令，並清空重做堆疊。"""
        self.undo_stack.append(command)
        if len(self.undo_stack) > self.MAX_HISTORY_SIZE:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> TodoCommand | None:
        """取出最近命令並移到重做堆疊；實際還原由呼叫端執行。"""
        if not self.undo_stack:
            return None
        command = self.undo_stack.pop()
        self.redo_stack.append(command)
        return command

    def redo(self) -> TodoCommand | None:
        """取出最近被復原的命令並移回復原堆疊；實際重做由呼叫端執行。"""
        if not self.redo_stack:
            return None
        command = self.redo_stack.pop()
        self.undo_stack.append(command)
        return command

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()


class AddTaskCommand(TodoCommand):
    """新增任務（可指定父項；父項有專案而自身沒有時繼承）。"""

    def __init__(
        self, service: "TodoService", text: str, parent_id: str | None = None, **fields: Any,
    ) -> None:
        super().__init__(service)
        self._text = text
        self._parent_id = parent_id
        self._fields = fields
        self._task: TodoTask | None = None

    @property
    def task(self) -> TodoTask | None:
        return self._task

    def execute(self) -> bool:
        siblings = self.service.container(self._parent_id)
        if siblings is None:
            return False
        if self._task is None:
            task = TodoTask(self._text, **self._fields)
            parent = self.service.find_task(self._parent_id) if self._parent_id else None
            if parent is not None and not task.project and parent.project:
                task.project = parent.project
            self._task = task
        siblings.append(self._task)
        return True

    def undo(self) -> None:
        if self._task is not None:
            self.service.detach(self._task.id)


class DeleteTasksCommand(TodoCommand):
    """刪除多個任務（選取到祖先時略過其子孫）。"""

    def __init__(self, service: "TodoService", task_ids: list[str]) -> None:
        super().__init__(service)
        self._task_ids = list(task_ids)
        self._removed: list[tuple[TodoTask, str | None, int]] = []

    def execute(self) -> bool:
        selected = {tid for tid in self._task_ids if self.service.find_task(tid)}
        targets = [
            tid for tid in selected
            if not any(a.id in selected for a in self.service.ancestors_of(tid))
        ]
        order = self.service.document_order()
        targets.sort(key=lambda tid: order[tid], reverse=True)
        self._removed = []
        for tid in targets:
            removed = self.service.detach(tid)
            if removed is not None:
                self._removed.append(removed)
        return bool(self._removed)

    def undo(self) -> None:
        for task, parent_id, index in reversed(self._removed):
            self.service.attach(task, parent_id, index)


class UpdateTaskCommand(TodoCommand):
    """更新任務欄位；專案變更會同步到子孫，完成狀態變更會連鎖。"""

    def __init__(self, service: "TodoService", task_id: str, **changes: Any) -> None:
        super().__init__(service)
        self._task_id = task_id
        self._changes = {k: v for k, v in changes.items() if k in UPDATABLE_FIELDS}
        self._old_values: dict[str, Any] = {}
        self._old_projects: dict[str, str | None] = {}
        self._old_done: dict[str, bool] = {}

    def execute(self) -> bool:
        task = self.service.find_task(self._task_id)
        if task is None:
            return False
        self._old_values = {}
        self._old_projects = {}
        self._old_done = {}
        changed = False
        for name, value in self._changes.items():
            if name == "is_done":
                if bool(value) != task.is_done:
                    self._old_done = self.service.apply_done(task, bool(value))
                    changed = True
                continue
            if getattr(task, name) == value:
                continue
            self._old_values[name] = getattr(task, name)
            setattr(task, name, value)
            changed = True
            if name == "project":
                for child in task.children:
                    for sub in iter_subtree(child):
                        self._old_projects[sub.id] = sub.project
                        sub.project = value
        return changed

    def undo(self) -> None:
        task = self.service.find_task(self._task_id)
        if task is None:
            return
        for name, value in self._old_values.items():
            setattr(task, name, value)
        for tid, project in self._old_projects.items():
            sub = self.service.find_task(tid)
            if sub is not None:
                sub.project = project
        self.service.restore_done(self._old_done)


class ToggleDoneCommand(TodoCommand):
    """切換完成狀態：完成時子孫一併完成；取消完成時祖先與子孫一併取消。"""

    def __init__(self, service: "TodoService", task_ids: list[str]) -> None:
        super().__init__(service)
        self._task_ids = list(task_ids)
        self._original: dict[str, bool] = {}

    def execute(self) -> bool:
        selected = {tid for tid in self._task_ids if self.service.find_task(tid)}
        targets = [
            tid for tid in selected
            if not any(a.id in selected for a in self.service.ancestors_of(tid))
        ]
        order = self.service.document_order()
        targets.sort(key=lambda tid: order[tid])
        self._original = {}
        for tid in targets:
            task = self.service.find_task(tid)
            if task is None:
                continue
            for changed_id, old in self.service.apply_done(task, not task.is_done).items():
                self._original.setdefault(changed_id, old)
        return bool(self._original)

    def undo(self) -> None:
        self.service.restore_done(self._original)


class MoveTaskCommand(TodoCommand):
    """移動任務到目標之前／之後／成為其子項，或提升一層／移到頂層。"""

    def __init__(
        self, service: "TodoService", task_id: str, target_id: str | None, position: str,
    ) -> None:
        super().__init__(service)
        self._task_id = task_id
        self._target_id = target_id
        self._position = position
        self._origin: tuple[str | None, int] | None = None
        self._old_projects: dict[str, str | None] = {}

    def _destination(self, task: TodoTask) -> tuple[str | None, int | None] | None:
        """回傳移除任務「之後」的目標 (父項 id, 插入位置)；不合法時回傳 None。"""
        service = self.service
        if self._position == POSITION_ROOT:
            return None, None
        if self._position == POSITION_PROMOTE:
            parent_id = service.parent_id_of(task.id)
            if parent_id is None:
                return None
            grand_id = service.parent_id_of(parent_id)
            index = service.locate(parent_id)
            return None if index is None else (grand_id, index[1] + 1)
        if self._target_id is None or self._target_id == task.id:
            return None
        target = service.find_task(self._target_id)
        if target is None or service.is_descendant(task.id, target.id):
            return None
        if self._position == POSITION_INTO:
            return target.id, None
        if self._position in (POSITION_BEFORE, POSITION_AFTER):
            located = service.locate(target.id)
            if located is None:
                return None
            parent_id, index = located
            own = service.locate(task.id)
            if own is not None and own[0] == parent_id and own[1] < index:
                index -= 1  # 先移除自身，後方索引前移
            return parent_id, index + (1 if self._position == POSITION_AFTER else 0)
        return None

    def execute(self) -> bool:
        task = self.service.find_task(self._task_id)
        if task is None or self._position not in POSITIONS:
            return False
        destination = self._destination(task)
        origin = self.service.locate(task.id)
        if destination is None or origin is None:
            return False
        parent_id, index = destination
        self._origin = origin
        self._old_projects = {}
        self.service.detach(task.id)
        self.service.attach(task, parent_id, index)
        if self.service.locate(task.id) == origin:
            return False
        new_parent = self.service.find_task(parent_id) if parent_id else None
        if new_parent is not None and new_parent.project and not task.project:
            for sub in iter_subtree(task):
                self._old_projects[sub.id] = sub.project
                sub.project = new_parent.project
        return True

    def undo(self) -> None:
        task = self.service.find_task(self._task_id)
        if task is None or self._origin is None:
            return
        self.service.detach(task.id)
        self.service.attach(task, self._origin[0], self._origin[1])
        for tid, project in self._old_projects.items():
            sub = self.service.find_task(tid)
            if sub is not None:
                sub.project = project


class RemoveLinkCommand(TodoCommand):
    """移除任務連結。"""

    def __init__(self, service: "TodoService", task_id: str) -> None:
        super().__init__(service)
        self._task_id = task_id
        self._old_link: str | None = None

    def execute(self) -> bool:
        task = self.service.find_task(self._task_id)
        if task is None or not task.link:
            return False
        self._old_link = task.link
        task.link = None
        return True

    def undo(self) -> None:
        task = self.service.find_task(self._task_id)
        if task is not None:
            task.link = self._old_link


class ImportTasksCommand(TodoCommand):
    """將外部任務附加到頂層。"""

    def __init__(self, service: "TodoService", tasks: list[TodoTask]) -> None:
        super().__init__(service)
        self._tasks = tasks

    def execute(self) -> bool:
        if not self._tasks:
            return False
        for task in self._tasks:
            self.service.attach(task, None, None)
        return True

    def undo(self) -> None:
        for task in self._tasks:
            self.service.detach(task.id)
