# ============================================================================
#  Makefile — управление локальным ассистентом через Docker Compose
# ============================================================================
COMPOSE ?= docker compose
GPU_FILES := -f docker-compose.yml -f docker-compose.gpu.yml
HF_REPO ?= unsloth/Qwen3.5-9B-GGUF
HF_INCLUDE ?= *Q6_K*.gguf

.PHONY: help start start-gpu pull-model build up up-gpu down restart logs logs-backend logs-llm ps health clean check-model eval test

help:
	@echo "Команды:"
	@echo "  make start         — ВСЁ одной командой: модель + сборка + запуск (CPU)"
	@echo "  make start-gpu     — то же в GPU режиме"
	@echo "  make pull-model    — только скачать GGUF-модель в ./models"
	@echo "  make check-model   — проверить наличие файла модели в ./models"
	@echo "  make build         — собрать образы"
	@echo "  make up            — запустить (CPU режим)"
	@echo "  make up-gpu        — запустить (GPU режим, NVIDIA)"
	@echo "  make down          — остановить"
	@echo "  make restart       — перезапустить"
	@echo "  make logs          — логи всех сервисов"
	@echo "  make logs-backend  — логи backend"
	@echo "  make logs-llm      — логи LLM"
	@echo "  make ps            — статус контейнеров"
	@echo "  make health        — проверить /health и /health/llm"
	@echo "  make eval          — метрики + quality gate (в контейнере)"
	@echo "  make test          — pytest (в контейнере)"
	@echo "  make clean         — остановить и удалить volume'ы"

start:
	bash run.sh

start-gpu:
	bash run.sh gpu

pull-model:
	hf download $(HF_REPO) --include "$(HF_INCLUDE)" --local-dir ./models

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d
	@echo "Frontend → http://localhost:3000 | Backend → http://localhost:8000/docs"

up-gpu:
	$(COMPOSE) $(GPU_FILES) up -d
	@echo "GPU режим запущен. Frontend → http://localhost:3000"

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

logs-backend:
	$(COMPOSE) logs -f backend

logs-llm:
	$(COMPOSE) logs -f llm

ps:
	$(COMPOSE) ps

health:
	@echo "== backend /health =="; curl -fsS http://localhost:$${BACKEND_PORT:-8000}/health || true; echo
	@echo "== backend /health/llm =="; curl -fsS http://localhost:$${BACKEND_PORT:-8000}/health/llm || true; echo

clean:
	$(COMPOSE) down -v --remove-orphans

check-model:
	@bash scripts/check_local_model.sh

eval:
	$(COMPOSE) exec backend python evals/eval.py --enforce-gate

test:
	$(COMPOSE) exec backend sh -c "pip install -q pytest && python -m pytest tests/ -q"
