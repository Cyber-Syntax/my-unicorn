# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## General Guidelines

1. Modern Python First: Use Python 3.12+ features extensively - built-in generics, pattern matching, and dataclasses.
2. KISS Principle: Aim for simplicity and clarity. Avoid unnecessary abstractions or metaprogramming.
3. DRY with Care: Reuse code appropriately but avoid over-engineering. Each command handler has single responsibility.

## Test after any change

1. Activate venv before any test execution:

```bash
source .venv/bin/activate
```

2. Run pytest with following command to ensure all tests pass:

```bash
pytest -v -q --strict-markers
```

## Run the application

```bash
python run.py --help
python run.py install appflowy
python run.py update appflowy
```
