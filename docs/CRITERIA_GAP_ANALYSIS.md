# Разбор по критериям и gap-анализ

Честная сводка: что закрыто, чем закрыто и что осталось. Статусы:
✅ закрыто · 🟡 частично · ⛔ gap (в плане).

## Агентность

| Критерий | Статус | Чем закрыто | Остаток |
|---|---|---|---|
| Role (роли/узлы) | ✅ | Supervisor + 7 профильных агентов + Reflection + Verifier (`app/agents/*`, `app/llm/prompts.py`) | — |
| Reasoning | ✅ | роутинг, планирование (`planning_tools.py`), приоритизация (`scoring.py`) | усилить live-LLM reasoning |
| Reflection | ✅ | `app/agents/reflection.py` (полнота, конфликты, дедлайны, подтверждение) | — |
| Memory | ✅ | `data/memory.json` (типизированная), используется в planning/prioritization | авто-подмешивание в контекст (опция) |
| Domain knowledge | 🟡 | эвристики scoring/slots, опц. markdown KB | vector RAG не реализован |
| Autonomy + Action | ✅ | 39 typed-инструментов, без подтверждения на каждый шаг; подтверждение для удаления | — |

## Инженерия и оформление

| Критерий | Статус | Чем закрыто | Остаток |
|---|---|---|---|
| Ролевая модель (роль→модуль→метрика) | ✅ | таблица в [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | — |
| Системные промпты по ролям | ✅ | `app/llm/prompts.py` (header + тело роли + SUPERVISOR_ROUTING) | — |
| Архитектура + диаграммы | ✅ | [ARCHITECTURE.md](ARCHITECTURE.md) (Mermaid), [architecture.puml](architecture.puml) (PlantUML), [DOCKER_ARCHITECTURE.md](DOCKER_ARCHITECTURE.md) | drawio при желании |
| Typed data/tool layer | ✅ | `app/tools/*` + `registry.py` (Pydantic вход/выход) | — |
| Production-grade данные | 🟡 | JSON storage, атомарная запись, persistence через volume | SSO/RBAC/secret manager, индексы/транзакции, vector store |
| Метрики + quality gate + честный snapshot | ✅ | `evals/eval.py --enforce-gate`, [METRICS.md](METRICS.md) | live-LLM benchmark по нескольким прогонам |
| Детерминированные тесты | ✅ | `backend/tests/` (pytest, 26 тестов: tools/scoring/verifier/reflection/storage/router) | расширять покрытие |
| Прототип: UI + API | ✅ | React (Chat/Tasks/Calendar/Memory/Digest) + FastAPI | — |
| Демо-сценарии | ✅ | [DEMO_SCENARIOS.md](DEMO_SCENARIOS.md) | приложить скриншоты |
| Локальный inference / запуск одной командой | ✅ | Docker Compose, `run.sh`, local Qwen (llama.cpp), CPU/GPU | — |
| Healthchecks / эксплуатация | ✅ | `/health`, `/health/llm`, healthcheck во всех сервисах | централизованная observability |

## Что у корешей есть, а у нас в плане (⛔/🟡)

| Их артефакт | Наш статус | Комментарий |
|---|---|---|
| Live-LLM benchmark runner (`run_benchmark`, pass@k) | 🟡 | `eval.py` работает и на live-LLM; нет повторных прогонов/pass@k |
| Human feedback rubric | ⛔ | можно добавить шаблон CSV для ручной оценки |
| Внешний MCP-провайдер (live example) | ⛔ | архитектура допускает (typed tool layer), но интеграция не сделана |
| Production contour (SSO/RBAC/observability) | ⛔ | спроектировано/описано, не реализовано |
| Скриншоты демо | ⛔ | сценарии есть текстом; скриншоты не приложены |
| Vector DB для knowledge base | ⛔ | сейчас markdown/lexical |

## План закрытия оставшихся gap'ов

1. Добавить repeated-benchmark режим в `eval.py` (несколько прогонов, агрегаты
   reliability) для честного сравнения 4B/9B на live-LLM.
2. Шаблон human-review (`data/qa/human_feedback_template.csv`).
3. Приложить скриншоты демо в `docs/demo_assets/`.
4. MCP-адаптер инструментов (config-driven) как опциональный источник.
5. Production-контур: SSO/RBAC/secret manager, централизованные логи/метрики,
   vector store для базы знаний.

## Вывод

Базовые признаки агентности и инженерные критерии (роли, промпты, архитектура,
typed tools, метрики с quality gate, детерминированные тесты, локальный
inference, healthchecks, документация) — **закрыты**. Оставшиеся пункты —
production-grade инфраструктура, live-benchmark, human-rubric, MCP и скриншоты —
вынесены в план и честно отмечены как незакрытые.
