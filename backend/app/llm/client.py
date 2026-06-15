"""Абстракция над LLM-провайдерами + универсальный agent loop с tool-calling.

Поддерживаются Anthropic и OpenAI (выбор через .env). Если ключ не задан
(provider == none), get_client() возвращает None, и оркестратор переключается
в детерминированный режим (см. agents/fallback.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..config import Settings
from ..models import ToolCall

# Колбэк выполнения инструмента: (имя, аргументы) -> ToolCall
ExecuteTool = Callable[[str, dict], ToolCall]


@dataclass
class AgentRunResult:
    final_text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    steps: int = 0


def _dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


class LLMClient:
    provider = "base"

    def run_agent_loop(
        self, *, system: str, user_message: str,
        tool_schemas: list[dict], execute_tool: ExecuteTool,
        history: Optional[list[dict]] = None, max_steps: int = 8,
    ) -> AgentRunResult:
        raise NotImplementedError

    def classify(self, *, system: str, user: str, choices: list[str]) -> str:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
#  Anthropic
# --------------------------------------------------------------------------- #
class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(self, settings: Settings) -> None:
        import anthropic  # ленивый импорт

        self.s = settings
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def run_agent_loop(self, *, system, user_message, tool_schemas,
                       execute_tool, history=None, max_steps=8) -> AgentRunResult:
        messages: list[dict] = list(history or [])
        messages.append({"role": "user", "content": user_message})
        collected: list[ToolCall] = []
        last_text = ""

        for step in range(max_steps):
            kwargs = dict(
                model=self.s.anthropic_model,
                max_tokens=self.s.llm_max_tokens,
                temperature=self.s.llm_temperature,
                system=system,
                messages=messages,
            )
            if tool_schemas:
                kwargs["tools"] = tool_schemas
            resp = self.client.messages.create(**kwargs)

            assistant_content = []
            tool_results = []
            text_parts = []
            has_tool_use = False

            for block in resp.content:
                if block.type == "text":
                    text_parts.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    has_tool_use = True
                    assistant_content.append({
                        "type": "tool_use", "id": block.id,
                        "name": block.name, "input": block.input,
                    })
                    tc = execute_tool(block.name, block.input or {})
                    collected.append(tc)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _dumps(tc.output),
                        "is_error": not tc.ok,
                    })

            messages.append({"role": "assistant", "content": assistant_content})
            last_text = "\n".join(text_parts).strip() or last_text

            if not has_tool_use:
                return AgentRunResult(last_text, collected, step + 1)
            messages.append({"role": "user", "content": tool_results})

        return AgentRunResult(
            last_text or "(достигнут лимит шагов агента)", collected, max_steps)

    def classify(self, *, system, user, choices) -> str:
        resp = self.client.messages.create(
            model=self.s.anthropic_model,
            max_tokens=20,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").lower()
        return _match_choice(text, choices)


# --------------------------------------------------------------------------- #
#  OpenAI
# --------------------------------------------------------------------------- #
class OpenAIClient(LLMClient):
    provider = "openai"

    def __init__(self, settings: Settings, base_url: Optional[str] = None,
                 api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        from openai import OpenAI  # ленивый импорт

        self.s = settings
        self.model = model or settings.openai_model
        kwargs = {"api_key": api_key or settings.openai_api_key or "local"}
        burl = base_url or settings.openai_base_url
        if burl:
            kwargs["base_url"] = burl
        self.client = OpenAI(**kwargs)

    def _tools(self, tool_schemas: list[dict]) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": t["input_schema"],
            }}
            for t in tool_schemas
        ]

    def run_agent_loop(self, *, system, user_message, tool_schemas,
                       execute_tool, history=None, max_steps=8) -> AgentRunResult:
        messages: list[dict] = [{"role": "system", "content": system}]
        messages += list(history or [])
        messages.append({"role": "user", "content": user_message})
        oa_tools = self._tools(tool_schemas)
        collected: list[ToolCall] = []
        last_text = ""

        for step in range(max_steps):
            kwargs = dict(
                model=self.model,
                temperature=self.s.llm_temperature,
                max_tokens=self.s.llm_max_tokens,
                messages=messages,
            )
            if oa_tools:
                kwargs["tools"] = oa_tools
            resp = self.client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            last_text = msg.content or last_text

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [{
                        "id": tc.id, "type": "function",
                        "function": {"name": tc.function.name,
                                     "arguments": tc.function.arguments},
                    } for tc in msg.tool_calls],
                })
                for tcall in msg.tool_calls:
                    try:
                        args = json.loads(tcall.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    tc = execute_tool(tcall.function.name, args)
                    collected.append(tc)
                    messages.append({
                        "role": "tool", "tool_call_id": tcall.id,
                        "content": _dumps(tc.output),
                    })
                continue

            return AgentRunResult(msg.content or "", collected, step + 1)

        return AgentRunResult(
            last_text or "(достигнут лимит шагов агента)", collected, max_steps)

    def stream_agent_loop(self, *, system, user_message, tool_schemas,
                          execute_tool, history=None, max_steps=8):
        """Генератор событий стрима:
        ('token', str) | ('tool_start', name) | ('tool', ToolCall) |
        ('result', AgentRunResult).
        """
        messages: list[dict] = [{"role": "system", "content": system}]
        messages += list(history or [])
        messages.append({"role": "user", "content": user_message})
        oa_tools = self._tools(tool_schemas)
        collected: list[ToolCall] = []
        last_text = ""

        for step in range(max_steps):
            kwargs = dict(model=self.model, temperature=self.s.llm_temperature,
                          max_tokens=self.s.llm_max_tokens, messages=messages,
                          stream=True)
            if oa_tools:
                kwargs["tools"] = oa_tools
            stream = self.client.chat.completions.create(**kwargs)

            content_buf = ""
            tools_acc: dict[int, dict] = {}
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    content_buf += delta.content
                    yield ("token", delta.content)
                for tc in (getattr(delta, "tool_calls", None) or []):
                    acc = tools_acc.setdefault(
                        tc.index, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function and tc.function.name:
                        acc["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        acc["args"] += tc.function.arguments

            if tools_acc:
                messages.append({
                    "role": "assistant",
                    "content": content_buf or None,
                    "tool_calls": [{
                        "id": a["id"] or f"call_{i}", "type": "function",
                        "function": {"name": a["name"], "arguments": a["args"] or "{}"},
                    } for i, a in tools_acc.items()],
                })
                for i, a in tools_acc.items():
                    yield ("tool_start", a["name"])
                    try:
                        args = json.loads(a["args"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    rec = execute_tool(a["name"], args)
                    collected.append(rec)
                    yield ("tool", rec)
                    messages.append({"role": "tool",
                                     "tool_call_id": a["id"] or f"call_{i}",
                                     "content": _dumps(rec.output)})
                last_text = content_buf or last_text
                continue

            last_text = content_buf or last_text
            yield ("result", AgentRunResult(last_text, collected, step + 1))
            return

        yield ("result", AgentRunResult(
            last_text or "(достигнут лимит шагов агента)", collected, max_steps))

    def classify(self, *, system, user, choices) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=20,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return _match_choice((resp.choices[0].message.content or "").lower(), choices)


def _match_choice(text: str, choices: list[str]) -> str:
    text = text.strip().lower()
    for c in choices:
        if c.lower() == text:
            return c
    for c in choices:
        if c.lower() in text:
            return c
    return choices[0] if choices else ""
