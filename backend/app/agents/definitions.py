"""Конфигурация агентов: какие инструменты доступны каждому агенту."""
from __future__ import annotations

# Имя агента -> список имён инструментов (как они зарегистрированы в registry).
AGENT_TOOLS: dict[str, list[str]] = {
    "task": [
        "create_task", "update_task", "delete_task", "get_task", "list_tasks",
        "search_tasks", "set_task_status", "set_task_priority",
        "create_checklist", "add_checklist_item", "update_checklist_item",
        "complete_checklist_item", "get_task_progress",
    ],
    "calendar": [
        "create_event", "update_event", "delete_event", "list_events",
        "get_day_schedule", "get_week_schedule", "find_free_slots",
        "check_time_conflicts",
    ],
    "planning": [
        "list_tasks", "create_task", "get_task", "estimate_task_duration",
        "split_goal_into_tasks", "schedule_tasks_to_free_slots",
        "list_events", "find_free_slots", "get_week_schedule",
        "search_memory", "create_checklist",
    ],
    "prioritization": [
        "list_tasks", "get_task", "get_task_progress", "get_day_schedule",
        "list_events", "search_memory", "set_task_status",
    ],
    "memory": [
        "save_memory", "search_memory", "update_memory", "delete_memory",
        "list_memory",
    ],
    "digest": [
        "generate_morning_digest", "generate_evening_digest", "save_digest",
        "list_digests", "list_tasks", "list_events",
    ],
    "sleep_fairy": [
        "generate_evening_digest", "reschedule_overdue_tasks", "list_tasks",
        "set_task_status", "create_event", "search_memory", "save_digest",
    ],
}

# Необратимые действия — требуют подтверждения пользователя (Reflection флагует).
DESTRUCTIVE_TOOLS = {"delete_task", "delete_event", "delete_memory"}

# Инструменты, создающие/меняющие persistent-данные — проверяет Verifier.
MUTATING_TOOLS = {
    "create_task", "update_task", "delete_task", "set_task_status",
    "set_task_priority", "create_checklist", "add_checklist_item",
    "update_checklist_item", "complete_checklist_item",
    "create_event", "update_event", "delete_event",
    "save_memory", "update_memory", "delete_memory",
    "generate_morning_digest", "generate_evening_digest", "save_digest",
    "split_goal_into_tasks", "schedule_tasks_to_free_slots",
    "reschedule_overdue_tasks", "create_note", "update_note",
}
