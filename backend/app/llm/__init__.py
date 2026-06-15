"""LLM-слой: абстракция над провайдерами (Anthropic / OpenAI / local_openai)."""
from __future__ import annotations

from .client import AgentRunResult, LLMClient
from .provider import get_client, llm_health

__all__ = ["AgentRunResult", "LLMClient", "get_client", "llm_health"]
