# Digital Clock Refactoring Constitution

1. Preserve observable behavior, event names, persisted schemas, and public service contracts.
2. Keep all tkinter mutations on the main thread; worker threads only transfer data/results.
3. Route todo mutations through `TodoCommand`; preserve undo/redo and immediate atomic persistence.
4. Preserve owner-only local storage and never log private task text or complete ICS URLs.
5. Prefer incremental adapters and compatibility seams over broad rewrites.
6. Every refactoring batch must add or retain focused regression coverage.
7. Use absolute imports, type hints, Google-style Traditional Chinese docstrings, and logging.
