#!/usr/bin/env bash
# Проверяет, что локальный файл модели существует по пути из .env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

CONT_PATH="${LLM_MODEL_PATH:-/models/qwen-3.5-9b-int6.gguf}"
HOST_PATH="./models/$(basename "$CONT_PATH")"

echo "Путь в контейнере: $CONT_PATH"
echo "Путь на хосте:     $HOST_PATH"

if [ -f "$HOST_PATH" ]; then
  SIZE="$(du -h "$HOST_PATH" 2>/dev/null | cut -f1)"
  echo "✅ Модель найдена (${SIZE})."
else
  echo "❌ Модель НЕ найдена."
  echo "   1) mkdir -p models"
  echo "   2) Положите GGUF-файл Qwen 3.5 9B (int6 / Q6_K) в ./models/"
  echo "   3) Имя файла должно совпадать с basename из LLM_MODEL_PATH в .env"
  echo "   Модель НЕ скачивается автоматически — добавьте её вручную."
  exit 1
fi
