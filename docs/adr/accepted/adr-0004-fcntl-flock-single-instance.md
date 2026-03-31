---
title: "ADR-0004: Use fcntl.flock for single-instance CLI locking"
status: "Accepted"
date: "2026-02-22"
authors: "Cyber-Syntax"
tags: ["architecture", "decision"]
supersedes: ""
superseded_by: ""
---

## Status

**Accepted**

---

## Context

my-unicorn is a Linux-first CLI that performs file- and state-modifying operations
(downloads, cache updates, backup creation, desktop entry and icon writes). Running
multiple instances of the CLI concurrently can produce race conditions that
lead to corrupted cache/app state, incomplete downloads, or overwritten backups.

Constraints and requirements:

- Must be lightweight and dependency-free for the common Linux CLI user case.
- Must be async-safe and acquired early in execution to protect file/metadata writes.
- Default behaviour should be predictable for CI/script usage (no hidden waits).
- Cross-process (not just in-process) mutual exclusion is required on Linux hosts.

Given the above and the repository's Linux-focused scope, we need a simple,
robust, process-level single-instance mechanism for the CLI.

---

## Decision

We will implement an advisory, process-level single-instance lock using Python's
`fcntl.flock` placed and acquired at the CLI entrypoint (early in
`src/my_unicorn/cli/runner.py` / `src/my_unicorn/main.py`).

- Lock type: exclusive file lock (fcntl.flock(..., LOCK_EX | LOCK_NB)).
- Lock file location: `/tmp/my-unicorn.lock`. Add a constant `LOCKFILE_PATH`
  in `src/my_unicorn/constants.py` pointing to this path.
- Default behaviour: fail-fast (non-blocking). If acquiring the lock fails,
  exit with a clear error message and non-zero exit code so scripts/CI fail fast.
- Future extension: add an optional `--wait`/`--lock-timeout` flag to block if needed.

Rationale:

- `fcntl.flock` is available in the Python standard library (no runtime dependency).
- OS-enforced release of locks on process exit avoids stale-PID complexities.
- `/tmp/` location is appropriate for transient lock files that don't require
  persistence across reboots (automatically cleaned up by system).
- System-wide lock (vs per-user) provides simpler semantics for single-instance enforcement.
- Simple to test and lightweight to implement in async context.
- Matches the project's Linux-first scope and avoids pulling cross-platform deps.

---

## Consequences

### Positive

- **POS-001**: Prevents concurrent `my-unicorn` processes from corrupting shared
  state (cache, app config, backups), reducing incidents and flakiness in CI.
- **POS-002**: No new runtime dependency — uses standard library (`fcntl`).
- **POS-003**: Fast fail-fast behaviour improves predictability for automation and scripts.
- **POS-004**: Simple semantics — OS releases lock on process exit, simplifying recovery.

### Negative

- **NEG-001**: Linux/Unix-only solution — `fcntl.flock` is not available on Windows
  (acceptable given project scope; revisit if Windows support is later required).
- **NEG-002**: Advisory locks require cooperating processes — an external process
  that ignores the lock file can still interfere.
- **NEG-003**: Flock semantics over certain filesystems (NFS) can be unreliable;
  NFS caveats must be documented and tested where applicable.
- **NEG-004**: Tests need careful mocking/fixtures for cross-process locking behaviours.

---

## Alternatives Considered

##### PID file (atomic create + PID check)

- **ALT-001**: **Description**: Create a lockfile containing the PID; guard via
  atomic create or mkdir. On start check PID and liveness, remove on exit.
- **ALT-001**: **Rejection Reason**: Correctly handling stale PID files and race
  windows is error-prone. OS does not automatically clear stale PID files when a
  process dies unexpectedly.

##### Third-party cross-platform lock library (`portalocker` / `filelock`)

- **ALT-002**: **Description**: Use a maintained library that provides cross-platform
  file locking and higher-level semantics.
- **ALT-002**: **Rejection Reason**: Adds a runtime dependency for a behaviour we can
  implement safely on Linux with the standard library. Reconsider if/when Windows
  support is required.

##### `fcntl.lockf` (POSIX record locking)

- **ALT-003**: **Description**: Use `fcntl.lockf` instead of `flock` for record-level locks.
- **ALT-003**: **Rejection Reason**: `lockf` provides different semantics (record/byte-range
  locking). For our file-level, process-wide use-case `flock` is simpler and sufficient.

##### Daemon / systemd socket or DB-backed locking

- **ALT-004**: **Description**: Use systemd sockets, a background daemon, or a shared DB
  to coordinate single instance behaviour.
- **ALT-004**: **Rejection Reason**: Heavyweight, increases operational complexity,
  not suitable for a small CLI invoked ad-hoc or in CI.

##### Do nothing

- **ALT-005**: **Description**: Keep current behaviour (no locking).
- **ALT-005**: **Rejection Reason**: Continued risk of corrupted state and flaky behaviour — not acceptable.

---

## Implementation Notes

- **IMP-001**: Add a constant `LOCKFILE_PATH: Final[Path] = Path("/tmp/my-unicorn.lock")`
  to `src/my_unicorn/constants.py`.
- **IMP-002**: Create `LockManager` async context manager in `src/my_unicorn/core/locking.py`
  that uses `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` with proper async-safe operations.
- **IMP-003**: Acquire the lock early in `src/my_unicorn/cli/runner.py` (before
  performing any state-changing work) using `async with LockManager(LOCKFILE_PATH):`.
  On failure, raise `LockError` with user-friendly message.
- **IMP-004**: Add `LockError` exception to `src/my_unicorn/exceptions.py` for lock
  acquisition failures.
- **IMP-005**: Unit tests: add tests to `tests/core/test_locking.py` covering
  (a) successful acquisition, (b) fail-fast behaviour when another FD holds lock,
  (c) release-on-exit behaviour, and (d) exception safety.
- **IMP-006**: Integration tests: add tests to `tests/cli/test_locking.py` for
  cross-process locking behavior using subprocess.
- **IMP-007**: Document `/tmp/` location behavior and that locks are advisory and Linux-only.
- **IMP-008**: Optional future enhancement — expose `--wait` / `--lock-timeout`
  to block for a configurable period.

---

## References

- **REF-001**: `src/my_unicorn/cli/runner.py` — location where lock is acquired
- **REF-002**: `src/my_unicorn/core/locking.py` — LockManager implementation
- **REF-003**: `src/my_unicorn/constants.py` — LOCKFILE_PATH constant definition
- **REF-004**: `src/my_unicorn/exceptions.py` — LockError exception
- **REF-005**: Python `fcntl.flock` docs — <https://docs.python.org/3/library/fcntl.html#fcntl.flock>
- **REF-006**: POSIX/Filesystem caveats (NFS) — <https://man7.org/linux/man-pages/man2/flock.2.html>
- **REF-007**: `/tmp/` usage for transient files — <https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s18.html>

---

<!-- Quality checklist (automated/for reviewers) -->
- [x] ADR number determined and filename follows convention
- [x] Front matter completed (status: Proposed)
- [x] Context describes problem and constraints
- [x] Decision is unambiguous and actionable
- [x] At least one positive and one negative consequence documented
- [x] Alternatives considered with rejection reasons
- [x] Implementation notes include concrete next steps and test guidance
- [x] References point to code and external docs
