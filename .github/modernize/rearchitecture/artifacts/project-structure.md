# Project Structure

## Classification

- Project type: desktop GUI application (single deployable process).
- Language: Python.
- Runtime UI: tkinter, with OS-specific window integration.
- Architecture: UI -> mediator/service -> strategy, with Observer events returning from services to UI.

## Source layout

| Path | File count | Role |
|---|---:|---|
| `core/` | 14 Python files | Orchestration, events, observer contract, domain models, commands, launch safety |
| `services/` | 15 Python files | Stateful feature engines, persistence adapters, calendar/keyboard integrations |
| `strategies/` | 8 Python files | Replaceable time and schedule decision logic |
| `ui/` | 21 Python files | Main window, menus, feature dialogs, themed popups |
| `tests/` | 40 Python files | unittest coverage for services, strategies, persistence, and UI |
| root | 1 Python file | `main.py` application entrypoint |

## Layers

1. `main.py` configures logging, DPI support, `ConfigManager`, and `DigitalClock`.
2. `DigitalClock` owns tkinter lifecycle, rendering, menus, dialogs, and observer dispatch.
3. `ClockLogic` composes services and exposes UI-facing delegates.
4. Services own feature state and persistence calls.
5. Strategies make time/schedule decisions without owning UI.
6. `AppState` and `NotificationCenter` consume emitted events and derive cross-feature views.

## Functional domains

- Clock rendering and window behavior
- Pomodoro
- Countdown
- Reminders and snooze
- Hourly URL/program launch
- Todo tree, command history, import/export, due reminders
- Manual/scheduled/calendar-driven do-not-disturb
- Notification history
- Multiple time zones
- Appearance, themes, fonts, transparency, and logs
- Screenshot shortcut hiding

## Entry points

- `main.py:31` starts the application when executed directly.
- `ui/main_window.py:1900` starts the tkinter main loop.
- `ui/main_window.py:1855` is the recurring UI/logic tick entrypoint.
- `core/clock_logic.py:307` coordinates one business-logic check cycle.

## Key configuration and packaging

- `pyproject.toml`: package metadata, Python 3.13+, runtime/dev dependencies, Ruff and coverage configuration.
- `requirements.txt`: runtime dependencies for direct startup scripts.
- `start_windows.bat`, `start_linux.sh`, `start_macos.command`: local environment bootstrap.
- `package_windows.bat`, `package_macos.sh`, `package_linux.sh`: PyInstaller release packaging.
- Runtime user data is outside the repository under `~/.digital_clock/`.

## Structural observations

- `ui/main_window.py` and `core/clock_logic.py` are the dominant coordination surfaces.
- Feature services are independently testable, but UI construction and event handling remain centralized in the main window.
- Settings persistence is shared broadly; several components reload and immediately save complete configuration dictionaries.
- Todo persistence is intentionally separated from settings persistence.
