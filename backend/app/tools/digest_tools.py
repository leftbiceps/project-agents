"""Инструменты дайджестов (Digest Agent).

generate_* собирают и СРАЗУ сохраняют дайджест в data/digests.json,
поэтому отдельно вызывать save_digest не обязательно (он нужен для
произвольного/кастомного контента).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from pydantic import BaseModel, Field

from ..models import Digest, Task, TaskStatus
from ..scoring import rank_tasks, recommend_next
from ..storage import storage
from ..utils import events_on_day, parse_date
from .registry import tool

_DONE = {TaskStatus.done, TaskStatus.archived}


class DigestDayIn(BaseModel):
    date: Optional[str] = Field(None, description="Дата; по умолчанию сегодня")


class SaveDigestIn(BaseModel):
    kind: str = Field(..., description="morning | evening")
    date: str
    content: str
    data: dict = Field(default_factory=dict)


class ListDigestsIn(BaseModel):
    kind: Optional[str] = None
    limit: int = 20


def _overdue(tasks: list[Task], ref: datetime) -> list[Task]:
    start_today = datetime.combine(ref.date(), time(0, 0))
    return [t for t in tasks
            if t.status not in _DONE and t.deadline and t.deadline < start_today]


def _due_on(tasks: list[Task], d: date) -> list[Task]:
    return [t for t in tasks
            if t.deadline and t.deadline.date() == d and t.status not in _DONE]


@tool("generate_morning_digest",
      "Собрать и сохранить утренний дайджест (задачи, события, просрочки, "
      "рекомендация дня).", DigestDayIn, output_hint="Digest")
def generate_morning_digest(inp: DigestDayIn) -> Digest:
    d = parse_date(inp.date) if inp.date else date.today()
    ref = datetime.combine(d, time(9, 0))
    tasks = storage.tasks.all()
    events = events_on_day(storage.events.all(), d)
    due_today = _due_on(tasks, d)
    overdue = _overdue(tasks, ref)
    rec = recommend_next(tasks, storage.memory.all(), ref)
    plan = [t for t, _, _ in rank_tasks(tasks, ref)[:3]]

    lines = [f"# Утренний дайджест — {d.isoformat()}", ""]
    lines.append("## Задачи на сегодня")
    if due_today:
        lines += [f"- [{t.priority.value}] {t.title}" for t in due_today]
    else:
        lines.append("- Задач с дедлайном сегодня нет.")
    lines.append("\n## События календаря")
    if events:
        lines += [f"- {e.start_datetime:%H:%M}–{e.end_datetime:%H:%M} {e.title}"
                  for e in events]
    else:
        lines.append("- Событий нет.")
    lines.append("\n## Просроченные задачи")
    lines += ([f"- {t.title} (дедлайн {t.deadline:%Y-%m-%d})" for t in overdue]
              or ["- Нет просрочек 🎯"])
    lines.append("\n## Главная рекомендация")
    lines.append(f"- {rec['explanation']}")
    if rec["risks"]:
        lines.append("\n## Риски")
        lines += [f"- {r}" for r in rec["risks"]]
    lines.append("\n## Короткий план")
    lines += ([f"{i + 1}. {t.title}" for i, t in enumerate(plan)]
              or ["1. Свободный день."])

    digest = Digest(
        kind="morning",
        date=d.isoformat(),
        content="\n".join(lines),
        data={
            "due_today": [t.model_dump(mode="json") for t in due_today],
            "events": [e.model_dump(mode="json") for e in events],
            "overdue": [t.model_dump(mode="json") for t in overdue],
            "recommendation": rec,
        },
    )
    return storage.digests.add(digest)


@tool("generate_evening_digest",
      "Собрать и сохранить вечерний дайджест (что сделано, что нет, что "
      "перенести, план на завтра).", DigestDayIn, output_hint="Digest")
def generate_evening_digest(inp: DigestDayIn) -> Digest:
    d = parse_date(inp.date) if inp.date else date.today()
    ref = datetime.combine(d, time(21, 0))
    tomorrow = d + timedelta(days=1)
    tasks = storage.tasks.all()
    events = events_on_day(storage.events.all(), d)

    completed = [t for t in tasks
                 if t.status == TaskStatus.done and t.updated_at.date() == d]
    planned = _due_on(tasks, d) + [t for t in tasks
                                   if t.status == TaskStatus.in_progress]
    planned = list({t.id: t for t in planned}.values())
    not_done = [t for t in planned if t.status not in _DONE]
    to_reschedule = _overdue(tasks, ref + timedelta(days=1))
    blocked = [t for t in tasks if t.status == TaskStatus.blocked]
    plan_tomorrow = [t for t, _, _ in rank_tasks(tasks,
                     datetime.combine(tomorrow, time(9, 0)))[:3]]

    lines = [f"# Вечерний дайджест — {d.isoformat()}", ""]
    lines.append("## Было запланировано")
    lines += ([f"- {t.title}" for t in planned] or ["- Ничего особенного."])
    lines.append("\n## Выполнено")
    lines += ([f"- ✅ {t.title}" for t in completed] or ["- Пока ничего не закрыто."])
    lines.append("\n## Не выполнено")
    lines += ([f"- ⬜ {t.title}" for t in not_done] or ["- Всё закрыто 🎉"])
    lines.append("\n## Стоит перенести")
    lines += ([f"- {t.title} → завтра" for t in to_reschedule] or ["- Нет."])
    if blocked:
        lines.append("\n## Вопрос по спорным задачам")
        lines += [f"- «{t.title}» заблокирована — что с ней делать?" for t in blocked]
    lines.append("\n## План на завтра")
    lines += ([f"{i + 1}. {t.title}" for i, t in enumerate(plan_tomorrow)]
              or ["1. Свободный день."])

    digest = Digest(
        kind="evening",
        date=d.isoformat(),
        content="\n".join(lines),
        data={
            "completed": [t.model_dump(mode="json") for t in completed],
            "not_done": [t.model_dump(mode="json") for t in not_done],
            "to_reschedule": [t.model_dump(mode="json") for t in to_reschedule],
            "events": [e.model_dump(mode="json") for e in events],
            "plan_tomorrow": [t.model_dump(mode="json") for t in plan_tomorrow],
        },
    )
    return storage.digests.add(digest)


@tool("save_digest", "Сохранить произвольный дайджест.", SaveDigestIn,
      output_hint="Digest")
def save_digest(inp: SaveDigestIn) -> Digest:
    digest = Digest(kind=inp.kind, date=inp.date, content=inp.content, data=inp.data)
    return storage.digests.add(digest)


@tool("list_digests", "История сохранённых дайджестов (новые сверху).",
      ListDigestsIn, output_hint="Digest[]")
def list_digests(inp: ListDigestsIn) -> list[Digest]:
    items = storage.digests.all()
    if inp.kind:
        items = [x for x in items if x.kind == inp.kind]
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[: inp.limit]
