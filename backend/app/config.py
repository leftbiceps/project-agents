"""Конфигурация приложения.

Настройки читаются из переменных окружения и файла backend/.env
(см. .env.example). Доступ к настройкам — через get_settings().
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend -> <корень проекта>
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Глобальные настройки, заполняются из окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM ---
    # auto = anthropic, если задан ключ, иначе openai, иначе none.
    # local_openai = локальный OpenAI-совместимый сервер (llama.cpp / Qwen).
    llm_provider: Literal["anthropic", "openai", "local_openai", "none", "auto"] = "auto"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    openai_base_url: Optional[str] = None

    # Локальный inference (llama.cpp server, OpenAI-compatible).
    llm_base_url: Optional[str] = None          # напр. http://llm:8000/v1
    llm_api_key: Optional[str] = None           # для llama.cpp обычно "local"
    llm_model: str = "qwen-3.5-9b-int6"

    llm_max_tokens: int = 1500
    llm_temperature: float = 0.2
    max_agent_steps: int = 8

    # --- Пути к данным и логам ---
    data_dir: Path = PROJECT_ROOT / "data"
    logs_dir: Path = PROJECT_ROOT / "logs"

    # --- Прочее ---
    timezone: str = "Europe/Moscow"
    cors_origins: str = "*"

    def resolved_provider(self) -> str:
        """Фактический провайдер с учётом режима auto."""
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "none"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "knowledge_base").mkdir(parents=True, exist_ok=True)
    return settings
