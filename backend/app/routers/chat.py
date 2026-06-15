"""POST /chat — основной вход в мультиагентную систему + история чата."""
from __future__ import annotations

from fastapi import APIRouter

from ..agents import get_orchestrator
from ..models import AgentMessage, ChatRequest
from ..storage import storage

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=AgentMessage)
def chat(req: ChatRequest) -> AgentMessage:
    return get_orchestrator().handle(req.message, req.history)


@router.get("/chat/history")
def chat_history():
    """Сохранённая переписка (переживает перезагрузку страницы)."""
    return storage.chat.all()


@router.delete("/chat/history")
def clear_chat_history():
    storage.chat._write_raw([])
    return {"cleared": True}
