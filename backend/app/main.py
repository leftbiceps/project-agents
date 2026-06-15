"""FastAPI-приложение: сборка роутеров, мета-эндпоинты, обработка ошибок."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__, tools  # импорт tools регистрирует инструменты
from .agents import get_orchestrator
from .agents.definitions import AGENT_TOOLS
from .config import get_settings
from .llm import llm_health
from .logging_conf import log_event, logger
from .routers import actions, calendar, chat, checklists, digest, memory, tasks
from .seed import seed_demo
from .storage import storage
from .tools import ToolError, registry

settings = get_settings()

app = FastAPI(
    title="Локальный мультиагентный личный ассистент",
    version=__version__,
    description="Backend: задачи, календарь, память, дайджесты, планирование, "
                "приоритизация, режим сна. Reflection + Verifier.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    log_event("http_request", method=request.method,
              path=request.url.path, status=response.status_code)
    return response


@app.exception_handler(ToolError)
async def tool_error_handler(request: Request, exc: ToolError):
    code = 404 if "не найден" in str(exc).lower() else 400
    log_event("tool_http_error", path=request.url.path, error=str(exc), code=code)
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Необработанная ошибка на %s", request.url.path)
    log_event("http_error", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# --- Роутеры ---
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(checklists.router)
app.include_router(calendar.router)
app.include_router(memory.router)
app.include_router(digest.router)
app.include_router(actions.router)


# --- Мета / сервис ---
@app.get("/", tags=["meta"])
def root():
    return {
        "name": "Локальный мультиагентный личный ассистент",
        "version": __version__,
        "docs": "/docs",
        "mode": get_orchestrator().mode,
    }


@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "service": "backend",
        "mode": get_orchestrator().mode,
        "llm_provider": settings.resolved_provider(),
        "counts": {
            "tasks": storage.tasks.count(),
            "events": storage.events.count(),
            "memory": storage.memory.count(),
            "checklists": storage.checklists.count(),
            "digests": storage.digests.count(),
        },
    }


@app.get("/health/llm", tags=["meta"])
def health_llm():
    """Доступность локального/удалённого LLM. Backend не падает, если LLM лежит."""
    result = llm_health()
    result["status"] = "ok" if result.get("reachable") else "degraded"
    return result


@app.get("/meta/agents", tags=["meta"])
def meta_agents():
    return {"mode": get_orchestrator().mode, "agents": AGENT_TOOLS,
            "special": ["supervisor", "reflection", "verifier"]}


@app.get("/meta/tools", tags=["meta"])
def meta_tools():
    return [{"name": t.name, "description": t.description,
             "output": t.output_hint, "input_schema": t.input_schema()}
            for t in registry.all()]


@app.post("/demo/seed", tags=["meta"])
def demo_seed():
    result = seed_demo()
    log_event("demo_seed", **result)
    return {"seeded": True, **result}


@app.post("/demo/reset", tags=["meta"])
def demo_reset():
    storage.reset()
    return {"reset": True}
