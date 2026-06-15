"""Supervisor / Orchestrator.

Принимает сообщение пользователя, маршрутизирует его профильному агенту,
выполняет его (через LLM tool-loop или детерминированный fallback), затем
прогоняет Reflection и Verifier и собирает итоговый AgentMessage.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Iterator, Optional

from ..llm import get_client
from ..llm.client import OpenAIClient
from ..llm.prompts import ROUTING_AGENTS, SUPERVISOR_ROUTING, get_system_prompt
from ..logging_conf import log_event
from ..models import AgentMessage, ChatTurn, ToolCall
from ..tools import registry
from . import fallback
from .definitions import AGENT_TOOLS
from .reflection import reflect
from .router import keyword_route
from .verifier import verify


def _sse(obj: dict) -> str:
    """Сериализация события в формат Server-Sent Events."""
    return "data: " + json.dumps(obj, ensure_ascii=False, default=str) + "\n\n"


def _chunks(text: str, n: int = 3) -> Iterator[str]:
    """Псевдо-стрим: режем готовый текст на группы слов (для не-стрим провайдеров)."""
    words = text.split(" ")
    for i in range(0, len(words), n):
        piece = " ".join(words[i:i + n])
        yield piece + (" " if i + n < len(words) else "")


def synthesize_text(content: str, tool_calls: list[ToolCall]) -> str:
    """Если модель не вернула финальный текст, собрать краткое подтверждение."""
    if content and content.strip():
        return content
    ok = [tc.tool for tc in tool_calls if tc.ok]
    if ok:
        return "Готово. Выполнено: " + ", ".join(dict.fromkeys(ok)) + "."
    return "Готово."


class Orchestrator:
    def __init__(self) -> None:
        self.client = get_client()
        self.mode = self.client.provider if self.client else "none"

    # --- маршрутизация ---
    def route(self, message: str) -> tuple[str, str]:
        if self.client:
            try:
                agent = self.client.classify(
                    system=SUPERVISOR_ROUTING, user=message, choices=ROUTING_AGENTS)
                if agent in ROUTING_AGENTS:
                    return agent, "LLM-маршрутизация (Supervisor)"
            except Exception as exc:  # noqa: BLE001
                log_event("route_error", error=str(exc))
            return keyword_route(message), "Keyword-маршрутизация (fallback после ошибки LLM)"
        return keyword_route(message), "Keyword-маршрутизация (режим без LLM)"

    # --- выполнение профильного агента ---
    def _run_llm_agent(self, agent: str, message: str,
                       history: list[ChatTurn]) -> tuple[str, list[ToolCall]]:
        allowed = AGENT_TOOLS.get(agent, [])
        schemas = registry.schemas_for(allowed)

        def execute(name: str, args: dict) -> ToolCall:
            if name not in allowed:
                tc = ToolCall(agent=agent, tool=name, input=args, ok=False,
                              error=f"Инструмент {name} недоступен агенту {agent}")
                return tc
            return registry.execute(name, args, agent)

        hist = [{"role": h.role, "content": h.content}
                for h in history if h.role in ("user", "assistant")][-10:]
        result = self.client.run_agent_loop(
            system=get_system_prompt(agent),
            user_message=message,
            tool_schemas=schemas,
            execute_tool=execute,
            history=hist,
            max_steps=get_settings_max_steps(),
        )
        return result.final_text, result.tool_calls

    # --- основной вход ---
    def handle(self, message: str,
               history: Optional[list[ChatTurn]] = None,
               force_agent: Optional[str] = None) -> AgentMessage:
        history = history or []
        log_event("user_request", message=message, mode=self.mode,
                  force_agent=force_agent)

        if force_agent:
            agent, rationale = force_agent, "Принудительный выбор агента (endpoint)"
        else:
            agent, rationale = self.route(message)
        log_event("routed", agent=agent, rationale=rationale)

        if self.client:
            content, tool_calls = self._run_llm_agent(agent, message, history)
        else:
            content, tool_calls = fallback.handle(agent, message)

        reflection = reflect(message, agent, tool_calls, content)
        verification = verify(tool_calls)

        log_event("reflection", agent=agent, passed=reflection.passed,
                  issues=reflection.issues,
                  requires_confirmation=reflection.requires_user_confirmation)
        log_event("verification", agent=agent, passed=verification.passed,
                  summary=verification.summary)

        return AgentMessage(
            agent=agent, routed_to=agent, rationale=rationale,
            content=synthesize_text(content, tool_calls),
            tool_calls=tool_calls, reflection=reflection, verification=verification,
        )

    # --- потоковый вариант (SSE) ---
    def handle_stream(self, message: str,
                      history: Optional[list[ChatTurn]] = None) -> Iterator[str]:
        history = history or []
        log_event("user_request", message=message, mode=self.mode, stream=True)
        agent, rationale = self.route(message)
        log_event("routed", agent=agent, rationale=rationale)
        yield _sse({"event": "routed", "agent": agent, "rationale": rationale})

        allowed = AGENT_TOOLS.get(agent, [])
        collected: list[ToolCall] = []
        final_text = ""

        def execute(name: str, args: dict) -> ToolCall:
            if name not in allowed:
                return ToolCall(agent=agent, tool=name, input=args, ok=False,
                                error=f"Инструмент {name} недоступен агенту {agent}")
            return registry.execute(name, args, agent)

        if isinstance(self.client, OpenAIClient):
            hist = [{"role": h.role, "content": h.content}
                    for h in history if h.role in ("user", "assistant")][-10:]
            try:
                for ev, data in self.client.stream_agent_loop(
                    system=get_system_prompt(agent), user_message=message,
                    tool_schemas=registry.schemas_for(allowed),
                    execute_tool=execute, history=hist,
                    max_steps=get_settings_max_steps(),
                ):
                    if ev == "token":
                        final_text += data
                        yield _sse({"event": "token", "text": data})
                    elif ev == "tool_start":
                        yield _sse({"event": "tool_start", "tool": data})
                    elif ev == "tool":
                        collected.append(data)
                        yield _sse({"event": "tool", "tool": data.tool, "ok": data.ok})
                    elif ev == "result":
                        final_text = data.final_text or final_text
                        collected = data.tool_calls or collected
            except Exception as exc:  # noqa: BLE001 — не роняем поток, финализируем
                log_event("stream_error", error=str(exc))
        else:
            # rule-based / anthropic: токенов модели нет — отдаём прогресс и финал чанками
            if self.client:
                final_text, collected = self._run_llm_agent(agent, message, history)
            else:
                final_text, collected = fallback.handle(agent, message)
            for tc in collected:
                yield _sse({"event": "tool", "tool": tc.tool, "ok": tc.ok})
            for piece in _chunks(final_text):
                yield _sse({"event": "token", "text": piece})

        final_text = synthesize_text(final_text, collected)
        reflection = reflect(message, agent, collected, final_text)
        verification = verify(collected)
        log_event("reflection", agent=agent, passed=reflection.passed)
        log_event("verification", agent=agent, passed=verification.passed,
                  summary=verification.summary)
        msg = AgentMessage(
            agent=agent, routed_to=agent, rationale=rationale, content=final_text,
            tool_calls=collected, reflection=reflection, verification=verification,
        )
        yield _sse({"event": "done", "message": msg.model_dump(mode="json")})


def get_settings_max_steps() -> int:
    from ..config import get_settings
    return get_settings().max_agent_steps


@lru_cache
def get_orchestrator() -> Orchestrator:
    return Orchestrator()
