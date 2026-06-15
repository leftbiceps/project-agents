"""Тесты эвристики приоритизации (scoring)."""
from datetime import datetime, timedelta

from app.models import Priority, Task, TaskStatus
from app.scoring import rank_tasks, recommend_next

NOW = datetime(2026, 6, 15, 12, 0)


def test_overdue_urgent_ranked_first():
    t1 = Task(title="просрочка urgent", priority=Priority.urgent,
              status=TaskStatus.in_progress, deadline=NOW - timedelta(days=1))
    t2 = Task(title="низкий приоритет", priority=Priority.low,
              status=TaskStatus.todo, deadline=NOW + timedelta(days=5))
    ranked = rank_tasks([t1, t2], NOW)
    assert ranked[0][0].id == t1.id


def test_blocked_task_deprioritized():
    blocked = Task(title="заблок", priority=Priority.high,
                   status=TaskStatus.blocked)
    todo = Task(title="обычная", priority=Priority.medium, status=TaskStatus.todo)
    ranked = rank_tasks([blocked, todo], NOW)
    assert ranked[0][0].id == todo.id


def test_recommend_next_with_risk():
    t = Task(title="скоро дедлайн", priority=Priority.high,
             status=TaskStatus.todo, deadline=NOW + timedelta(hours=2))
    rec = recommend_next([t], [], NOW)
    assert rec["main"]["id"] == t.id
    assert rec["risks"], "близкий дедлайн должен дать риск"


def test_recommend_next_empty():
    rec = recommend_next([], [], NOW)
    assert rec["main"] is None
