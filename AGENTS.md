# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## General Guidelines

1. Modern Python First: Use Python 3.12+ features extensively - built-in generics, pattern matching, and dataclasses.
2. Async-First Architecture: All I/O operations must be async. Use modern async patterns like `asyncio.TaskGroup` for concurrency.
3. Type Safety: Full type annotations on all functions including return types. Use modern syntax (`dict[str, int]`, `str | None`).
4. KISS Principle: Aim for simplicity and clarity. Avoid unnecessary abstractions or metaprogramming.
5. DRY with Care: Reuse code appropriately but avoid over-engineering. Each command handler has single responsibility.
6. Performance-Conscious: Use `@dataclass(slots=True)` when object count justifies it, orjson for JSON, and async-safe patterns over explicit locks.

## Activate venv before any test execution

Unit test located in `tests/` directory

```bash
source .venv/bin/activate
pytest -v -qa --strict-markers
```

## Run the application

```bash
python run.py --help
python run.py install appflowy
python run.py update appflowy
```

## More information about cli

- Read developers.md for an overview of the architecture, api structure etc.
    - [docs/developers.md](docs/developers.md)
- Read wiki for detailed information about configuration, commands etc.
    - [docs/wiki.md](docs/wiki.md)
