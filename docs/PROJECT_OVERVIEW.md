# Расширенный обзор проекта

Локальный мультиагентный личный ассистент: задачи, календарь, личная память,
планирование, приоритизация, дайджесты и режим сна. Полностью локальный запуск
(Docker + локальный LLM Qwen через llama.cpp), прозрачные tool calls,
самопроверка результата (Reflection + Verifier).

## Материалы под критерии

- Архитектура и поток запроса: [ARCHITECTURE.md](ARCHITECTURE.md)
- Диаграмма архитектуры (PlantUML): [architecture.puml](architecture.puml)
- Контейнерная архитектура (Mermaid): [DOCKER_ARCHITECTURE.md](DOCKER_ARCHITECTURE.md)
- Агенты, роли, ограничения: [AGENTS.md](AGENTS.md)
- Справочник инструментов: [TOOLS.md](TOOLS.md)
- Метрики качества и quality gate: [METRICS.md](METRICS.md)
- Разбор по критериям и оставшиеся gap'ы: [CRITERIA_GAP_ANALYSIS.md](CRITERIA_GAP_ANALYSIS.md)
- Демо-сценарии: [DEMO_SCENARIOS.md](DEMO_SCENARIOS.md)
- Локальный запуск: [DEPLOYMENT_LOCAL.md](DEPLOYMENT_LOCAL.md)
- Локальный inference (Qwen/llama.cpp): [LLM_LOCAL_INFERENCE.md](LLM_LOCAL_INFERENCE.md)
- История изменений: [../CHANGELOG.md](../CHANGELOG.md)

## Почему это именно агент

Проект закрывает базовые признаки агентности:

- **Role**: запрос обрабатывает не один промпт, а граф ролей — `Supervisor`
  (маршрутизатор) и профильные агенты `task / calendar / planning /
  prioritization / memory / digest / sleep_fairy`. Системные промпты у ролей
  различаются по задаче и ограничениям (`app/llm/prompts.py`).
- **Reasoning**: агент не идёт по жёсткому `if-then` — он классифицирует intent,
  планирует (разбивает цели на задачи, оценивает длительность, ищет свободные
  окна), приоритизирует с учётом дедлайнов/срочности/памяти.
- **Reflection**: `Reflection Agent` проверяет полноту (выполнена ли цель, нет ли
  конфликтов календаря и задач без дедлайна, нужно ли подтверждение), а
  `Verifier Agent` проверяет фактические изменения в storage.
- **Memory**: личная память (`data/memory.json`, типы `user_preference`,
  `recurring_routine`, `constraint`, …) сохраняется на диск и используется при
  планировании и приоритизации.
- **Domain knowledge**: эвристики приоритизации (`app/scoring.py`), модель
  рабочего дня и свободных слотов (`app/utils.py`), опциональная Obsidian-like
  база знаний (`data/knowledge_base/*.md`).
- **Autonomy + Action**: агент сам вызывает инструменты (39 шт., typed Pydantic),
  делает structured-запросы к tool layer и не спрашивает подтверждение на каждом
  промежуточном шаге — только для необратимых действий (удаление).

## Ролевая модель решения

Задача сформулирована как набор ролей внутри orchestrated agent pipeline, а не
один большой prompt.

| Роль | Модуль | Что делает | Основная метрика |
|---|---|---|---|
| Supervisor / Router | `app/agents/orchestrator.py`, `router.py` | определяет агента под запрос | `Routing Accuracy` |
| Task Agent | `app/tools/task_tools.py` | задачи и чеклисты (Jira-стиль) | `Task Success Rate`, `Checklist Completion` |
| Calendar Agent | `app/tools/calendar_tools.py` | события, свободные слоты, конфликты | `Calendar Conflict Rate` |
| Planning Agent | `app/tools/planning_tools.py` | разбивка целей и распределение по дням | `Planning Quality` |
| Prioritization Agent | `app/scoring.py` | «что делать дальше» + объяснение и риски | `Tool Call Accuracy` (выбор/перевод задачи) |
| Memory Agent | `app/tools/memory_tools.py` | личная память пользователя | `Memory Usage Accuracy` |
| Digest Agent | `app/tools/digest_tools.py` | утренний/вечерний дайджест | `Digest Usefulness` |
| Sleep Fairy | `app/agents/*` (sleep_fairy) | режим сна, перенос незавершённого | качество shutdown-ritual |
| Reflection | `app/agents/reflection.py` | проверка хода и полноты | `Human Confirmation Precision` |
| Verifier | `app/agents/verifier.py` | проверка фактических изменений | `Verification Pass Rate` |

## Архитектура и ИТ-ландшафт

Архитектура разделена на шесть слоёв:

1. **Точки входа**: фронтенд (React/Vite: Chat, Tasks, Calendar, Memory,
   Digest), REST API (FastAPI), eval runner (`backend/evals`).
2. **Оркестрация**: `Supervisor / Orchestrator` (`app/agents/orchestrator.py`),
   профильные агенты.
3. **Память**: JSON storage (`app/storage.py`) + persistent личная память
   (`data/memory.json`), задачи/события/чеклисты/дайджесты на диске.
4. **Инструменты**: реестр из 39 typed-инструментов (`app/tools/*`,
   `registry.py`) с Pydantic-схемами входа/выхода.
5. **Знания и данные**: JSON-коллекции, опциональная markdown база знаний,
   eval-датасет сценариев (`backend/evals/eval.py`).
6. **Интеграции и inference**: LLM-провайдеры через единый адаптер
   (`app/llm/provider.py`): `anthropic` / `openai` / `local_openai`
   (llama.cpp/Qwen); контейнеризация (Docker Compose), CPU/GPU режимы.

Архитектурная идея проекта:

- LLM используется только там, где нужна недетерминированность: маршрутизация
  (опционально), reasoning профильных агентов, финальный текст ответа.
- **Reflection, Verifier, scoring, поиск слотов, проверка конфликтов и storage —
  это код**, чтобы сохранить воспроизводимость и проверяемость изменений.
- **Safety-net**: если LLM (особенно малая модель) не довёл действие до конца,
  детерминированный слой гарантированно доделывает шаг — LLM ведёт, код страхует
  результат.
- Источники данных и действия изолированы за typed tool layer: локальный JSON
  storage можно заменить другим бэкендом, не переписывая агентов.
- UI и eval-runner работают поверх **того же** агента, а не поверх отдельных
  веток бизнес-логики.

Подробные диаграммы: [ARCHITECTURE.md](ARCHITECTURE.md) (Mermaid),
[architecture.puml](architecture.puml) (PlantUML),
[DOCKER_ARCHITECTURE.md](DOCKER_ARCHITECTURE.md) (контейнеры/порты/volume'ы).

## Системные промпты

Системные промпты вынесены по ролям в `app/llm/prompts.py` (общий header с
текущей датой + тело каждой роли):

| Узел | Где лежит | Назначение промпта |
|---|---|---|
| Supervisor | `prompts.py: SUPERVISOR_ROUTING` | классифицировать запрос в один из агентов |
| Task | `prompts.py: _BODIES["task"]` | управлять задачами/чеклистами, статусами; «разбей» → задача + чеклист |
| Calendar | `prompts.py: _BODIES["calendar"]` | события, свободные слоты, проверка конфликтов |
| Planning | `prompts.py: _BODIES["planning"]` | распознать цели → задачи → длительность → окна → план |
| Prioritization | `prompts.py: _BODIES["prioritization"]` | одна рекомендация + альтернативы + объяснение + риски |
| Memory | `prompts.py: _BODIES["memory"]` | сохранять/искать факты с типами |
| Digest | `prompts.py: _BODIES["digest"]` | собрать и сохранить дайджест |
| Sleep Fairy | `prompts.py: _BODIES["sleep_fairy"]` | подвести итог дня, перенести незавершённое, мягкий план утра |

Почему это важно для защиты: проект не сводится к одному системному prompt; роли
разведены по ответственности; ограничения по датам (ISO), формату и
необходимости подтверждений описаны прямо в инструкциях.

## Данные и доступ к ним

### Что используется сейчас

- `data/tasks.json`, `data/checklists.json`, `data/events.json`,
  `data/memory.json`, `data/digests.json`, `data/notes.json` — operational
  storage;
- `data/knowledge_base/*.md` — markdown-заметки с YAML-фронтматтером (опционально);
- `backend/evals/eval.py` — набор eval-сценариев и метрик;
- `logs/agent.log` — журнал событий (запрос, агент, tool calls, изменения,
  reflection, verifier, ошибки).

### Что уже похоже на промышленный подход

- доступ к данным идёт не напрямую из агентов, а через typed tool layer
  (`app/tools/*`) с Pydantic-валидацией входа;
- запись в storage атомарная (временный файл + `os.replace`), потокобезопасная;
- конфигурация через env/`.env` (`app/config.py`), без hardcoded ключей/URL;
- LLM-провайдер абстрагирован (`app/llm/provider.py`), легко переключается;
- persistent память переживает рестарт контейнеров (volume `./data`).

### Что пока не production-grade

- нет SSO / RBAC / secret manager;
- JSON storage подходит для прототипа, но не для промышленной нагрузки (нет
  индексов, транзакций, конкурентного доступа из многих процессов);
- observability — это файл-лог, а не отдельная платforма метрик/трейсинга;
- нет планировщика обновления внешних данных и алертов.

## Метрики качества

Метрики и quality gate реализованы в `backend/evals/eval.py`
(подробности — [METRICS.md](METRICS.md)).

| Метрика | Порог | Тип |
|---|---|---|
| `Task Success Rate` | ≥ 0.90 | hard |
| `Tool Call Accuracy` | ≥ 0.90 | hard |
| `Verification Pass Rate` | ≥ 0.95 | hard |
| `Human Confirmation Precision` | ≥ 0.90 | hard |
| `Calendar Conflict Rate` | ≤ 0.34 | hard |
| `Routing Accuracy` | ≥ 0.85 | soft |
| `Autonomy Rate` | ≥ 0.80 | soft |
| `Digest Usefulness` | ≥ 0.70 | soft |

Минимальный quality gate: все hard-метрики проходят, soft pass rate ≥ 75%.
Запуск: `python evals/eval.py --enforce-gate` (exit code 1 при провале).

Честный snapshot (rule-based режим, `LLM=none`):

- `Routing Accuracy = 1.00`
- `Tool Call Accuracy = 1.00`
- `Task Success Rate = 1.00`
- `Autonomy Rate = 1.00`
- `Verification Pass Rate = 1.00`
- `Human Confirmation Precision = 1.00`
- `Digest Usefulness = 0.75`
- `Calendar Conflict Rate = 0.25`
- **QUALITY GATE: PASSED ✅**

В live-LLM режиме значения зависят от модели (Qwen 4B/9B); тот же eval применим
для сравнения моделей.

## Прототип и техническая готовность

Что реализовано end-to-end:

- веб-интерфейс (React): Chat (с визуализацией tool calls, Reflection, Verifier
  и персистентной историей на сервере), Tasks (Jira-доска),
  Calendar (события + дедлайны задач), Memory, Digest;
- REST API (FastAPI): `/chat`, `/chat/history`, `/tasks`, `/calendar/*`,
  `/memory`, `/digest/*`, `/plan`, `/prioritize`, `/sleep-mode`, `/health`,
  `/health/llm`;
- **детерминированные тесты** (`backend/tests/`, pytest): tools, scoring,
  verifier, reflection, storage round-trip, router — 26 тестов;
- eval-runner с quality gate;
- LLM через единый адаптер: локальный llama.cpp/Qwen (`local_openai`) или
  облако (`anthropic`/`openai`); деградация в rule-based режим без ключа;
- контейнеризация (Docker Compose), CPU/GPU режимы, healthchecks, `Makefile`,
  запуск одной командой (`bash run.sh`).

### Что показать на демонстрации

- создание задачи и разбивка на чеклист;
- планирование недели → задачи + события в календаре;
- «что мне делать дальше?» с объяснением и рисками;
- вечерний дайджест + режим сна с переносом незавершённого;
- видимые tool calls и результаты Reflection/Verifier в чате;
- persistence: задача остаётся после `docker compose down/up`.

Сценарии: [DEMO_SCENARIOS.md](DEMO_SCENARIOS.md).

## LLM-провайдеры и внешние интеграции

Агент работает через единый адаптер `app/llm/provider.py`:

- `local_openai` — локальный OpenAI-совместимый сервер (llama.cpp + Qwen GGUF),
  адрес/ключ/модель из env;
- `anthropic` / `openai` — облачные провайдеры (опционально);
- `none` — rule-based режим (демо без ключа).

Архитектура допускает подключение внешних MCP-провайдеров инструментов через
конфиг (без переписывания агентов) — на текущем этапе это в roadmap.

## Ограничения, проблемы и развитие

### С какими проблемами столкнулись

- совместить агентность и воспроизводимость: решено выносом Reflection/Verifier/
  scoring/storage в детерминированный код, а LLM — только на недетерминированные
  шаги;
- стриминг tool-calls у локального llama.cpp нестабилен — поэтому стрим сделан
  надёжным (агент отрабатывает обычным путём, текст отдаётся порциями) и
  опциональным;
- скорость на CPU: 9B медленная — добавлен быстрый keyword-роутинг и
  рекомендация по более лёгкой модели (Qwen 4B / квантизация Q4_K_M).

### Текущие ограничения

- production auth / SSO / RBAC и централизованная observability не реализованы;
- JSON storage, не vector DB / не реляционная промышленная БД;
- полноценная агентность узлов зависит от tool-capable LLM (llama.cpp с `--jinja`);
- внешние MCP-провайдеры — пока проектное направление.

### Что улучшать дальше

1. Production-контур: SSO, RBAC, secret manager, централизованные логи/метрики.
2. Поднять live-LLM качество роутинга и нарратива до прохождения gate на 4B/9B.
3. Заменить JSON storage на реляционную БД + vector store для базы знаний.
4. Online-метрики, latency tracing, дашборд по категориям запросов.
5. Стабилизировать MCP-интеграцию и вынести её в конфиг-driven слой.
