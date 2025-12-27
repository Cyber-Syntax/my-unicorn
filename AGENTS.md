# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## General Guidelines

1. KISS (Keep It Simple, Stupid): Aim for simplicity and clarity. Avoid unnecessary abstractions or metaprogramming.
2. DRY (Don't Repeat Yourself): Reuse code appropriately but avoid over-engineering. Each command handler has single responsibility.
3. YAGNI (You Aren't Gonna Need It): Always implement things when you actually need them, never when you just foresee that you need them.
4. ALWAYS use `ruff check <filepath>` on each Python file you modify to ensure proper linting and formatting:
    - Use `ruff check --fix <filepath>` to automatically fix any fixable errors.
    - Use `ruff format path/to/file.py` to format a specific file.
    - Use `ruff format path/to/code/` to format all files in `path/to/code` (and any subdirectories).
    - Use `ruff format` to format all files in the current directory.

## Testing Instructions

Critical: Run tests after any change to ensure nothing breaks.

```bash
# Run all tests:
uv run pytest
# Run specific test file:
uv run pytest tests/test_config.py
# Run specific test function:
uv run pytest tests/test_config.py::test_function_name
# Run with coverage
uv run pytest tests/python/ --cov=aps.<folder>.<module>
uv run pytest tests/cli/test_parser.py --cov=my_unicorn.cli.parser
```

## Code Style Guidelines

 Use built-in types: `list[str]`, `dict[str, int]` (not `List`, `Dict`)
 Never use f-strings in logging statements, instead use `%s` formatting.

## Project Overview

My Unicorn is a Python 3.12+ CLI tool for managing AppImages on Linux. It installs, updates, and verifies AppImage applications from GitHub with hash verification (SHA256/SHA512).

Key Technologies:

- Python 3.12+ with asyncio/aiohttp for async operations

Architecture:

- Binary location: `~/.local/bin/my-unicorn`
- Source Code stored in `~/.local/share/my-unicorn/`
- Configuration stored in `~/.config/my-unicorn/`
    - settings.conf - Global configuration file (GLOBAL_CONFIG_VERSION="1.0.2")
    - cache/ - Cache files, filtered for AppImage/checksums only (Windows, mac removed)
        - `AppFlowy-IO_AppFlowy.json` - AppFlowy cache config
        - `zen-browser_desktop.json` - Zen Browser cache config
    - logs/ - Log files for my-unicorn
    - apps/ - AppImages state data folder (APP_CONFIG_VERSION="2.0.0")
        - `appflowy.json` - AppFlowy app config (v2 format)
        - `zen-browser.json` - Zen Browser app config (v2 format)
        - `backups/` - Config backups created during migration

Project Structure:

- `my_unicorn/` - Main application directory (e.g. src)
    - `catalog/` - AppImage catalog data (owner, repo, verification logic etc.)
        - `appflowy.json` - AppFlowy catalog config (v2 format with descriptions)
        - `zen-browser.json` - Zen Browser catalog config (v2 format with descriptions)
    - `cli/` - CLI interface (parser, runner)
    - `commands/` - Command handlers
        - `auth.py` - Auth command handler
        - `backup.py` - Backup command handler
        - `base.py` - Base command handler
        - `cache.py` - Cache command handler
        - `catalog.py` - Catalog command handler (renamed from list.py)
        - `config.py` - Config command handler
        - `install.py` - Install command handler
        - `migrate.py` - Migrate command handler (v1→v2 config migration)
        - `remove.py` - Remove command handler
        - `update.py` - Update command handler
        - `upgrade.py` - Upgrade command handler
    - `migration/` - Config migration modules
        - `base.py` - Common migration utilities
        - `app_config.py` - App config v1→v2 migration
        - `global_config.py` - Global config migration
    - `schemas/` - JSON schemas for config validation
        - `catalog_v1.schema.json` - v1 catalog schema
        - `catalog_v2.schema.json` - v2 catalog schema
        - `app_state_v1.schema.json` - v1 app state schema
        - `app_state_v2.schema.json` - v2 app state schema
    - `utils/` - Utility functions
    - `verification/` - Checksum verification logic
    - app_config_migration.py: Config migration module (v1→v2)
    - auth.py: Authentication handler module for github token management
    - backup.py: Backup configuration module
    - cache.py: Cache management module
    - config.py: Configuration management module
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
    - progress.py: Progress bar module with ASCII backend
    - update.py: Update module that updates AppImages
    - upgrade.py: Upgrade module that upgrades my-unicorn
- `scripts/`: Scripts for various tasks
- `tests/`: Test files written in Python using pytest (910 tests passing)
- setup.sh: Setup script for installation my-unicorn
- run.py: my-unicorn development entry point

## Running the CLI

```bash
# Running(development entry point) the application:
uv run my-unicorn --help
```
