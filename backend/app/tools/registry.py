"""Реестр инструментов.

Каждый инструмент — функция-обработчик с Pydantic-схемой входа. Реестр умеет:
  * отдавать JSON-схемы инструментов для LLM (tool-calling);
  * валидировать вход, выполнять инструмент, нормализовать выход;
  * логировать каждый вызов и ошибки.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel, ValidationError

from ..logging_conf import log_event
from ..models import ToolCall


class ToolError(Exception):
    """Ошибка валидации или выполнения инструмента."""


def _normalize(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, list):
        return [_normalize(x) for x in result]
    if isinstance(result, dict):
        return {k: _normalize(v) for k, v in result.items()}
    return result


@dataclass
class Tool:
    name: str
    description: str
    input_model: Type[BaseModel]
    handler: Callable[[BaseModel], Any]
    output_hint: str = ""

    def input_schema(self) -> dict:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return schema

    def llm_schema(self) -> dict:
        """Схема в формате, понятном Anthropic/OpenAI tool-calling."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }

    def run(self, raw: Optional[dict]) -> Any:
        try:
            data = self.input_model.model_validate(raw or {})
        except ValidationError as exc:
            raise ToolError(
                f"Некорректные аргументы для '{self.name}': {exc}"
            ) from exc
        return _normalize(self.handler(data))


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool_obj: Tool) -> None:
        self._tools[tool_obj.name] = tool_obj

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"Неизвестный инструмент: {name}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas_for(self, names: list[str]) -> list[dict]:
        return [self._tools[n].llm_schema() for n in names if n in self._tools]

    def execute(self, name: str, raw_input: Optional[dict], agent: str) -> ToolCall:
        """Выполнить инструмент и вернуть запись ToolCall (с логированием)."""
        call = ToolCall(agent=agent, tool=name, input=raw_input or {})
        log_event("tool_call", agent=agent, tool=name, input=raw_input or {})
        try:
            call.output = self.get(name).run(raw_input)
            call.ok = True
            log_event("tool_result", agent=agent, tool=name, ok=True)
        except Exception as exc:  # noqa: BLE001 — логируем любую ошибку инструмента
            call.ok = False
            call.error = str(exc)
            call.output = {"error": str(exc)}
            log_event("tool_error", agent=agent, tool=name, error=str(exc))
        return call


registry = ToolRegistry()


def tool(name: str, description: str, input_model: Type[BaseModel],
         output_hint: str = "") -> Callable:
    """Декоратор для регистрации инструмента."""

    def decorator(fn: Callable[[BaseModel], Any]) -> Callable:
        registry.register(Tool(name, description, input_model, fn, output_hint))
        return fn

    return decorator
