# Single-Instance Architecture (CLI)

## Goal

Ensure only one `my-unicorn` process performs CLI command execution at a time, preventing concurrent state mutations and conflicting filesystem/config operations.

## Interface Boundary

- **Ingress**: CLI invocation handled by `CLIRunner.run()` in `src/my_unicorn/cli/runner.py`.
- **Concurrency gate**: `LockManager` async context manager in `src/my_unicorn/core/locking.py`.
- **Lock contract**:
    - Default lock location: `LOCKFILE_PATH` (`/tmp/my-unicorn.lock`) from `src/my_unicorn/constants.py`.
    - Runtime override: `MY_UNICORN_LOCKFILE_PATH` environment variable.
- **Failure surface**: `LockError` from `src/my_unicorn/exceptions.py`, translated into a user-facing error and process exit code `1`.

## High-Level Flow

[single-instance-cli-flow.mmd](../../diagrams/single-instance-cli-flow.mmd)

## Behavioral Contract

1. `CLIRunner` parses arguments and resolves lock file path.
2. `CLIRunner` enters `async with LockManager(lock_path)` before command routing.
3. `LockManager` attempts non-blocking exclusive file lock (`flock(LOCK_EX | LOCK_NB)`).
4. If lock acquisition succeeds, command execution proceeds in the protected section.
5. On exit (success or error), context close releases lock via file descriptor close.

### Why this matters

- **Consistency**: avoids overlapping install/update/remove operations touching the same config, cache, or AppImage paths.
- **Fail-fast UX**: second instance immediately gets a clear error instead of waiting indefinitely.
- **Operational safety**: no global daemon required; relies on OS-level advisory locking semantics.

## Failure Modes (Boundary-Visible)

- **Another process already holds the lock**
    - Observable result: CLI prints single-instance message and exits `1`.
- **Lock path open/create errors (permission, FS issues)**
    - Observable result: treated as lock acquisition failure (`LockError`), exits `1`.
- **Interrupted execution (`KeyboardInterrupt`) while lock is held**
    - Observable result: runner exits `1`; lock is released during context teardown.

## Scope and Non-Goals

### In scope

- Process-level mutual exclusion for one host.
- Serialization of CLI command execution via a lock file.

### Out of scope

- Distributed locking across multiple machines.
- Per-command lock granularity (current model is whole-runner critical section).
- Queueing/waiting behavior for second instance (current behavior is immediate fail).

## Observability and Operations Notes

- Lock location can be redirected through `MY_UNICORN_LOCKFILE_PATH` for testing/container scenarios.
- Primary user-facing signal is deterministic non-zero exit (`1`) with a concise lock message.
