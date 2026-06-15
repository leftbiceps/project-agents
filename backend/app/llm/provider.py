"""LLM provider adapter.

Единая точка выбора LLM-провайдера. Все агенты ходят к LLM через этот модуль
(`get_client`), а не импортируют конкретный клиент напрямую. Поддерживаются:

  * anthropic       — облачный Anthropic API;
  * openai          — облачный OpenAI API;
  * local_openai    — локальный OpenAI-совместимый сервер (llama.cpp / Qwen),
                      адрес и ключ берутся из env (LLM_BASE_URL / LLM_API_KEY /
                      LLM_MODEL);
  * none            — деградационный rule-based режим (без ключа/сервера).

Никаких hardcoded ключей, моделей или URL — всё из конфигурации (env / .env).
"""
from __future__ import annotations

from typing import Optional

import httpx

from ..config import get_settings
from ..logging_conf import log_event
from .client import AnthropicClient, LLMClient, OpenAIClient

DEFAULT_LOCAL_BASE_URL = "http://llm:8000/v1"


def get_client() -> Optional[LLMClient]:
    """Построить LLM-клиент согласно конфигурации (или None для rule-based)."""
    s = get_settings()
    provider = s.resolved_provider()
    try:
        if provider == "anthropic":
            log_event("llm_client", provider="anthropic", model=s.anthropic_model)
            return AnthropicClient(s)
        if provider == "openai":
            log_event("llm_client", provider="openai", model=s.openai_model)
            return OpenAIClient(s)
        if provider == "local_openai":
            base = s.llm_base_url or DEFAULT_LOCAL_BASE_URL
            log_event("llm_client", provider="local_openai",
                      model=s.llm_model, base_url=base)
            return OpenAIClient(s, base_url=base,
                                api_key=s.llm_api_key or "local",
                                model=s.llm_model)
    except Exception as exc:  # пакет не установлен / ключ битый
        log_event("llm_client_error", provider=provider, error=str(exc))
        return None
    log_event("llm_client", provider="none")
    return None


def _effective_endpoint() -> tuple[str, Optional[str], Optional[str], str]:
    """(base_url, api_key, model, provider) для проверки доступности."""
    s = get_settings()
    provider = s.resolved_provider()
    if provider == "local_openai":
        return (s.llm_base_url or DEFAULT_LOCAL_BASE_URL,
                s.llm_api_key or "local", s.llm_model, provider)
    if provider == "openai":
        return (s.openai_base_url or "https://api.openai.com/v1",
                s.openai_api_key, s.openai_model, provider)
    if provider == "anthropic":
        return ("https://api.anthropic.com", s.anthropic_api_key,
                s.anthropic_model, provider)
    return ("", None, None, "none")


def llm_health(timeout: float = 4.0) -> dict:
    """Проверить доступность LLM, не роняя backend.

    Для OpenAI-совместимых провайдеров делает GET {base_url}/models.
    Возвращает {reachable, provider, base_url, model, detail}.
    """
    base_url, api_key, model, provider = _effective_endpoint()

    if provider == "none":
        return {
            "reachable": False, "provider": "none", "base_url": None,
            "model": None,
            "detail": "LLM не настроен — система работает в rule-based режиме.",
        }

    if provider == "anthropic":
        return {
            "reachable": bool(api_key), "provider": provider,
            "base_url": base_url, "model": model,
            "detail": ("Ключ задан (удалённый API)." if api_key
                       else "ANTHROPIC_API_KEY не задан."),
        }

    # openai / local_openai — пингуем /models
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        # trust_env=False — не ходить через системный прокси (важно для
        # обращения к внутреннему адресу llm-контейнера).
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            resp = client.get(url, headers=headers)
        ok = resp.status_code < 500
        return {
            "reachable": ok, "provider": provider, "base_url": base_url,
            "model": model, "status_code": resp.status_code,
            "detail": ("LLM endpoint доступен." if ok
                       else f"LLM ответил кодом {resp.status_code}."),
        }
    except Exception as exc:  # сервер не поднят / недоступен
        return {
            "reachable": False, "provider": provider, "base_url": base_url,
            "model": model,
            "detail": f"LLM недоступен по {url}: {exc}",
        }
