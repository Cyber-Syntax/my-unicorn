---
title: "ADR-0006: Hardcode Console Log Level to INFO"
status: "Proposed"
date: "2026-03-01"
authors: "Cyber-Syntax"
tags: ["logging", "configuration", "simplification"]
supersedes: ""
superseded_by: ""
---

## Status

**Proposed**

## Context

The global configuration (`settings.conf`) currently exposes a `console_log_level` setting that lets users change the console output verbosity. This option is defined across multiple layers:

- **Schema**: `global_config_v1.schema.json` lists `console_log_level` as a required field with an enum of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- **Constants**: `DEFAULT_CONSOLE_LOG_LEVEL = "INFO"` in `constants.py`, with a dedicated key constant `KEY_CONSOLE_LOG_LEVEL`.
- **Types**: `GlobalConfig` TypedDict includes `console_log_level: str`.
- **Config manager**: `config/global.py` reads, writes, and defaults `console_log_level`.
- **Logger config**: `logger/config.py` applies `console_log_level` from config to the console handler at runtime via `update_logger_from_config()`.
- **Config comments/parser**: `config/parser.py` documents the option with inline comments.

In practice, the console log level should always be `INFO` for normal usage. The CLI already provides `--verbose` flags on `install` and `update` commands that temporarily set the console handler to `DEBUG` for that invocation. Allowing users to permanently change the console level via config creates problems:

1. **User confusion**: Setting `console_log_level = DEBUG` floods the terminal with internal details. Setting it to `WARNING` or higher hides normal operational messages (install progress, update results) that the user expects to see.
2. **Support burden**: Unusual console levels make troubleshooting harder—output shared in bug reports may be incomplete or noisy depending on the user's config.
3. **Redundancy**: The `--verbose` flag already covers the legitimate use case of seeing more detail for a specific command invocation.
4. **File log level is sufficient**: The `log_level` setting (file log level) remains user-configurable for deeper diagnostics, written to `~/.config/my-unicorn/logs/my-unicorn.log`.

## Decision

Remove `console_log_level` from the user-facing configuration and hardcode it to `INFO` internally. Specifically:

1. **Remove `console_log_level`** from `settings.conf` defaults, the JSON schema, the `GlobalConfig` TypedDict, and the config read/write logic.
2. **Hardcode `INFO`** as the console handler level in `logger/config.py` (the `update_logger_from_config()` function), ignoring any lingering config value.
3. **Keep the `--verbose` CLI flag** as the mechanism for per-invocation `DEBUG` console output—no behavioral change there.
4. **Keep `log_level`** (file log level) as a user-configurable option for diagnostic file logging.
5. **Handle migration**: Existing `settings.conf` files that contain `console_log_level` should have the key silently ignored or stripped during the next config migration. Bump `GLOBAL_CONFIG_VERSION` to reflect the schema change.

This approach was chosen because:

- It simplifies the configuration surface by removing an option that has no safe alternative value for normal use.
- It preserves the `--verbose` escape hatch for when users genuinely need debug output.
- The file log level remains configurable for persistent diagnostic needs.

## Main issue

Verbose flag not work as expected;

```bash
uv run my-unicorn update --verbose appflowy

📦 Update Summary:
--------------------------------------------------
appflowy                  ℹ️  Already up to date (0.11.3)

ℹ️  1 app(s) already up to date
```

As you can see, there is no additional debug information in the output when using `--verbose`. This may be due to the fact that the `console_log_level` is set to `INFO` in the config, and the `--verbose` flag is not properly overriding it to `DEBUG` for that invocation.

- We need to ensure that the verbose flag correctly sets the console log level to debug after the console_log_level is removed from the config and hardcoded to INFO. We must write a test to verify that the `--verbose` flag still works as intended after the change, both unit test and e2e test.

- We can use qownnotes on e2e test and use onyl --check-only flag to check both flags work as expected without actually performing the update/install.

## Consequences

### Positive

- **POS-001**: Users cannot accidentally misconfigure console output (e.g., setting `WARNING` and losing all progress/status messages, or setting `DEBUG` and flooding the terminal).
- **POS-002**: Reduces configuration surface area—one fewer setting to document, validate, and maintain across schema, types, and config manager.
- **POS-003**: Bug reports will consistently contain `INFO`-level console output, simplifying troubleshooting.
- **POS-004**: Eliminates the `DEFAULT_CONSOLE_LOG_LEVEL` constant, `KEY_CONSOLE_LOG_LEVEL` constant, and related code paths, reducing codebase complexity.

### Negative

- **NEG-001**: Power users who currently set `console_log_level = WARNING` to suppress output lose that ability. They would need to redirect stdout/stderr instead.
- **NEG-002**: Requires a config schema version bump and migration logic to remove the key from existing `settings.conf` files.
- **NEG-003**: The `LOG_LEVEL` environment variable override used in testing may need adjustment if it currently also controls console level in test runs.

## Alternatives Considered

### Keep console_log_level but restrict its values

- **ALT-001**: **Description**: Limit the enum to only `INFO` and `DEBUG`, preventing users from setting it to `WARNING` or higher which hides operational output.
- **ALT-002**: **Rejection Reason**: This still allows `DEBUG` permanently via config, which floods the terminal and is already covered by `--verbose`. If the only valid permanent value is `INFO`, the option serves no purpose.

### Add validation warnings instead of removing

- **ALT-003**: **Description**: Keep the option but emit a warning when the user sets it to anything other than `INFO`, explaining potential issues.
- **ALT-004**: **Rejection Reason**: Warnings add noise without solving the problem. Users who intentionally set a non-`INFO` level would be annoyed by the warning, and users who set it accidentally would still experience the broken behavior before reading the warning.

### Move to a CLI-only --quiet flag

- **ALT-005**: **Description**: Replace `console_log_level` with a `--quiet` CLI flag that sets console level to `WARNING` for a single invocation, mirroring how `--verbose` works.
- **ALT-006**: **Rejection Reason**: This could be implemented later as an additive improvement, but the primary goal of this ADR is to remove the persistent config option. A `--quiet` flag could be a follow-up feature if demand arises.

## Implementation Notes

- **IMP-001**: Remove `console_log_level` from the `required` array and `properties` in `config/schemas/global_config_v1.schema.json` (or create a v1.2.0 schema).
- **IMP-002**: Remove `console_log_level: str` from the `GlobalConfig` TypedDict in `types.py`.
- **IMP-003**: Remove `KEY_CONSOLE_LOG_LEVEL` and `DEFAULT_CONSOLE_LOG_LEVEL` from `constants.py`.
- **IMP-004**: Update `config/global.py` to stop reading/writing `console_log_level` in `get_default_global_config()`, `_write_config()`, and `_convert_to_global_config()`.
- **IMP-005**: In `logger/config.py`, hardcode `console_level = logging.INFO` in `update_logger_from_config()` instead of reading from config.
- **IMP-006**: Add config migration logic in `config/migration/global_config.py` to strip `console_log_level` from existing `settings.conf` files and bump `GLOBAL_CONFIG_VERSION` from `"1.1.0"` to `"1.2.0"`.
- **IMP-007**: Update config comment templates in `config/parser.py` to remove the `console_log_level` inline comment.
- **IMP-008**: Update tests that reference `console_log_level` in config fixtures or assertions.

## References

- **REF-001**: Global config schema — [src/my_unicorn/config/schemas/global_config_v1.schema.json](../../src/my_unicorn/config/schemas/global_config_v1.schema.json)
- **REF-002**: GlobalConfig TypedDict — [src/my_unicorn/types.py](../../src/my_unicorn/types.py#L132-L143)
- **REF-003**: Console log level constants — [src/my_unicorn/constants.py](../../src/my_unicorn/constants.py#L51-L65)
- **REF-004**: Logger config applying console level — [src/my_unicorn/logger/config.py](../../src/my_unicorn/logger/config.py#L110-L125)
- **REF-005**: Config manager read/write — [src/my_unicorn/config/global.py](../../src/my_unicorn/config/global.py#L160-L283)
- **REF-006**: Verbose flag in runner — [src/my_unicorn/cli/runner.py](../../src/my_unicorn/cli/runner.py#L231-L251)
