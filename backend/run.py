"""Точка входа backend.

Запуск:
    cd backend
    python run.py

Либо напрямую через uvicorn:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
