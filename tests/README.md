# Token Management Tests

This directory contains tests for the secure token and authentication management modules.

## Test Files

- `test_secure_token.py`: Tests for the `SecureTokenManager` class in `src/secure_token.py`
- `test_auth_manager.py`: Tests for the `GitHubAuthManager` class in `src/auth_manager.py`
- `test_manage_token.py`: Tests for the `ManageTokenCommand` class in `src/commands/manage_token.py`

## Running Tests

Run all tests with:

```bash
python -m pytest
```

Run specific test files with:

```bash
python -m pytest tests/test_secure_token.py
python -m pytest tests/test_auth_manager.py
python -m pytest tests/test_manage_token.py
```

Run tests with verbosity:

```bash
python -m pytest -v
```

Run with coverage reporting:

```bash
python -m pytest --cov=src
```

Note: You may need to install the required packages:

```bash
pip install pytest pytest-mock pytest-cov httmock requests-mock
```

## Test Structure

Each test file follows the same structure:

1. Fixtures to set up test data and mock dependencies
2. Tests organized by class method or functionality
3. Each test focuses on a single behavior or edge case

The tests use `monkeypatch`, `mock` and other pytest features to isolate the code being tested from its dependencies.
