"""Детерминированный режим (без LLM-ключа).

Используется, когда provider == none. Покрывает ключевые интенты из демо-сценариев
с помощью правил и прямых вызовов инструментов. Это не замена LLM, а
работоспособная деградация, чтобы систему можно было запустить и показать
без ключа.
"""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Callable

from dateutil import parser as dtparser

from ..models import MemoryItem, Task, ToolCall
from ..scoring import recommend_next
from ..tools import registry

_CMD_PHRASES = [
    "создай задачу", "создай событие", "создай", "добавь задачу",
    "добавь событие", "добавь", "заведи задачу", "заведи",
    "сделай задачу", "сделать", "новая задача", "разбей задачу",
    "разбей на чеклист", "разбей на пункты", "разбей на шаги", "разбей",
    "на чеклист", "спланируй", "запланируй встречу", "запланируй",
    "распредели", "составь план", "поставь встречу", "поставь",
    "нужно", "надо", "пожалуйста",
]


def _run(agent: str, tool: str, args: dict) -> ToolCall:
    return registry.execute(tool, args, agent)


def _clean_title(message: str) -> str:
    text = message.strip()
    low = text.lower()
    for ph in _CMD_PHRASES:
        idx = low.find(ph)
        if idx != -1:
            text = (text[:idx] + text[idx + len(ph):])
            low = text.lower()
    text = re.sub(r"\s+", " ", text).strip(" ,.:;—-\t\n")
    # убрать висящие союзы/предлоги в конце
    text = re.sub(r"\s+(и|а|но|или|на|по|за|в)$", "", text, flags=re.IGNORECASE)
    text = text.strip(" ,.:;—-")
    if not text:
        text = message.strip()
    if len(text) > 120:
        text = text[:117] + "…"
    return text[:1].upper() + text[1:] if text else "Новая задача"


def _extract_after(message: str, keywords: list[str]) -> str:
    low = message.lower()
    best = len(message)
    klen = 0
    for k in keywords:
        i = low.find(k)
        if i != -1 and i < best:
            best, klen = i, len(k)
    if best == len(message):
        return message.strip()
    tail = message[best + klen:].lstrip(" ,:.—-\t")
    if tail.lower().startswith("что "):
        tail = tail[4:]
    return tail.strip() or message.strip()


def _infer_mem_type(content: str) -> str:
    c = content.lower()
    if any(w in c for w in ("лучше работаю", "предпочитаю", "люблю", "не люблю",
                            "удобнее", "комфортно")):
        return "user_preference"
    if any(w in c for w in ("каждый", "по утрам", "по вечерам", "обычно",
                            "регулярно", "каждое")):
        return "recurring_routine"
    if any(w in c for w in ("нельзя", "не планировать", "ограничен", "запрещ",
                            "не позже", "не раньше")):
        return "constraint"
    return "personal_context"


def _try_parse_dt(message: str):
    if not re.search(r"\d", message):
        return None
    low = message.lower()
    base = datetime.now().date()
    if "послезавтра" in low:
        base = base + timedelta(days=2)
    elif "завтра" in low:
        base = base + timedelta(days=1)
    default = datetime.combine(base, time(9, 0))
    try:
        return dtparser.parse(message, fuzzy=True, default=default).replace(microsecond=0)
    except (ValueError, OverflowError):
        return None


def _clean_event_title(message: str) -> str:
    title = _clean_title(message)
    # убрать упоминания дат/времени из названия события
    title = re.sub(r"\b(сегодня|завтра|послезавтра)\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\bв\s*\d{1,2}[:.]\d{2}\b", "", title)
    title = re.sub(r"\b\d{1,2}[:.]\d{2}\b", "", title)
    title = re.sub(r"\bв\s*\d{1,2}\s*час\w*\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" ,.:;—-")
    return title or "Встреча"


def _fmt_day(out) -> str:
    events = out.get("events", []) if isinstance(out, dict) else []
    if not events:
        return f"На {out.get('date', 'сегодня')} событий нет."
    lines = [f"Расписание на {out.get('date')}:"]
    lines += [f"- {e['start_datetime'][11:16]}–{e['end_datetime'][11:16]} {e['title']}"
              for e in events]
    return "\n".join(lines)


def _fmt_week(out) -> str:
    days = out.get("days", []) if isinstance(out, dict) else []
    lines = ["Расписание на неделю:"]
    for d in days:
        evs = d.get("events", [])
        if evs:
            lines.append(f"{d['date']}:")
            lines += [f"  - {e['start_datetime'][11:16]} {e['title']}" for e in evs]
    if len(lines) == 1:
        lines.append("Событий на неделю нет.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Обработчики по агентам
# --------------------------------------------------------------------------- #
def _handle_memory(message: str):
    t = message.lower()
    calls = []
    if any(k in t for k in ("запомни", "запиши", "заметь")):
        content = _extract_after(message, ["запомни", "запиши", "заметь"])
        mtype = _infer_mem_type(content)
        tc = _run("memory", "save_memory", {"content": content, "type": mtype})
        calls.append(tc)
        return f"Запомнил: «{content}» (тип: {mtype}).", calls
    tc = _run("memory", "list_memory", {})
    calls.append(tc)
    items = tc.output or []
    if not items:
        return "Память пока пуста.", calls
    lines = ["Вот что я помню:"] + [f"- ({m['type']}) {m['content']}" for m in items]
    return "\n".join(lines), calls


def _handle_task(message: str):
    t = message.lower()
    calls = []
    title = _clean_title(message)
    if any(k in t for k in ("разбей", "чеклист", "подзадач", "на пункт", "на шаги")):
        tc1 = _run("task", "create_task", {"title": title, "status": "todo"})
        calls.append(tc1)
        task_id = tc1.output.get("id") if isinstance(tc1.output, dict) else None
        items = [f"Подготовка: {title}", "Основная работа", "Проверка и финализация"]
        tc2 = _run("task", "create_checklist",
                   {"task_id": task_id, "title": "Чеклист", "items": items})
        calls.append(tc2)
        return f"Создал задачу «{title}» и чеклист из {len(items)} пунктов.", calls
    if any(k in t for k in ("созда", "добавь", "заведи", "нужно", "надо",
                            "сделать задачу", "новая задача")):
        tc = _run("task", "create_task", {"title": title, "status": "todo"})
        calls.append(tc)
        return f"Создал задачу «{title}».", calls
    tc = _run("task", "list_tasks", {})
    calls.append(tc)
    tasks = tc.output or []
    if not tasks:
        return "Задач пока нет.", calls
    lines = ["Текущие задачи:"] + [f"- [{x['status']}] {x['title']}" for x in tasks]
    return "\n".join(lines), calls


def _handle_calendar(message: str):
    t = message.lower()
    calls = []
    if "недел" in t and not any(k in t for k in ("создай", "добавь", "поставь")):
        tc = _run("calendar", "get_week_schedule", {})
        calls.append(tc)
        return _fmt_week(tc.output), calls
    if any(k in t for k in ("создай событие", "добавь событие", "встреч",
                            "поставь", "запланируй встречу")):
        dt = _try_parse_dt(message)
        if dt:
            end = dt + timedelta(hours=1)
            title = _clean_event_title(message)
            tc = _run("calendar", "create_event", {
                "title": title, "start_datetime": dt.isoformat(),
                "end_datetime": end.isoformat(), "type": "meeting"})
            calls.append(tc)
            note = ""
            if isinstance(tc.output, dict) and tc.output.get("conflicts"):
                note = " (внимание: пересечение по времени)"
            return f"Создал событие «{title}» на {dt:%Y-%m-%d %H:%M}{note}.", calls
        tc = _run("calendar", "get_day_schedule", {})
        calls.append(tc)
        return ("Не удалось распознать дату/время. " + _fmt_day(tc.output)), calls
    tc = _run("calendar", "get_day_schedule", {})
    calls.append(tc)
    return _fmt_day(tc.output), calls


def _handle_planning(message: str):
    calls = []
    goal = _clean_title(message)
    tc1 = _run("planning", "split_goal_into_tasks", {"goal": goal})
    calls.append(tc1)
    tasks = tc1.output.get("tasks", []) if isinstance(tc1.output, dict) else []
    task_ids = [x["id"] for x in tasks]
    tc2 = _run("planning", "schedule_tasks_to_free_slots",
               {"task_ids": task_ids, "horizon_days": 7})
    calls.append(tc2)
    events = tc2.output.get("events", []) if isinstance(tc2.output, dict) else []
    warnings = tc2.output.get("warnings", []) if isinstance(tc2.output, dict) else []
    lines = [f"План по цели «{goal}» ({len(tasks)} задач):"]
    for e in events:
        lines.append(f"- {e['start_datetime'][:16].replace('T', ' ')} — {e['title']}")
    if warnings:
        lines.append("Предупреждения:")
        lines += [f"- {w}" for w in warnings]
    return "\n".join(lines), calls


def _handle_priority(message: str):
    calls = []
    tc = _run("prioritization", "list_tasks", {})
    calls.append(tc)
    tasks = [Task.model_validate(x) for x in (tc.output or [])]
    mem_tc = _run("prioritization", "search_memory", {})
    calls.append(mem_tc)
    mem = [MemoryItem.model_validate(x) for x in (mem_tc.output or [])]
    rec = recommend_next(tasks, mem)
    if not rec["main"]:
        return rec["explanation"], calls
    set_tc = _run("prioritization", "set_task_status",
                  {"id": rec["main"]["id"], "status": "in_progress"})
    calls.append(set_tc)
    lines = [f"👉 Сейчас лучше: «{rec['main']['title']}».", rec["explanation"]]
    if rec["alternatives"]:
        lines.append("Альтернативы:")
        lines += [f"- {a['title']}" for a in rec["alternatives"]]
    if rec["risks"]:
        lines.append("Риски, если отложить:")
        lines += [f"- {r}" for r in rec["risks"]]
    return "\n".join(lines), calls


def _handle_digest(message: str):
    t = message.lower()
    calls = []
    kind = "evening" if any(k in t for k in ("вечер", "итог", "evening")) else "morning"
    tool = "generate_evening_digest" if kind == "evening" else "generate_morning_digest"
    tc = _run("digest", tool, {})
    calls.append(tc)
    content = tc.output.get("content", "") if isinstance(tc.output, dict) else ""
    return content or "Дайджест сформирован.", calls


def _handle_sleep(message: str):
    calls = []
    tc1 = _run("sleep_fairy", "generate_evening_digest", {})
    calls.append(tc1)
    tc2 = _run("sleep_fairy", "reschedule_overdue_tasks", {"within_days": 1})
    calls.append(tc2)
    moved = tc2.output.get("moved", []) if isinstance(tc2.output, dict) else []
    plan = (tc1.output.get("data", {}).get("plan_tomorrow", [])
            if isinstance(tc1.output, dict) else [])
    lines = ["🌙 Подвёл итоги дня и подготовил тебя ко сну."]
    if moved:
        lines.append(f"Перенёс незавершённые задачи на завтра: {len(moved)}.")
        lines += [f"- {t['title']}" for t in moved]
    else:
        lines.append("Просроченных задач нет — переносить нечего.")
    if plan:
        lines.append("Мягкий план на утро:")
        lines += [f"{i + 1}. {t['title']}" for i, t in enumerate(plan)]
    lines.append("Критичного на сегодня не осталось. Ритуал на сон: закрой "
                 "ноутбук, 5 медленных вдохов-выдохов, отложи телефон. "
                 "Спокойной ночи 🌙")
    return "\n".join(lines), calls


_HANDLERS: dict[str, Callable[[str], tuple[str, list[ToolCall]]]] = {
    "task": _handle_task,
    "calendar": _handle_calendar,
    "planning": _handle_planning,
    "prioritization": _handle_priority,
    "memory": _handle_memory,
    "digest": _handle_digest,
    "sleep_fairy": _handle_sleep,
}


def handle(agent: str, message: str) -> tuple[str, list[ToolCall]]:
    fn = _HANDLERS.get(agent, _handle_task)
    return fn(message)
