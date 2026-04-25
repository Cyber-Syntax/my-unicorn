---
title: "ADR-0008: Simplicity-First CLI Rewrite"
status: "Proposed"
date: "2026-04-24"
authors: "Project Maintainer (Solo Developer)"
tags: ["architecture", "decision", "cli", "rewrite"]
supersedes: ""
superseded_by: ""
---

## Status

**Proposed**

## Context

My Unicorn is a Linux CLI for installing, updating, verifying, and removing
AppImages from GitHub releases. The current implementation is functionally
successful, but has accumulated high abstraction density in command execution
and service orchestration. In practice, protocol-heavy indirection, layered
wiring, and duplicated orchestration logic make debugging and change delivery
slower than required.

The rewrite initiative prioritizes simplicity, reliability, and maintainability
while preserving user value: trustworthy AppImage lifecycle management with
hash verification, cache reuse, backups, and clear command output. The project
must remain Linux-focused, Python 3.12+ compatible, async-safe, and secure with
keyring-based token handling.

The decision is constrained by migration safety requirements. Existing users
must be protected through backup-first migration behavior and recoverable state
transitions. Backward compatibility is desirable where practical, but migration
correctness and long-term maintainability take precedence.

Primary stakeholders are desktop Linux users, automation users, catalog
contributors, and the project maintainer responsible for operating and evolving
the codebase.

## Decision

Adopt a full, simplicity-first rewrite of the command and core orchestration
layers using a direct command-to-use-case model.

The new architecture will:

- Keep one primary orchestration flow per command with explicit input/output
  contracts.
- Remove non-essential protocol and dependency-injection layers that only add
  indirection without improving behavior.
- Preserve core workflows (install, update, verify, remove, cache, backup,
  migration, token management) with deterministic and testable flow control.
- Retain user-facing command semantics where practical, but allow selective
  behavior cleanup when needed to reduce technical debt.
- Enforce quality gates (ruff, mypy, async-safe tests, command smoke checks)
  as release criteria.

This option is selected because it best balances reliability goals,
maintainability, and contributor velocity, while directly addressing structural
causes of current complexity.

## Consequences

### Positive

- **POS-001**: End-to-end command flow becomes easier to trace, reducing time
to diagnose install/update regressions.
- **POS-002**: Lower indirection improves maintainability and reduces routine
bug-fix cycle time.
- **POS-003**: Explicit orchestration contracts improve testability,
particularly for batch operations and partial-failure scenarios.
- **POS-004**: Migration-first safety model reduces risk of user data loss
during schema evolution.
- **POS-005**: Consistent phase-based CLI output improves usability for both
interactive and automation workflows.

### Negative

- **NEG-001**: Rewrite work introduces short-term delivery risk and may delay
feature throughput while migration is in progress.
- **NEG-002**: Behavioral parity is not guaranteed for every legacy edge case,
which can surface transition issues for existing users.
- **NEG-003**: Temporary duplication of logic may be required during phased
cutover and validation.
- **NEG-004**: Expanded migration and verification coverage increases initial
implementation scope and test burden.
- **NEG-005**: Team knowledge concentration risk remains high because execution
is led by a single maintainer.

## Alternatives Considered

### Incremental Refactor of Existing Architecture

- **ALT-001**: **Description**: Keep current layered architecture and gradually
remove abstractions over multiple iterations.
- **ALT-002**: **Rejection Reason**: Repeated partial refactors have not reduced
complexity enough; structural indirection remains a persistent source of cost.

### Maintain Current Architecture and Apply Bugfix-Only Strategy

- **ALT-003**: **Description**: Avoid rewrite and limit changes to defect fixes
and minor enhancements.
- **ALT-004**: **Rejection Reason**: Does not address root architectural debt
and conflicts with maintainability, velocity, and reliability targets.

### Full Rewrite with Strict Legacy Compatibility Layer

- **ALT-005**: **Description**: Rewrite internals but preserve all existing
internal extension points and compatibility shims.
- **ALT-006**: **Rejection Reason**: Preserving legacy indirection undermines
simplicity goals and retains a high long-term maintenance burden.

### Do Nothing

- **ALT-007**: **Description**: Continue operating as-is with no structural
change.
- **ALT-008**: **Rejection Reason**: Incompatible with documented goals and
expected quality metrics in reliability, contributor velocity, and debugging
time.

## Implementation Notes

- **IMP-001**: Implement in phases: architecture baseline, core workflow
rewrite, config/migration/auth hardening, then stabilization and release
readiness.
- **IMP-002**: Define explicit command flow modules with bounded size and clear
contracts; keep orchestration modules concise and directly testable.
- **IMP-003**: Add migration command behavior with backup-before-change,
validation-after-change, and recovery guidance on failure.
- **IMP-004**: Enforce CI quality gates for lint, format, type checks, and test
coverage before release.
- **IMP-005**: Track success metrics from the PRD (failure rate, latency,
maintainer throughput) during rollout to validate architectural outcomes.

## References

- **REF-001**: Product requirements source: `prd.md`
- **REF-002**: Related decision record: `docs/adr/ADR-003-Project-Phoenix-Architecture.md`
- **REF-003**: Related decision record: `docs/adr/adr-0007-integrity-checks-and-export-for-reinstallation.md`
- **REF-004**: Related decision record: `docs/adr/adr-0006-hardcode-console-log-level.md`
- **REF-005**: Project-wide architecture and workflow guidance: `AGENTS.md`
