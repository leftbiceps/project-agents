"""Чтение чеклистов и переключение пунктов (для UI задач)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..storage import storage
from ..tools import task_tools as tt

router = APIRouter(prefix="/checklists", tags=["checklists"])


class ItemPatch(BaseModel):
    text: Optional[str] = None
    done: Optional[bool] = None


@router.get("")
def list_checklists(task_id: Optional[str] = None):
    items = storage.checklists.all()
    if task_id:
        items = [c for c in items if c.task_id == task_id]
    return items


@router.get("/{checklist_id}")
def get_checklist(checklist_id: str):
    return storage.checklists.get(checklist_id)


@router.patch("/{checklist_id}/items/{item_id}")
def patch_item(checklist_id: str, item_id: str, body: ItemPatch):
    return tt.update_checklist_item(tt.UpdateItemIn(
        checklist_id=checklist_id, item_id=item_id,
        text=body.text, done=body.done))
