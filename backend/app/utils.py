"""Вспомогательные функции: парсинг дат, окна времени, поиск свободных слотов."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional

from dateutil import parser as _dtparser

from .models import CalendarEvent


def parse_dt(value: object) -> Optional[datetime]:
    """Привести значение к datetime (ISO / распространённые форматы).

    Относительные выражения («завтра», «через 2 дня») должен превращать в
    конкретную дату сам LLM-агент — ему передаётся текущее время в промпте.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return _dtparser.parse(value).replace(microsecond=0)
        except (ValueError, OverflowError):
            return None
    return None


def parse_date(value: object) -> Optional[date]:
    dt = parse_dt(value)
    return dt.date() if dt else None


def fmt_dt(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


def fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time(0, 0, 0))
    end = datetime.combine(d, time(23, 59, 59))
    return start, end


def parse_hhmm(s: str, default: time) -> time:
    try:
        h, m = s.split(":")
        return time(int(h), int(m))
    except Exception:
        return default


def working_window(d: date, start_str: str, end_str: str) -> tuple[datetime, datetime]:
    start = datetime.combine(d, parse_hhmm(start_str, time(9, 0)))
    end = datetime.combine(d, parse_hhmm(end_str, time(19, 0)))
    return start, end


def overlaps(a_start: datetime, a_end: datetime,
             b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def events_on_day(events: Iterable[CalendarEvent], d: date) -> list[CalendarEvent]:
    res = [e for e in events if e.start_datetime.date() == d
           or e.end_datetime.date() == d
           or (e.start_datetime.date() < d < e.end_datetime.date())]
    return sorted(res, key=lambda e: e.start_datetime)


def detect_conflicts(start: datetime, end: datetime,
                     events: Iterable[CalendarEvent],
                     ignore_id: Optional[str] = None) -> list[CalendarEvent]:
    out = []
    for e in events:
        if ignore_id and e.id == ignore_id:
            continue
        if overlaps(start, end, e.start_datetime, e.end_datetime):
            out.append(e)
    return out


def find_free_slots(window_start: datetime, window_end: datetime,
                    busy: list[CalendarEvent], min_minutes: int = 30
                    ) -> list[tuple[datetime, datetime]]:
    """Свободные интервалы внутри окна с учётом занятых событий."""
    busy_sorted = sorted(
        [(e.start_datetime, e.end_datetime) for e in busy
         if overlaps(window_start, window_end, e.start_datetime, e.end_datetime)],
        key=lambda x: x[0],
    )
    slots: list[tuple[datetime, datetime]] = []
    cursor = window_start
    for b_start, b_end in busy_sorted:
        b_start = max(b_start, window_start)
        if b_start > cursor:
            if (b_start - cursor) >= timedelta(minutes=min_minutes):
                slots.append((cursor, b_start))
        cursor = max(cursor, min(b_end, window_end))
    if window_end > cursor and (window_end - cursor) >= timedelta(minutes=min_minutes):
        slots.append((cursor, window_end))
    return slots
