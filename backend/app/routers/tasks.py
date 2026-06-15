"""CRUD задач и прогресс/чеклисты."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..models import Priority, TaskStatus
from ..tools import task_tools as tt

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[TaskStatus] = None
    deadline: Optional[str] = None
    tags: Optional[list[str]] = None
    project: Optional[str] = None
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None


@router.get("")
def list_tasks(status: Optional[TaskStatus] = None, project: Optional[str] = None,
               tag: Optional[str] = None, include_archived: bool = False):
    return tt.list_tasks(tt.ListTasksIn(status=status, project=project,
                                        tag=tag, include_archived=include_archived))


@router.post("")
def create_task(body: tt.CreateTaskIn):
    return tt.create_task(body)


@router.get("/{task_id}")
def get_task(task_id: str):
    return tt.get_task(tt.TaskIdIn(id=task_id))


@router.patch("/{task_id}")
def patch_task(task_id: str, body: TaskPatch):
    return tt.update_task(tt.UpdateTaskIn(id=task_id, **body.model_dump(exclude_none=True)))


@router.delete("/{task_id}")
def delete_task(task_id: str):
    return tt.delete_task(tt.TaskIdIn(id=task_id))


@router.get("/{task_id}/progress")
def task_progress(task_id: str):
    return tt.get_task_progress(tt.TaskIdIn(id=task_id))
