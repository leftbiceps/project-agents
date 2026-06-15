"""Reflection Agent (детерминированный).

Проверяет ход и полноту работы: выполнена ли цель, нет ли ошибок инструментов,
конфликтов в календаре, задач без дедлайна, нужно ли подтверждение пользователя.
Возвращает структурированный ReflectionResult.
"""
from __future__ import annotations

from typing import Any

from ..models import ReflectionResult, ToolCall
from ..storage import storage
from .definitions import DESTRUCTIVE_TOOLS

_ACTION_WORDS = ("созда", "добав", "разбей", "запланир", "сплан", "перенес",
                 "запомни", "удали", "распредели", "поставь", "отметь",
                 "сделай", "заведи", "обнови", "измени")


def _g(out: Any, key: str, default: Any = None) -> Any:
    return out.get(key, default) if isinstance(out, dict) else default


def reflect(user_message: str, agent: str,
            tool_calls: list[ToolCall], final_text: str) -> ReflectionResult:
    issues: list[str] = []
    fixes: list[str] = []
    confirm = False
    passed = True
    t = user_message.lower()

    # 1. Ошибки инструментов
    for tc in tool_calls:
        if not tc.ok:
            passed = False
            issues.append(f"Инструмент {tc.tool} завершился ошибкой: {tc.error}")
            fixes.append(f"Повторить {tc.tool} с корректными аргументами.")

    # 2. Цель похоже не выполнена (просили действие, но инструменты не вызваны)
    if not tool_calls and any(w in t for w in _ACTION_WORDS):
        passed = False
        issues.append("Запрос предполагал действие, но ни один инструмент не вызван.")
        fixes.append("Выполнить нужный инструмент (создание/изменение данных).")

    # 3. Конфликты в календаре
    conflicts = 0
    for tc in tool_calls:
        if tc.tool == "create_event" and _g(tc.output, "conflicts"):
            conflicts += len(_g(tc.output, "conflicts", []))
        if tc.tool == "check_time_conflicts" and _g(tc.output, "has_conflict"):
            conflicts += len(_g(tc.output, "conflicts", []))
    if conflicts:
        issues.append(f"В календаре есть пересечения событий: {conflicts}.")
        fixes.append("Перенести событие в свободный слот (find_free_slots).")
        confirm = True

    # 4. Задачи без дедлайна (для планирования — мягкое замечание)
    no_deadline = [tc for tc in tool_calls
                   if tc.tool == "create_task" and not _g(tc.output, "deadline")]
    if no_deadline and agent in ("planning",):
        issues.append(f"Созданы задачи без дедлайна: {len(no_deadline)}.")
        fixes.append("Проставить дедлайны или запланировать их в календаре.")

    # 5. Необратимые действия — нужно подтверждение
    if any(tc.tool in DESTRUCTIVE_TOOLS for tc in tool_calls):
        confirm = True
        fixes.append("Подтвердить удаление у пользователя перед окончательным действием.")

    # 6. Лёгкая проверка противоречий с памятью (предпочтения по времени)
    if agent in ("planning", "calendar"):
        prefs = [m.content.lower() for m in storage.memory.all()
                 if m.type.value in ("user_preference", "recurring_routine",
                                      "constraint")]
        if any("утр" in p for p in prefs):
            created_evening = [
                tc for tc in tool_calls
                if tc.tool in ("create_event", "schedule_tasks_to_free_slots")
            ]
            # информативное замечание, не ошибка
            if created_evening:
                issues.append("Учтите предпочтение из памяти: работать лучше утром.")

    notes = ("Reflection (детерминированный): проверены ошибки инструментов, "
             "факт выполнения цели, конфликты календаря, дедлайны, "
             "необходимость подтверждения и предпочтения из памяти.")
    return ReflectionResult(
        passed=passed, issues=issues, suggested_fixes=fixes,
        requires_user_confirmation=confirm, notes=notes)
