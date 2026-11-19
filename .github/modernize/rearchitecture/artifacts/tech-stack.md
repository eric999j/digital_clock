# Technology Stack

## Runtime and language

- Python 3.13 or newer (`pyproject.toml:10`).
- tkinter is the desktop UI toolkit.
- CPython packaging uses setuptools and PyInstaller scripts.

## Runtime dependencies

| Dependency | Declared version | Purpose |
|---|---|---|
| `pynput` | `>=1.8.1` | Global screenshot shortcut listener |
| `tkinterdnd2` | `>=0.4.2` | Drag-and-drop XML/JSON into hourly-launch settings |
| `icalendar` | `>=6.0` | ICS parsing |
| `recurring-ical-events` | `>=3.0` | Recurring calendar occurrence expansion |
| `tzdata` | `>=2024.1` on Windows | IANA time-zone database |

## Development tooling

- unittest: 40 test files.
- Ruff: `E`, `F`, `W`, `I`, `B`, `UP`; target Python 3.13; line length 120.
- coverage: source scope `core`, `services`, `strategies`.
- setuptools build backend: `setuptools.build_meta`.

## Framework and OS bindings

- tkinter main-loop scheduling via `root.after`.
- `urllib.request` for HTTPS ICS download.
- `webbrowser` for safe HTTP(S) launch.
- `subprocess.Popen` for program launch without a shell.
- `pynput.keyboard.Listener` for global keyboard monitoring.
- `ctypes.windll` on Windows for foreground-window behavior.
- `ElementTree` for Windows Task Scheduler XML import.
- `zoneinfo` for IANA time zones.

## Persistence

- JSON settings: `~/.digital_clock/config.json`, atomically replaced.
- JSON todos: `~/.digital_clock/todos.json`, atomically replaced; corrupt data becomes `.bak`.
- Plain rotated log files under `~/.digital_clock/`.

## Existing constraints

- tkinter mutations must run on the main thread.
- Calendar fetching and connection testing use worker threads.
- Keyboard input arrives from a background listener and is marshalled with `root.after`.
- `ConfigManager.load_config(read_only=True)` returns a cache reference whose caller must not mutate it.
- Multiple legacy configuration fields coexist with source-based pause state.
- Python 3.13 syntax/type usage is part of the declared runtime contract.

No target framework or target runtime is selected in this analysis phase.
