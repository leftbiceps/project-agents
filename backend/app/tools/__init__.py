"""Tool layer: реестр инструментов и их регистрация.

Импорт этого пакета регистрирует все инструменты в общем `registry`.
"""
from __future__ import annotations

from .registry import Tool, ToolError, ToolRegistry, registry, tool

# Импортируем модули ради их side-effect (регистрация инструментов).
from . import task_tools  # noqa: E402,F401
from . import calendar_tools  # noqa: E402,F401
from . import memory_tools  # noqa: E402,F401
from . import digest_tools  # noqa: E402,F401
from . import planning_tools  # noqa: E402,F401
from . import kb_tools  # noqa: E402,F401

__all__ = ["Tool", "ToolError", "ToolRegistry", "registry", "tool"]
