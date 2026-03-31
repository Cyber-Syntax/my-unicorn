---
title: "ADR-0005: Make ProgressReporter a Required Dependency"
status: "Proposed"
date: "2026-03-01"
authors: "Cyber-Syntax"
tags: ["architecture", "progress", "dependency-injection"]
supersedes: ""
superseded_by: ""
---

## Status

**Proposed**

## Context

The `ProgressReporter` protocol is a core abstraction used across most domain services to decouple progress UI from business logic. Currently, every service that accepts a `ProgressReporter` declares it as optional (`ProgressReporter | None = None`) and falls back to `NullProgressReporter()` when none is provided:

```python
def __init__(self, progress_reporter: ProgressReporter | None = None):
    self.progress_reporter = progress_reporter or NullProgressReporter()
```

This pattern is repeated in at least 9 modules:

- `core/download.py` — `DownloadService`
- `core/post_download.py` — `PostDownloadProcessor`
- `core/install/handler.py` — `InstallHandler`
- `core/services/install_service.py` — `InstallService`
- `core/services/update_service.py` — `UpdateService`
- `core/verification/service.py` — `VerificationService`
- `core/github/client.py` — `GitHubClient`
- `core/github/release_fetcher.py` — `ReleaseFetcher`, `BatchReleaseFetcher`
- `core/update/manager.py` — `UpdateManager`

In production, a real `ProgressDisplay` is **always** injected via the DI container (`ServiceContainer`). The `NullProgressReporter` fallback only silences the type checker and serves as a safety net that hides missing wiring bugs at runtime instead of surfacing them early.

The only module that legitimately does not need progress reporting is the **upgrade module** (`cli/upgrade.py`), which delegates entirely to the `uv` package manager for installation and update. It uses `ReleaseFetcher` only for a version check—not for download/install workflows—and does not create or inject a `ProgressReporter` at all.

Making `progress_reporter` required would enforce correct wiring at construction time, eliminate redundant `NullProgressReporter` fallbacks, and make the dependency graph explicit.

## Decision

Change `progress_reporter` from an optional to a required parameter in all services that participate in install/update workflows. Specifically:

1. **Change the constructor signature** in all affected services from `ProgressReporter | None = None` to `ProgressReporter` (required, no default).
2. **Remove the `or NullProgressReporter()` fallback** in each `__init__` body.
3. **Keep `NullProgressReporter` in the codebase** — it remains useful for tests and for the upgrade module's `ReleaseFetcher` usage, where no progress UI is needed. Callers that genuinely do not need progress must explicitly pass `NullProgressReporter()`, making the choice visible and intentional.
4. **Upgrade module exception**: The `cli/upgrade.py` module will explicitly pass `NullProgressReporter()` to `ReleaseFetcher` since it only performs a lightweight version check via the GitHub API and does not run download/install workflows.

This approach was chosen because:

- It converts a hidden default into an explicit contract, surfacing DI wiring bugs at construction time rather than at runtime.
- It aligns with the project's DI and protocol-based architecture, where dependencies should be injected, not silently defaulted.
- It is a safe, incremental refactor—existing tests that use mocks already pass a `ProgressReporter`; those that rely on the default can switch to an explicit `NullProgressReporter()`.

## Consequences

### Positive

- **POS-001**: Missing `ProgressReporter` wiring errors are caught immediately at construction time (by mypy and at runtime) instead of silently falling back to a no-op.
- **POS-002**: Eliminates ~9 instances of redundant `or NullProgressReporter()` fallback code, reducing boilerplate.
- **POS-003**: Makes the dependency graph fully explicit—every service clearly declares that it needs a `ProgressReporter`, improving code readability and auditability.
- **POS-004**: Aligns with Dependency Inversion Principle: callers are responsible for providing the dependency, not the callee.
- **POS-005**: Reduces ambiguity in test code—tests must explicitly choose between a mock reporter and `NullProgressReporter`, making test intent clearer.

### Negative

- **NEG-001**: Every caller that previously relied on the default `None` must now provide a `ProgressReporter` explicitly, increasing the surface area of the change.
- **NEG-002**: Test fixtures that instantiate services without providing `progress_reporter` will need updates, adding a one-time migration cost.
- **NEG-003**: Future modules that don't need progress (like upgrade) must explicitly pass `NullProgressReporter()`, which is slightly more verbose than omitting the argument.

## Alternatives Considered

### Keep the current optional pattern

- **ALT-001**: **Description**: Leave `progress_reporter` as `ProgressReporter | None = None` in all services and continue using the `NullProgressReporter` fallback.
- **ALT-002**: **Rejection Reason**: This hides DI wiring bugs. If a service is constructed without a progress reporter due to a bug in the container, the application silently runs without progress feedback instead of failing fast. The optional pattern was appropriate during initial development but is now a source of hidden fragility.

### Remove NullProgressReporter entirely

- **ALT-003**: **Description**: Make `ProgressReporter` required everywhere and remove the `NullProgressReporter` class completely, forcing all callers to provide a real implementation.
- **ALT-004**: **Rejection Reason**: `NullProgressReporter` remains valuable for tests and for the upgrade module. Removing it would force test code to create full mock implementations even when progress tracking is irrelevant to the test. The null object pattern itself is sound; the issue is only with using it as a silent default.

### Use a factory/provider function instead of direct injection

- **ALT-005**: **Description**: Instead of injecting `ProgressReporter` directly, inject a factory callable (`Callable[[], ProgressReporter]`) that creates reporters on demand.
- **ALT-006**: **Rejection Reason**: Adds unnecessary indirection. The current protocol-based injection is idiomatic Python and well-understood by the codebase. A factory would complicate the API without solving the actual problem of optional vs. required semantics.

## Implementation Notes

- **IMP-001**: Update constructor signatures in all 9 affected modules to change `progress_reporter: ProgressReporter | None = None` to `progress_reporter: ProgressReporter`. Remove the corresponding `or NullProgressReporter()` fallback in each `__init__`.
- **IMP-002**: In `cli/upgrade.py`, pass `NullProgressReporter()` explicitly when constructing `ReleaseFetcher` for version checks, since the upgrade workflow delegates to `uv` and does not need progress tracking.
- **IMP-003**: Update `ServiceContainer` (if needed) to ensure it always provides a `ProgressReporter` when creating services. Verify the container already does this—the change should be a no-op for production wiring.
- **IMP-004**: Update all test fixtures and test code that instantiate affected services without `progress_reporter`. Tests should pass either a mock or `NullProgressReporter()` explicitly.
- **IMP-005**: Run `uv run mypy src/my_unicorn/` after the change to verify all call sites provide the required argument. mypy will catch any missed callers at compile time.
- **IMP-006**: Preserve the `NullProgressReporter` class and its exports from `core/protocols/progress.py`—it remains part of the public API for tests and opt-out scenarios.

## References

- **REF-001**: ProgressReporter protocol — [src/my_unicorn/core/protocols/progress.py](../../src/my_unicorn/core/protocols/progress.py)
- **REF-002**: NullProgressReporter class — [src/my_unicorn/core/protocols/progress.py](../../src/my_unicorn/core/protocols/progress.py#L233-L336)
- **REF-003**: Upgrade module (no progress needed) — [src/my_unicorn/cli/upgrade.py](../../src/my_unicorn/cli/upgrade.py)
- **REF-004**: Example affected service — [src/my_unicorn/core/services/install_service.py](../../src/my_unicorn/core/services/install_service.py#L64)
- **REF-005**: Example affected service — [src/my_unicorn/core/download.py](../../src/my_unicorn/core/download.py#L60)
