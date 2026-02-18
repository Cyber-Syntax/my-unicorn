# Migration Guide: Singleton to Dependency Injection

This guide documents the refactoring from singleton patterns to dependency injection
in my-unicorn core services. The migration maintains backward compatibility for most
use cases.

## Overview

Three module-level singletons were removed:

1. `_cache_manager` / `get_cache_manager()` in `core/cache.py`
2. `_validator` / `get_validator()` in `config/schemas/validator.py`
3. `config_manager` in `config/config.py`

The logger singleton (`_state` in `logger.py`) is intentionally preserved for
cross-cutting logging infrastructure.

## Breaking Changes

### Minimal Impact

Backward compatibility was maintained for most use cases:

- Convenience functions (`validate_app_state()`, `validate_cache_release()`,
  `validate_global_config()`) continue to work unchanged
- All CLI commands work identically
- Factory methods (`create_default()`) continue to work

### Potentially Breaking Changes

If your code directly imported module-level singletons, you'll need to update:

```python
# No longer available:
from my_unicorn.config import config_manager  # ImportError
from my_unicorn.core.cache import get_cache_manager  # ImportError
from my_unicorn.config.schemas.validator import get_validator  # ImportError
```

## Migration Examples

### ReleaseCacheManager

**Before (singleton pattern):**

```python
from my_unicorn.core.cache import get_cache_manager

# Get global singleton
cache = get_cache_manager(ttl_hours=48)
cached_release = cache.get_cached_release("owner/repo")
```

**After (constructor injection):**

```python
from my_unicorn.config import ConfigManager
from my_unicorn.core.cache import ReleaseCacheManager

# Create instances explicitly
config_manager = ConfigManager()
cache = ReleaseCacheManager(config_manager, ttl_hours=48)
cached_release = cache.get_cached_release("owner/repo")
```

**After (dependency injection in class):**

```python
from my_unicorn.core.cache import ReleaseCacheManager

class MyService:
    def __init__(self, cache_manager: ReleaseCacheManager):
        self.cache = cache_manager
    
    def get_release(self, repo: str):
        return self.cache.get_cached_release(repo)

# Caller creates and injects the dependency
cache = ReleaseCacheManager(config_manager, ttl_hours=24)
service = MyService(cache_manager=cache)
```

### ConfigValidator

**Before (singleton pattern):**

```python
from my_unicorn.config.schemas.validator import get_validator

# Get global singleton
validator = get_validator()
validator.validate_app_state(config, "myapp")
```

**After (constructor injection):**

```python
from my_unicorn.config.schemas.validator import ConfigValidator

# Create instance explicitly
validator = ConfigValidator()
validator.validate_app_state(config, "myapp")
```

**Convenience functions still work (unchanged):**

```python
from my_unicorn.config.schemas.validator import validate_app_state

# Still works - creates validator internally
validate_app_state(config, "myapp")

# Or inject your own validator for better control
validator = ConfigValidator()
validate_app_state(config, "myapp", validator=validator)
```

### ConfigManager (module-level instance)

**Before (module-level singleton):**

```python
from my_unicorn.config import config_manager

# Use pre-created global instance
settings = config_manager.load_global_config()
```

**After (explicit instantiation):**

```python
from my_unicorn.config import ConfigManager

# Create instance explicitly
config_manager = ConfigManager()
settings = config_manager.load_global_config()
```

**After (dependency injection in class):**

```python
from my_unicorn.config import ConfigManager

class MyService:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
    
    def get_settings(self):
        return self.config.load_global_config()

# Caller creates and injects the dependency
config = ConfigManager()
service = MyService(config_manager=config)
```

## New Recommended Patterns

### Composition Root Pattern

CLIRunner acts as the composition root where all dependencies are created and wired:

```python
class CLIRunner:
    def __init__(self):
        # 1. Create validator first (no dependencies)
        self.validator = ConfigValidator()
        
        # 2. Create config manager with validator
        self.config_manager = ConfigManager(validator=self.validator)
        
        # 3. Create cache manager with config manager
        self.cache_manager = ReleaseCacheManager(
            self.config_manager, 
            ttl_hours=24
        )
        
        # 4. Create auth manager
        self.auth_manager = GitHubAuthManager.create_default()
        
        # 5. Create update manager with all dependencies
        self.update_manager = UpdateManager(
            self.config_manager,
            self.auth_manager,
            self.cache_manager,
        )
```

### Factory Methods

Classes may provide `create_default()` factory methods for convenience when you
don't need to customize dependencies:

```python
# Use factory for default configuration
auth = GitHubAuthManager.create_default()

# Or use constructor for full control (e.g., testing)
auth = GitHubAuthManager(token_storage=mock_storage)
```

### Testing with Dependency Injection

Tests should create isolated mock instances:

```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_config():
    """Create isolated config manager mock."""
    config = MagicMock(spec=ConfigManager)
    config.load_global_config.return_value = GlobalConfig(...)
    return config

@pytest.fixture
def mock_cache(mock_config):
    """Create isolated cache manager mock."""
    return MagicMock(spec=ReleaseCacheManager)

def test_my_feature(mock_config, mock_cache):
    handler = MyHandler(
        config_manager=mock_config,
        cache_manager=mock_cache,
    )
    # Test with isolated dependencies
    result = handler.execute()
    mock_cache.get_cached_release.assert_called_once()
```

## What Stayed the Same

### Logger Singleton (Intentionally Preserved)

The logger singleton in `logger.py` is intentionally preserved:

```python
from my_unicorn.logger import get_logger

# Still works exactly the same
logger = get_logger(__name__)
logger.info("This works as before")
```

**Rationale:**

- Manages global logging infrastructure (handlers, queue, listener)
- Thread-safe initialization required
- Standard pattern for logging frameworks
- No testability issues

### Convenience Validation Functions

These functions continue to work without modification:

```python
from my_unicorn.config.schemas.validator import (
    validate_app_state,
    validate_cache_release,
    validate_global_config,
)

# All work unchanged
validate_app_state(config, "myapp")
validate_cache_release(release_data)
validate_global_config(settings)
```

### CLI Commands

All CLI commands work identically. The refactoring is internal and transparent
to end users:

```bash
# All commands work exactly as before
my-unicorn install zen-browser
my-unicorn update --all
my-unicorn cache --clear
my-unicorn list
```

## DI-Enabled Classes Reference

| Class | Dependencies | Factory Method |
|-------|-------------|----------------|
| `ConfigValidator` | None | Direct instantiation |
| `ConfigManager` | `validator: ConfigValidator` (optional) | Direct instantiation |
| `ReleaseCacheManager` | `config_manager: ConfigManager` (optional) | Direct instantiation |
| `GitHubReleaseFetcher` | `session`, `cache_manager` (required) | None |
| `GitHubClient` | `session`, `auth_manager`, `cache_manager` | None |
| `GitHubAuthManager` | `token_storage` (optional) | `create_default()` |
| `UpdateManager` | `config_manager`, `auth_manager`, `cache_manager` (optional) | `create_default()` |
| `BaseCommandHandler` | All dependencies via constructor | None |

## Troubleshooting

### ImportError for Removed Singletons

If you encounter:

```
ImportError: cannot import name 'config_manager' from 'my_unicorn.config'
```

Update your code to create instances explicitly:

```python
# Before
from my_unicorn.config import config_manager

# After
from my_unicorn.config import ConfigManager
config_manager = ConfigManager()
```

### AttributeError for get_* Functions

If you encounter:

```
AttributeError: module 'my_unicorn.core.cache' has no attribute 'get_cache_manager'
```

Update your code to instantiate directly:

```python
# Before
cache = get_cache_manager(ttl_hours=24)

# After
cache = ReleaseCacheManager(config_manager, ttl_hours=24)
```

## Summary

This refactoring improves:

- **Testability**: Each test creates isolated instances with mocks
- **Explicitness**: Dependencies are visible in constructors
- **Flexibility**: Different configurations per instance
- **Maintainability**: No hidden global state

While maintaining:

- **Backward compatibility** for convenience functions
- **Identical CLI behavior**
- **Logger singleton** for infrastructure concerns
