# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## General Guidelines

1. Simple is better than complex.
2. KISS (Keep It Simple, Stupid): Aim for simplicity and clarity. Avoid unnecessary abstractions or metaprogramming.
3. DRY (Don't Repeat Yourself): Reuse code appropriately but avoid over-engineering. Each command handler has single responsibility.
4. YAGNI (You Aren't Gonna Need It): Always implement things when you actually need them, never when you just foresee that you need them.
5. Confirm understanding before making changes: If you're unsure about the purpose of a piece of code, ask for clarification rather than making assumptions.

## Project Overview

**My Unicorn** is a Python 3.12+ CLI tool for managing AppImages on Linux. It installs, updates, and verifies AppImage applications from GitHub repositories with hash verification (SHA256/SHA512).

**Key Technologies:**

- Python 3.12+ with asyncio/aiohttp for async operations
- Virtual environment (venv) for dependency isolation
- pytest for testing with async support

**Architecture:**

- Command pattern: Each CLI command has a dedicated handler in `my_unicorn/commands/`
- Catalog system: App definitions in `my_unicorn/catalog/` as JSON files

## Development Workflow

**Running the application:**

```bash
# Direct execution (development mode)
python run.py --help
python run.py install appflowy
python run.py update appflowy
```

**Available commands:**

- `install <app>` - Install an AppImage
- `update <app>` - Update an installed AppImage
- `remove <app>` - Remove an installed AppImage
- `list` - List installed AppImages
- `upgrade` - Upgrade all installed AppImages
- `backup` - Backup configuration
- `config` - Manage configuration
- `cache` - Manage cache

## Testing Instructions

**Always activate venv before testing:**

```bash
source .venv/bin/activate
```

**Run all tests:**

```bash
pytest -v -q --strict-markers
```

**Run specific test file:**

```bash
pytest tests/test_config.py -v
```

**Run specific test function:**

```bash
pytest tests/test_config.py::test_function_name -v
```

**Test patterns:**

- Test files: `tests/test_*.py`
- Test functions: `def test_*()`
- Async tests: Use `pytest-asyncio` with `@pytest.mark.asyncio`
- Mock external calls: Use `pytest-mock` and `aioresponses`

**Critical: Run tests after any change to ensure nothing breaks.**

## Code Style Guidelines

**Language:** Python 3.12+

**Code Formatting (Ruff):**

```bash
# Check formatting
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

**Style Rules:**

- Follow PEP 8 strictly
- Max line length: 79 characters
- Use double quotes for strings
- Use spaces (not tabs) for indentation
- Include type hints for all functions
- Use Google-style docstrings

**Type Annotations:**

- Use built-in types: `list[str]`, `dict[str, int]` (not `List`, `Dict`)
- Use `from typing import TYPE_CHECKING` for imports only used in type hints

**Docstring Format (Google Style):**

```python
def function_name(param1: str, param2: int) -> bool:
    """Brief description.

    Longer description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When something goes wrong.
    """
```

**Logging:**

- Use `%s` style formatting in logging: `logger.info("Message: %s", value)`
- Never use f-strings in logging statements

**Project Conventions:**

- Each command handler inherits from `BaseCommand`
- Services handle business logic, commands handle CLI interaction
- Use async/await for I/O operations (network, file system)
- my-unicorn source code stored in `~/.local/share/my-unicorn/`
- Configuration stored in `~/.config/my-unicorn/`

## Common Development Tasks

**Adding a new command:**

1. Create handler in `my_unicorn/commands/`
2. Inherit from `BaseCommand`
3. Implement `execute()` method
4. Register in CLI parser
5. Add tests in `tests/commands/`

**Debugging:**

- Check logs in `~/.config/my-unicorn/logs/`
- Use `--verbose` flag for detailed output

## Additional Notes

**External dependencies:** Managed via `pyproject.toml`

**Binary location:** `~/.local/bin/my-unicorn`
