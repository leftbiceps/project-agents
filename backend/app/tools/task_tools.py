"""Инструменты для задач и чеклистов (Task Agent)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..models import (
    Checklist,
    ChecklistItem,
    Priority,
    Task,
    TaskStatus,
    now,
)
from ..storage import storage
from ..utils import parse_dt
from .registry import ToolError, tool


# --------------------------------------------------------------------------- #
#  Схемы входа
# --------------------------------------------------------------------------- #
class CreateTaskIn(BaseModel):
    title: str = Field(..., description="Краткое название задачи")
    description: str = ""
    priority: Priority = Priority.medium
    status: TaskStatus = TaskStatus.backlog
    deadline: Optional[str] = Field(None, description="Дедлайн в ISO, напр. 2026-06-10T18:00")
    tags: list[str] = Field(default_factory=list)
    project: Optional[str] = None
    estimated_minutes: Optional[int] = None
    source: str = "chat"


class UpdateTaskIn(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[TaskStatus] = None
    deadline: Optional[str] = None
    tags: Optional[list[str]] = None
    project: Optional[str] = None
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None


class TaskIdIn(BaseModel):
    id: str


class ListTasksIn(BaseModel):
    status: Optional[TaskStatus] = None
    project: Optional[str] = None
    tag: Optional[str] = None
    include_archived: bool = False


class SearchTasksIn(BaseModel):
    query: str


class SetStatusIn(BaseModel):
    id: str
    status: TaskStatus


class SetPriorityIn(BaseModel):
    id: str
    priority: Priority


class CreateChecklistIn(BaseModel):
    task_id: Optional[str] = Field(None, description="К какой задаче привязать")
    title: str = "Чеклист"
    items: list[str] = Field(default_factory=list, description="Тексты пунктов")


class AddItemIn(BaseModel):
    checklist_id: str
    text: str


class UpdateItemIn(BaseModel):
    checklist_id: str
    item_id: str
    text: Optional[str] = None
    done: Optional[bool] = None


class CompleteItemIn(BaseModel):
    checklist_id: str
    item_id: str


# --------------------------------------------------------------------------- #
#  Реализация
# --------------------------------------------------------------------------- #
@tool("create_task", "Создать новую задачу.", CreateTaskIn,
      output_hint="Task")
def create_task(inp: CreateTaskIn) -> Task:
    task = Task(
        title=inp.title,
        description=inp.description,
        priority=inp.priority,
        status=inp.status,
        deadline=parse_dt(inp.deadline),
        tags=inp.tags,
        project=inp.project,
        estimated_minutes=inp.estimated_minutes,
        source=inp.source,
    )
    return storage.tasks.add(task)


@tool("update_task", "Обновить поля задачи по id.", UpdateTaskIn,
      output_hint="Task")
def update_task(inp: UpdateTaskIn) -> Task:
    changes = inp.model_dump(exclude={"id"}, exclude_none=True)
    if "deadline" in changes:
        changes["deadline"] = parse_dt(changes["deadline"])
    updated = storage.tasks.update(inp.id, changes)
    if not updated:
        raise ToolError(f"Задача {inp.id} не найдена")
    return updated


@tool("delete_task", "Удалить задачу по id.", TaskIdIn,
      output_hint="{deleted: bool}")
def delete_task(inp: TaskIdIn) -> dict:
    return {"deleted": storage.tasks.delete(inp.id), "id": inp.id}


@tool("get_task", "Получить задачу по id.", TaskIdIn, output_hint="Task | null")
def get_task(inp: TaskIdIn) -> Optional[Task]:
    task = storage.tasks.get(inp.id)
    if not task:
        raise ToolError(f"Задача {inp.id} не найдена")
    return task


@tool("list_tasks", "Список задач с фильтрами по статусу/проекту/тегу.",
      ListTasksIn, output_hint="Task[]")
def list_tasks(inp: ListTasksIn) -> list[Task]:
    result = storage.tasks.all()
    if not inp.include_archived:
        result = [t for t in result if t.status != TaskStatus.archived]
    if inp.status:
        result = [t for t in result if t.status == inp.status]
    if inp.project:
        result = [t for t in result if t.project == inp.project]
    if inp.tag:
        result = [t for t in result if inp.tag in t.tags]
    return sorted(result, key=lambda t: t.created_at)


@tool("search_tasks", "Поиск задач по подстроке в названии/описании/тегах.",
      SearchTasksIn, output_hint="Task[]")
def search_tasks(inp: SearchTasksIn) -> list[Task]:
    q = inp.query.lower().strip()
    out = []
    for t in storage.tasks.all():
        hay = " ".join([t.title, t.description, " ".join(t.tags),
                        t.project or ""]).lower()
        if q in hay:
            out.append(t)
    return out


@tool("set_task_status", "Изменить статус задачи.", SetStatusIn,
      output_hint="Task")
def set_task_status(inp: SetStatusIn) -> Task:
    updated = storage.tasks.update(inp.id, {"status": inp.status.value})
    if not updated:
        raise ToolError(f"Задача {inp.id} не найдена")
    return updated


@tool("set_task_priority", "Изменить приоритет задачи.", SetPriorityIn,
      output_hint="Task")
def set_task_priority(inp: SetPriorityIn) -> Task:
    updated = storage.tasks.update(inp.id, {"priority": inp.priority.value})
    if not updated:
        raise ToolError(f"Задача {inp.id} не найдена")
    return updated


@tool("create_checklist",
      "Создать чеклист (опц. привязать к задаче) и наполнить пунктами.",
      CreateChecklistIn, output_hint="Checklist")
def create_checklist(inp: CreateChecklistIn) -> Checklist:
    items = [ChecklistItem(text=t) for t in inp.items]
    cl = Checklist(task_id=inp.task_id, title=inp.title, items=items)
    storage.checklists.add(cl)
    if inp.task_id:
        task = storage.tasks.get(inp.task_id)
        if not task:
            raise ToolError(f"Задача {inp.task_id} не найдена")
        ids = task.checklist_ids + [cl.id]
        storage.tasks.update(inp.task_id, {"checklist_ids": ids})
    return cl


@tool("add_checklist_item", "Добавить пункт в чеклист.", AddItemIn,
      output_hint="Checklist")
def add_checklist_item(inp: AddItemIn) -> Checklist:
    cl = storage.checklists.get(inp.checklist_id)
    if not cl:
        raise ToolError(f"Чеклист {inp.checklist_id} не найден")
    cl.items.append(ChecklistItem(text=inp.text))
    cl.updated_at = now()
    return storage.checklists.replace(cl)


@tool("update_checklist_item", "Изменить текст и/или статус пункта чеклиста.",
      UpdateItemIn, output_hint="Checklist")
def update_checklist_item(inp: UpdateItemIn) -> Checklist:
    cl = storage.checklists.get(inp.checklist_id)
    if not cl:
        raise ToolError(f"Чеклист {inp.checklist_id} не найден")
    found = False
    for item in cl.items:
        if item.id == inp.item_id:
            if inp.text is not None:
                item.text = inp.text
            if inp.done is not None:
                item.done = inp.done
                item.done_at = now() if inp.done else None
            item.updated_at = now()
            found = True
            break
    if not found:
        raise ToolError(f"Пункт {inp.item_id} не найден")
    cl.updated_at = now()
    return storage.checklists.replace(cl)


@tool("complete_checklist_item", "Отметить пункт чеклиста выполненным.",
      CompleteItemIn, output_hint="Checklist")
def complete_checklist_item(inp: CompleteItemIn) -> Checklist:
    return update_checklist_item(  # переиспользуем логику
        UpdateItemIn(checklist_id=inp.checklist_id, item_id=inp.item_id, done=True)
    )


@tool("get_task_progress",
      "Прогресс по задаче: агрегирует пункты всех связанных чеклистов.",
      TaskIdIn, output_hint="{total, completed, percent, status}")
def get_task_progress(inp: TaskIdIn) -> dict:
    task = storage.tasks.get(inp.id)
    if not task:
        raise ToolError(f"Задача {inp.id} не найдена")
    total = completed = 0
    checklists = []
    for cl_id in task.checklist_ids:
        cl = storage.checklists.get(cl_id)
        if cl:
            total += cl.total
            completed += cl.completed
            checklists.append({"id": cl.id, "title": cl.title,
                               "progress": cl.progress})
    percent = round(completed / total * 100, 1) if total else 0.0
    return {
        "task_id": task.id,
        "title": task.title,
        "status": task.status.value,
        "total_items": total,
        "completed_items": completed,
        "percent": percent,
        "checklists": checklists,
    }
