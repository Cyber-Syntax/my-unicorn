# AGENTS.md

## General Guidelines

- KISS (Keep It Simple, Stupid): Aim for simplicity and clarity. Avoid unnecessary abstractions or metaprogramming.
- DRY (Don't Repeat Yourself): Reuse code appropriately but avoid over-engineering. Each command handler has single responsibility.
- YAGNI (You Aren't Gonna Need It): Always implement things when you actually need them, never when you just foresee that you need them.
- ALWAYS use `ruff check <filepath>` on each Python file you modify to ensure proper linting and formatting:
    - Use `ruff check --fix <filepath>` to automatically fix any fixable errors.
    - Use `ruff format path/to/file.py` to format a specific file.
    - Use `ruff format path/to/code/` to format all files in `path/to/code` (and any subdirectories).
    - Use `ruff format` to format all files in the current directory.

## Testing Instructions

Critical: Run tests after any change to ensure nothing breaks.

- Run the full suite (≈995 tests): `uv run pytest`
- Focused runs:
    - File: `uv run pytest tests/test_backup.py`
    - Marker filtering: `uv run pytest -m "not slow and not integration"`
    - Single test: `uv run pytest tests/test_backup.py::test_restore_doesnt_delete_restore_target`
- Coverage examples:
    - `uv run pytest --cov=my_unicorn`
    - `uv run pytest --cov=my_unicorn.commands.migrate tests/migration/test_migrate_command.py`

## Code Style Guidelines

- Use built-in types: `list[str]`, `dict[str, int]`
- Use `%s` style formatting in logging statements
- Use `logger.exception("message")` for stack traces

## Project Overview

My Unicorn is a Python 3.12+ CLI tool for managing AppImages on Linux. It installs, updates, and verifies AppImages from GitHub with hash verification (SHA256/SHA512).

### Configuration Structure

- Configuration stored in `~/.config/my-unicorn/`:
    - `settings.conf` - Global configuration file (GLOBAL_CONFIG_VERSION="1.0.2")
    - `cache/releases/` - Cache files, filtered for AppImage/checksums only (Windows, mac removed)
        - `AppFlowy-IO_AppFlowy.json` - AppFlowy cache config
        - `zen-browser_desktop.json` - Zen Browser cache config
    - `logs/` - Log files for my-unicorn
    - `apps/` - AppImages state data folder (APP_CONFIG_VERSION="2.0.0")
        - `appflowy.json` - AppFlowy app config
        - `zen-browser.json` - Zen Browser app config
        - `backups/` - Config backups created during migration

### Key Technologies

- **Python 3.12+** with asyncio/aiohttp for async operations
- **uv** - Fast Python package installer and resolver
- **aiohttp** - Async HTTP client for GitHub API interactions
- **orjson** - Fast JSON library for config and cache files
- **uvloop** - Fast asyncio event loop
- **keyring** - Secure credential storage for GitHub tokens
- **pytest** - Testing framework with pytest-asyncio and pytest-mock
- **ruff** - Fast Python linter and formatter

### Architecture

- `src/my_unicorn/` - Main package source code
    - `catalog/` - Application catalog JSON files
    - `cli/` - CLI argument parsing and command runners
        - `commands/` - Individual command handlers (install, update, remove, list, etc.)
        - `parser.py` - Argument parser setup
        - `runner.py` - Command execution orchestration
    - `config/` - Configuration management
        - `global.py` - Global INI configuration
        - `app.py` - Per-app JSON configuration
        - `catalog.py` - Application catalog loader
        - `migration/` - Configuration migration logic
        - `schemas/` - JSON schema validation
    - `domain/` - Domain models and business logic
        - `asset.py` - AppImage asset handling
        - `release.py` - Release information
        - `verification/` - Hash verification logic
        - `constants.py` - Application constants (versions, paths, defaults)
        - `types.py` - Type definitions and dataclasses
    - `infrastructure/` - External integrations and I/O
        - `github/` - GitHub API client
        - `cache.py` - Release cache management
        - `download.py` - File download logic
        - `desktop_entry.py` - Desktop file generation
        - `icon.py` - Icon extraction and management
        - `file_ops.py` - File system operations
        - `auth.py` - Authentication handling
        - `token.py` - Token storage and retrieval
    - `ui/` - User interface and display
        - `progress.py` - Progress bar management
        - `display.py` - Output formatting and rendering
        - `formatters.py` - Text formatters
    - `utils/` - Utility functions and helpers
    - `workflows/` - Business workflows (use cases)
        - `install.py` - Install workflow
        - `update.py` - Update workflow
        - `remove.py` - Remove workflow
        - `services/` - Workflow helper services
    - `exceptions.py` - Custom exception classes
    - `logger.py` - Logging setup and configuration
    - `main.py` - Application entry point
- `tests/` - Comprehensive test suite(Same structure as src/my_unicorn/)
    - `cli/` - CLI tests
    - `commands/` - Command handler tests
    - `integration/` - Integration tests
    - `migration/` - Migration tests
    - `services/` - Service tests
    - `schemas/` - Schema validation tests
- `docs/` - Documentation and design decisions
- `scripts/` - Helper scripts for development

## Review Checklist

- [ ] Code follows KISS, DRY, and YAGNI principles
- [ ] All tests pass (`uv run pytest`)
- [ ] Code is formatted (`ruff format`)
- [ ] No linting errors (`ruff check`)
- [ ] No unnecessary dependencies added

## Project-Specific Notes

### AppImage Management

- AppImages are downloaded to user-specified directory
- Desktop entries are created in `~/.local/share/applications/`
- Icons are extracted from AppImages and stored to user-specified directory
- Hash verification (SHA256/SHA512) is required for security

### GitHub API Interaction

- All GitHub API calls go through `infrastructure/github/`
- Release data is cached in `infrastructure/cache.py` to reduce API calls
- Cache invalidation happens on update commands
- Asset filtering removes non-Linux assets to reduce cache size
- Authentication tokens stored securely via `infrastructure/token.py` using system keyring
- Authentication is implemented via `infrastructure/auth.py` module

### Configuration Migration

- Migrations are automatic on first run after upgrade
- Backups are created in `~/.config/my-unicorn/apps/backups/`
- Migration logic is in `config/migration/` directory
    - `global_config.py` - Global INI config migrations
    - `app_config.py` - Per-app JSON config migrations
- Always bump VERSION constants in `domain/constants.py` when changing config schema
    - `GLOBAL_CONFIG_VERSION` - Currently "1.0.2"
    - `APP_CONFIG_VERSION` - Currently "2.0.0"

### Error Handling

- Use custom exceptions from `exceptions.py`
- Always log exceptions with `logger.exception()` unless if it is token-related.
- Do not use `logger.exception()` for expected errors (e.g., network issues, invalid user input) and secure data (e.g., tokens) to avoid leaking sensitive information.
- Handle network errors gracefully with retries

## Additional Resources

- **Documentation:** See `docs/` directory for detailed design decisions
- **Scripts:** Helper scripts in `scripts/` for development tasks
