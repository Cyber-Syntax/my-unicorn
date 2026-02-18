# Testing Guide

This guide covers everything you need to know about testing My Unicorn - from running tests to understanding the logging architecture to debugging failures.

## Quick Start

Common test commands you'll use daily:

```bash
# Run fast tests only (excludes slow logger integration tests)
uv run pytest -m "not slow"

# Run all tests (including slow tests)
uv run pytest

# Run with coverage report
uv run pytest --cov=my_unicorn --cov-report=html

# Run specific module
uv run pytest tests/core/verification/

# Run specific test file
uv run pytest tests/test_install.py

# Run specific test function
uv run pytest tests/test_install.py::test_install_success

# Run with verbose output and show print statements
uv run pytest -v -s
```

## Test Organization

### Directory Structure

The test directory mirrors the `src/my_unicorn/` structure:

```
tests/
├── conftest.py                                     # Global fixtures (all tests)
├── integration/                                    # Integration tests (no network calls)
├── custom/                                         # Custom tests (GitHub Action CI, line count)
├── e2e/                                            # End-to-end tests
├── fixtures                                        # Real test data and expected outputs
│  ├── checksums                                    # Real checksums for integration tests
│  │  └── superproductivity_latest-linux.yml        # Super Productivity latest release checksums
│  └── expected_ui_output                           # Expected progress bar, print outputs
│     ├── install_success.txt
│     ├── install_warning.txt
│     └── update_success.txt
├── core/
│   ├── conftest.py                                 # Core module fixtures
│   ├── install/
│   │   ├── conftest.py                             # Install-specific fixtures
│   │   └── test_*.py
│   └── update/
│       ├── conftest.py                             # Update-specific fixtures
│       └── test_*.py
└── [mirrors src/ structure]
```

### Test Markers

Tests are organized with pytest markers:

- `@pytest.mark.slow` - Slow tests (skipped with `-m "not slow"`)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.asyncio` - Async tests (required for async functions)

### Fixture Organization

Fixtures follow a hierarchical organization:

| Fixture Scope | Location | Purpose |
|---------------|----------|---------|
| **Global fixtures** | `tests/conftest.py` | Shared across all tests (e.g., `enable_log_propagation`) |
| **Module-group fixtures** | `tests/<group>/conftest.py` | Shared across submodules (e.g., `tests/core/conftest.py`) |
| **Module-specific fixtures** | `tests/<module>/conftest.py` | Used only by tests in that module |

Pytest automatically discovers fixtures from parent directories, so child tests can use parent fixtures without imports.

## Logging During Tests

### Architecture Overview

My Unicorn implements a **4-part logging isolation mechanism** to keep test logs completely separate from production logs:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Environment Variable (pyproject.toml)                       │
│     MY_UNICORN_LOG_DIR = "/tmp/pytest-of-{USER}-logs"          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. Log Redirection (logger/config.py)                          │
│     load_log_settings() reads MY_UNICORN_LOG_DIR                │
│     - If set: Use /tmp/pytest-of-{USER}-logs/my-unicorn.log     │
│     - If not set: Use ~/.config/my-unicorn/logs/my-unicorn.log  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. Test Isolation (pytest execution)                           │
│     Tests write logs to: /tmp/pytest-of-developer-logs/         │
│     Production writes to: ~/.config/my-unicorn/logs/            │
│     NEVER any cross-contamination                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. Cleanup (system tmpdir)                                     │
│     /tmp/ is automatically cleaned up by the OS                 │
│     No manual cleanup required                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**

- **Complete Isolation**: Tests NEVER write to `~/.config/my-unicorn/logs/`
- **Environment-driven**: The `MY_UNICORN_LOG_DIR` environment variable controls the log directory
- **Zero Configuration**: Works automatically when running `uv run pytest`

### Viewing Test Logs

Test logs are written to `/tmp/pytest-of-$USER-logs/my-unicorn.log`. Here are practical examples:

```bash
# Watch logs in real-time while tests run
tail -f /tmp/pytest-of-$USER-logs/my-unicorn.log

# View the last 100 log entries
tail -100 /tmp/pytest-of-$USER-logs/my-unicorn.log

# View the first 50 log entries
head -50 /tmp/pytest-of-$USER-logs/my-unicorn.log

# Search for ERROR entries
grep ERROR /tmp/pytest-of-$USER-logs/my-unicorn.log

# Search for WARNING entries
grep WARNING /tmp/pytest-of-$USER-logs/my-unicorn.log

# Search for specific module logs (e.g., verification)
grep "verification" /tmp/pytest-of-$USER-logs/my-unicorn.log

# Search for install/remove/update operations
grep -E "install|remove|update" /tmp/pytest-of-$USER-logs/my-unicorn.log

# Count log entries by level
grep -c INFO /tmp/pytest-of-$USER-logs/my-unicorn.log
grep -c ERROR /tmp/pytest-of-$USER-logs/my-unicorn.log

# Follow logs with colored output (if you have ccze installed)
tail -f /tmp/pytest-of-$USER-logs/my-unicorn.log | ccze -A
```

**Pro Tip**: Keep a terminal window open with `tail -f` running while you develop tests. This gives you immediate feedback on what the logger is doing.

### Production Log Isolation

The test logs are completely isolated from production logs:

```bash
# Production logs (NEVER touched by tests)
~/.config/my-unicorn/logs/my-unicorn.log

# Test logs (isolated in /tmp)
/tmp/pytest-of-developer-logs/my-unicorn.log
```

**Verify Isolation**:

You can verify that tests don't contaminate production logs:

```bash
# 1. Note the current modification time of production logs
ls -lh ~/.config/my-unicorn/logs/my-unicorn.log

# 2. Run the full test suite
uv run pytest

# 3. Check the modification time again - it should NOT have changed
ls -lh ~/.config/my-unicorn/logs/my-unicorn.log

# 4. Verify test logs were written instead
ls -lh /tmp/pytest-of-$USER-logs/my-unicorn.log
```

### pytest's caplog Fixture

Pytest provides two ways to capture logs during tests:

1. **caplog fixture**: Captures console logs for assertions in tests
2. **File logs**: Persistent logs written to `/tmp/` for debugging

**When to use each:**

```python
import pytest

def test_with_caplog(caplog):
    """Use caplog for asserting log messages in tests."""
    # caplog captures console output
    my_function_that_logs()
    
    # Assert specific log messages were emitted
    assert "Expected message" in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)

# File logs are always written automatically - check them when:
# - Tests fail and you need more context
# - Debugging complex async operations
# - Need to see the full sequence of events
```

**Example**:

```python
@pytest.mark.asyncio
async def test_install_workflow(caplog, tmp_path):
    """Test installation with both caplog and file logs."""
    # caplog captures console logs for assertions
    result = await install_workflow.execute()
    
    # Assert using caplog
    assert "Installing" in caplog.text
    
    # If test fails, check file logs for full context:
    # tail -f /tmp/pytest-of-$USER-logs/my-unicorn.log
```

## Debugging Failed Tests

When a test fails, follow this debugging workflow:

### 1. Run the failing test with verbose output

```bash
# Run with -v (verbose) and -s (show print statements)
uv run pytest tests/test_install.py::test_install_failure -v -s
```

### 2. Check the test log file

```bash
# View recent ERROR entries
grep ERROR /tmp/pytest-of-$USER-logs/my-unicorn.log | tail -20

# View logs around a specific operation
grep -A 5 -B 5 "install" /tmp/pytest-of-$USER-logs/my-unicorn.log
```

### 3. Common patterns in logs

Look for these patterns when debugging:

```
ERROR - Hash verification failed: expected abc123, got def456
→ Problem: Checksum mismatch (check test fixtures)

ERROR - Failed to download: 404 Client Error
→ Problem: Mock not configured or URL mismatch

WARNING - Configuration file not found
→ Problem: Test setup missing config initialization

INFO - Starting installation for app-name
DEBUG - Downloaded 1024 bytes
ERROR - Installation failed: Permission denied
→ Problem: File permissions in test tmp_path
```

### 4. Enable debug logging

For deeper investigation, you can temporarily increase log verbosity:

```python
def test_with_debug_logging(caplog):
    """Test with DEBUG level logging."""
    caplog.set_level(logging.DEBUG)
    
    # Now all DEBUG messages will be captured
    my_complex_function()
    
    # Check debug logs
    assert "Detailed debug info" in caplog.text
```

### 5. Use pytest's built-in debugging

```bash
# Drop into debugger on failure
uv run pytest --pdb tests/test_install.py

# Drop into debugger at start of test
uv run pytest --trace tests/test_install.py
```

## Writing New Tests

### Best Practices

Follow these patterns when writing new tests:

#### 1. Use tmp_path fixture for file operations

```python
def test_file_operations(tmp_path):
    """Always use tmp_path for temporary files."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    # Cleanup is automatic - pytest removes tmp_path after test
    assert test_file.exists()
```

#### 2. Use caplog fixture for log assertions

```python
def test_logging_behavior(caplog):
    """Use caplog to assert log messages."""
    my_function()
    
    assert "Expected message" in caplog.text
    assert caplog.records[0].levelname == "INFO"
```

#### 3. Follow test naming conventions

```python
# GOOD - Descriptive test names
def test_install_creates_desktop_entry()
def test_update_skips_when_version_unchanged()
def test_verification_fails_with_invalid_hash()

# BAD - Vague test names
def test_install()
def test_update()
def test_verification()
```

#### 4. Structure tests with Arrange-Act-Assert

```python
def test_example():
    """Test follows AAA pattern."""
    # Arrange - Set up test data and mocks
    mock_data = {"key": "value"}
    expected_result = "expected"
    
    # Act - Execute the function under test
    result = my_function(mock_data)
    
    # Assert - Verify the outcome
    assert result == expected_result
```

#### 5. Async test patterns

```python
@pytest.mark.asyncio
async def test_async_function():
    """Always mark async tests with @pytest.mark.asyncio."""
    result = await my_async_function()
    assert result is not None
```

#### 6. Mock external dependencies

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mocked_http(mock_session):
    """Mock external HTTP calls."""
    mock_session.get = AsyncMock(return_value=fake_response)
    
    result = await fetch_data()
    
    assert result == expected_data
    mock_session.get.assert_called_once()
```

### Test Checklist

Before committing new tests, verify:

- [ ] Test fails when the code it tests is broken (test is valid)
- [ ] Happy path is covered
- [ ] Edge cases and error conditions are tested
- [ ] External dependencies are mocked (no real network calls)
- [ ] Tests are deterministic (no flaky behavior)
- [ ] Async tests use `@pytest.mark.asyncio`
- [ ] Test names clearly describe what they test
- [ ] File operations use `tmp_path` fixture
- [ ] Log assertions use `caplog` fixture

## Running Specific Test Subsets

### By Markers

```bash
# Run fast tests only (default for development)
uv run pytest -m "not slow"

# Run slow tests
uv run pytest -m "slow"

# Run integration tests
uv run pytest -m "integration"

# Run e2e tests
uv run pytest -m "e2e"
```

### By Directory/Module

```bash
# Run all core tests
uv run pytest tests/core/

# Run verification tests only
uv run pytest tests/core/verification/

# Run install workflow tests
uv run pytest tests/core/install/
```

### By Pattern

```bash
# Run all tests matching "install"
uv run pytest -k install

# Run all tests matching "verification"
uv run pytest -k verification

# Run tests matching "install" but not "workflow"
uv run pytest -k "install and not workflow"
```

### With Coverage

```bash
# Generate HTML coverage report
uv run pytest --cov=my_unicorn --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Generate terminal coverage report
uv run pytest --cov=my_unicorn --cov-report=term

# Coverage for specific module
uv run pytest --cov=my_unicorn.core.verification tests/core/verification/
```

## Advanced Testing Topics

### Test Fixtures Organization

Fixtures are organized hierarchically. When you need a new fixture:

1. **Module-specific**: Add to `tests/<module>/conftest.py` if only used in that module
2. **Module-group**: Add to `tests/<group>/conftest.py` if shared across submodules
3. **Global**: Add to `tests/conftest.py` if used across many modules

Example:

```python
# tests/core/install/conftest.py
@pytest.fixture
def sample_asset():
    """Fixture specific to install tests."""
    return Asset(name="test.AppImage", size=1024)

# tests/core/conftest.py
@pytest.fixture
def mock_session():
    """Fixture shared across all core tests."""
    return AsyncMock()

# tests/conftest.py
@pytest.fixture
def enable_log_propagation():
    """Fixture used by all tests."""
    # Global setup
    yield
    # Global teardown
```

### Test Data and Fixtures

Real test data is stored in `tests/fixtures/`:

```
tests/fixtures/
├── checksums/              # Real SHA256/SHA512 checksums
│   ├── appflowy.json
│   └── zen-browser.json
└── [other test data]
```

Use these for integration tests that need realistic data.

### Continuous Integration

Tests run automatically on GitHub Actions. See `.github/workflows/` for CI configuration.

Key CI test commands:

```bash
# CI runs fast tests by default
uv run pytest -m "not slow" --cov=my_unicorn

# Check CI test results in GitHub Actions tab
```

## Troubleshooting

### Tests hang indefinitely

**Cause**: Async test without `@pytest.mark.asyncio` marker  
**Solution**: Add the marker:

```python
@pytest.mark.asyncio
async def test_my_async_function():
    ...
```

### Import errors in tests

**Cause**: Missing `uv run` prefix  
**Solution**: Always use `uv run pytest`, not just `pytest`

### Tests pass locally but fail in CI

**Cause**: Environment-specific behavior or missing mocks  
**Solution**: Check test logs in GitHub Actions, verify all external calls are mocked

### Cannot find test logs

**Cause**: Environment variable not set or incorrect path  
**Solution**: Verify pytest is setting `MY_UNICORN_LOG_DIR`:

```bash
# Check environment during test run
uv run pytest -v -s tests/test_logger.py

# Verify log directory exists
ls -la /tmp/pytest-of-$USER-logs/
```

## Related Documentation

- [AGENTS.md](../../AGENTS.md) - Development workflow and coding standards
- [developers.md](developers.md) - General development guide
- [pytest Documentation](https://docs.pytest.org/) - Official pytest docs
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) - Async testing guide

---

**Questions or issues with testing?** Check the test logs first, then review this guide. Most issues can be debugged with the logging patterns above.
