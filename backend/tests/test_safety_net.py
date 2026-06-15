"""Тесты safety-net: доделывает действие, если LLM не довёл, и не дублирует."""
from app.agents import safety_net as sn
from app.models import ToolCall
from app.storage import storage


def setup_function():
    storage.reset()


def _tc(tool, output, ok=True, agent="x"):
    return ToolCall(agent=agent, tool=tool, input={}, output=output, ok=ok)


def test_adds_checklist_when_missing():
    # LLM создал задачу, но не чеклист — safety-net добавляет чеклист
    calls = [_tc("create_task", {"id": "task_X", "title": "Подготовка доклада"})]
    extra = sn.complete("task", "Разбей на чеклист: подготовка доклада", calls)
    assert any(x.tool == "create_checklist" for x in extra)


def test_adds_schedule_when_missing():
    # LLM создал задачи, но не запланировал — safety-net вызывает планировщик
    calls = [_tc("create_task", {"id": "task_A"}), _tc("create_task", {"id": "task_B"})]
    extra = sn.complete("planning", "Спланируй неделю: презентация, статья", calls)
    assert any(x.tool == "schedule_tasks_to_free_slots" for x in extra)


def test_adds_event_when_missing():
    # LLM проверил конфликты, но не создал событие — safety-net создаёт
    calls = [_tc("check_time_conflicts", {"has_conflict": False})]
    extra = sn.complete("calendar", "Создай событие созвон завтра в 16:00", calls)
    assert any(x.tool == "create_event" for x in extra)
    assert storage.events.count() == 1


def test_no_duplicate_when_done():
    # действие уже выполнено — safety-net ничего не добавляет
    calls = [_tc("create_task", {"id": "task_Y"})]
    extra = sn.complete("task", "Создай задачу купить молоко", calls)
    assert extra == []


def test_saves_memory_when_missing():
    extra = sn.complete("memory", "Запомни, что я люблю кофе", [])
    assert any(x.tool == "save_memory" for x in extra)
    assert storage.memory.count() == 1
