"""CRUD личной памяти."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..models import MemoryType
from ..tools import memory_tools as mt

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryPatch(BaseModel):
    content: Optional[str] = None
    type: Optional[MemoryType] = None
    key: Optional[str] = None
    tags: Optional[list[str]] = None


@router.get("")
def list_memory(type: Optional[MemoryType] = None):
    return mt.list_memory(mt.ListMemoryIn(type=type))


@router.get("/search")
def search_memory(query: str = "", type: Optional[MemoryType] = None):
    return mt.search_memory(mt.SearchMemoryIn(query=query, type=type))


@router.post("")
def create_memory(body: mt.SaveMemoryIn):
    return mt.save_memory(body)


@router.patch("/{memory_id}")
def patch_memory(memory_id: str, body: MemoryPatch):
    return mt.update_memory(mt.UpdateMemoryIn(id=memory_id, **body.model_dump(exclude_none=True)))


@router.delete("/{memory_id}")
def delete_memory(memory_id: str):
    return mt.delete_memory(mt.MemoryIdIn(id=memory_id))
