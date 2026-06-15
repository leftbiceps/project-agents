"""Высокоуровневые действия: планирование, приоритизация, режим сна."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..agents import get_orchestrator
from ..models import AgentMessage, PlanningRequest

router = APIRouter(tags=["actions"])


class PrioritizeBody(BaseModel):
    message: Optional[str] = None


@router.post("/plan", response_model=AgentMessage)
def plan(req: PlanningRequest):
    msg = (f"{req.text} (горизонт {req.horizon_days} дн., рабочий день "
           f"{req.work_day_start}–{req.work_day_end})")
    return get_orchestrator().handle(msg, force_agent="planning")


@router.post("/prioritize", response_model=AgentMessage)
def prioritize(body: PrioritizeBody | None = None):
    message = (body.message if body and body.message else "Что мне делать дальше?")
    return get_orchestrator().handle(message, force_agent="prioritization")


@router.post("/sleep-mode", response_model=AgentMessage)
def sleep_mode():
    return get_orchestrator().handle("Переведи меня в режим сна",
                                     force_agent="sleep_fairy")
