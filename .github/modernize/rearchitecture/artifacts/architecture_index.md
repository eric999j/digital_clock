# Architecture Analysis Index

This index is not the full contract. Do not implement from this file alone; follow the artifact paths below.

## Scope

This run reviews the current application and refreshes source-anchored analysis. It does not authorize application-code changes and does not select a target framework or final unit count.

## Implementation Guide

### Global artifacts

- `unit_graph.yaml`: all workers; filter to the assigned unit for trigger, anchors, dependencies, signatures, and shared references.
- `migration_boundary.yaml`: all workers; `must_rewrite` is currently empty because the user requested analysis only.
- `wire_contracts.yaml`: filter `unit` by assigned name or `global`; preserve frozen external shapes.
- `shared_modules.yaml`: filter `used_by_units`; honor `migration_strategy` and the unit's `used_fields` subset.
- `cross_unit_state.yaml`: filter `writer.unit` or `reader.unit`; resolve every `must_confirm: runtime`.
- `seams.yaml`: filter `cut_between`; inferred seams are candidates, while frozen-side rules protect current behavior during extraction.
- `project-structure.md`, `tech-stack.md`, `data-model.md`: read for repository context, runtime constraints, and existing schemas.

### Unit: clock-shell

- External trigger: CLI startup, recurring tkinter tick, screenshot shortcut, shutdown.
- Must read: `units/clock-shell/behavior.yaml`, `units/clock-shell/bindings.yaml`.
- Optional design evidence: `units/clock-shell/unit_decomposition.yaml` (`commit: false`).
- Relevant globals: contracts `unit: global` or `clock-shell`; shared rows containing `clock-shell`; seams around tick/config/events.
- Before DONE report: artifacts read, all startup/shutdown and thread-marshalling contracts preserved, unresolved runtime checks, full test/build evidence.

### Unit: reminders

- External trigger: reminder menu/dialog, pause toggle, recurring due tick, snooze.
- Must read: `units/reminders/behavior.yaml`, `units/reminders/bindings.yaml`.
- Optional design evidence: `units/reminders/unit_decomposition.yaml`.
- Relevant globals: filter reminder unit, pause-source flow, settings contract, clock/event/popup shared modules.
- Before DONE report: trigger/dedup/cleanup/snooze behavior, unresolved config races, focused tests.

### Unit: hourly-launch

- External trigger: settings dialog, hourly/startup schedule, URL/program test, XML/JSON import.
- Must read: `units/hourly-launch/behavior.yaml`, `units/hourly-launch/bindings.yaml`.
- Optional design evidence: `units/hourly-launch/unit_decomposition.yaml`.
- Relevant globals: browser/program/file contracts, pause-source state, launch/config/event shared modules.
- Before DONE report: no-shell and URL contracts, disabled imported-program semantics, importer/launcher tests.

### Unit: pomodoro

- External trigger: menu controls and per-second tick.
- Must read: `units/pomodoro/behavior.yaml`, `units/pomodoro/bindings.yaml`.
- Optional design evidence: `units/pomodoro/unit_decomposition.yaml`.
- Relevant globals: event rows, vacation-to-stop flow, timer/config/app-state shared modules.
- Before DONE report: phase cycle, deadline behavior, stop-on-vacation, focused service/UI tests.

### Unit: countdown

- External trigger: quick/custom menu, pause/cancel, completion.
- Must read: `units/countdown/behavior.yaml`, `units/countdown/bindings.yaml`.
- Optional design evidence: `units/countdown/unit_decomposition.yaml`.
- Relevant globals: completion event, info/app-state shared rows.
- Before DONE report: validation limits, replacement/pause/reset behavior, bell/popup path, tests.

### Unit: todo

- External trigger: todo window, tree actions, file dialogs, hourly due policy.
- Must read: `units/todo/behavior.yaml`, `units/todo/bindings.yaml`.
- Optional design evidence: `units/todo/unit_decomposition.yaml`.
- Relevant globals: todos-json contract, pending-count and pause flows, command/store/event shared modules.
- Before DONE report: every mutation remains command-based, atomic schema/recovery preserved, import/export/undo evidence.

### Unit: vacation-mode

- External trigger: manual menu and date schedule tick.
- Must read: `units/vacation-mode/behavior.yaml`, `units/vacation-mode/bindings.yaml`.
- Optional design evidence: `units/vacation-mode/unit_decomposition.yaml`.
- Relevant globals: settings contract, all pause/vacation flows, config/pause/event shared modules.
- Before DONE report: source-order matrix, legacy-field compatibility, cleanup/auto-start behavior, tests.

### Unit: calendar-sync

- External trigger: settings/test UI, background refresh, main-thread meeting tick.
- Must read: `units/calendar-sync/behavior.yaml`, `units/calendar-sync/bindings.yaml`.
- Optional design evidence: `units/calendar-sync/unit_decomposition.yaml`.
- Relevant globals: outlook-ics-feed contract, calendar-vacation flow, pause/config/event shared modules.
- Before DONE report: worker/UI boundary, secret-safe errors, cache fallback, overlap and recurrence tests.

### Unit: notifications

- External trigger: completion events and notification-center commands.
- Must read: `units/notifications/behavior.yaml`, `units/notifications/bindings.yaml`.
- Optional design evidence: `units/notifications/unit_decomposition.yaml`.
- Relevant globals: notification event flows, event/app-state shared modules.
- Before DONE report: event mapping, bounded count, privacy rule, read/clear UI tests.

### Unit: timezones

- External trigger: timezone menu selection and info-band refresh.
- Must read: `units/timezones/behavior.yaml`, `units/timezones/bindings.yaml`.
- Optional design evidence: `units/timezones/unit_decomposition.yaml`.
- Relevant globals: TIMEZONES_UPDATED state, config/event/clock shared modules.
- Before DONE report: max-three rule, unavailable zone behavior, day-offset rendering tests.

### Unit: appearance-settings

- External trigger: clock settings menus, theme dialogs, log cleanup.
- Must read: `units/appearance-settings/behavior.yaml`, `units/appearance-settings/bindings.yaml`.
- Optional design evidence: `units/appearance-settings/unit_decomposition.yaml`.
- Relevant globals: settings contract, config pending-state flow, config-save seam, main-window/popup shared modules.
- Before DONE report: all live redraws, bounded window placement, debounce/flush behavior, tests.

## Recommended refactoring order

1. Define explicit config-slice ownership while preserving the current patch-on-latest merge and serialized writer.
2. Finish extracting feature event payload mapping from `DigitalClock`; `EventRouter` is the current adapter seam.
3. Continue separating feature UI controllers from `DigitalClock`, preserving observer and popup adapters.
4. Split source-based pause policy from its persistence adapter without losing legacy-field compatibility.
5. Split todo UI presentation from tree/command/file-transfer responsibilities.
6. Only then split `ClockLogic` and `DigitalClock` by feature, preserving old adapters until runtime evidence passes.
