# Implementation Plan: Sequential Functional Flow Refactoring

**Date**: 2026-11-18 | **Spec**: `.github/modernize/rearchitecture/artifacts/spec.md`

## Summary

Refactor the highest-risk coordination surfaces in independently verifiable batches. Begin with pending config merge safety, then extract scheduler/event translation, pause persistence, todo responsibilities, and finally controller boundaries.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: tkinter, pynput, icalendar, recurring-ical-events, tzdata on Windows  
**Storage**: Atomic JSON config and todo files  
**Testing**: unittest  
**Target Platform**: Desktop Python application  
**Performance Goals**: No additional per-second allocations beyond existing config checks  
**Constraints**: UI remains main-thread only; source-based pause and persisted schemas remain compatible

## Constitution Check

- Behavior and schema preservation: PASS
- Main-thread UI discipline: PASS
- Todo command discipline: PASS
- Privacy and secure local persistence: PASS
- Incremental compatibility adapters: PASS
- Regression coverage per batch: PASS

## Applied Guidelines

- Source anchors and split candidates from architecture analysis determine behavior fidelity.
- Refactoring is phased; `migration_boundary.yaml` forbids interpreting every anchor as a rewrite target.

## Implementation Steps

### Phase 1: Pending Config Merge Safety

#### Step 1.1: Capture recursive pending config patches
- **Requirements**: REQ-001, REQ-002, REQ-003
- **Design inputs**: `seams.yaml`, `cross_unit_state.yaml`, appearance behavior/bindings
- **Description**: Record pending UI mutations as a recursive diff instead of replacing the latest full dictionary.

#### Step 1.2: Merge patches at flush
- **Requirements**: REQ-001, REQ-002, REQ-003
- **Design inputs**: config wire contract and settings-cache flow
- **Description**: Apply additions, updates, and deletions to the latest persisted config immediately before save.

#### Step 1.3: Verify config race behavior
- **Requirements**: REQ-001, REQ-002, REQ-003, REQ-009
- **Design inputs**: config and clock settings unit tests
- **Description**: Add focused unit tests and run the full suite.

Tasks:

- [x] T001 [Plan:1.1] Add recursive config patch calculation and application helpers in `core/clock_logic.py` with focused unit tests.
- [x] T002 [Plan:1.2] Update `ClockLogic` delayed-save state to preserve the original base and merge onto the latest config during flush.
- [x] T003 [Plan:1.3] Add race/deletion/flush regression tests in `tests/test_clock_logic_observer.py` and run the complete unittest suite.

### Phase 2: Scheduler and Event Adapters

#### Step 2.1: Extract tick coordinator
- **Requirements**: REQ-005, REQ-008
- **Description**: Move ordered feature checks behind a compatibility coordinator while retaining the shared timestamp.

#### Step 2.2: Type event payload adapters
- **Requirements**: REQ-004, REQ-008
- **Description**: Introduce explicit adapters around stable `Events` names and positional payloads.

Tasks:

- [x] T004 [Plan:2.1] Add a feature check coordinator in `core/check_coordinator.py` and delegate `ClockLogic.check_reminders` to it.
- [x] T005 [Plan:2.2] Add the UI event-handler adapter in `ui/event_router.py` and preserve `DigitalClock.update` behavior.
- [x] T006 [Plan:2.1,2.2] Add ordering/mapping compatibility tests and run the full unittest suite.

### Phase 3: Pause and Todo Ownership

#### Step 3.1: Separate pause transition policy
- **Requirements**: REQ-006, REQ-008
- **Description**: Split source-set policy from config persistence while preserving legacy projections.

#### Step 3.2: Separate todo responsibilities
- **Requirements**: REQ-007, REQ-008
- **Description**: Keep command-based tree mutation while isolating file transfer, filtering, and due projection.

Tasks:

- [x] T007 [Plan:3.1] Extract pure source-set transition logic to `core/pause_policy.py` and retain `PauseManager` compatibility methods.
- [x] T008 [Plan:3.2] Extract todo import/export/restore operations to `services/todo_transfer_service.py` behind `TodoService` delegates.
- [x] T009 [Plan:3.1,3.2] Add policy/transfer regression coverage and run the complete unittest suite.

### Phase 4: Controller Decomposition

#### Step 4.1: Split feature presentation adapters
- **Requirements**: REQ-004, REQ-008, REQ-009
- **Description**: Gradually extract menu/dialog/event handlers behind the current public adapters.

Tasks:

- [x] T010 [Plan:4.1] Extract feature window construction and singleton foregrounding to `ui/window_controller.py`.
- [x] T011 [Plan:4.1] Preserve existing `DigitalClock` window-opening methods as compatibility delegates.
- [x] T012 [Plan:4.1] Add adapter regression coverage and run the complete unittest suite.

## Project Structure

```text
core/clock_logic.py
tests/test_clock_logic_observer.py
core/check_coordinator.py
ui/event_router.py
tests/test_check_coordinator.py
tests/test_event_router.py
core/pause_policy.py
services/todo_transfer_service.py
tests/test_pause_policy.py
ui/window_controller.py
tests/test_window_controller.py
```

Future phases will add narrow coordinator/adapter modules only after their compatibility tests exist.

## Testing Strategy

- **appType**: desktop
- **Critical user journeys**: settings race safety, reminders/timers, pause source composition, todo mutation and recovery.
- **primaryValidationStack**: unittest plus existing service/UI unit tests.
- **fallbackMatrix**:
  - `infra-tier`: no infrastructure required.
  - `browser-tier`: not applicable.
- **Environment requirements**: Python 3.13 and existing dependencies.
- **knownGaps**: Full native window rendering is skipped where no display is available; service-level behavior remains covered.
- **Test data strategy**: Temporary home directories and MagicMock schedulers.
- **Acceptance criteria**: No failed tests; all race cases retain unrelated config.
- **Validation review expectations**: Verify schemas, events, order, thread handoff, and source anchors.

## Complexity Tracking

No constitution violations.

## Requirement Mapping

| REQ ID | Description | Plan Items | Implementation Evidence |
|--------|-------------|------------|------------------------|
| REQ-001 | Merge pending UI changes onto latest config | 1.1, 1.2 | `core/clock_logic.py`, race tests |
| REQ-002 | Preserve unrelated recursive sibling changes | 1.1, 1.2, 1.3 | recursive patch tests |
| REQ-003 | Preserve key deletions | 1.1, 1.2, 1.3 | deletion merge tests |
| REQ-004 | Preserve event compatibility | 2.2, 4.1 | event adapter tests |
| REQ-005 | Preserve check order and timestamp | 2.1 | coordinator ordering tests |
| REQ-006 | Preserve pause source semantics | 3.1 | pause manager tests |
| REQ-007 | Preserve todo command/persistence flow | 3.2 | todo service/store tests |
| REQ-008 | Retain compatibility adapters | 2.1, 2.2, 3.1, 3.2, 4.1 | existing exported signatures |
| REQ-009 | Verify every batch | 1.3, 4.1 | batch reports and unittest results |
