---
title: "ADR-0004: Add remove --all Command"
status: "Proposed"
date: "2026-03-01"
authors: "Cyber-Syntax"
tags: ["cli", "remove", "feature"]
supersedes: ""
superseded_by: ""
---

## Status

**Proposed**

## Context

The `remove` command currently requires explicit app names as positional arguments (`apps`, `nargs="+"`). There is no way to remove all installed AppImages in a single invocation. Users who want to uninstall everything must list every app name manually, which is tedious and error-prone.

Other commands in the CLI already support bulk operations:

- `update` accepts `apps` with `nargs="*"` and treats an empty list as "update all".
- `cache clear --all` uses a `--all` flag to clear all cache entries.

Adding a `--all` flag to `remove` would bring consistency with these patterns and improve the user experience for full cleanup scenarios (e.g., before uninstalling my-unicorn itself).

Key constraints:

- **Safety**: Removing all installed AppImages is a destructive, irreversible operation. A confirmation prompt is essential.
- **Consistency**: The flag style should align with existing CLI conventions (`--all` flag pattern used by `cache clear`).
- **Argument conflict**: The current `apps` argument uses `nargs="+"` (one or more required). Adding `--all` means `apps` must become optional (`nargs="*"`) or the two must be mutually exclusive.

## Decision

Add a `--all` flag to the `remove` command using a mutually exclusive argument group, so users can either specify app names or pass `--all`, but not both. When `--all` is provided, the command will:

1. Discover all installed apps via `ConfigManager.list_installed_apps()`.
2. Display the list of apps that will be removed and prompt for confirmation (unless `--yes` / `-y` is also passed).
3. Iterate over each app and call `RemoveService.remove_app()`, respecting the existing `--keep-config` flag.

This approach was chosen because:

- It reuses the existing `list_installed_apps()` method and `RemoveService` loop pattern already present in `RemoveHandler`.
- A mutually exclusive group prevents ambiguous input (e.g., `remove appflowy --all`).
- The confirmation prompt guards against accidental bulk deletion.

## Consequences

### Positive

- **POS-001**: Users can remove all installed AppImages with a single command (`my-unicorn remove --all`), simplifying full cleanup.
- **POS-002**: Consistent with existing `--all` patterns in the CLI (e.g., `cache clear --all`), reducing cognitive load.
- **POS-003**: The `--keep-config` flag composes naturally with `--all`, allowing users to remove all AppImages while preserving configs for potential reinstallation.
- **POS-004**: Confirmation prompt prevents accidental mass removal, maintaining safety for a destructive operation.

### Negative

- **NEG-001**: Introduces a destructive bulk operation that, if confirmed carelessly, removes all managed AppImages at once.
- **NEG-002**: Changing `apps` from `nargs="+"` to `nargs="*"` requires validation logic to ensure at least one of `apps` or `--all` is provided, adding a small amount of argument-parsing complexity.
- **NEG-003**: If an individual app removal fails mid-loop, some apps will be removed and others will not, leaving the system in a partial state. Error handling strategy for partial failures must be considered.

## Alternatives Considered

### Update-style implicit all (empty args means all)

- **ALT-001**: **Description**: Make `apps` argument optional (`nargs="*"`) and treat an empty list as "remove all", matching how the `update` command works.
- **ALT-002**: **Rejection Reason**: Remove is a destructive operation unlike update. An implicit "all" behavior with no arguments is too dangerous—users could accidentally remove everything by simply running `my-unicorn remove`. An explicit `--all` flag provides a clear signal of intent.

### Separate `remove-all` subcommand

- **ALT-003**: **Description**: Add a dedicated `remove-all` subcommand instead of a flag on `remove`.
- **ALT-004**: **Rejection Reason**: This fragments the CLI surface and diverges from the existing `--all` flag convention used by `cache clear`. It also duplicates `RemoveHandler` logic unnecessarily.

### Glob/wildcard patterns

- **ALT-005**: **Description**: Support glob patterns in app names (e.g., `remove *`) to allow bulk removal.
- **ALT-006**: **Rejection Reason**: Shell glob expansion could cause unexpected behavior. It adds parsing complexity and is not consistent with how other commands handle bulk operations. The `--all` flag is simpler and more predictable.

## Implementation Notes

- **IMP-001**: Change `apps` argument in `_add_remove_command` from `nargs="+"` to `nargs="*"` and wrap `apps` and `--all` in a mutually exclusive group, or add validation in `RemoveHandler.execute()` to ensure at least one of `args.apps` or `args.all` is set.
- **IMP-002**: Add a `--yes` / `-y` flag to skip the confirmation prompt, enabling non-interactive/scripted usage (e.g., `my-unicorn remove --all --yes`).
- **IMP-003**: Use `ConfigManager.list_installed_apps()` (already exists in `config/app.py`) to discover all installed apps when `--all` is specified.
- **IMP-004**: After iterating over all apps, summarize results (e.g., "Removed 5/5 apps" or "Removed 3/5 apps, 2 failed") to give clear feedback on partial failures.
- **IMP-005**: Update shell autocomplete scripts in `autocomplete/` to include the new `--all` and `--yes` flags for the `remove` command.
- **IMP-006**: Add unit tests covering: `--all` removes all installed apps, `--all` with `--keep-config` preserves configs, `--all` with `--yes` skips confirmation, mutual exclusivity of `apps` and `--all`, and empty args without `--all` shows an error.

## References

- **REF-001**: Existing remove command parser — [src/my_unicorn/cli/parser.py](../../src/my_unicorn/cli/parser.py) (lines 324-352)
- **REF-002**: Remove command handler — [src/my_unicorn/cli/commands/remove.py](../../src/my_unicorn/cli/commands/remove.py)
- **REF-003**: RemoveService — [src/my_unicorn/core/remove.py](../../src/my_unicorn/core/remove.py)
- **REF-004**: `list_installed_apps()` — [src/my_unicorn/config/app.py](../../src/my_unicorn/config/app.py) (line 153)
- **REF-005**: `--all` flag precedent — `cache clear --all` in [src/my_unicorn/cli/parser.py](../../src/my_unicorn/cli/parser.py) (line 534)
