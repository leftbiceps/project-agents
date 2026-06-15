"""POST /chat — основной вход в мультиагентную систему."""
from __future__ import annotations

from fastapi import APIRouter

from ..agents import get_orchestrator
from ..models import AgentMessage, ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=AgentMessage)
def chat(req: ChatRequest) -> AgentMessage:
    return get_orchestrator().handle(req.message, req.history)
