# Локальный мультиагентный личный ассистент

Локальный ассистент для управления задачами, календарём, личной памятью,
планированием и режимом сна. Это **мультиагентная система** с инструментами,
маршрутизацией, рефлексией и проверкой результата — а не просто чат-бот.

Работает полностью локально: данные лежат в JSON-файлах на вашем устройстве,
inference выполняется локальной LLM (Qwen 3.5 9B в int6) через Docker.

## Возможности

- Задачи в стиле Jira (статусы, приоритеты, дедлайны, теги, проекты).
- Разбиение большой задачи на чеклист и отметка пунктов по ходу работы.
- Локальный календарь (события, свободные слоты, проверка конфликтов).
- Личная память пользователя (предпочтения, правила, контекст).
- Утренний и вечерний дайджесты.
- Приоритизация: ответ на вопрос «Что мне делать дальше?».
- Свободное планирование: «надо сделать X, Y, Z за неделю».
- Агент «Сонная фея» для режима сна.
- Reflection Agent и Verifier Agent для самопроверки результата.
- Локальный фронтенд: Chat, Tasks, Calendar, Memory, Digest.

## Архитектура (кратко)

```
Браузер → frontend (nginx) → backend (FastAPI) → local LLM (llama.cpp)
                                   │                      │
                                   ├── ./data  (storage)  └── ./models (GGUF)
                                   └── ./logs  (логи)
```

Supervisor маршрутизирует запрос профильному агенту (Task / Calendar / Planning /
Prioritization / Memory / Digest / Sleep Fairy). Агент вызывает инструменты,
затем Reflection проверяет полноту, а Verifier — фактические изменения в storage.
Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/AGENTS.md](docs/AGENTS.md), [docs/DOCKER_ARCHITECTURE.md](docs/DOCKER_ARCHITECTURE.md).

## Быстрый старт через Docker (рекомендуется)

Запускается одной командой. Нужны Docker + Docker Compose и файл модели в `./models`.

```bash
cp .env.example .env
# положите GGUF-файл Qwen 3.5 9B (int6 / Q6_K) в ./models/ (см. models/README.md)
make check-model
make build
make up
```

Откройте:
- Frontend: <http://localhost:3000>
- Backend API + Swagger: <http://localhost:8000/docs>
- Проверка LLM: `make health`

Остановить: `make down`. Полная инструкция — [docs/DEPLOYMENT_LOCAL.md](docs/DEPLOYMENT_LOCAL.md).

GPU-режим (NVIDIA): `make up-gpu` (выставьте `LLM_GPU_LAYERS` в `.env`).

## Запуск без Docker (режим разработки)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # при желании укажите ключ/локальный LLM
python run.py               # http://127.0.0.1:8000
```

Frontend (в другом терминале):

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173 (проксирует /api на :8000)
```

Без настроенного LLM backend работает в **деградационном rule-based режиме**:
маршрутизация по ключевым словам и эвристики. Демо-сценарии при этом проходят,
но «интеллект» агентов ограничен. Для полноценной работы настройте LLM
(локальный `local_openai` или облачный `anthropic`/`openai`) — см.
[docs/LLM_LOCAL_INFERENCE.md](docs/LLM_LOCAL_INFERENCE.md).

## Демо-данные

```bash
curl -X POST http://localhost:8000/demo/seed     # наполнить примерами
curl -X POST http://localhost:8000/demo/reset    # очистить
```

В UI те же действия — кнопки «Загрузить демо» / «Сброс». Готовые сценарии
защиты — [docs/DEMO_SCENARIOS.md](docs/DEMO_SCENARIOS.md).

## Структура проекта

```
backend/            FastAPI backend
  app/
    models.py       Pydantic-модели (Task, Event, Memory, Digest, …)
    storage.py      JSON storage layer
    config.py       настройки из env/.env
    tools/          инструменты + реестр (39 шт.)
    llm/            провайдер LLM (anthropic/openai/local_openai) + agent loop
    agents/         supervisor, профильные агенты, reflection, verifier
    routers/        REST endpoints
    seed.py         демо-данные
  evals/eval.py     метрики качества
frontend/           Vite + React + TypeScript (Chat/Tasks/Calendar/Memory/Digest)
docs/               документация (см. ниже)
data/  logs/        локальные данные и логи (монтируются в контейнеры)
models/             сюда кладётся GGUF-модель (не качается автоматически)
docker-compose.yml  + Dockerfile.* + Makefile + scripts/
```

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура, поток запроса, storage.
- [docs/AGENTS.md](docs/AGENTS.md) — роли агентов, доступные инструменты, ограничения.
- [docs/TOOLS.md](docs/TOOLS.md) — справочник всех инструментов (вход/выход).
- [docs/DEMO_SCENARIOS.md](docs/DEMO_SCENARIOS.md) — 3 демо-сценария.
- [docs/METRICS.md](docs/METRICS.md) — метрики качества и eval-скрипт.
- [docs/DEPLOYMENT_LOCAL.md](docs/DEPLOYMENT_LOCAL.md) — локальный запуск через Docker.
- [docs/LLM_LOCAL_INFERENCE.md](docs/LLM_LOCAL_INFERENCE.md) — локальный inference (Qwen/llama.cpp).
- [docs/DOCKER_ARCHITECTURE.md](docs/DOCKER_ARCHITECTURE.md) — контейнеры, порты, volume'ы.
- [CHANGELOG.md](CHANGELOG.md) — история изменений.

## Ограничения

Это рабочий прототип, а не production-система: без сложной авторизации, облачной
синхронизации и реальной отправки писем. Главный приоритет — рабочий end-to-end
сценарий, прозрачные tool calls, локальные данные и проверяемые изменения.
