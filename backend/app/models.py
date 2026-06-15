"""Доменные и служебные Pydantic-модели.

Здесь описаны все сущности из ТЗ (раздел 7): Task, Checklist, ChecklistItem,
CalendarEvent, MemoryItem, Digest, AgentMessage, ToolCall, ReflectionResult,
VerificationResult, PlanningRequest, PlanningResult, а также вспомогательные
перечисления статусов/приоритетов/типов.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field


# --------------------------------------------------------------------------- #
#  Утилиты
# --------------------------------------------------------------------------- #
def now() -> datetime:
    """Текущее локальное время без микросекунд (удобно для JSON и тестов)."""
    return datetime.now().replace(microsecond=0)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


# --------------------------------------------------------------------------- #
#  Перечисления
# --------------------------------------------------------------------------- #
class TaskStatus(str, Enum):
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    archived = "archived"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


PRIORITY_WEIGHT = {
    Priority.low: 1,
    Priority.medium: 2,
    Priority.high: 3,
    Priority.urgent: 4,
}


class EventType(str, Enum):
    meeting = "meeting"
    focus = "focus"
    reminder = "reminder"
    personal = "personal"
    task_block = "task_block"
    other = "other"


class MemoryType(str, Enum):
    user_preference = "user_preference"
    recurring_routine = "recurring_routine"
    personal_context = "personal_context"
    project_context = "project_context"
    contact = "contact"
    rule = "rule"
    constraint = "constraint"


# --------------------------------------------------------------------------- #
#  Чеклисты
# --------------------------------------------------------------------------- #
class ChecklistItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ci"))
    text: str
    done: bool = False
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    done_at: Optional[datetime] = None


class Checklist(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cl"))
    task_id: Optional[str] = None
    title: str = "Чеклист"
    items: list[ChecklistItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> int:
        return len(self.items)

    @computed_field  # type: ignore[misc]
    @property
    def completed(self) -> int:
        return sum(1 for i in self.items if i.done)

    @computed_field  # type: ignore[misc]
    @property
    def progress(self) -> float:
        if not self.items:
            return 0.0
        return round(self.completed / self.total * 100, 1)


# --------------------------------------------------------------------------- #
#  Задачи
# --------------------------------------------------------------------------- #
class Task(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.backlog
    priority: Priority = Priority.medium
    deadline: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    tags: list[str] = Field(default_factory=list)
    project: Optional[str] = None
    checklist_ids: list[str] = Field(default_factory=list)
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None
    source: str = "chat"  # chat | planning | email | manual | ...


# --------------------------------------------------------------------------- #
#  Календарь
# --------------------------------------------------------------------------- #
class CalendarEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evt"))
    title: str
    description: str = ""
    start_datetime: datetime
    end_datetime: datetime
    type: EventType = EventType.other
    linked_task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------------------- #
#  Память
# --------------------------------------------------------------------------- #
class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    type: MemoryType = MemoryType.personal_context
    content: str
    key: Optional[str] = None  # короткий ключ для поиска/обновления
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    source: str = "chat"


# --------------------------------------------------------------------------- #
#  Дайджесты
# --------------------------------------------------------------------------- #
class Digest(BaseModel):
    id: str = Field(default_factory=lambda: new_id("dig"))
    kind: str  # morning | evening
    date: str  # YYYY-MM-DD
    content: str = ""  # человекочитаемый markdown
    data: dict[str, Any] = Field(default_factory=dict)  # структурированные данные
    created_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------------------- #
#  Агентные сообщения и tool calls
# --------------------------------------------------------------------------- #
class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tc"))
    agent: str
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    ok: bool = True
    error: Optional[str] = None
    ts: datetime = Field(default_factory=now)


class ReflectionResult(BaseModel):
    passed: bool = True
    issues: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool = False
    notes: str = ""


class VerificationCheck(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class VerificationResult(BaseModel):
    passed: bool = True
    checks: list[VerificationCheck] = Field(default_factory=list)
    summary: str = ""


class AgentMessage(BaseModel):
    role: str = "assistant"  # user | assistant | system
    agent: Optional[str] = None  # какой агент отвечал
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reflection: Optional[ReflectionResult] = None
    verification: Optional[VerificationResult] = None
    routed_to: Optional[str] = None
    rationale: Optional[str] = None
    created_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------------------- #
#  Планирование
# --------------------------------------------------------------------------- #
class PlanningRequest(BaseModel):
    text: str
    horizon_days: int = 7
    work_day_start: str = "09:00"
    work_day_end: str = "19:00"


class PlanningResult(BaseModel):
    goals: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    plan_text: str = ""
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
#  Запрос в чат
# --------------------------------------------------------------------------- #
class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
#  База знаний (опционально)
# --------------------------------------------------------------------------- #
class Note(BaseModel):
    id: str = Field(default_factory=lambda: new_id("note"))
    title: str
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    linked_task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
