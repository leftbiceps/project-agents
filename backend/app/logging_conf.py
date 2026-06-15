"""Настройка логирования.

Все события (запрос пользователя, выбранный агент, tool calls, изменения
storage, результаты Reflection/Verifier, ошибки) пишутся в logs/agent.log
и дублируются в stdout.
"""
from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Any

from .config import get_settings

_LOGGER_NAME = "assistant"


def setup_logging() -> logging.Logger:
    settings = get_settings()
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:  # уже настроено
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        settings.logs_dir / "agent.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


logger = setup_logging()


def log_event(event: str, **fields: Any) -> None:
    """Структурированное событие одной строкой JSON (удобно грепать)."""
    payload = {"event": event, **fields}
    try:
        logger.info(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:  # на всякий случай не роняем основной поток
        logger.info("%s | %s", event, fields)
