# LLM_LOCAL_INFERENCE — локальный inference (Qwen / llama.cpp)

## Как backend обращается к LLM

Все агенты ходят к модели через единый адаптер `app/llm/provider.py`
(`get_client()`), а не напрямую. В режиме `local_openai` адаптер использует
OpenAI-совместимый клиент, направленный на локальный сервер **llama.cpp**
(`llm`-контейнер). Запросы идут на `http://llm:8000/v1` внутри compose-сети.

Поток: `backend (OpenAI-совместимый клиент) → http://llm:8000/v1/chat/completions
→ llama.cpp server → модель из /models`.

Никаких хардкод-ключей, URL или имён моделей в коде нет — всё из env.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|------------|------------|--------------|
| `LLM_PROVIDER` | провайдер: `local_openai` / `openai` / `anthropic` / `none` / `auto` | `local_openai` |
| `LLM_BASE_URL` | адрес OpenAI-совместимого API | `http://llm:8000/v1` |
| `LLM_API_KEY` | ключ (для llama.cpp — произвольный, напр. `local`) | `local` |
| `LLM_MODEL` | имя модели, передаётся в запросах | `qwen-3.5-9b-int6` |
| `LLM_MODEL_PATH` | путь к GGUF **внутри** llm-контейнера | `/models/qwen-3.5-9b-int6.gguf` |
| `LLM_CONTEXT_SIZE` | размер контекста (токены) | `8192` |
| `LLM_THREADS` | потоки CPU для inference | `8` |
| `LLM_GPU_LAYERS` | число слоёв на GPU (`0` = CPU) | `0` |
| `LLM_MAX_TOKENS` | лимит токенов ответа | `1500` |
| `LLM_TEMPERATURE` | температура | `0.2` |
| `LLM_IMAGE` / `LLM_IMAGE_GPU` | образы llama.cpp (CPU/CUDA) | `ghcr.io/ggml-org/llama.cpp:server[-cuda]` |

## Где лежит модель

На хосте — в `./models`, смонтирована в llm-контейнер как `/models`. Файл
кладётся вручную (не качается автоматически). Имя файла = `basename` от
`LLM_MODEL_PATH`.

## int6 и название квантизации

«int6» в терминах llama.cpp обычно соответствует **`Q6_K`**. Файл может
называться, например, `qwen3.5-9b-Q6_K.gguf`. Имя модели в `LLM_MODEL` можно
оставить как `qwen-3.5-9b-int6` — оно используется лишь как идентификатор в
запросах; решает именно путь к файлу (`LLM_MODEL_PATH`). Если ваш файл назван
иначе, поправьте `LLM_MODEL_PATH` (и при желании имя файла).

## CPU mode vs GPU mode

- **CPU (по умолчанию, `make up`):** `LLM_GPU_LAYERS=0`, скорость зависит от
  `LLM_THREADS` и CPU. Работает везде.
- **GPU (`make up-gpu`):** используется CUDA-образ и `deploy.resources` NVIDIA;
  выставьте `LLM_GPU_LAYERS` (например `999`, чтобы выгрузить все слои на GPU).
  Требуется `nvidia-container-toolkit`. CPU-конфиг при этом не меняется и
  остаётся рабочим.

## Как поменять модель

1. Положите новый GGUF в `./models`.
2. Обновите `LLM_MODEL_PATH` (и при желании `LLM_MODEL`) в `.env`.
3. `make down && make up` (или `make restart`).
4. `make check-model` и `make health` для проверки.

## Как увеличить context size

Увеличьте `LLM_CONTEXT_SIZE` в `.env` (например `16384`) и перезапустите
(`make restart`). Больший контекст требует больше RAM/VRAM.

## Если не хватает RAM

- Возьмите более лёгкую квантизацию (например `Q4_K_M` вместо `Q6_K`).
- Уменьшите `LLM_CONTEXT_SIZE` (например `4096`).
- Уменьшите `LLM_THREADS`, закройте другие приложения.
- Рассмотрите GPU-режим, если есть видеокарта.

## Если LLM-контейнер долго стартует

Загрузка 9B-модели в память занимает время. Это нормально: backend стартует
независимо, а `/health/llm` будет показывать `degraded`, пока модель не
прогрузится. Дождаться готовности:

```bash
bash scripts/wait_for_llm.sh        # опрашивает /v1/models
make logs-llm                        # смотреть прогресс загрузки
```

## Ручная проверка endpoint через curl

```bash
# список моделей
curl http://localhost:8001/v1/models

# пробный chat-запрос
curl http://localhost:8001/v1/chat/completions \
  -H "Authorization: Bearer local" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-3.5-9b-int6","messages":[{"role":"user","content":"Привет!"}]}'
```

## О tool-calling

Агенты используют OpenAI-style function calling. Для полноценной работы
инструментов локальный сервер и модель должны поддерживать tools (для llama.cpp
— запуск с поддержкой шаблона инструментов, напр. флаг `--jinja` и
tool-совместимый чат-шаблон Qwen). Если локальная модель не вызывает инструменты,
ответы будут текстовыми, а Reflection пометит, что действие не выполнено. В этом
случае используйте tool-capable сборку/модель или облачный провайдер.
