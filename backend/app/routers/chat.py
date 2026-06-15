"""POST /chat — основной вход в мультиагентную систему (+ /chat/stream SSE)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..agents import get_orchestrator
from ..models import AgentMessage, ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=AgentMessage)
def chat(req: ChatRequest) -> AgentMessage:
    return get_orchestrator().handle(req.message, req.history)


@router.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Потоковый ответ (Server-Sent Events): routed / token / tool / done."""
    generator = get_orchestrator().handle_stream(req.message, req.history)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # отключить буферизацию у прокси
        },
    )
