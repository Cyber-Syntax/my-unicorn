# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## General Guidelines

1. KISS (Keep It Simple, Stupid): Aim for simplicity and clarity. Avoid unnecessary abstractions or metaprogramming.
2. DRY (Don't Repeat Yourself): Reuse code appropriately but avoid over-engineering. Each command handler has single responsibility.
3. YAGNI (You Aren't Gonna Need It): Always implement things when you actually need them, never when you just foresee that you need them.
4. **ALWAYS** use `ruff check <filepath>` on each python file you modify to ensure proper formatting and linting.
    - Use `ruff format <filepath>` on each python file you modify to ensure proper formatting.
    - Use `ruff check --fix <filepath>` on each python file you modify to fix any fixable errors.

## Testing Instructions

Critical: Run tests after any change to ensure nothing breaks.

```bash
# Always activate venv before testing:
source .venv/bin/activate

# Run all tests:
pytest -v -q --strict-markers

# Run specific test file:
pytest tests/test_config.py -v

# Run specific test function:
pytest tests/test_config.py::test_function_name -v
```

## Code Style Guidelines

Style Rules:

- Follow PEP 8 strictly
- Max line length: 79 characters

Type Annotations:

- Use built-in types: `list[str]`, `dict[str, int]` (not `List`, `Dict`)
- Use `from typing import TYPE_CHECKING` for imports only used in type hints

Logging:

- Use `%s` style formatting in logging: `logger.info("Message: %s", value)`
- Never use f-strings in logging statements

## Project Overview

My Unicorn is a Python 3.12+ CLI tool for managing AppImages on Linux. It installs, updates, and verifies AppImage applications from GitHub with hash verification (SHA256/SHA512).

Key Technologies:

- Python 3.12+ with asyncio/aiohttp for async operations

Architecture:

- Binary location: `~/.local/bin/my-unicorn`
- Source Code stored in `~/.local/share/my-unicorn/`
- Configuration stored in `~/.config/my-unicorn/`
    - settings.conf - Configuration file for my-unicorn cli
    - cache/ - Cache files, filtered for AppImage/checksums only (Windows, mac removed)
        - `AppFlowy-IO_AppFlowy.json` - AppFlowy cache config
        - `zen-browser_desktop.json` - Zen Browser cache config
    - logs/ - Log files for my-unicorn
    - apps/ - AppImages state data folder (Keeps track of versions, checksum statuses)
        - `appflowy.json` - AppFlowy app config
        - `zen-browser.json` - Zen Browser app config

Project Structure:

- `my_unicorn/` - Main application directory (e.g. src)
    - `catalog/` - AppImage catalog data (owner, repo, verification logic etc.)
        - `appflowy.json` - AppFlowy catalog config
        - `zen-browser.json` - Zen Browser catalog config
    - `cli/` - CLI interface (parser, runner)
    - `commands/` - Command handlers
        - `auth.py` - Auth command handler
        - `backup.py` - Backup command handler
        - `base.py` - Base command handler
        - `cache.py` - Cache command handler
        - `config.py` - Config command handler
        - `install.py` - Install command handler
        - `list.py` - List command handler
        - `remove.py` - Remove command handler
        - `update.py` - Update command handler
        - `upgrade.py` - Upgrade command handler
    - `utils/` - Utility functions
    - `verification/` - Checksum verification logic
    - auth.py: Authentication handler module for github token management
    - backup.py: Backup configuration module
    - cache.py: Cache management module
    - config.py: Configuration management module
    - config_migration.py: Configuration migration module
    - constants.py: Constants module
    - desktop_entry.py: Desktop entry creation module
    - download.py: Download module that downloads AppImage, checksum files
    - exceptions.py: Exception handling module
    - file_ops.py: File operations module
    - github_client.py: GitHub API client module for requests
    - icon.py: Icon management module
    - install.py: Installation module
    - logger.py: Logging module
    - main.py: Main entry point for the application
    - progress.py: Progress bar module using rich library
    - update.py: Update module that updates AppImages
    - upgrade.py: Upgrade module that upgrades my-unicorn
- `scripts/`: Scripts for various tasks
- `tests/`: Test files written in Python using pytest
- setup.sh: Setup script for installation my-unicorn
- run.py: my-unicorn development entry point

## Commands

```bash
# Running(development entry point) the application:
python run.py --help
python run.py install appflowy
```
