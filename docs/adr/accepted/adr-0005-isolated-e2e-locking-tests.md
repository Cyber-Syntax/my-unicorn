---
title: "ADR-0005: Isolate E2E locking tests and make lock path configurable"
status: "Accepted"
date: "2026-02-22"
authors: "Cyber-Syntax"
tags: ["architecture", "testing", "cli", "locking"]
supersedes: "adr-0004-fcntl-flock-single-instance.md"
superseded_by: ""
---

## Status

**Accepted** - Implemented on 2026-02-22. All implementation notes completed successfully.

## Context

`my-unicorn` uses a single-instance lock (implemented with `fcntl.flock`) to
prevent concurrent CLI processes from corrupting shared state. This decision is
captured in `adr-0004-fcntl-flock-single-instance.md`.

The current E2E tests for single-instance locking (`tests/e2e/cli/test_single_instance_locking.py`)
spawn real CLI processes using `subprocess`. While the tests demonstrate that
locking works, there are practical and quality issues:

- **CTX-001**: The tests currently invoke `my-unicorn update` without sandboxing.
  On developer machines this can unintentionally update *real*, already-installed
  AppImages (because the CLI uses the developer’s actual `$HOME` / config).
- **CTX-002**: The tests hardcode `/tmp/my-unicorn.lock` and delete it.
  This can interfere with a real `my-unicorn` process running at the same time,
  and it couples tests to a global, shared path.
- **CTX-003**: The contention tests rely on timing (e.g., assuming `update` will
  “hold the lock for a while”). That can become flaky depending on cache state,
  network speed, and machine performance.
- **CTX-004**: The test module contains small quality issues that show up under
  static analysis (mypy/ruff), including unnecessary `type: ignore`, disabled
  mypy checks, and typos / confusing comments.

We already have a proven isolation mechanism for E2E tests via
`tests/e2e/sandbox.py` (`SandboxEnvironment`) and `tests/e2e/runner.py`
(`E2ERunner`), used by `tests/e2e/test_quick_flow.py`. The locking tests should
use the same sandbox approach.

Constraints and requirements:

- Must remain Linux-first (the lock implementation stays `fcntl.flock`).
- E2E tests must not mutate real user configuration or installed AppImages.
- Lock contention tests must be deterministic (avoid “sleep and hope” timing).
- Changes should be minimal and not alter production behavior by default.

## Decision

We will keep the existing `fcntl.flock` locking mechanism and default lock file
location, but we will improve test isolation and determinism.

- **DEC-001**: Make the lock file path configurable via an environment variable
  (e.g., `MY_UNICORN_LOCKFILE_PATH`) used by the CLI runner when acquiring the
  lock.
    - Default remains `/tmp/my-unicorn.lock` when the env var is not set.
    - This enables E2E tests to use a per-test lock file inside the sandbox
    directory.
- **DEC-002**: Refactor `tests/e2e/cli/test_single_instance_locking.py` to:
    - Run all `my-unicorn` subprocesses with `$HOME` pointing to a
    `SandboxEnvironment` directory (same pattern as `test_quick_flow.py`).
    - Use a per-test lock file path (via `MY_UNICORN_LOCKFILE_PATH`).
    - Use a deterministic lock-holder helper process (a tiny Python subprocess
    that acquires `flock()` and sleeps) to create contention without invoking
    long-running `my-unicorn update` flows.
- **DEC-003**: Clean up mypy/ruff issues in the locking E2E tests by:
    - Removing unnecessary `# type: ignore` and `mypy: disable` directives.
    - Adding proper type hints for fixtures and helpers.
    - Keeping security-related `ruff` ignores scoped to test subprocess calls.

Rationale:

- `SandboxEnvironment` already exists and is designed specifically to prevent
  touching real config.
- A per-test lock path removes interference with real user runs and reduces
  flakiness when tests are run concurrently.
- A dedicated lock-holder subprocess makes the lock contention tests stable and
  independent of cache/network timing.

## Consequences

### Positive

- **POS-001**: Running E2E tests no longer risks updating or mutating the
  developer’s real installed AppImages/config.
- **POS-002**: Lock contention tests become deterministic and less flaky.
- **POS-003**: Tests no longer delete or depend on the global
  `/tmp/my-unicorn.lock`, avoiding interference with real CLI executions.
- **POS-004**: Improved mypy/ruff compliance in the E2E tests reduces noise and
  keeps the test suite maintainable.

### Negative

- **NEG-001**: Adds a small new configuration surface area (`MY_UNICORN_LOCKFILE_PATH`).
  While intended for tests, it must be documented and handled carefully.
- **NEG-002**: Slightly more complex test code (helper subprocess + env wiring).
- **NEG-003**: The lock-holder helper process tests “lock is respected” rather
  than “a real my-unicorn command holds the lock for a long time”; this is a
  trade-off for determinism.

## Alternatives Considered

##### Keep current E2E locking tests as-is

- **ALT-001**: **Description**: Continue running `my-unicorn update` directly and
  cleaning `/tmp/my-unicorn.lock` in tests.
- **ALT-001**: **Rejection Reason**: Risks mutating real user state and is prone
  to timing flakiness.

##### Use `SandboxEnvironment` but still rely on `my-unicorn update` for lock-hold

- **ALT-002**: **Description**: Run `update` in the sandbox to avoid real-world
  updates, and depend on `update` runtime to create contention.
- **ALT-002**: **Rejection Reason**: Still timing-dependent; cached/no-op updates
  can complete too quickly, making contention tests flaky.

##### Add a built-in test hook to sleep after lock acquisition

- **ALT-003**: **Description**: Add a test-only environment variable that forces
  the CLI to sleep after acquiring the lock, ensuring contention.
- **ALT-003**: **Rejection Reason**: Introduces test-only behavior into
  production code paths; avoided in favor of an external lock-holder process.

## Implementation Notes

- **IMP-001**: Update `src/my_unicorn/cli/runner.py` to resolve the lock path as:
    - `Path(os.environ.get("MY_UNICORN_LOCKFILE_PATH", str(LOCKFILE_PATH)))`
- **IMP-002**: Update `tests/e2e/runner.py` to allow optional env overrides for
  subprocess execution (needed to pass `MY_UNICORN_LOCKFILE_PATH`).
- **IMP-003**: Refactor `tests/e2e/cli/test_single_instance_locking.py`:
    - Replace global `/tmp/my-unicorn.lock` cleanup with a sandbox-local lockfile.
    - Replace “run update and hope it takes long enough” with a deterministic
    Python lock-holder subprocess.
- **IMP-004**: Success criteria:
    - Running the E2E suite does not modify `~/.config/my-unicorn`.
    - Lock tests pass reliably on repeated runs.
    - mypy/ruff errors for the modified test module(s) are eliminated.

## References

- **REF-001**: `docs/adr/adr-0004-fcntl-flock-single-instance.md`
- **REF-002**: `src/my_unicorn/core/locking.py` (LockManager implementation)
- **REF-003**: `src/my_unicorn/cli/runner.py` (lock acquisition location)
- **REF-004**: `tests/e2e/sandbox.py` (SandboxEnvironment)
- **REF-005**: `tests/e2e/runner.py` (E2ERunner)
- **REF-006**: `tests/e2e/test_quick_flow.py` (existing sandboxed E2E pattern)

---

<!-- Quality checklist (automated/for reviewers) -->
- [x] ADR number determined and filename follows convention
- [x] Front matter completed
- [x] Status is set appropriately
- [x] Context describes the problem and constraints
- [x] Decision is clear and actionable
- [x] Positive and negative consequences documented
- [x] Alternatives considered with rejection reasons
- [x] Implementation notes provide actionable guidance
- [x] References include code pointers and related ADRs
