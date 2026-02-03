# AGENTS.md

## General Guidelines

- **KISS** (Keep It Simple, Stupid): Aim for simplicity and clarity. Avoid unnecessary abstractions or metaprogramming.
- **DRY** (Don't Repeat Yourself): Reuse code appropriately but avoid over-engineering. Each command handler has single responsibility.
- **YAGNI** (You Aren't Gonna Need It): Always implement things when you actually need them, never when you just foresee that you need them.
- ALWAYS run `ruff check --fix <filepath>` and `ruff format <filepath>` on each Python file you modify.
- Use a subagent to avoid context-limit issues when reading modules.

## Project Overview

My Unicorn is a Python 3.12+ CLI tool for managing AppImages on Linux. It installs, updates, and verifies AppImages from GitHub with hash verification (SHA256/SHA512).

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
    - `core/` - Core functionality and integrations
        - `auth.py` - Authentication handling
        - `cache.py` - Release cache management
        - `desktop_entry.py` - Desktop file generation
        - `download.py` - File download logic
        - `file_ops.py` - File system operations
        - `http_session.py` - HTTP session management
        - `icon.py` - Icon extraction and management
        - `remove.py` - Remove operations
        - `token.py` - Token storage and retrieval
        - `github/` - GitHub API client
        - `verification/` - Hash verification logic
        - `workflows/` - Business workflows (install, update, remove)
    - `ui/` - User interface and display
        - `progress.py` - Progress bar management
        - `display.py` - Output formatting and rendering
        - `formatters.py` - Text formatters
    - `utils/` - Utility functions and helpers
    - `constants.py` - Application constants (versions, paths, defaults)
    - `types.py` - Type definitions and dataclasses
    - `exceptions.py` - Custom exception classes
    - `logger.py` - Logging setup and configuration
    - `main.py` - Application entry point
- `tests/` - Comprehensive test suite (same structure as src/my_unicorn/)
- `docs/` - Documentation and design decisions
- `scripts/` - Helper scripts for development

## Development Workflow

### Running the CLI

```bash
# Run via uv
uv run my-unicorn <command> [options]

# Examples
uv run my-unicorn catalog
uv run my-unicorn install qownnotes
uv run my-unicorn update
```

### Making Code Changes

1. Make your changes to files in `src/my_unicorn/`
2. Run linting: `ruff check --fix <filepath>`
3. Run formatting: `ruff format <filepath>`
4. Run tests: `uv run pytest` (see Testing Instructions below)
5. Verify CLI still works: `uv run my-unicorn --help`
6. Verify ui still work as expected: `uv run scripts/test.py --quick`

### Adding New Dependencies

```bash
# Add a dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Update all dependencies
uv lock --upgrade
```

## Testing Instructions

Critical: Run tests after any change on cli code to ensure nothing breaks.

- Run the full suite (≈995 tests): `uv run pytest`
- Focused runs:
    - File: `uv run pytest tests/test_backup.py`
    - Marker filtering: `uv run pytest -m "not slow"` (skips slow tests, keeps fast integration tests)
    - Full marker filtering: `uv run pytest -m "not slow and not integration"` (skips all integration tests)
    - Single test: `uv run pytest tests/test_backup.py::test_restore_doesnt_delete_restore_target`
- Coverage examples:
    - `uv run pytest --cov=my_unicorn`
    - `uv run pytest --cov=my_unicorn.commands.migrate tests/migration/test_migrate_command.py`

Note: The `slow` marker is applied to performance-heavy tests (e.g., 10MB log file rotation). Integration tests in `tests/integration/` are marked with `integration` but may not be slow—use `-m "not slow"` for quick runs that include fast integration tests. Skip integration tests entirely if changes don't affect config, upgrade, or cross-component interactions.

## Code Style Guidelines

### Python Conventions

- Use built-in types: `list[str]`, `dict[str, int]` (not typing.List, typing.Dict)
- Use `%s` style formatting in logging statements
- Use `logger.exception("message")` for stack traces
- Follow PEP 8 standards (enforced by ruff)
- Use `astimezone()` for local time in datetime operations

### Linting and Formatting

ALWAYS run ruff on each Python file you modify:

```bash
# Check and auto-fix linting errors
ruff check --fix <filepath>

# Format a specific file
ruff format path/to/file.py

# Format all files in a directory
ruff format path/to/code/

# Format all files in current directory
ruff format .
```

### File Organization

- One class per file (generally)
- Group related functionality in modules
- Keep files focused and under 500 lines.
- Use `__init__.py` for public API exports

## Build and Deployment

### Running Locally (Development)

```bash
# Run from source without installation
uv run my-unicorn <command>
```

### Installation Methods

```bash
# Install from GitHub (main branch, for production use)
uv tool install git+https://github.com/Cyber-Syntax/my-unicorn
./install.sh -i

# Upgrade to latest from GitHub
my-unicorn upgrade
uv tool install --upgrade git+https://github.com/Cyber-Syntax/my-unicorn
```

## Review Checklist

- [ ] Code follows KISS, DRY, and YAGNI principles
- [ ] All tests pass (`uv run pytest`)
- [ ] Code is formatted (`ruff format`)
- [ ] No linting errors (`ruff check`)
- [ ] No unnecessary dependencies added
- [ ] Exception handling follows Ruff guidelines (TRY003, TRY301)
- [ ] No assert statements used (S100)

## Project-Specific Notes

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

### AppImage Management

- AppImages are downloaded to user-specified directory
- Desktop entries are created in `~/.local/share/applications/`
- Icons are extracted from AppImages and stored to user-specified directory
    - Default `~/Applications` for appimages, backups, and icons
- Hash verification (SHA256/SHA512) is performed on available assets

### GitHub API Interaction

- All GitHub API calls go through `core/github/`
- Release data is cached in `core/cache.py` to reduce API calls
- Cache invalidation happens on update commands
- Asset filtering removes non-Linux assets to reduce cache size
- Authentication tokens stored securely via `core/token.py` using system keyring
- Authentication is implemented via `core/auth.py` module

### Configuration Migration

- Migrations are detected and notified on startup
- Backups are created in `~/.config/my-unicorn/apps/backups/`
- Migration logic is in `config/migration/` directory
    - `global_config.py` - Global INI config migrations
    - `app_config.py` - Per-app JSON config migrations
- Always bump VERSION constants in `constants.py` when changing config schema
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
