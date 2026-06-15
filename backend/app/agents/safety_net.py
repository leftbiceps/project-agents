"""Safety-net: гарантированное завершение действия.

LLM остаётся главным (ведёт диалог и сам вызывает инструменты), но если модель
не довела действие до конца (типично для малых моделей: «проанализировал, но не
создал»), детерминированный слой доделывает недостающий шаг. Запускается только
в LLM-режиме; в rule-based режиме fallback уже делает всё сам.
"""
from __future__ import annotations

from datetime import timedelta

from ..models import ToolCall
from ..storage import storage
from ..tools import registry
from . import fallback

_CREATE_KW = ("созда", "добавь", "заведи", "нужно", "надо", "купить", "сходить",
              "позвонить", "записаться", "забрать", "оплат", "отправ", "написать",
              "напомни")
_CHECKLIST_KW = ("разбей", "чеклист", "подзадач", "на пункт", "на шаги", "на этап")
_CAL_READ_KW = ("покажи", "расписан", "что в календаре", "свободн", "конфликт")


def _did(tool_calls, name: str) -> bool:
    return any(tc.tool == name and tc.ok for tc in tool_calls)


def _created_task_ids(tool_calls) -> list[str]:
    ids = []
    for tc in tool_calls:
        if not tc.ok or not isinstance(tc.output, dict):
            continue
        if tc.tool == "create_task" and tc.output.get("id"):
            ids.append(tc.output["id"])
        elif tc.tool == "split_goal_into_tasks":
            t = tc.output.get("task") or {}
            if t.get("id"):
                ids.append(t["id"])
    return ids


def _run(agent: str, tool: str, args: dict) -> ToolCall:
    return registry.execute(tool, args, agent)


def complete(agent: str, message: str, tool_calls: list[ToolCall]) -> list[ToolCall]:
    """Вернуть список доп. tool-calls, завершающих недоделанное действие."""
    t = message.lower()
    extra: list[ToolCall] = []

    if agent == "task":
        checklist_intent = any(k in t for k in _CHECKLIST_KW)
        create_intent = checklist_intent or any(k in t for k in _CREATE_KW)
        ids = _created_task_ids(tool_calls)
        if checklist_intent:
            task_id = ids[-1] if ids else None
            if not task_id:
                tc = _run("task", "create_task",
                          {"title": fallback._clean_title(message), "status": "todo"})
                extra.append(tc)
                task_id = tc.output.get("id") if isinstance(tc.output, dict) else None
            if task_id and not _did(tool_calls, "create_checklist"):
                extra.append(_run("task", "create_checklist", {
                    "task_id": task_id, "title": "План",
                    "items": ["Подготовка", "Основная работа", "Проверка и финализация"],
                }))
        elif create_intent and not _did(tool_calls, "create_task") and not ids:
            for g in fallback._split_goals(message):
                extra.append(_run("task", "create_task",
                                  {"title": g[:1].upper() + g[1:], "status": "todo"}))

    elif agent == "calendar":
        if not _did(tool_calls, "create_event") and not any(k in t for k in _CAL_READ_KW):
            dt = fallback._try_parse_dt(message)
            if dt:
                extra.append(_run("calendar", "create_event", {
                    "title": fallback._clean_event_title(message),
                    "start_datetime": dt.isoformat(),
                    "end_datetime": (dt + timedelta(hours=1)).isoformat(),
                    "type": "meeting",
                }))

    elif agent == "planning":
        if not _did(tool_calls, "schedule_tasks_to_free_slots"):
            ids = _created_task_ids(tool_calls)
            if not ids:
                ids = [x.id for x in storage.tasks.all()
                       if x.status.value in ("todo", "backlog")][:5]
            if ids:
                extra.append(_run("planning", "schedule_tasks_to_free_slots",
                                  {"task_ids": ids, "horizon_days": 7}))

    elif agent == "memory":
        if any(k in t for k in ("запомни", "запиши", "заметь")) \
                and not _did(tool_calls, "save_memory"):
            content = fallback._extract_after(message, ["запомни", "запиши", "заметь"])
            extra.append(_run("memory", "save_memory",
                              {"content": content,
                               "type": fallback._infer_mem_type(content)}))

    return extra
