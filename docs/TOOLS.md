# TOOLS — справочник инструментов

Справочник соответствует реестру инструментов (`app/tools/registry.py`). Всего инструментов: **39**.

Каждый инструмент — функция с Pydantic-схемой входа; выход нормализуется в JSON. Все вызовы логируются в `logs/agent.log` (события `tool_call`, `tool_result`, `tool_error`).

Пример вызова (через агента в `/chat`): модель отдаёт tool-call с именем инструмента и JSON-аргументами по схеме ниже; реестр валидирует вход, выполняет обработчик и возвращает результат агенту.

## Задачи и чеклисты (Task Agent)

### `create_task`
Создать новую задачу.

- **Вход:**
  - `title`: string **(обяз.)** — Краткое название задачи
  - `description`: string
  - `priority`: enum/ref
  - `status`: enum/ref
  - `deadline`: string | null — Дедлайн в ISO, напр. 2026-06-10T18:00
  - `tags`: array
  - `project`: string | null
  - `estimated_minutes`: integer | null
  - `source`: string
- **Выход:** Task

### `update_task`
Обновить поля задачи по id.

- **Вход:**
  - `id`: string **(обяз.)**
  - `title`: string | null
  - `description`: string | null
  - `priority`: ref | null
  - `status`: ref | null
  - `deadline`: string | null
  - `tags`: array | null
  - `project`: string | null
  - `estimated_minutes`: integer | null
  - `actual_minutes`: integer | null
- **Выход:** Task

### `delete_task`
Удалить задачу по id.

- **Вход:**
  - `id`: string **(обяз.)**
- **Выход:** {deleted: bool}

### `get_task`
Получить задачу по id.

- **Вход:**
  - `id`: string **(обяз.)**
- **Выход:** Task | null

### `list_tasks`
Список задач с фильтрами по статусу/проекту/тегу.

- **Вход:**
  - `status`: ref | null
  - `project`: string | null
  - `tag`: string | null
  - `include_archived`: boolean
- **Выход:** Task[]

### `search_tasks`
Поиск задач по подстроке в названии/описании/тегах.

- **Вход:**
  - `query`: string **(обяз.)**
- **Выход:** Task[]

### `set_task_status`
Изменить статус задачи.

- **Вход:**
  - `id`: string **(обяз.)**
  - `status`: enum/ref **(обяз.)**
- **Выход:** Task

### `set_task_priority`
Изменить приоритет задачи.

- **Вход:**
  - `id`: string **(обяз.)**
  - `priority`: enum/ref **(обяз.)**
- **Выход:** Task

### `create_checklist`
Создать чеклист (опц. привязать к задаче) и наполнить пунктами.

- **Вход:**
  - `task_id`: string | null — К какой задаче привязать
  - `title`: string
  - `items`: array — Тексты пунктов
- **Выход:** Checklist

### `add_checklist_item`
Добавить пункт в чеклист.

- **Вход:**
  - `checklist_id`: string **(обяз.)**
  - `text`: string **(обяз.)**
- **Выход:** Checklist

### `update_checklist_item`
Изменить текст и/или статус пункта чеклиста.

- **Вход:**
  - `checklist_id`: string **(обяз.)**
  - `item_id`: string **(обяз.)**
  - `text`: string | null
  - `done`: boolean | null
- **Выход:** Checklist

### `complete_checklist_item`
Отметить пункт чеклиста выполненным.

- **Вход:**
  - `checklist_id`: string **(обяз.)**
  - `item_id`: string **(обяз.)**
- **Выход:** Checklist

### `get_task_progress`
Прогресс по задаче: агрегирует пункты всех связанных чеклистов.

- **Вход:**
  - `id`: string **(обяз.)**
- **Выход:** {total, completed, percent, status}

## Календарь (Calendar Agent)

### `create_event`
Создать событие в локальном календаре.

- **Вход:**
  - `title`: string **(обяз.)**
  - `start_datetime`: string **(обяз.)** — ISO, напр. 2026-06-10T10:00
  - `end_datetime`: string **(обяз.)** — ISO, напр. 2026-06-10T11:30
  - `description`: string
  - `type`: enum/ref
  - `linked_task_id`: string | null
- **Выход:** {event, conflicts}

### `update_event`
Обновить событие календаря по id.

- **Вход:**
  - `id`: string **(обяз.)**
  - `title`: string | null
  - `start_datetime`: string | null
  - `end_datetime`: string | null
  - `description`: string | null
  - `type`: ref | null
  - `linked_task_id`: string | null
- **Выход:** CalendarEvent

### `delete_event`
Удалить событие календаря по id.

- **Вход:**
  - `id`: string **(обяз.)**
- **Выход:** {deleted: bool}

### `list_events`
Список событий, опц. в диапазоне дат.

- **Вход:**
  - `from_date`: string | null — С какой даты (вкл.)
  - `to_date`: string | null — По какую дату (вкл.)
- **Выход:** CalendarEvent[]

### `get_day_schedule`
Расписание на конкретный день.

- **Вход:**
  - `date`: string | null — Дата дня; по умолчанию сегодня
- **Выход:** {date, events}

### `get_week_schedule`
Расписание на 7 дней от даты (по умолч. сегодня).

- **Вход:**
  - `start_date`: string | null — Начало недели; по умолчанию сегодня
- **Выход:** {days: [{date, events}]}

### `find_free_slots`
Найти свободные окна в рабочем дне.

- **Вход:**
  - `date`: string | null
  - `work_day_start`: string
  - `work_day_end`: string
  - `min_minutes`: integer
- **Выход:** {slots: [{start, end, minutes}]}

### `check_time_conflicts`
Проверить конфликты по времени для интервала.

- **Вход:**
  - `start_datetime`: string **(обяз.)**
  - `end_datetime`: string **(обяз.)**
  - `ignore_event_id`: string | null
- **Выход:** {has_conflict, conflicts}

## Память (Memory Agent)

### `save_memory`
Сохранить факт/предпочтение пользователя в память.

- **Вход:**
  - `content`: string **(обяз.)** — Сам факт/предпочтение/правило
  - `type`: enum/ref
  - `key`: string | null — Короткий ключ для поиска/обновления
  - `tags`: array
  - `source`: string
- **Выход:** MemoryItem

### `search_memory`
Найти факты в памяти по подстроке и/или типу.

- **Вход:**
  - `query`: string
  - `type`: ref | null
- **Выход:** MemoryItem[]

### `update_memory`
Обновить факт в памяти по id.

- **Вход:**
  - `id`: string **(обяз.)**
  - `content`: string | null
  - `type`: ref | null
  - `key`: string | null
  - `tags`: array | null
- **Выход:** MemoryItem

### `delete_memory`
Удалить факт из памяти по id.

- **Вход:**
  - `id`: string **(обяз.)**
- **Выход:** {deleted: bool}

### `list_memory`
Список всех фактов памяти, опц. по типу.

- **Вход:**
  - `type`: ref | null
- **Выход:** MemoryItem[]

## Дайджесты (Digest Agent)

### `generate_morning_digest`
Собрать и сохранить утренний дайджест (задачи, события, просрочки, рекомендация дня).

- **Вход:**
  - `date`: string | null — Дата; по умолчанию сегодня
- **Выход:** Digest

### `generate_evening_digest`
Собрать и сохранить вечерний дайджест (что сделано, что нет, что перенести, план на завтра).

- **Вход:**
  - `date`: string | null — Дата; по умолчанию сегодня
- **Выход:** Digest

### `save_digest`
Сохранить произвольный дайджест.

- **Вход:**
  - `kind`: string **(обяз.)** — morning | evening
  - `date`: string **(обяз.)**
  - `content`: string **(обяз.)**
  - `data`: object
- **Выход:** Digest

### `list_digests`
История сохранённых дайджестов (новые сверху).

- **Вход:**
  - `kind`: string | null
  - `limit`: integer
- **Выход:** Digest[]

## Планирование (Planning Agent)

### `estimate_task_duration`
Оценить длительность задачи в минутах (эвристика по ключевым словам).

- **Вход:**
  - `title`: string **(обяз.)**
  - `description`: string
- **Выход:** {minutes, rationale}

### `split_goal_into_tasks`
Разбить цель на задачи и создать их. Если subtasks не заданы — используется типовой шаблон этапов.

- **Вход:**
  - `goal`: string **(обяз.)** — Цель пользователя одной фразой
  - `subtasks`: array — Готовые подзадачи (если есть). Иначе будет шаблон.
  - `project`: string | null
  - `priority`: enum/ref
  - `deadline`: string | null
- **Выход:** {tasks: Task[]}

### `schedule_tasks_to_free_slots`
Распределить задачи по свободным окнам календаря и создать события (type=task_block), связанные с задачами.

- **Вход:**
  - `task_ids`: array **(обяз.)**
  - `start_date`: string | null
  - `horizon_days`: integer
  - `work_day_start`: string
  - `work_day_end`: string
  - `default_minutes`: integer
- **Выход:** {events: CalendarEvent[], warnings: []}

### `reschedule_overdue_tasks`
Перенести просроченные/незавершённые задачи на ближайшие дни.

- **Вход:**
  - `within_days`: integer
- **Выход:** {moved: Task[]}

## База знаний (опционально)

### `create_note`
Создать заметку в базе знаний (.md + метаданные).

- **Вход:**
  - `title`: string **(обяз.)**
  - `body`: string
  - `tags`: array
  - `linked_task_ids`: array
- **Выход:** Note

### `update_note`
Обновить заметку по id.

- **Вход:**
  - `id`: string **(обяз.)**
  - `title`: string | null
  - `body`: string | null
  - `tags`: array | null
- **Выход:** Note

### `search_notes`
Поиск заметок по подстроке в заголовке/тексте/тегах.

- **Вход:**
  - `query`: string
- **Выход:** Note[]

### `link_note_to_task`
Связать заметку с задачей.

- **Вход:**
  - `note_id`: string **(обяз.)**
  - `task_id`: string **(обяз.)**
- **Выход:** Note

### `summarize_note`
Короткая выжимка заметки (обрезка по символам).

- **Вход:**
  - `note_id`: string **(обяз.)**
  - `max_chars`: integer
- **Выход:** {summary}
