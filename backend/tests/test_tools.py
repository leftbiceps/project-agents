"""Тесты tool layer: задачи, чеклисты, календарь, память."""
from app.storage import storage
from app.tools import calendar_tools as ct
from app.tools import memory_tools as mt
from app.tools import task_tools as tt


def setup_function():
    storage.reset()


def test_create_task_and_status():
    t = tt.create_task(tt.CreateTaskIn(title="Купить хлеб"))
    assert storage.tasks.get(t.id) is not None
    upd = tt.set_task_status(tt.SetStatusIn(id=t.id, status="in_progress"))
    assert upd.status.value == "in_progress"


def test_checklist_flow_and_progress():
    t = tt.create_task(tt.CreateTaskIn(title="Доклад"))
    cl = tt.create_checklist(tt.CreateChecklistIn(task_id=t.id, items=["a", "b"]))
    # чеклист связан с задачей
    assert cl.id in storage.tasks.get(t.id).checklist_ids
    tt.complete_checklist_item(
        tt.CompleteItemIn(checklist_id=cl.id, item_id=cl.items[0].id))
    prog = tt.get_task_progress(tt.TaskIdIn(id=t.id))
    assert prog["total_items"] == 2
    assert prog["completed_items"] == 1
    assert prog["percent"] == 50.0


def test_search_tasks():
    tt.create_task(tt.CreateTaskIn(title="Позвонить маме", tags=["личное"]))
    tt.create_task(tt.CreateTaskIn(title="Сдать отчёт"))
    assert len(tt.search_tasks(tt.SearchTasksIn(query="отчёт"))) == 1
    assert len(tt.search_tasks(tt.SearchTasksIn(query="личное"))) == 1


def test_calendar_conflict_detection():
    ct.create_event(ct.CreateEventIn(
        title="A", start_datetime="2026-06-20T10:00",
        end_datetime="2026-06-20T11:00"))
    out = ct.create_event(ct.CreateEventIn(
        title="B", start_datetime="2026-06-20T10:30",
        end_datetime="2026-06-20T11:30"))
    assert out["conflicts"], "пересечение должно быть обнаружено"


def test_free_slots():
    ct.create_event(ct.CreateEventIn(
        title="Занято", start_datetime="2026-06-20T09:00",
        end_datetime="2026-06-20T12:00"))
    res = ct.find_free_slots_tool(ct.FreeSlotsIn(
        date="2026-06-20", work_day_start="09:00", work_day_end="18:00",
        min_minutes=60))
    assert any(s["minutes"] >= 60 for s in res["slots"])


def test_memory_save_and_search():
    mt.save_memory(mt.SaveMemoryIn(content="я лучше работаю утром",
                                   type="user_preference"))
    res = mt.search_memory(mt.SearchMemoryIn(query="утром"))
    assert len(res) == 1
    assert res[0].type.value == "user_preference"
