"""Демо-данные: наполняют storage реалистичным набором задач/событий/памяти.

Используется эндпоинтом POST /demo/seed и удобно для прогонки демо-сценариев.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from .models import now
from .storage import storage
from .tools import calendar_tools as ct
from .tools import memory_tools as mt
from .tools import task_tools as tt


def _at(day_offset: int, hh: int, mm: int) -> str:
    base = (now() + timedelta(days=day_offset)).date()
    return datetime.combine(base, time(hh, mm)).isoformat()


def seed_demo() -> dict:
    storage.reset()

    mt.save_memory(mt.SaveMemoryIn(
        content="Я лучше работаю по утрам", type="user_preference",
        key="утренний человек", source="seed"))
    mt.save_memory(mt.SaveMemoryIn(
        content="Не ставить задачи после 22:00", type="constraint",
        key="без поздних задач", source="seed"))

    pres = tt.create_task(tt.CreateTaskIn(
        title="Подготовить презентацию по проекту", priority="high",
        status="todo", deadline=_at(2, 18, 0), project="Презентация",
        estimated_minutes=120, tags=["учёба", "проект"], source="seed"))
    tt.create_checklist(tt.CreateChecklistIn(
        task_id=pres.id, title="Этапы презентации",
        items=["Собрать материалы", "Сделать структуру", "Подготовить слайды",
               "Прогнать демо", "Отрепетировать выступление"]))

    tt.create_task(tt.CreateTaskIn(
        title="Прочитать статью по теме курса", priority="medium",
        status="todo", deadline=_at(3, 18, 0), estimated_minutes=60,
        tags=["учёба"], source="seed"))
    tt.create_task(tt.CreateTaskIn(
        title="Написать письмо преподавателю", priority="medium",
        status="todo", deadline=_at(1, 12, 0), estimated_minutes=20,
        tags=["учёба"], source="seed"))
    tt.create_task(tt.CreateTaskIn(
        title="Починить баг на проде", priority="urgent",
        status="in_progress", deadline=_at(-1, 18, 0), estimated_minutes=90,
        project="Работа", tags=["работа"], source="seed"))
    tt.create_task(tt.CreateTaskIn(
        title="Купить продукты на неделю", priority="low",
        status="backlog", estimated_minutes=40, source="seed"))

    ct.create_event(ct.CreateEventIn(
        title="Дейли-стендап", start_datetime=_at(0, 10, 0),
        end_datetime=_at(0, 10, 15), type="meeting"))
    ct.create_event(ct.CreateEventIn(
        title="Обед", start_datetime=_at(0, 13, 0),
        end_datetime=_at(0, 14, 0), type="personal"))
    ct.create_event(ct.CreateEventIn(
        title="Лекция по матанализу", start_datetime=_at(1, 11, 0),
        end_datetime=_at(1, 12, 30), type="meeting"))

    return {
        "tasks": storage.tasks.count(),
        "events": storage.events.count(),
        "memory": storage.memory.count(),
        "checklists": storage.checklists.count(),
    }
