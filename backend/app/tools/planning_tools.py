"""Инструменты планирования (Planning Agent)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from pydantic import BaseModel, Field

from ..models import (
    CalendarEvent,
    Checklist,
    ChecklistItem,
    EventType,
    Priority,
    Task,
    TaskStatus,
    now,
)
from ..scoring import rank_tasks
from ..storage import storage
from ..utils import (
    events_on_day,
    find_free_slots,
    parse_date,
    parse_dt,
    working_window,
)
from .registry import ToolError, tool

_DONE = {TaskStatus.done, TaskStatus.archived}

# Эвристики длительности по ключевым словам (минуты).
_DURATION_HINTS = [
    (("презентац", "слайд", "deck", "pitch"), 120),
    (("репетир", "прогон", "demo", "выступл"), 45),
    (("прочитать", "статья", "почитать", "read", "изуч"), 60),
    (("письмо", "email", "почт", "mail", "ответ"), 20),
    (("встреч", "созвон", "звонок", "call", "митинг"), 30),
    (("структур", "план", "набросать", "outline"), 40),
    (("собрать материал", "research", "найти", "ресёрч"), 50),
]


class EstimateIn(BaseModel):
    title: str
    description: str = ""


class SplitGoalIn(BaseModel):
    goal: str = Field(..., description="ОДНА цель одной фразой (станет заголовком задачи)")
    steps: list[str] = Field(
        default_factory=list,
        description="Шаги-пункты чеклиста для этой цели. Если пусто — типовой шаблон.",
    )
    project: Optional[str] = None
    priority: Priority = Priority.medium
    deadline: Optional[str] = None


class ScheduleIn(BaseModel):
    task_ids: list[str]
    start_date: Optional[str] = None
    horizon_days: int = 7
    work_day_start: str = "09:00"
    work_day_end: str = "19:00"
    default_minutes: int = 60


class RescheduleIn(BaseModel):
    within_days: int = 1


@tool("estimate_task_duration",
      "Оценить длительность задачи в минутах (эвристика по ключевым словам).",
      EstimateIn, output_hint="{minutes, rationale}")
def estimate_task_duration(inp: EstimateIn) -> dict:
    text = f"{inp.title} {inp.description}".lower()
    for keywords, minutes in _DURATION_HINTS:
        if any(k in text for k in keywords):
            return {"minutes": minutes,
                    "rationale": f"Тип работы распознан по ключевым словам → ~{minutes} мин."}
    minutes = 30 if len(inp.title) < 40 else 60
    return {"minutes": minutes, "rationale": "Оценка по умолчанию."}


@tool("split_goal_into_tasks",
      "Разбить ОДНУ цель на ОДНУ задачу + чеклист шагов (план). Шаги становятся "
      "пунктами чеклиста, а не отдельными задачами. Для нескольких РАЗНЫХ дел "
      "вызывай этот инструмент по разу на каждое (или create_task на каждое).",
      SplitGoalIn, output_hint="{task: Task, checklist: Checklist}")
def split_goal_into_tasks(inp: SplitGoalIn) -> dict:
    steps = inp.steps or [
        "Собрать материалы",
        "Сделать структуру",
        "Подготовить черновик",
        "Ревью и правки",
        "Финализировать",
    ]
    project = inp.project or inp.goal[:40]
    est = estimate_task_duration(EstimateIn(title=inp.goal))["minutes"]
    task = Task(title=inp.goal, status=TaskStatus.todo, priority=inp.priority,
                project=project, estimated_minutes=est,
                deadline=parse_dt(inp.deadline), source="planning")
    storage.tasks.add(task)
    checklist = Checklist(task_id=task.id, title="План",
                          items=[ChecklistItem(text=s) for s in steps])
    storage.checklists.add(checklist)
    storage.tasks.update(task.id, {"checklist_ids": [checklist.id]})
    return {"task": task.model_dump(mode="json"),
            "checklist": checklist.model_dump(mode="json")}


@tool("schedule_tasks_to_free_slots",
      "Распределить задачи по свободным окнам календаря и создать события "
      "(type=task_block), связанные с задачами.", ScheduleIn,
      output_hint="{events: CalendarEvent[], warnings: []}")
def schedule_tasks_to_free_slots(inp: ScheduleIn) -> dict:
    start = parse_date(inp.start_date) if inp.start_date else date.today()
    # Локальная копия занятости (существующие + создаваемые события).
    busy: list[CalendarEvent] = list(storage.events.all())
    created: list[CalendarEvent] = []
    warnings: list[str] = []

    # Планируем в порядке приоритета/срочности.
    tasks = [storage.tasks.get(tid) for tid in inp.task_ids]
    tasks = [t for t in tasks if t and t.status not in _DONE]
    order = [t for t, _, _ in rank_tasks(tasks)] or tasks

    for task in order:
        duration = task.estimated_minutes or inp.default_minutes
        placed = False
        for day_offset in range(inp.horizon_days):
            d = start + timedelta(days=day_offset)
            win_start, win_end = working_window(d, inp.work_day_start, inp.work_day_end)
            # не планируем в прошлое
            win_start = max(win_start, now())
            if win_start >= win_end:
                continue
            slots = find_free_slots(win_start, win_end,
                                    events_on_day(busy, d), duration)
            if slots:
                s_start, _ = slots[0]
                s_end = s_start + timedelta(minutes=duration)
                event = CalendarEvent(
                    title=f"Работа: {task.title}",
                    description=f"Автопланирование под задачу {task.id}",
                    start_datetime=s_start,
                    end_datetime=s_end,
                    type=EventType.task_block,
                    linked_task_id=task.id,
                )
                storage.events.add(event)
                busy.append(event)
                created.append(event)
                # фиксируем дедлайн/статус
                storage.tasks.update(task.id, {
                    "deadline": (task.deadline or s_end),
                    "status": TaskStatus.todo.value,
                })
                placed = True
                break
        if not placed:
            warnings.append(
                f"Не нашлось свободного окна {duration} мин для «{task.title}» "
                f"в ближайшие {inp.horizon_days} дн."
            )

    return {"events": [e.model_dump(mode="json") for e in created],
            "warnings": warnings}


@tool("reschedule_overdue_tasks",
      "Перенести просроченные/незавершённые задачи на ближайшие дни.",
      RescheduleIn, output_hint="{moved: Task[]}")
def reschedule_overdue_tasks(inp: RescheduleIn) -> dict:
    ref = now()
    new_deadline = datetime.combine(
        (ref + timedelta(days=inp.within_days)).date(), time(18, 0))
    moved = []
    for t in storage.tasks.all():
        if t.status in _DONE:
            continue
        is_overdue = t.deadline and t.deadline < ref
        if is_overdue:
            updated = storage.tasks.update(t.id, {
                "deadline": new_deadline,
                "status": (TaskStatus.todo.value
                           if t.status == TaskStatus.blocked
                           else t.status.value),
            })
            if updated:
                moved.append(updated)
    return {"moved": [t.model_dump(mode="json") for t in moved],
            "new_deadline": new_deadline.isoformat(timespec="minutes")}
