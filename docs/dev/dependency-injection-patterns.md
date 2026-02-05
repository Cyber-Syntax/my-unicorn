### Dependency Injection Patterns

The codebase uses **constructor injection** for dependency management. Singletons were removed in favor of explicit dependency injection to improve testability and make the dependency graph explicit.

#### Composition Root: CLIRunner

`CLIRunner` in `cli/runner.py` acts as the **composition root** - the single place where all shared dependencies are created and wired together:

```python
# CLIRunner creates dependencies in order:
# 1. ConfigValidator() - no dependencies
# 2. ConfigManager(validator=validator)
# 3. ReleaseCacheManager(config_manager, ttl_hours=24)
# 4. GitHubAuthManager.create_default()
# 5. UpdateManager(config_manager, auth_manager)
```

#### Key DI-Enabled Classes

| Class | Dependencies | Notes |
|-------|-------------|-------|
| `ConfigValidator` | None | Create first, inject into ConfigManager |
| `ConfigManager` | `validator: ConfigValidator` | Accepts optional validator |
| `ReleaseCacheManager` | `config_manager: ConfigManager` | Requires config_manager |
| `BaseCommandHandler` | All dependencies | Base class for all command handlers |

#### Usage Examples

```python
# Production: CLIRunner creates and injects all dependencies
runner = CLIRunner()
await runner.run()

# Testing: Create isolated instances with mocks
config = MagicMock(spec=ConfigManager)
cache = ReleaseCacheManager(config, ttl_hours=1)
handler = MyHandler(
    config_manager=config,
    cache_manager=cache,
    # ... other dependencies
)
```

#### Factory Methods

Classes may provide `create_default()` factory methods for convenience:

```python
# Factory creates default dependencies internally
auth = GitHubAuthManager.create_default()

# Or use constructor for full control (testing)
auth = GitHubAuthManager(token_storage=mock_storage)
```

#### Testing with Dependency Injection

- Create isolated mock instances per test using `MagicMock()`
- Inject mocks via constructor parameters
- No patching of global singletons needed
- Each test gets clean, isolated instances

```python
@pytest.fixture
def mock_config():
    """Create isolated config manager mock."""
    config = MagicMock(spec=ConfigManager)
    config.load_global_config.return_value = GlobalConfig(...)
    return config

def test_my_feature(mock_config):
    handler = MyHandler(config_manager=mock_config, ...)
    # Test with isolated dependencies
```

#### Logger Exception

The logger singleton (`_state` in `logger.py`) is intentionally preserved - it manages cross-cutting logging infrastructure safely and is a standard pattern for logging frameworks.