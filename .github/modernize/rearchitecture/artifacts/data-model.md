# Data Model

## Storage boundaries

The application has no database or ORM. It uses two JSON stores:

1. `config.json`: application configuration and small feature collections.
2. `todos.json`: hierarchical todo tasks and command-persisted state.

## Configuration entities

### Reminder

Stored in `config.reminders[]`.

- Single reminder: `datetime`, `message`, `weekdays: []`, `title`.
- Recurring reminder: `time`, `message`, localized weekday names, `title`.

### Hourly launch rule

Stored in `config.hourly_web_reminder.url_rules[]`.

- Common: `type`, `enabled`, `start_hour`, `end_hour`, optional `weekdays`, optional `trigger`.
- URL rule: `url`.
- Program rule: `command`, `arguments`, `working_dir`, optional `name`.

### Vacation schedule

Stored in `config.vacation_schedules[]`.

- `start`: ISO date.
- `end`: ISO date.
- `note`.
- `auto_started`: runtime/persistence marker.

### Pause and vacation sources

- `pause_sources.reminder[]`
- `pause_sources.hourly_web[]`
- `vacation_sources[]`

The source sets coexist with synchronized legacy booleans for compatibility.

### Calendar synchronization

Stored in `config.calendar_sync`.

- `enabled`
- `ics_url`
- `refresh_minutes`
- `lead_minutes`

### Other configuration groups

- `window`: geometry and opacity.
- `appearance`: font, time/date format, theme, radius.
- `ui_behavior`: rendering and window geometry parameters.
- `system`: save delay, screenshot keys, performance monitor, log cleanup.
- `themes`: named colors.
- `todo`: reminder window and info-bar behavior.
- `pomodoro`: phase durations and cycle count.
- `timezones.selected`: IANA zone keys.

## TodoTask

Defined at `core/todo_task.py:64`.

Fields:

- `id: str`
- `text: str`
- `children: list[TodoTask]`
- `link: str | None`
- `creation_time: datetime`
- `is_done: bool`
- `priority: "low" | "normal" | "high"`
- `due_date: date | None`
- `start_date: date | None`
- `project: str | None`

Relationships:

- A task owns a recursive list of child tasks.
- Project values may propagate from parent to descendants.
- Completing a task affects descendants; reopening a child affects ancestors.

## Derived/in-memory entities

- `ZoneTime`: selected IANA zone and converted local time.
- `AppStateSnapshot`: aggregated pomodoro, countdown, pause, todo, and meeting state.
- `Notification`: bounded in-memory history item; not persisted.
- Calendar intervals: normalized local-naive start/end/summary records.

## File schema versions

- Settings `schema_version`: 1.
- Todo file `version`: 1.
- Hourly launch backup format: `digital-clock-hourly-launch`, version 1.

## Atomicity and invariants

- Config saves use temp file, `fsync`, optional owner restriction, then replace.
- Todo saves use temp file, `fsync`, owner restriction, then replace.
- Each successful todo mutation persists immediately and then emits `TODO_UPDATED`.
- Todo commands are the only supported mutation path and retain at most 50 undo entries.
