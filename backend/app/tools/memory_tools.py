"""Инструменты личной памяти (Memory Agent)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..models import MemoryItem, MemoryType
from ..storage import storage
from .registry import ToolError, tool


class SaveMemoryIn(BaseModel):
    content: str = Field(..., description="Сам факт/предпочтение/правило")
    type: MemoryType = MemoryType.personal_context
    key: Optional[str] = Field(None, description="Короткий ключ для поиска/обновления")
    tags: list[str] = Field(default_factory=list)
    source: str = "chat"


class SearchMemoryIn(BaseModel):
    query: str = ""
    type: Optional[MemoryType] = None


class UpdateMemoryIn(BaseModel):
    id: str
    content: Optional[str] = None
    type: Optional[MemoryType] = None
    key: Optional[str] = None
    tags: Optional[list[str]] = None


class MemoryIdIn(BaseModel):
    id: str


class ListMemoryIn(BaseModel):
    type: Optional[MemoryType] = None


@tool("save_memory", "Сохранить факт/предпочтение пользователя в память.",
      SaveMemoryIn, output_hint="MemoryItem")
def save_memory(inp: SaveMemoryIn) -> MemoryItem:
    item = MemoryItem(content=inp.content, type=inp.type, key=inp.key,
                      tags=inp.tags, source=inp.source)
    return storage.memory.add(item)


@tool("search_memory", "Найти факты в памяти по подстроке и/или типу.",
      SearchMemoryIn, output_hint="MemoryItem[]")
def search_memory(inp: SearchMemoryIn) -> list[MemoryItem]:
    q = inp.query.lower().strip()
    out = []
    for m in storage.memory.all():
        if inp.type and m.type != inp.type:
            continue
        hay = " ".join([m.content, m.key or "", " ".join(m.tags)]).lower()
        if not q or q in hay:
            out.append(m)
    return out


@tool("update_memory", "Обновить факт в памяти по id.", UpdateMemoryIn,
      output_hint="MemoryItem")
def update_memory(inp: UpdateMemoryIn) -> MemoryItem:
    changes = inp.model_dump(exclude={"id"}, exclude_none=True)
    updated = storage.memory.update(inp.id, changes)
    if not updated:
        raise ToolError(f"Запись памяти {inp.id} не найдена")
    return updated


@tool("delete_memory", "Удалить факт из памяти по id.", MemoryIdIn,
      output_hint="{deleted: bool}")
def delete_memory(inp: MemoryIdIn) -> dict:
    return {"deleted": storage.memory.delete(inp.id), "id": inp.id}


@tool("list_memory", "Список всех фактов памяти, опц. по типу.", ListMemoryIn,
      output_hint="MemoryItem[]")
def list_memory(inp: ListMemoryIn) -> list[MemoryItem]:
    items = storage.memory.all()
    if inp.type:
        items = [m for m in items if m.type == inp.type]
    return sorted(items, key=lambda m: m.created_at)
