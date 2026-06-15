"""Verifier Agent (детерминированный).

В отличие от Reflection (проверяет ход рассуждения и полноту), Verifier
проверяет КОНКРЕТНЫЕ изменения данных: реально ли задача/событие/чеклист/
дайджест/память попали в storage.
"""
from __future__ import annotations

from typing import Any

from ..models import ToolCall, VerificationCheck, VerificationResult
from ..storage import storage
from .definitions import MUTATING_TOOLS


def _g(out: Any, key: str, default: Any = None) -> Any:
    return out.get(key, default) if isinstance(out, dict) else default


def verify(tool_calls: list[ToolCall]) -> VerificationResult:
    checks: list[VerificationCheck] = []

    for tc in tool_calls:
        out = tc.output
        if not tc.ok:
            checks.append(VerificationCheck(
                name=tc.tool, ok=False,
                detail=f"Инструмент завершился ошибкой: {tc.error}"))
            continue
        if tc.tool not in MUTATING_TOOLS:
            continue

        if tc.tool == "create_task":
            tid = _g(out, "id")
            ok = bool(tid) and storage.tasks.get(tid) is not None
            checks.append(VerificationCheck(
                name="create_task", ok=ok,
                detail=f"Задача {tid} {'есть' if ok else 'отсутствует'} в storage"))

        elif tc.tool in ("update_task", "set_task_status", "set_task_priority"):
            tid = _g(out, "id")
            ok = bool(tid) and storage.tasks.get(tid) is not None
            checks.append(VerificationCheck(name=tc.tool, ok=ok,
                          detail=f"Задача {tid} обновлена в storage"))

        elif tc.tool == "delete_task":
            tid = _g(out, "id")
            ok = bool(_g(out, "deleted")) and storage.tasks.get(tid) is None
            checks.append(VerificationCheck(name="delete_task", ok=ok,
                          detail=f"Задача {tid} удалена из storage"))

        elif tc.tool == "create_checklist":
            cid = _g(out, "id")
            cl = storage.checklists.get(cid) if cid else None
            ok = cl is not None
            detail = f"Чеклист {cid} в storage"
            if cl and cl.task_id:
                task = storage.tasks.get(cl.task_id)
                linked = bool(task and cid in task.checklist_ids)
                ok = ok and linked
                detail += f"; связь с задачей {cl.task_id}: {'да' if linked else 'нет'}"
            checks.append(VerificationCheck(name="create_checklist", ok=ok, detail=detail))

        elif tc.tool in ("add_checklist_item", "update_checklist_item",
                         "complete_checklist_item"):
            cid = _g(out, "id")
            ok = bool(cid) and storage.checklists.get(cid) is not None
            checks.append(VerificationCheck(name=tc.tool, ok=ok,
                          detail=f"Чеклист {cid} обновлён"))

        elif tc.tool == "create_event":
            ev = _g(out, "event", {})
            eid = _g(ev, "id")
            ok = bool(eid) and storage.events.get(eid) is not None
            checks.append(VerificationCheck(name="create_event", ok=ok,
                          detail=f"Событие {eid} {'есть' if ok else 'нет'} в календаре"))

        elif tc.tool == "update_event":
            eid = _g(out, "id")
            ok = bool(eid) and storage.events.get(eid) is not None
            checks.append(VerificationCheck(name="update_event", ok=ok,
                          detail=f"Событие {eid} обновлено"))

        elif tc.tool == "delete_event":
            eid = _g(out, "id")
            ok = bool(_g(out, "deleted")) and storage.events.get(eid) is None
            checks.append(VerificationCheck(name="delete_event", ok=ok,
                          detail=f"Событие {eid} удалено"))

        elif tc.tool == "save_memory":
            mid = _g(out, "id")
            ok = bool(mid) and storage.memory.get(mid) is not None
            checks.append(VerificationCheck(name="save_memory", ok=ok,
                          detail=f"Запись памяти {mid} сохранена"))

        elif tc.tool == "update_memory":
            mid = _g(out, "id")
            ok = bool(mid) and storage.memory.get(mid) is not None
            checks.append(VerificationCheck(name="update_memory", ok=ok,
                          detail=f"Запись памяти {mid} обновлена"))

        elif tc.tool == "delete_memory":
            mid = _g(out, "id")
            ok = bool(_g(out, "deleted")) and storage.memory.get(mid) is None
            checks.append(VerificationCheck(name="delete_memory", ok=ok,
                          detail=f"Запись памяти {mid} удалена"))

        elif tc.tool in ("generate_morning_digest", "generate_evening_digest",
                         "save_digest"):
            did = _g(out, "id")
            ok = bool(did) and storage.digests.get(did) is not None
            checks.append(VerificationCheck(name=tc.tool, ok=ok,
                          detail=f"Дайджест {did} сохранён в data/digests.json"))

        elif tc.tool == "split_goal_into_tasks":
            tid = _g(_g(out, "task", {}), "id")
            cid = _g(_g(out, "checklist", {}), "id")
            ok = bool(tid) and storage.tasks.get(tid) is not None and (
                not cid or storage.checklists.get(cid) is not None)
            checks.append(VerificationCheck(name="split_goal_into_tasks", ok=ok,
                          detail=f"Цель → задача {tid} + чеклист {cid}"))

        elif tc.tool == "schedule_tasks_to_free_slots":
            ids = [_g(e, "id") for e in _g(out, "events", [])]
            ok = all(storage.events.get(i) for i in ids)
            checks.append(VerificationCheck(name="schedule_tasks_to_free_slots", ok=ok,
                          detail=f"Создано событий: {len(ids)}, все в календаре"))

        elif tc.tool == "reschedule_overdue_tasks":
            ids = [_g(t, "id") for t in _g(out, "moved", [])]
            ok = all(storage.tasks.get(i) for i in ids)
            checks.append(VerificationCheck(name="reschedule_overdue_tasks", ok=ok,
                          detail=f"Перенесено задач: {len(ids)}"))

        elif tc.tool in ("create_note", "update_note"):
            nid = _g(out, "id")
            ok = bool(nid) and storage.notes.get(nid) is not None
            checks.append(VerificationCheck(name=tc.tool, ok=ok,
                          detail=f"Заметка {nid} сохранена"))

    if not checks:
        return VerificationResult(passed=True, checks=[],
                                  summary="Изменений данных не было — проверять нечего.")
    passed = all(c.ok for c in checks)
    ok_n = sum(1 for c in checks if c.ok)
    return VerificationResult(
        passed=passed, checks=checks,
        summary=f"Пройдено {ok_n}/{len(checks)} проверок изменений в storage.")
