"""Инструменты базы знаний в стиле Obsidian (опционально).

Заметки хранятся двойственно: метаданные в data/notes.json (для быстрого
списка) и сам markdown-файл data/knowledge_base/<id>.md с YAML-фронтматтером.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ..config import get_settings
from ..models import Note, now
from ..storage import storage
from .registry import ToolError, tool


def _md_path(note_id: str):
    return get_settings().data_dir / "knowledge_base" / f"{note_id}.md"


def _write_md(note: Note) -> None:
    fm = [
        "---",
        f"title: {note.title}",
        f"tags: [{', '.join(note.tags)}]",
        f"created_at: {note.created_at.isoformat()}",
        f"updated_at: {note.updated_at.isoformat()}",
        f"linked_task_ids: [{', '.join(note.linked_task_ids)}]",
        "---",
        "",
        note.body,
        "",
    ]
    path = _md_path(note.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(fm), encoding="utf-8")


class CreateNoteIn(BaseModel):
    title: str
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    linked_task_ids: list[str] = Field(default_factory=list)


class UpdateNoteIn(BaseModel):
    id: str
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[list[str]] = None


class SearchNotesIn(BaseModel):
    query: str = ""


class LinkNoteIn(BaseModel):
    note_id: str
    task_id: str


class SummarizeNoteIn(BaseModel):
    note_id: str
    max_chars: int = 280


@tool("create_note", "Создать заметку в базе знаний (.md + метаданные).",
      CreateNoteIn, output_hint="Note")
def create_note(inp: CreateNoteIn) -> Note:
    note = Note(title=inp.title, body=inp.body, tags=inp.tags,
                linked_task_ids=inp.linked_task_ids)
    storage.notes.add(note)
    _write_md(note)
    return note


@tool("update_note", "Обновить заметку по id.", UpdateNoteIn, output_hint="Note")
def update_note(inp: UpdateNoteIn) -> Note:
    changes = inp.model_dump(exclude={"id"}, exclude_none=True)
    updated = storage.notes.update(inp.id, changes)
    if not updated:
        raise ToolError(f"Заметка {inp.id} не найдена")
    _write_md(updated)
    return updated


@tool("search_notes", "Поиск заметок по подстроке в заголовке/тексте/тегах.",
      SearchNotesIn, output_hint="Note[]")
def search_notes(inp: SearchNotesIn) -> list[Note]:
    q = inp.query.lower().strip()
    out = []
    for n in storage.notes.all():
        hay = " ".join([n.title, n.body, " ".join(n.tags)]).lower()
        if not q or q in hay:
            out.append(n)
    return out


@tool("link_note_to_task", "Связать заметку с задачей.", LinkNoteIn,
      output_hint="Note")
def link_note_to_task(inp: LinkNoteIn) -> Note:
    note = storage.notes.get(inp.note_id)
    if not note:
        raise ToolError(f"Заметка {inp.note_id} не найдена")
    if inp.task_id not in note.linked_task_ids:
        note.linked_task_ids.append(inp.task_id)
        note.updated_at = now()
        storage.notes.replace(note)
        _write_md(note)
    return note


@tool("summarize_note", "Короткая выжимка заметки (обрезка по символам).",
      SummarizeNoteIn, output_hint="{summary}")
def summarize_note(inp: SummarizeNoteIn) -> dict:
    note = storage.notes.get(inp.note_id)
    if not note:
        raise ToolError(f"Заметка {inp.note_id} не найдена")
    body = note.body.strip().replace("\n", " ")
    summary = body[: inp.max_chars] + ("…" if len(body) > inp.max_chars else "")
    return {"note_id": note.id, "title": note.title, "summary": summary}
