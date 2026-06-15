#!/usr/bin/env bash
# Ждёт готовности локального LLM (OpenAI-совместимый /v1/models).
# Использование: bash scripts/wait_for_llm.sh [timeout_sec]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

PORT="${LLM_PORT:-8001}"
URL="http://localhost:${PORT}/v1/models"
TIMEOUT="${1:-600}"

echo "Жду готовности LLM на ${URL} (до ${TIMEOUT}s, загрузка большой модели может быть долгой)…"
elapsed=0
until curl -fsS "$URL" >/dev/null 2>&1; do
  if [ "$elapsed" -ge "$TIMEOUT" ]; then
    echo
    echo "❌ LLM не ответил за ${TIMEOUT}s. Проверьте: make logs-llm"
    exit 1
  fi
  sleep 5
  elapsed=$((elapsed + 5))
  printf '.'
done
echo
echo "✅ LLM готов: ${URL}"
