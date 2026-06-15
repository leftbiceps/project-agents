"""Конфигурация тестов: изолированный временный storage, без LLM."""
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Тестовые данные — во временную папку (не трогаем data/ проекта).
_tmp = tempfile.mkdtemp(prefix="assistant_test_")
os.environ.setdefault("DATA_DIR", str(pathlib.Path(_tmp) / "data"))
os.environ.setdefault("LOGS_DIR", str(pathlib.Path(_tmp) / "logs"))
os.environ.setdefault("LLM_PROVIDER", "none")
