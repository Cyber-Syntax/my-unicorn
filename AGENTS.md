# AGENTS.md

This document provides context, patterns, and guidelines for AI coding assistants working in this repository.

## Project Overview

My Unicorn is a Python 3.12+ CLI tool for managing AppImages on Linux
**Core Features**: Install, update, and verify AppImages from GitHub with hash verification (SHA256/SHA512)
**Package Manager**: uv (replaces pip/poetry)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/Cyber-Syntax/my-unicorn
cd my-unicorn

# Install dependencies (uv creates virtual environment automatically)
uv sync

# Run CLI from source
uv run my-unicorn --help

# Run fast tests (excludes slow logger integration tests)
uv run pytest -m "not slow"

# Run all tests
uv run pytest
```

## Core Technologies

- **Python**: 3.12+ with asyncio/aiohttp for async operations
- **HTTP Client**: aiohttp for GitHub API interactions
- **JSON**: orjson for fast config/cache file handling
- **Event Loop**: uvloop for performance
- **Security**: keyring for secure GitHub token storage
- **Testing**: pytest with pytest-asyncio, pytest-mock, pytest-cov
- **Linting**: ruff (linter + formatter)
- **Type Checking**: mypy

## Repository Structure

```
src/my_unicorn/
├── main.py                 # Application entry point
├── types.py                # Type definitions and dataclasses
├── constants.py            # Application constants (versions, paths, defaults)
├── exceptions.py           # Custom exception classes
├── logger.py               # Logging setup and configuration
├── catalog/                # Application catalog JSON files
├── cli/                    # CLI parsing and command execution
│   ├── parser.py           # Argument parser setup
│   ├── runner.py           # Command execution orchestration
│   └── commands/           # Command handlers (install, update, remove, list)
├── config/                 # Configuration management
│   ├── global.py           # Global INI configuration
│   ├── app.py              # Per-app JSON configuration
│   ├── catalog.py          # Application catalog loader
│   ├── schemas/            # JSON schema validation
│   └── migration/          # Config migration logic (v1→v2)
├── core/                   # Core functionality
│   ├── auth.py             # Authentication handling
│   ├── token.py            # Token storage via keyring
│   ├── cache.py            # Release cache management
│   ├── http_session.py     # HTTP session management
│   ├── download.py         # File download logic
│   ├── icon.py             # Icon extraction
│   ├── desktop_entry.py    # Desktop file generation
│   ├── github/             # GitHub API client
│   ├── verification/       # Hash verification (SHA256/SHA512)
│   └── workflows/          # Business workflows (install, update, remove)
├── ui/                     # User interface
│   ├── progress.py         # Progress bar management
│   └── display.py          # Output formatting
└── utils/                  # Utility functions

tests/                      # Test suite (mirrors src structure)
├── conftest.py             # Pytest fixtures and configuration
├── integration/            # Integration tests (network calls allowed)
├── test_*.py               # Unit tests (no network calls)
└── [subdirs mirror src/my_unicorn structure]

docs/                       # Technical documentation
└── dev/                    # Development guides (architecture, adr records)

scripts/                    # Helper scripts
├── test.py                 # UI testing script
├── autocomplete.bash       # Shell autocomplete setup
└── update.bash             # Self-update script

autocomplete/               # Shell autocomplete scripts (bash, zsh)
container/                  # Container configuration (Dockerfile, podman-compose.yml)
```

## Development Workflow

### Common Development Tasks

#### Running the CLI

```bash
# Run from source without installation
uv run my-unicorn <command> [options]

# Examples
uv run my-unicorn install qownnotes
uv run my-unicorn update qownnotes --refresh-cache
uv run my-unicorn update --all --refresh-cache
uv run my-unicorn --help # for more command examples
```

#### Making Code Changes

**CRITICAL**: Always run ruff on modified files before committing.

```bash
# 1. Make your changes to files in src/my_unicorn/

# 2. Run linting (auto-fix issues)
ruff check --fix path/to/file.py
ruff check --fix . # or all Python files

# 3. Run formatting
ruff format path/to/file.py
ruff format . # or all Python files

# 4. Run type checking
uv run mypy src/my_unicorn/

# 5. Run fast tests (excludes slow logger tests)
uv run pytest -m "not slow"

# 6. Verify CLI still works
uv run my-unicorn --help

# 7. Test UI behavior (quick smoke test)
uv run scripts/test.py --quick
```

### Managing Dependencies

```bash
# Add a runtime dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Update all dependencies
uv lock --upgrade

# Sync dependencies after pulling changes
uv sync

# Remove a dependency
uv remove <package-name>
```

## Code Quality Standards

### Type Hints

CRITICAL: All Python code MUST include type hints and return types.

```python
# CORRECT
def filter_unknown_users(users: list[str], known_users: set[str]) -> list[str]:
    """Filter out users that are not in the known users set.

    Args:
        users: List of user identifiers to filter.
        known_users: Set of known/valid user identifiers.

    Returns:
        List of users that are not in the `known_users` set.
    """
    return [u for u in users if u not in known_users]

# INCORRECT (no type hints)
def filter_unknown_users(users, known_users):
    return [u for u in users if u not in known_users]
```

- **Type Annotations**: Use built-in types: `list[str]`, `dict[str, int]` (not `typing.List`, `typing.Dict`)

### Coding Standards

- **Logging Format**: Use `%s` style formatting in logging statements: `logger.info("User %s logged in", username)`
- **PEP 8**: Enforced by ruff
- **Datetime**: Use `astimezone()` for local time conversions
- **Variable Names**: Use descriptive, self-explanatory names
- **Function Size**: Keep functions focused (<20 lines when possible)
- **Error Handling**: Use custom exceptions from `exceptions.py`
- **Async Safe**:
    - All I/O operations must have async variants
    - Never block the event loop with sync I/O in async context
- **DRY Approach**:
    - Reuse existing abstractions; don't duplicate
    - Refactor safely when duplication is found
    - Check existing protocols before creating new ones

### Error Handling Guidelines

```python
# CORRECT - Use custom exceptions
from my_unicorn.exceptions import NetworkError, VerificationError

if not hash_matches:
    raise VerificationError(f"Hash mismatch for {filename}")

# CORRECT - Handle expected errors gracefully (no exception logging)
try:
    response = await session.get(url)
except aiohttp.ClientError as e:
    logger.warning("Network request failed: %s", e)
    return None

# INCORRECT - Don't use logger.exception() for expected errors
try:
    response = await session.get(url)
except aiohttp.ClientError as e:
    logger.exception("Network error")  # Leaks stack trace unnecessarily

# INCORRECT - Don't log tokens or sensitive data
logger.debug("Token: %s", token)  # Security risk!
```

### File Organization

**Target**: Keep files between 150-500 lines

```bash
# Check file line counts
uv run pytest tests/test_lines.py -v

# If tests fail, refactor large files:
# 1. Find natural split points (don't force arbitrary divisions)
# 2. Extract related functionality into new modules
# 3. Re-run tests until they pass
```

## Testing Instructions

### Writing Tests

**CRITICAL**: Every new feature or bugfix MUST be covered by unit tests.

```python
# Example test structure
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from my_unicorn.core.workflows import InstallWorkflow
from my_unicorn.exceptions import VerificationError


@pytest.mark.asyncio
async def test_install_workflow_success(tmp_path, mock_session):
    """Test successful installation workflow."""
    # Arrange
    workflow = InstallWorkflow(...)

    # Act
    result = await workflow.execute()

    # Assert
    assert result.success is True
    assert result.app_name == "test-app"


def test_hash_verification_failure():
    """Test that verification fails with incorrect hash."""
    # Arrange
    expected_hash = "abc123"
    actual_hash = "def456"

    # Act & Assert
    with pytest.raises(VerificationError):
        verify_hash(actual_hash, expected_hash)
```

### Running Tests

```bash
# Run fast tests only (excludes slow logger integration tests)
uv run pytest -m "not slow"

# Run all tests (including slow tests)
uv run pytest

# Run tests with coverage
uv run pytest --cov=my_unicorn --cov-report=html

# Run specific test file
uv run pytest tests/test_install.py

# Run specific test function
uv run pytest tests/test_install.py::test_install_success
```

### Test Checklist

Before committing, verify:

- [ ] Tests fail when your new logic is broken
- [ ] Happy path is covered
- [ ] Edge cases and error conditions are tested
- [ ] External dependencies are mocked (no real network calls in unit tests)
- [ ] Tests are deterministic (no flaky tests)
- [ ] **Async-safe**: Support async/await patterns
- [ ] Async tests use `@pytest.mark.asyncio`
- [ ] Test names clearly describe what they test

## Debugging and Troubleshooting

### Common Issues and Solutions

#### Linting/Formatting Issues

```bash
# Problem: Ruff errors that can't be auto-fixed
# Solution: Review ruff output and fix manually
ruff check path/to/file.py

# Problem: Type checking errors
# Solution: Run mypy with verbose output
uv run mypy --show-error-codes src/my_unicorn/

# Common type error fixes:
# - Update type hints to match actual usage
# - Check for missing return type annotations
# - Ensure correct use of built-in types (list[str], dict[str, int], etc.)
```

### Debugging Tips

#### Gather Runtime Information

```bash
# Check log file
tail -f ~/.config/my-unicorn/logs/my-unicorn.log

# Check app state config
cat ~/.config/my-unicorn/apps/<app-name>.json

# Check cache file
cat ~/.config/my-unicorn/cache/releases/<owner_repo>.json

# View global config
cat ~/.config/my-unicorn/settings.conf
```

## Project-Specific Notes

### Configuration Structure

- Configuration stored in `~/.config/my-unicorn/`:
    - `settings.conf` - Global configuration file (GLOBAL_CONFIG_VERSION="1.1.0")
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
    - `GLOBAL_CONFIG_VERSION` - Currently "1.1.0"
    - `APP_CONFIG_VERSION` - Currently "2.0.0"

### 8.3 Documentation Principles

| Principle | Description |
|-----------|-------------|
| **Beginner-friendly** | Non-developers should understand core concepts |
| **Copy-paste success** | Code examples must run with minimal setup |
| **Less text, more interaction** | Prefer components over long paragraphs |
| **Show, don't tell** | Use diagrams, tabs, and accordions to explain |
| **Few lines, big impact** | Examples should feel like "only 3 lines to do this" |

## Additional Resources

- **Documentation:** See `docs/` directory for detailed design decisions, architecture diagrams, and API documentation
- **Scripts:** Helper scripts in `scripts/` for development tasks
- **Architecture Decision Records:** `docs/adr/` for major technical decisions
- **Development Guides:** `docs/dev/` for in-depth development patterns and best practices
