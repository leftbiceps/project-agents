"""Дайджесты: генерация и история."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..tools import digest_tools as dt

router = APIRouter(prefix="/digest", tags=["digest"])


class DigestBody(BaseModel):
    date: Optional[str] = None


@router.post("/morning")
def morning(body: DigestBody | None = None):
    return dt.generate_morning_digest(dt.DigestDayIn(date=(body.date if body else None)))


@router.post("/evening")
def evening(body: DigestBody | None = None):
    return dt.generate_evening_digest(dt.DigestDayIn(date=(body.date if body else None)))


@router.get("")
def list_digests(kind: Optional[str] = None, limit: int = 20):
    return dt.list_digests(dt.ListDigestsIn(kind=kind, limit=limit))
