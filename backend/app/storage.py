"""Локальное хранилище данных на JSON-файлах.

Каждая коллекция хранится в отдельном файле в data/:
    tasks.json, events.json, memory.json, checklists.json,
    digests.json, notes.json, mail_mock.json

Доступ потокобезопасный (общий RLock), запись атомарная (через временный файл).
Любое изменение пишется в лог как событие storage_change.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from .config import get_settings
from .logging_conf import log_event
from .models import (
    AgentMessage,
    CalendarEvent,
    Checklist,
    Digest,
    MemoryItem,
    Note,
    Task,
    now,
)

T = TypeVar("T", bound=BaseModel)

_LOCK = threading.RLock()


class Repo(Generic[T]):
    """Простой репозиторий «список объектов в одном JSON-файле»."""

    def __init__(self, path: Path, model: Type[T], name: str) -> None:
        self.path = path
        self.model = model
        self.name = name
        if not self.path.exists():
            self._write_raw([])

    # --- низкоуровневое чтение/запись ---
    def _read_raw(self) -> list[dict]:
        with _LOCK:
            if not self.path.exists():
                return []
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    return data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                return []

    def _write_raw(self, rows: list[dict]) -> None:
        with _LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(rows, fh, ensure_ascii=False, indent=2, default=str)
                os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)

    # --- операции над моделями ---
    def all(self) -> list[T]:
        return [self.model.model_validate(r) for r in self._read_raw()]

    def get(self, obj_id: str) -> Optional[T]:
        for row in self._read_raw():
            if row.get("id") == obj_id:
                return self.model.model_validate(row)
        return None

    def add(self, obj: T) -> T:
        with _LOCK:
            rows = self._read_raw()
            rows.append(obj.model_dump(mode="json"))
            self._write_raw(rows)
        log_event("storage_change", collection=self.name, op="add",
                  id=getattr(obj, "id", None))
        return obj

    def replace(self, obj: T) -> T:
        """Upsert по id."""
        with _LOCK:
            rows = self._read_raw()
            obj_id = getattr(obj, "id")
            replaced = False
            for i, row in enumerate(rows):
                if row.get("id") == obj_id:
                    rows[i] = obj.model_dump(mode="json")
                    replaced = True
                    break
            if not replaced:
                rows.append(obj.model_dump(mode="json"))
            self._write_raw(rows)
        log_event("storage_change", collection=self.name,
                  op="replace", id=getattr(obj, "id", None))
        return obj

    def update(self, obj_id: str, changes: dict[str, Any]) -> Optional[T]:
        with _LOCK:
            rows = self._read_raw()
            for i, row in enumerate(rows):
                if row.get("id") == obj_id:
                    merged = {**row, **{k: v for k, v in changes.items()
                                        if v is not None}}
                    if "updated_at" in self.model.model_fields:
                        merged["updated_at"] = now().isoformat()
                    obj = self.model.model_validate(merged)
                    rows[i] = obj.model_dump(mode="json")
                    self._write_raw(rows)
                    log_event("storage_change", collection=self.name,
                              op="update", id=obj_id,
                              fields=list(changes.keys()))
                    return obj
        return None

    def delete(self, obj_id: str) -> bool:
        with _LOCK:
            rows = self._read_raw()
            new_rows = [r for r in rows if r.get("id") != obj_id]
            if len(new_rows) == len(rows):
                return False
            self._write_raw(new_rows)
        log_event("storage_change", collection=self.name, op="delete", id=obj_id)
        return True

    def count(self) -> int:
        return len(self._read_raw())


class Storage:
    """Фасад над всеми коллекциями."""

    def __init__(self) -> None:
        d = get_settings().data_dir
        self.tasks: Repo[Task] = Repo(d / "tasks.json", Task, "tasks")
        self.events: Repo[CalendarEvent] = Repo(d / "events.json", CalendarEvent, "events")
        self.memory: Repo[MemoryItem] = Repo(d / "memory.json", MemoryItem, "memory")
        self.checklists: Repo[Checklist] = Repo(d / "checklists.json", Checklist, "checklists")
        self.digests: Repo[Digest] = Repo(d / "digests.json", Digest, "digests")
        self.notes: Repo[Note] = Repo(d / "notes.json", Note, "notes")
        # Переписка чата (persistent, чтобы переживала перезагрузку страницы).
        self.chat: Repo[AgentMessage] = Repo(d / "chat.json", AgentMessage, "chat")

    def reset(self) -> None:
        """Очистить все коллекции (используется в тестах/демо-сидинге)."""
        for repo in (self.tasks, self.events, self.memory,
                     self.checklists, self.digests, self.notes, self.chat):
            repo._write_raw([])


# Глобальный синглтон, который импортируют инструменты и агенты.
storage = Storage()
