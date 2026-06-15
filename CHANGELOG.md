# CHANGELOG

Все существенные изменения проекта документируются здесь.
Формат записи: дата · что изменено · затронутые файлы · зачем · как проверить.

---

## 2026-06-15 — v0.3.0 · Стриминг ответа, персистентная история чата, UX

**Что изменено**

- Потоковый ответ в чате: SSE-эндпоинт `POST /chat/stream` (события
  routed / token / tool / done). Фронт показывает ответ по мере генерации,
  с автоматическим откатом на обычный `/chat`, если стрим недоступен.
- История чата сохраняется в `localStorage` (не пропадает при перезагрузке
  страницы / перезапуске), добавлена кнопка «Очистить».
- Календарь теперь показывает дедлайны задач (⏰) в дни их срока — помимо
  событий, созданных планировщиком.
- Локальный LLM запускается с `--jinja` (включает tool-calling для Qwen).
- Если модель после tool-call не вернула текст — формируется краткое
  подтверждение (нет пустых ответов «агент не вернул текста»).
- `run.sh` корректно работает с несколькими моделями: уважает явный
  `LLM_MODEL_PATH` из `.env`, иначе берёт самый свежий `.gguf`.

**Затронутые файлы**

- backend: `app/agents/orchestrator.py`, `app/llm/client.py`,
  `app/routers/chat.py`
- frontend: `src/pages/Chat.tsx`, `src/pages/Calendar.tsx`, `src/api.ts`
- инфра: `docker-compose.yml` (`--jinja`), `docker/nginx.conf` (SSE без
  буферизации), `run.sh`

**Как проверить**

`bash run.sh` → открыть чат: ответ печатается по токенам; перезагрузить
страницу — переписка на месте; на вкладке Calendar видны дедлайны задач.

---

## 2026-06-08 — v0.2.0 · Docker Compose + локальный LLM inference

**Что изменено**

- Добавлена контейнеризация: проект поднимается одной командой (`make up`).
- Добавлен сервис локального inference (llama.cpp server, OpenAI-compatible)
  для Qwen 3.5 9B int6; модель монтируется из `./models`.
- LLM-провайдер вынесен в адаптер `app/llm/provider.py`; добавлен режим
  `local_openai` (base_url / api_key / model из env). Хардкода ключей/URL нет.
- Добавлены эндпоинты `GET /health` (`{"status":"ok","service":"backend"}`) и
  `GET /health/llm` (проверка доступности LLM без падения backend).
- Добавлены CPU-режим (по умолчанию) и GPU-режим (`make up-gpu`, NVIDIA).
- Healthchecks для всех трёх сервисов; persistent storage через `./data`,
  `./logs`; frontend на nginx проксирует `/api` на backend.
- Makefile с командами и скрипты `check_local_model.sh`, `wait_for_llm.sh`.

**Затронутые файлы**

- Новые: `Dockerfile.backend`, `Dockerfile.frontend`, `docker/nginx.conf`,
  `docker-compose.yml`, `docker-compose.gpu.yml`, `.dockerignore`, `.env.example`
  (корневой), `Makefile`, `scripts/check_local_model.sh`,
  `scripts/wait_for_llm.sh`, `models/README.md`,
  `docs/DEPLOYMENT_LOCAL.md`, `docs/LLM_LOCAL_INFERENCE.md`,
  `docs/DOCKER_ARCHITECTURE.md`.
- Изменены: `backend/app/config.py` (env `LLM_PROVIDER=local_openai`,
  `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`), `backend/app/llm/client.py`
  (OpenAIClient принимает base_url/api_key/model), `backend/app/llm/__init__.py`,
  `backend/app/main.py` (`/health`, `/health/llm`), `.gitignore`.

**Зачем**

Дать локальный, воспроизводимый запуск всего стека (frontend + backend + LLM)
одной командой, с локальным inference и без внешних API-ключей.

**Как проверить**

```bash
cp .env.example .env
make check-model          # положив GGUF в ./models
make build && make up
make ps                   # все сервисы healthy
make health               # /health и /health/llm
# Frontend http://localhost:3000, Backend http://localhost:8000/docs
# Создать задачу в чате → make down && make up → задача на месте (./data)
```

---

## 2026-06-08 — v0.1.0 · Базовая мультиагентная система (MVP1 + MVP2)

**Что изменено**

- Backend на FastAPI: модели, JSON storage, реестр из 39 инструментов.
- 10 агентов: Supervisor, Task, Calendar, Planning, Prioritization, Memory,
  Digest, Sleep Fairy, Reflection (детерминированный), Verifier (детерминированный).
- LLM-слой с tool-calling (Anthropic/OpenAI) и rule-based деградацией без ключа.
- REST API: `/chat`, `/tasks`, `/calendar/events`, `/memory`, `/digest/*`,
  `/plan`, `/prioritize`, `/sleep-mode`, мета- и demo-эндпоинты.
- Frontend (Vite + React + TS): Chat (с визуализацией tool calls и
  Reflection/Verifier), Tasks (Jira-доска), Calendar, Memory, Digest.
- Логирование в `logs/agent.log`; eval-скрипт `backend/evals/eval.py`.
- Документация: ARCHITECTURE, AGENTS, TOOLS, DEMO_SCENARIOS, METRICS.

**Затронутые файлы**

- `backend/app/**` (models, storage, config, logging, utils, scoring, tools/,
  llm/, agents/, routers/, seed, main), `backend/requirements.txt`,
  `backend/run.py`, `frontend/**`, `docs/**`, `README.md`.

**Зачем**

Реализовать рабочий end-to-end мультиагентный ассистент по ТЗ: задачи,
чеклисты, календарь, память, дайджесты, планирование, приоритизация, режим сна,
с прозрачными tool calls и проверяемыми изменениями.

**Как проверить**

```bash
cd backend && pip install -r requirements.txt
python evals/eval.py      # метрики качества по сценариям
python run.py             # затем frontend: cd frontend && npm install && npm run dev
```
