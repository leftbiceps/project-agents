"""Инструменты локального календаря (Calendar Agent)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field

from ..models import CalendarEvent, EventType, now
from ..storage import storage
from ..utils import (
    detect_conflicts,
    events_on_day,
    find_free_slots,
    parse_date,
    parse_dt,
    working_window,
)
from .registry import ToolError, tool


# --------------------------------------------------------------------------- #
#  Схемы входа
# --------------------------------------------------------------------------- #
class CreateEventIn(BaseModel):
    title: str
    start_datetime: str = Field(..., description="ISO, напр. 2026-06-10T10:00")
    end_datetime: str = Field(..., description="ISO, напр. 2026-06-10T11:30")
    description: str = ""
    type: EventType = EventType.other
    linked_task_id: Optional[str] = None


class UpdateEventIn(BaseModel):
    id: str
    title: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    description: Optional[str] = None
    type: Optional[EventType] = None
    linked_task_id: Optional[str] = None


class EventIdIn(BaseModel):
    id: str


class ListEventsIn(BaseModel):
    from_date: Optional[str] = Field(None, description="С какой даты (вкл.)")
    to_date: Optional[str] = Field(None, description="По какую дату (вкл.)")


class DayIn(BaseModel):
    date: Optional[str] = Field(None, description="Дата дня; по умолчанию сегодня")


class WeekIn(BaseModel):
    start_date: Optional[str] = Field(None, description="Начало недели; по умолчанию сегодня")


class FreeSlotsIn(BaseModel):
    date: Optional[str] = None
    work_day_start: str = "09:00"
    work_day_end: str = "19:00"
    min_minutes: int = 30


class ConflictsIn(BaseModel):
    start_datetime: str
    end_datetime: str
    ignore_event_id: Optional[str] = None


# --------------------------------------------------------------------------- #
#  Реализация
# --------------------------------------------------------------------------- #
def _require_dt(value: object, field: str) -> datetime:
    dt = parse_dt(value)
    if dt is None:
        raise ToolError(f"Не удалось распознать дату/время в поле {field}: {value!r}")
    return dt


@tool("create_event", "Создать событие в локальном календаре.", CreateEventIn,
      output_hint="{event, conflicts}")
def create_event(inp: CreateEventIn) -> dict:
    start = _require_dt(inp.start_datetime, "start_datetime")
    end = _require_dt(inp.end_datetime, "end_datetime")
    if end <= start:
        raise ToolError("end_datetime должен быть позже start_datetime")
    conflicts = detect_conflicts(start, end, storage.events.all())
    event = CalendarEvent(
        title=inp.title,
        description=inp.description,
        start_datetime=start,
        end_datetime=end,
        type=inp.type,
        linked_task_id=inp.linked_task_id,
    )
    storage.events.add(event)
    return {
        "event": event.model_dump(mode="json"),
        "conflicts": [c.model_dump(mode="json") for c in conflicts],
    }


@tool("update_event", "Обновить событие календаря по id.", UpdateEventIn,
      output_hint="CalendarEvent")
def update_event(inp: UpdateEventIn) -> CalendarEvent:
    changes = inp.model_dump(exclude={"id"}, exclude_none=True)
    if "start_datetime" in changes:
        changes["start_datetime"] = _require_dt(changes["start_datetime"], "start_datetime")
    if "end_datetime" in changes:
        changes["end_datetime"] = _require_dt(changes["end_datetime"], "end_datetime")
    updated = storage.events.update(inp.id, changes)
    if not updated:
        raise ToolError(f"Событие {inp.id} не найдено")
    return updated


@tool("delete_event", "Удалить событие календаря по id.", EventIdIn,
      output_hint="{deleted: bool}")
def delete_event(inp: EventIdIn) -> dict:
    return {"deleted": storage.events.delete(inp.id), "id": inp.id}


@tool("list_events", "Список событий, опц. в диапазоне дат.", ListEventsIn,
      output_hint="CalendarEvent[]")
def list_events(inp: ListEventsIn) -> list[CalendarEvent]:
    events = sorted(storage.events.all(), key=lambda e: e.start_datetime)
    d_from = parse_date(inp.from_date) if inp.from_date else None
    d_to = parse_date(inp.to_date) if inp.to_date else None
    if d_from:
        events = [e for e in events if e.end_datetime.date() >= d_from]
    if d_to:
        events = [e for e in events if e.start_datetime.date() <= d_to]
    return events


@tool("get_day_schedule", "Расписание на конкретный день.", DayIn,
      output_hint="{date, events}")
def get_day_schedule(inp: DayIn) -> dict:
    d = parse_date(inp.date) if inp.date else date.today()
    evs = events_on_day(storage.events.all(), d)
    return {"date": d.isoformat(),
            "events": [e.model_dump(mode="json") for e in evs]}


@tool("get_week_schedule", "Расписание на 7 дней от даты (по умолч. сегодня).",
      WeekIn, output_hint="{days: [{date, events}]}")
def get_week_schedule(inp: WeekIn) -> dict:
    start = parse_date(inp.start_date) if inp.start_date else date.today()
    all_events = storage.events.all()
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        evs = events_on_day(all_events, d)
        days.append({"date": d.isoformat(),
                     "events": [e.model_dump(mode="json") for e in evs]})
    return {"start_date": start.isoformat(), "days": days}


@tool("find_free_slots", "Найти свободные окна в рабочем дне.", FreeSlotsIn,
      output_hint="{slots: [{start, end, minutes}]}")
def find_free_slots_tool(inp: FreeSlotsIn) -> dict:
    d = parse_date(inp.date) if inp.date else date.today()
    win_start, win_end = working_window(d, inp.work_day_start, inp.work_day_end)
    busy = events_on_day(storage.events.all(), d)
    slots = find_free_slots(win_start, win_end, busy, inp.min_minutes)
    return {
        "date": d.isoformat(),
        "slots": [
            {
                "start": s.isoformat(timespec="minutes"),
                "end": e.isoformat(timespec="minutes"),
                "minutes": int((e - s).total_seconds() // 60),
            }
            for s, e in slots
        ],
    }


@tool("check_time_conflicts", "Проверить конфликты по времени для интервала.",
      ConflictsIn, output_hint="{has_conflict, conflicts}")
def check_time_conflicts(inp: ConflictsIn) -> dict:
    start = _require_dt(inp.start_datetime, "start_datetime")
    end = _require_dt(inp.end_datetime, "end_datetime")
    conflicts = detect_conflicts(start, end, storage.events.all(),
                                 ignore_id=inp.ignore_event_id)
    return {
        "has_conflict": bool(conflicts),
        "conflicts": [c.model_dump(mode="json") for c in conflicts],
    }
