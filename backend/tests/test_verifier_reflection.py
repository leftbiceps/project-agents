"""Тесты Verifier и Reflection (детерминированные самопроверки)."""
from app.agents.reflection import reflect
from app.agents.verifier import verify
from app.models import ToolCall
from app.storage import storage
from app.tools import task_tools as tt


def setup_function():
    storage.reset()


def test_verifier_confirms_real_change():
    t = tt.create_task(tt.CreateTaskIn(title="V"))
    tc = ToolCall(agent="task", tool="create_task", input={},
                  output=t.model_dump(mode="json"), ok=True)
    res = verify([tc])
    assert res.passed
    assert res.checks[0].ok


def test_verifier_detects_phantom():
    tc = ToolCall(agent="task", tool="create_task", input={},
                  output={"id": "task_phantom"}, ok=True)
    res = verify([tc])
    assert not res.passed


def test_verifier_flags_tool_error():
    tc = ToolCall(agent="task", tool="create_task", input={}, ok=False,
                  error="boom")
    res = verify([tc])
    assert not res.passed


def test_reflection_requires_confirmation_on_delete():
    tc = ToolCall(agent="task", tool="delete_task", input={"id": "x"},
                  output={"deleted": True, "id": "x"}, ok=True)
    r = reflect("удали задачу", "task", [tc], "готово")
    assert r.requires_user_confirmation


def test_reflection_no_confirmation_on_create():
    tc = ToolCall(agent="task", tool="create_task", input={},
                  output={"id": "task_1"}, ok=True)
    r = reflect("создай задачу", "task", [tc], "готово")
    assert not r.requires_user_confirmation


def test_reflection_flags_missing_action():
    # запрос предполагал действие, но инструменты не вызваны
    r = reflect("создай задачу купить кофе", "task", [], "")
    assert not r.passed
