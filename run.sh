#!/usr/bin/env bash
# ============================================================================
#  run.sh — поднять весь проект одной командой.
#
#  Делает всё:
#    1) проверяет Docker;
#    2) готовит .env;
#    3) скачивает GGUF-модель в ./models (через новый CLI `hf`), если её нет;
#    4) прописывает путь к модели в .env;
#    5) собирает и запускает контейнеры (frontend + backend + llm);
#    6) ждёт готовности LLM и печатает ссылки.
#
#  Использование:
#     bash run.sh          # CPU режим (по умолчанию)
#     bash run.sh gpu      # GPU режим (NVIDIA)
#
#  Настройки (можно переопределить через окружение):
#     HF_REPO     — репозиторий модели на Hugging Face
#     HF_INCLUDE  — маска файла квантизации
# ============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MODE="${1:-cpu}"
HF_REPO="${HF_REPO:-unsloth/Qwen3.5-9B-GGUF}"
# Ровно один файл Q6_K (маска без хвостового *, чтобы не цеплять Q6_K_L и т.п.)
HF_INCLUDE="${HF_INCLUDE:-*Q6_K.gguf}"

echo "==> [1/6] Проверка Docker"
command -v docker >/dev/null 2>&1 || { echo "❌ Docker не установлен. Поставьте Docker Desktop."; exit 1; }
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "❌ Docker Compose не найден."; exit 1
fi
docker info >/dev/null 2>&1 || { echo "❌ Docker не запущен. Откройте Docker Desktop и повторите."; exit 1; }

echo "==> [2/6] Подготовка .env"
[ -f .env ] || cp .env.example .env

echo "==> [3/6] Модель (GGUF)"
mkdir -p models
EXISTING="$(find models -type f -name '*.gguf' 2>/dev/null | head -n1 || true)"
if [ -n "$EXISTING" ]; then
  echo "✔ Модель уже есть: $EXISTING — скачивание пропускаю."
else
  if ! command -v hf >/dev/null 2>&1; then
    echo "❌ Утилита 'hf' не найдена. Установите: pip install -U huggingface_hub"; exit 1
  fi
  if [ -z "${HF_TOKEN:-}" ]; then
    echo "ℹ Без HF_TOKEN HF ограничивает скорость. Ускорить: export HF_TOKEN=ваш_токен"
  fi
  # Ускоритель загрузки, если установлен (pip install hf_transfer)
  if python3 -c "import hf_transfer" >/dev/null 2>&1; then
    export HF_HUB_ENABLE_HF_TRANSFER=1
    echo "⚡ hf_transfer включён (ускоренная загрузка)"
  fi
  echo "⬇ Качаю $HF_REPO ($HF_INCLUDE) в ./models — ~7 ГБ, может занять время…"
  hf download "$HF_REPO" --include "$HF_INCLUDE" --local-dir ./models
fi

echo "==> [4/6] Прописываю путь к модели в .env"
MODEL_FILE="$(find models -type f -name '*.gguf' 2>/dev/null | head -n1 || true)"
[ -n "$MODEL_FILE" ] || { echo "❌ .gguf не найден в ./models после загрузки."; exit 1; }
REL="${MODEL_FILE#models/}"
CONT_PATH="/models/$REL"
grep -v '^LLM_MODEL_PATH=' .env > .env.tmp || true
echo "LLM_MODEL_PATH=$CONT_PATH" >> .env.tmp
mv .env.tmp .env
echo "✔ LLM_MODEL_PATH=$CONT_PATH  (файл: $MODEL_FILE)"

# подгрузить переменные .env для вывода ссылок
set -a; . ./.env; set +a

echo "==> [5/6] Сборка и запуск контейнеров (режим: $MODE)"
# Обход бага BuildKit: при не-ASCII пути (кириллица/пробел) в имени папки
# сборка падает на "x-docker-expose-session-sharedkey". Переключаемся на
# классический сборщик, который не использует этот gRPC-заголовок.
export COMPOSE_BAKE=false
case "$PWD" in
  *[!\ -~]*)
    echo "⚠ В пути проекта есть не-ASCII символы:"
    echo "    $PWD"
    echo "  Включаю legacy-сборщик Docker (обход бага BuildKit)."
    echo "  Надёжнее — перенести проект в путь без кириллицы/пробелов (см. вывод в конце)."
    export DOCKER_BUILDKIT=0
    export COMPOSE_DOCKER_CLI_BUILD=0
    ;;
esac
if [ "$MODE" = "gpu" ]; then
  $COMPOSE -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
else
  $COMPOSE up -d --build
fi

echo "==> [6/6] Ожидание готовности"
$COMPOSE ps
echo "Жду загрузки модели в LLM-контейнер (может быть долго на CPU)…"
bash scripts/wait_for_llm.sh 900 || echo "⚠ LLM ещё грузится — смотрите '$COMPOSE logs -f llm'"

echo
echo "✅ Готово!"
echo "   Frontend:   http://localhost:${FRONTEND_PORT:-3000}"
echo "   Backend:    http://localhost:${BACKEND_PORT:-8000}/docs"
echo "   LLM (curl): curl http://localhost:${LLM_PORT:-8001}/v1/models"
echo "   Логи:       $COMPOSE logs -f      |   Стоп: $COMPOSE down"
