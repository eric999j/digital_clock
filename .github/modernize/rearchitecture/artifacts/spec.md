# Feature Specification: Sequential Functional Flow Refactoring

> Governed by: `./constitution.md`

**Created**: 2026-11-18  
**Status**: Approved for phased implementation  
**Input**: "依序開始重構"

## Scope Baseline

- **Discovery method**: Existing architecture artifacts covering entry points, behavior, bindings, state flows, and external contracts.
- **Total items discovered**: 11 functional units.
- **Items in scope**: 11, implemented sequentially in phased batches without changing persisted schemas or user behavior.

## User Scenarios & Testing

### User Story 1 - No setting is lost during concurrent feature changes (Priority: P1)

As a clock user, I can change appearance and operate another feature before the delayed save finishes without losing either change.

**Independent Test**: Queue a UI config change, write an unrelated service setting, flush the UI save, and verify both values persist.

**Acceptance Scenarios**:

1. **Given** a UI change is pending, **When** a service immediately saves another section, **Then** the eventual save contains both changes.
2. **Given** multiple UI changes occur before one flush, **When** the debounce callback runs, **Then** all pending UI leaves persist.
3. **Given** shutdown follows a final edit, **When** flush runs, **Then** no pending change is lost.

### User Story 2 - Feature flows remain independently verifiable (Priority: P1)

As a maintainer, I can extract flow coordination and event translation without changing reminder, timer, todo, or pause behavior.

**Independent Test**: Run focused unit tests for each extracted coordinator and the existing full suite.

### User Story 3 - Large controllers become cohesive without breaking compatibility (Priority: P2)

As a maintainer, I can extend a feature without editing the clock renderer or the all-feature mediator for unrelated behavior.

**Independent Test**: New adapters preserve exported signatures and existing observers while ownership is split.

### Edge Cases

- Different features mutate different leaves under the same top-level section.
- Service writes occur after a UI mutation but before debounce flush.
- The same setting is changed by both paths before flush; the later explicit UI patch remains authoritative.
- A key is removed from a pending config and must remain removed after merge.

## Requirements

### Functional Requirements

- **REQ-001**: Pending full-config UI changes MUST merge onto the latest persisted config at flush time.
- **REQ-002**: Recursive pending changes MUST preserve unrelated service changes, including siblings under the same top-level section.
- **REQ-003**: Deleted config keys MUST be represented and preserved by the pending update.
- **REQ-004**: Existing event names, positional payloads, and observer isolation MUST remain compatible during refactoring.
- **REQ-005**: Scheduler extraction MUST preserve check order and one shared timestamp per tick.
- **REQ-006**: Pause/vacation source semantics and legacy field projection MUST remain unchanged.
- **REQ-007**: Todo commands, atomic persistence, history, and file recovery MUST remain unchanged.
- **REQ-008**: Main-window and ClockLogic compatibility adapters MUST remain until full regression verification passes.
- **REQ-009**: Every refactoring batch MUST have focused regression tests and full unittest verification.

### Key Entities

- **Pending config patch**: Recursive additions, updates, and deletions relative to the latest state.
- **Feature flow unit**: One externally triggerable behavior and its compatibility contract.
- **Compatibility event**: Stable event name plus positional payload.
- **Pause source set**: Manual, schedule, calendar, or other source contributing to effective pause.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of focused race-condition cases preserve both UI and service changes.
- **SC-002**: All existing unittest suites pass after every completed batch.
- **SC-003**: No persisted config/todo schema version changes are required.
- **SC-004**: No existing event constant or exported service signature is removed before compatibility verification.
- **SC-005**: Each phase can be stopped independently with the previous phase still complete and testable.
