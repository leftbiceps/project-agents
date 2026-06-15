"""Эвристика приоритизации задач.

Используется как Prioritization Agent'ом (детерминированный режим без LLM),
так и Digest Agent'ом для «главной рекомендации дня». LLM-агент может
переопределить вывод, но эвристика даёт разумную базовую логику.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .models import PRIORITY_WEIGHT, MemoryItem, Priority, Task, TaskStatus

_ACTIVE = {TaskStatus.backlog, TaskStatus.todo,
           TaskStatus.in_progress, TaskStatus.blocked}


def task_score(task: Task, ref: datetime) -> tuple[float, list[str]]:
    """Вернуть (оценка, причины) для задачи."""
    reasons: list[str] = []
    score = PRIORITY_WEIGHT.get(task.priority, 2) * 10.0
    reasons.append(f"приоритет={task.priority.value}")

    if task.deadline:
        delta = task.deadline - ref
        hours = delta.total_seconds() / 3600
        if hours < 0:
            score += 120
            reasons.append(f"просрочена на {abs(int(hours))} ч")
        elif hours <= 24:
            score += 70
            reasons.append("дедлайн в ближайшие 24 ч")
        elif hours <= 72:
            score += 35
            reasons.append("дедлайн в ближайшие 3 дня")
        else:
            score += 10
            reasons.append(f"дедлайн {task.deadline:%Y-%m-%d}")

    if task.status == TaskStatus.in_progress:
        score += 25
        reasons.append("уже в работе — стоит закончить")
    elif task.status == TaskStatus.todo:
        score += 8
    elif task.status == TaskStatus.blocked:
        score -= 60
        reasons.append("заблокирована")

    if task.estimated_minutes and task.estimated_minutes <= 30:
        score += 6
        reasons.append("быстрая задача (≤30 мин)")

    return score, reasons


def rank_tasks(tasks: list[Task], ref: Optional[datetime] = None
               ) -> list[tuple[Task, float, list[str]]]:
    ref = ref or datetime.now()
    scored = [
        (t, *task_score(t, ref))
        for t in tasks
        if t.status in _ACTIVE
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def recommend_next(tasks: list[Task],
                   memory: Optional[list[MemoryItem]] = None,
                   ref: Optional[datetime] = None) -> dict:
    """Главная рекомендация + альтернативы + объяснение + риски."""
    ref = ref or datetime.now()
    ranked = rank_tasks(tasks, ref)
    if not ranked:
        return {
            "main": None,
            "alternatives": [],
            "explanation": "Активных задач нет — можно отдохнуть или "
                           "запланировать что-то новое.",
            "risks": [],
        }

    main_task, _, main_reasons = ranked[0]
    alternatives = [
        {"id": t.id, "title": t.title, "reasons": r}
        for t, _, r in ranked[1:4]
    ]

    risks: list[str] = []
    if main_task.deadline and main_task.deadline < ref:
        risks.append("Задача уже просрочена — дальнейшая отсрочка увеличивает риск.")
    elif main_task.deadline and (main_task.deadline - ref) <= timedelta(hours=48):
        risks.append("До дедлайна < 48 ч: откладывание создаст спешку.")

    mem_hint = ""
    if memory:
        prefs = [m.content for m in memory
                 if m.type.value in ("user_preference", "recurring_routine")]
        if prefs:
            mem_hint = " С учётом ваших предпочтений: " + "; ".join(prefs[:2]) + "."

    explanation = (
        f"Рекомендую «{main_task.title}», потому что "
        + ", ".join(main_reasons) + "." + mem_hint
    )

    return {
        "main": {"id": main_task.id, "title": main_task.title,
                 "status": main_task.status.value, "reasons": main_reasons},
        "alternatives": alternatives,
        "explanation": explanation,
        "risks": risks,
    }
