# DEPLOYMENT_LOCAL — локальный запуск через Docker

Проект поднимается одной командой и работает полностью локально: frontend,
backend и локальный LLM (Qwen 3.5 9B int6) в отдельных контейнерах.

## 1. Требования

- **Docker** (20.10+) и **Docker Compose v2** (`docker compose`).
- **RAM:** для Qwen 3.5 9B в int6 (Q6_K) рекомендуется **≥ 12–16 ГБ** свободной
  памяти (сама модель ~7–8 ГБ + контекст). Меньше — см. раздел про нехватку RAM
  в [LLM_LOCAL_INFERENCE.md](LLM_LOCAL_INFERENCE.md).
- **Локальный файл модели** в `./models` (GGUF, int6 / Q6_K). Модель
  **не скачивается автоматически**.
- (Опционально) NVIDIA GPU + `nvidia-container-toolkit` для GPU-режима.

## 2. Как положить модель

```bash
mkdir -p models
# поместите GGUF-файл, например:
#   ./models/qwen-3.5-9b-int6.gguf
```

Имя файла должно совпадать с `basename` из `LLM_MODEL_PATH` в `.env`
(по умолчанию `/models/qwen-3.5-9b-int6.gguf` → файл `qwen-3.5-9b-int6.gguf`).
Подробности — `models/README.md`.

## 3. Как запустить

```bash
cp .env.example .env     # конфигурация (по умолчанию режим local_openai)
make check-model         # проверит, что файл модели на месте
make build               # собрать образы backend и frontend
make up                  # запустить все сервисы (CPU режим)
```

Первый старт LLM-контейнера может занять время (загрузка модели в память).
Готовность можно дождаться скриптом:

```bash
bash scripts/wait_for_llm.sh
```

GPU-режим (NVIDIA): выставьте `LLM_GPU_LAYERS` в `.env` (например `999`) и:

```bash
make up-gpu
```

## 4. Как открыть

- **Frontend:** <http://localhost:3000>
- **Backend API:** <http://localhost:8000>
- **Swagger (docs):** <http://localhost:8000/docs>

## 5. Как проверить LLM

```bash
make health
```

Выводит `GET /health` (backend жив) и `GET /health/llm` (доступность локального
LLM). Если модель ещё грузится, `/health/llm` вернёт `degraded` — это нормально,
backend при этом не падает.

Ручная проверка OpenAI-совместимого эндпоинта:

```bash
curl http://localhost:8001/v1/models
```

## 6. Как смотреть логи

```bash
make logs            # все сервисы
make logs-backend    # только backend
make logs-llm        # только LLM
```

Журнал агента также пишется в `./logs/agent.log` на хосте.

## 7. Как остановить

```bash
make down            # остановить контейнеры (данные в ./data сохраняются)
make clean           # остановить и удалить volume'ы
```

## 8. Проверка persistence

Создайте задачу (через чат или вкладку Tasks), затем:

```bash
make down && make up
```

Задача останется на месте — данные лежат в `./data` на хосте.

## Частые проблемы

- **`make check-model` ругается на отсутствие файла** — положите GGUF в `./models`
  и проверьте имя относительно `LLM_MODEL_PATH`.
- **LLM долго стартует / `/health/llm` = degraded** — большая модель грузится
  не мгновенно; смотрите `make logs-llm`, дождитесь `wait_for_llm.sh`.
- **Порт занят** — измените `FRONTEND_PORT` / `BACKEND_PORT` / `LLM_PORT` в `.env`.
- **Нет Docker** — можно запустить без контейнеров (см. README, раздел «Запуск
  без Docker»).
