---
title: "ADR-0003: ProgressReporter Protocol for Dependency Inversion"
status: "Accepted"
date: "2026-02-03"
authors: "Development Team"
tags: ["architecture", "decision", "protocols", "dependency-inversion", "clean-architecture"]
supersedes: ""
superseded_by: ""
---

# ADR-0003: ProgressReporter Protocol for Dependency Inversion

## Status

**Accepted** (Implemented)

## Context

The my-unicorn application has a clear architectural separation between two layers:

- **Core module** (`src/my_unicorn/core/`): Business logic, workflows, external integrations (GitHub API, downloads, hash verification)
- **UI module** (`src/my_unicorn/ui/`): Progress displays, formatters, user-facing output rendering

Long-running operations (downloading AppImages, fetching GitHub releases, verifying checksums) require progress feedback to maintain good user experience. However, allowing the core layer to directly depend on UI implementations violates fundamental architectural principles:

1. **Dependency Inversion Principle**: High-level modules (core business logic) should not depend on low-level modules (UI details)
2. **Clean Architecture**: Domain/application layers should remain independent of infrastructure concerns
3. **Testability**: Core workflows should be testable without instantiating heavy UI components (progress bars, formatters, Rich library dependencies)
4. **Flexibility**: The application should support multiple UI paradigms (CLI, GUI, web API, silent mode) without modifying core logic

The challenge was to enable progress reporting from core workflows while maintaining architectural boundaries and ensuring the codebase remains testable, maintainable, and extensible.

## Decision

Introduce a `ProgressReporter` protocol in `core/protocols/progress.py` that defines an abstract interface for progress reporting. The core layer depends on this abstraction, while the UI layer provides concrete implementations.

**Key Design Elements:**

1. **Protocol Definition** (Python `typing.Protocol`):

```python
class ProgressReporter(Protocol):
    def create_task(self, task_id: str, description: str, total: int) -> None: ...
    def update_progress(self, task_id: str, completed: int) -> None: ...
    def finish_task(self, task_id: str) -> None: ...
```

1. **Core Layer Usage**: Workflows receive `ProgressReporter` via dependency injection through `ServiceContainer`

2. **UI Implementation**: `ProgressDisplay` class (`ui/progress.py`, 815 LOC) implements the protocol with Rich-based progress bars

3. **Testing Implementation**: `NullProgressReporter` provides no-op implementation for testing environments

**Rationale:**

- **Dependency Inversion**: Core workflows depend on the `ProgressReporter` abstraction, not concrete UI classes
- **Type Safety**: Python protocols provide static type checking without runtime overhead (duck typing with guarantees)
- **Zero Runtime Cost**: Protocols are erased at runtime—no performance penalty compared to direct calls
- **Testability**: `NullProgressReporter` enables testing core workflows without UI dependencies
- **Extensibility**: New UI paradigms (GUI, web dashboard, API) can implement the protocol without touching core code
- **Simplicity**: Protocol requires only 3 methods, minimizing implementation burden

## Consequences

### Positive

- **POS-001**: **Clean Architecture Compliance** - Core layer has zero dependency on UI layer, enforcing proper layering and separation of concerns
- **POS-002**: **Enhanced Testability** - Core workflows can be tested with `NullProgressReporter`, eliminating UI overhead and improving test execution speed (≈995 tests run in <10s)
- **POS-003**: **Type Safety Without Overhead** - Static type checkers (mypy, pyright) validate protocol compliance at development time with zero runtime cost
- **POS-004**: **Multiple UI Paradigm Support** - Any implementation satisfying the protocol contract can be used (CLI with Rich, headless CI/CD, future GUI, web API)
- **POS-005**: **Maintainability** - Protocol acts as contract documentation, making progress reporting expectations explicit and reducing coupling

### Negative

- **NEG-001**: **Additional Abstraction Layer** - Developers must understand protocol pattern and dependency injection, increasing cognitive load for new contributors
- **NEG-002**: **Protocol Contract Maintenance** - Protocol changes require updating all implementations (`ProgressDisplay`, `NullProgressReporter`, and any future implementations)
- **NEG-003**: **Code Duplication** - `NullProgressReporter` duplicates method signatures with no-op implementations (minimal but unavoidable)
- **NEG-004**: **Indirect Coupling** - While not directly coupled, core and UI must agree on protocol semantics (task lifecycle, task_id scheme, total units meaning)
- **NEG-005**: **Debugging Complexity** - Protocol-based calls are harder to trace in debuggers compared to direct method calls (requires understanding dependency injection flow)

## Alternatives Considered

### Direct UI Dependency

- **ALT-001**: **Description**: Core workflows directly import and instantiate `ProgressDisplay` from UI module
- **ALT-002**: **Rejection Reason**: Violates Dependency Inversion Principle and Clean Architecture; makes core layer untestable without UI dependencies; couples core to specific Rich library implementation; prevents headless/silent operation modes

### Callback Functions

- **ALT-003**: **Description**: Core workflows accept progress callback functions (`Callable[[str, int, int], None]`) instead of protocol objects
- **ALT-004**: **Rejection Reason**: Less type-safe (callback signatures not enforced by type system); harder to extend (adding new progress operations requires signature changes); no encapsulation of progress state; difficult to support multiple concurrent tasks

### Event Emitter Pattern

- **ALT-005**: **Description**: Core workflows emit progress events to event bus; UI subscribes to events
- **ALT-006**: **Rejection Reason**: Over-engineering for current requirements; adds complexity (event bus infrastructure, subscription management, event serialization); harder to reason about data flow; potential memory leaks from forgotten unsubscribes; no clear ownership of progress state

### Observer Pattern with Abstract Base Classes

- **ALT-007**: **Description**: Define `ProgressReporter` as ABC (Abstract Base Class) requiring explicit inheritance
- **ALT-008**: **Rejection Reason**: Runtime overhead (ABC metaclass machinery); requires explicit inheritance (less flexible than structural typing); unnecessary complexity (Protocol achieves same goals with zero runtime cost); violates Python's duck typing philosophy

### No Progress Reporting

- **ALT-009**: **Description**: Remove all progress reporting; rely on logging for operation feedback
- **ALT-010**: **Rejection Reason**: Poor user experience for long-running operations (downloads can take 30+ seconds); logging doesn't provide real-time feedback; users cannot estimate completion time; no indication if operation is frozen vs. progressing slowly

## Implementation Notes

- **IMP-001**: **Protocol Location** - `ProgressReporter` protocol defined in `core/protocols/progress.py` to maintain core layer independence
- **IMP-002**: **Dependency Injection** - `ServiceContainer` accepts `ProgressReporter` in constructor and provides it to workflows (`InstallWorkflow`, `UpdateWorkflow`, etc.)
- **IMP-003**: **Testing Strategy** - All core workflow tests use `NullProgressReporter` to eliminate UI coupling; `ProgressDisplay` tested separately in UI layer tests
- **IMP-004**: **Implementation Classes**:
    - `ProgressDisplay` (`ui/progress.py`, 815 LOC): Rich-based CLI progress bars with task management
    - `NullProgressReporter` (`core/protocols/progress.py`): No-op implementation for testing/silent mode
- **IMP-005**: **Migration Path** - Legacy code using direct `ProgressDisplay` gradually refactored to accept `ProgressReporter` protocol
- **IMP-006**: **Future Extensions** - Protocol can be extended with additional optional methods (e.g., `pause_task`, `set_task_metadata`) without breaking existing implementations

## References

- **REF-001**: [PEP 544 – Protocols: Structural subtyping (static duck typing)](https://peps.python.org/pep-0544/)
- **REF-002**: Clean Architecture Principles - Dependency Inversion (Uncle Bob Martin)
- **REF-003**: [`core/protocols/progress.py`](../../dev/src/my_unicorn/core/protocols/progress.py) - Protocol definition and `NullProgressReporter`
- **REF-004**: [`ui/progress.py`](../../dev/src/my_unicorn/ui/progress.py) - `ProgressDisplay` implementation (815 LOC)
- **REF-005**: [`core/workflows/install.py`](../../dev/src/my_unicorn/core/workflows/install.py) - Example protocol usage in workflows
- **REF-006**: [ADR-0001: Hybrid v2 Configuration Format](adr-0001-hybrid-v2-config-format.md) - Related architectural decision
- **REF-007**: [ADR-0002: uvloop Adoption](adr-0002-uvloop-adoption.md) - Async architecture context
