"""CRUD событий календаря + расписание/слоты."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..models import EventType
from ..tools import calendar_tools as ct

router = APIRouter(prefix="/calendar", tags=["calendar"])


class EventPatch(BaseModel):
    title: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    description: Optional[str] = None
    type: Optional[EventType] = None
    linked_task_id: Optional[str] = None


@router.get("/events")
def list_events(from_date: Optional[str] = None, to_date: Optional[str] = None):
    return ct.list_events(ct.ListEventsIn(from_date=from_date, to_date=to_date))


@router.post("/events")
def create_event(body: ct.CreateEventIn):
    return ct.create_event(body)


@router.patch("/events/{event_id}")
def patch_event(event_id: str, body: EventPatch):
    return ct.update_event(ct.UpdateEventIn(id=event_id, **body.model_dump(exclude_none=True)))


@router.delete("/events/{event_id}")
def delete_event(event_id: str):
    return ct.delete_event(ct.EventIdIn(id=event_id))


@router.get("/day")
def day_schedule(date: Optional[str] = None):
    return ct.get_day_schedule(ct.DayIn(date=date))


@router.get("/week")
def week_schedule(start_date: Optional[str] = None):
    return ct.get_week_schedule(ct.WeekIn(start_date=start_date))


@router.get("/free-slots")
def free_slots(date: Optional[str] = None, work_day_start: str = "09:00",
               work_day_end: str = "19:00", min_minutes: int = 30):
    return ct.find_free_slots_tool(ct.FreeSlotsIn(
        date=date, work_day_start=work_day_start,
        work_day_end=work_day_end, min_minutes=min_minutes))
