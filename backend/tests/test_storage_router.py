"""Тесты storage round-trip (persistence) и keyword-роутера."""
import pytest

from app.agents.router import keyword_route
from app.models import Task
from app.storage import storage


def setup_function():
    storage.reset()


def test_storage_roundtrip():
    t = Task(title="сохрани меня")
    storage.tasks.add(t)
    again = storage.tasks.get(t.id)
    assert again is not None and again.title == "сохрани меня"
    storage.tasks.update(t.id, {"title": "изменено"})
    assert storage.tasks.get(t.id).title == "изменено"
    assert storage.tasks.delete(t.id)
    assert storage.tasks.get(t.id) is None


def test_storage_persists_to_disk():
    # данные должны переживать пересоздание объекта Storage (как рестарт)
    t = Task(title="на диск")
    storage.tasks.add(t)
    from app.storage import Storage
    fresh = Storage()
    assert fresh.tasks.get(t.id) is not None


@pytest.mark.parametrize("msg,expected", [
    ("Создай задачу купить хлеб", "task"),
    ("Разбей задачу на чеклист", "task"),
    ("Что мне сейчас делать дальше?", "prioritization"),
    ("Спланируй неделю: статья и презентация", "planning"),
    ("Запомни, что я люблю кофе", "memory"),
    ("Сделай утренний дайджест", "digest"),
    ("Переведи меня в режим сна", "sleep_fairy"),
    ("Покажи расписание на неделю", "calendar"),
])
def test_keyword_router(msg, expected):
    assert keyword_route(msg) == expected
