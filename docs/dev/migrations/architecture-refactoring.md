# Architecture Refactoring Migration Guide

**Version:** 1.0.0  
**Date:** February 2026  
**Status:** Complete  

---

## Overview

This guide documents the architectural changes introduced in the core refactoring initiative. The refactoring focuses on four key improvements:

1. **ProgressReporter Protocol** - Decouples UI from core domain services
2. **ServiceContainer** - Centralized dependency injection for service wiring
3. **Domain Exceptions** - Structured, context-rich exception hierarchy
4. **Async File I/O** - Non-blocking file operations using aiofiles

These changes improve testability, maintainability, and performance while maintaining backward compatibility for external callers.

---

## Table of Contents

- [ProgressDisplay → ProgressReporter Protocol](#progressdisplay--progressreporter-protocol)
- [Direct Service Creation → ServiceContainer](#direct-service-creation--servicecontainer)
- [Generic Exceptions → Domain Exceptions](#generic-exceptions--domain-exceptions)
- [Sync File I/O → Async File I/O](#sync-file-io--async-file-io)
- [Breaking Changes](#breaking-changes)
- [Step-by-Step Migration](#step-by-step-migration)

---

## ProgressDisplay → ProgressReporter Protocol

### What Changed

Previously, core services directly imported `ProgressDisplay` from the `ui/` package, creating a coupling between domain logic and UI implementation. Now, core services depend on the `ProgressReporter` protocol defined in `core/protocols/progress.py`.

### Before

```python
# In core services (coupling to UI layer)
from my_unicorn.ui.display import ProgressDisplay

class DownloadService:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        progress_service: ProgressDisplay | None = None,  # UI dependency
    ) -> None:
        self.progress_service = progress_service
        # ...

    async def download_file(self, url: str, path: Path) -> Path:
        if self.progress_service is not None:
            task_id = self.progress_service.add_task(...)
            # Update progress
        # Download logic
```

### After

```python
# In core services (protocol dependency)
from my_unicorn.core.protocols.progress import (
    ProgressReporter,
    ProgressType,
    NullProgressReporter,
)

class DownloadService:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        # Null object pattern eliminates None checks
        self.progress_reporter = progress_reporter or NullProgressReporter()
        # ...

    async def download_file(self, url: str, path: Path) -> Path:
        # No None checks needed - NullProgressReporter handles inactive state
        task_id = self.progress_reporter.add_task(
            name="Downloading file",
            progress_type=ProgressType.DOWNLOAD,
            total=content_length,
        )
        # Download logic with progress updates
        self.progress_reporter.finish_task(task_id, success=True)
```

### Migration Steps

1. **Update imports** in your service:

   ```python
   # Remove UI imports
   # from my_unicorn.ui.display import ProgressDisplay  # DELETE

   # Add protocol imports
   from my_unicorn.core.protocols.progress import (
       ProgressReporter,
       ProgressType,
       NullProgressReporter,
   )
   ```

2. **Rename parameter and attribute**:

   ```python
   # Old: progress_service: ProgressDisplay | None = None
   # New: progress_reporter: ProgressReporter | None = None
   
   self.progress_reporter = progress_reporter or NullProgressReporter()
   ```

3. **Remove None checks** - the null object pattern handles inactive state:

   ```python
   # Old
   if self.progress_service is not None:
       self.progress_service.add_task(...)

   # New (no check needed)
   self.progress_reporter.add_task(...)  # NullProgressReporter is a no-op
   ```

4. **Use ProgressType enum** for task categorization:

   ```python
   self.progress_reporter.add_task(
       name="Downloading",
       progress_type=ProgressType.DOWNLOAD,  # Not a string
       total=file_size,
   )
   ```

### Protocol Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_active()` | `() -> bool` | Check if progress reporting is enabled |
| `add_task()` | `(name, progress_type, total) -> str` | Add a new progress task, returns task ID |
| `update_task()` | `(task_id, completed, description) -> None` | Update progress for existing task |
| `finish_task()` | `(task_id, success, description) -> None` | Mark task as complete |
| `get_task_info()` | `(task_id) -> dict[str, object]` | Get current task information |

### Testing with Protocols

```python
# In tests, use NullProgressReporter or a mock
from my_unicorn.core.protocols.progress import NullProgressReporter

def test_download_service():
    reporter = NullProgressReporter()
    service = DownloadService(session, progress_reporter=reporter)
    
    # Or use a mock for verifying calls
    mock_reporter = Mock(spec=ProgressReporter)
    mock_reporter.add_task.return_value = "task-123"
    service = DownloadService(session, progress_reporter=mock_reporter)
```

---

## Direct Service Creation → ServiceContainer

### What Changed

Previously, CLI commands directly instantiated services with complex dependency chains. Now, `ServiceContainer` manages service lifecycle and wiring through lazy initialization and factory methods.

### Before

```python
# In CLI commands (complex wiring)
from my_unicorn.core.http_session import create_http_session
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.download import DownloadService
from my_unicorn.core.verification import VerificationService
from my_unicorn.core.install.install import InstallHandler

class InstallCommandHandler:
    async def execute(self, args: Namespace) -> int:
        session = await create_http_session()
        try:
            auth_manager = GitHubAuthManager()
            download_service = DownloadService(session, auth_manager=auth_manager)
            verification_service = VerificationService()
            progress = ProgressDisplay()
            
            handler = InstallHandler(
                download_service=download_service,
                verification_service=verification_service,
                progress_service=progress,
                # ... many more dependencies
            )
            
            await handler.install_from_catalog(args.app_name)
        finally:
            await session.close()
```

### After

```python
# In CLI commands (container-based wiring)
from my_unicorn.cli.container import ServiceContainer
from my_unicorn.ui.display import ProgressDisplay

class InstallCommandHandler:
    async def execute(self, args: Namespace) -> int:
        progress = ProgressDisplay()  # UI created in CLI layer
        container = ServiceContainer(
            config_manager=self.config,
            progress_reporter=progress,
        )
        
        try:
            handler = container.create_install_handler()
            await handler.install_from_catalog(args.app_name)
        finally:
            await container.cleanup()  # Cleans up HTTP session
```

### ServiceContainer Features

1. **Lazy Initialization**: Services are created only when first accessed
2. **Singleton Pattern**: Same service instance returned on repeated access
3. **Factory Methods**: Create fully-wired workflow handlers
4. **Resource Cleanup**: Single cleanup() call releases all resources

### Available Services

```python
# Properties (singleton, lazy-loaded)
container.session           # aiohttp.ClientSession
container.auth_manager      # GitHubAuthManager
container.cache_manager     # ReleaseCacheManager
container.file_ops          # FileOperations
container.download_service  # DownloadService
container.verification_service  # VerificationService
container.icon_extractor    # AppImageIconExtractor
container.github_client     # GitHubClient
container.backup_service    # BackupService
container.remove_service    # RemoveService
container.post_download_processor  # PostDownloadProcessor

# Factory methods (create new instances)
container.create_install_handler()       # InstallHandler
container.create_update_manager()        # UpdateManager
container.create_remove_service()        # RemoveService
container.create_install_application_service()  # InstallApplicationService
container.create_update_application_service()   # UpdateApplicationService
```

### Migration Steps

1. **Remove direct service instantiation**:

   ```python
   # Delete these imports and instantiations
   # session = await create_http_session()
   # download_service = DownloadService(session, ...)
   ```

2. **Create ServiceContainer**:

   ```python
   from my_unicorn.cli.container import ServiceContainer

   container = ServiceContainer(
       config_manager=config,
       progress_reporter=progress_display,
   )
   ```

3. **Use factory methods**:

   ```python
   # Instead of manually wiring InstallHandler
   handler = container.create_install_handler()
   ```

4. **Always cleanup in finally block**:

   ```python
   try:
       handler = container.create_install_handler()
       await handler.install(...)
   finally:
       await container.cleanup()
   ```

---

## Generic Exceptions → Domain Exceptions

### What Changed

Previously, services raised generic `Exception` or `ValueError`. Now, a structured exception hierarchy provides context-rich errors with retry metadata.

### Before

```python
# Generic exceptions without context
class VerificationService:
    async def verify_file(self, file_path: Path) -> bool:
        if not hash_available:
            raise Exception(f"No hash available for {app_name}")
        
        if computed_hash != expected_hash:
            raise Exception("Hash mismatch")

# In callers
try:
    await verification_service.verify_file(path)
except Exception as e:
    logger.exception("Verification failed")
    raise  # Lost context, no retry info
```

### After

```python
from my_unicorn.exceptions import (
    VerificationError,
    HashMismatchError,
    HashUnavailableError,
)

class VerificationService:
    async def verify_file(self, file_path: Path) -> bool:
        if not hash_available:
            raise HashUnavailableError(app_name=app_name, version=version)
        
        if computed_hash != expected_hash:
            raise HashMismatchError(
                expected=expected_hash,
                actual=computed_hash,
                algorithm="sha256",
                file_path=str(file_path),
            )

# In callers - rich context available
try:
    await verification_service.verify_file(path)
except HashMismatchError as e:
    logger.error(
        "Hash mismatch: expected=%s actual=%s",
        e.context["expected_hash"],
        e.context["actual_hash"],
    )
    # No retry - hash mismatch is definitive
except HashUnavailableError as e:
    logger.warning("No hash for %s v%s", e.context["app_name"], e.context["version"])
    # Decide whether to skip verification or fail
```

### Exception Hierarchy

```
MyUnicornError (base)
├── VerificationError
│   ├── HashMismatchError
│   ├── HashUnavailableError
│   └── HashComputationError
├── WorkflowError
│   ├── InstallError
│   ├── UpdateError
│   └── PostProcessingError
├── NetworkError
│   ├── DownloadError
│   └── GitHubAPIError
└── ConfigurationError
```

### Exception Attributes

All domain exceptions inherit from `MyUnicornError` which provides:

| Attribute | Type | Description |
|-----------|------|-------------|
| `message` | `str` | Human-readable error message |
| `context` | `dict[str, object]` | Contextual data (app_name, url, etc.) |
| `is_retryable` | `bool` | Whether the error can be retried |
| `retry_after` | `int \| None` | Suggested retry delay in seconds |
| `__cause__` | `Exception \| None` | Original exception (for chaining) |

### Retry Pattern

```python
from my_unicorn.exceptions import NetworkError, InstallError

MAX_RETRIES = 3

async def download_with_retry(url: str) -> Path:
    for attempt in range(MAX_RETRIES):
        try:
            return await download_service.download_file(url, destination)
        except NetworkError as e:
            if e.is_retryable and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(e.retry_after or 5)
                continue
            raise InstallError(
                f"Download failed after {MAX_RETRIES} attempts",
                context={"url": url, "attempts": MAX_RETRIES},
                cause=e,
            ) from e
```

### Migration Steps

1. **Import domain exceptions**:

   ```python
   from my_unicorn.exceptions import (
       VerificationError,
       InstallError,
       UpdateError,
       NetworkError,
   )
   ```

2. **Replace generic raises**:

   ```python
   # Old
   raise Exception(f"Failed for {app_name}")
   
   # New
   raise InstallError(
       f"Installation failed",
       context={"app_name": app_name, "version": version},
   )
   ```

3. **Add exception chaining**:

   ```python
   except OSError as e:
       raise InstallError(
           "File operation failed",
           context={"path": str(path)},
           cause=e,
       ) from e
   ```

4. **Handle specific exceptions**:

   ```python
   try:
       await install()
   except VerificationError as e:
       # Handle verification-specific error
   except NetworkError as e:
       if e.is_retryable:
           # Implement retry logic
   except InstallError as e:
       # General install failure
   ```

---

## Sync File I/O → Async File I/O

### What Changed

File writes during downloads now use `aiofiles` for non-blocking I/O, and hash computation runs in a thread pool executor for large files.

### Before

```python
# Blocking file write in async function
class DownloadService:
    async def download_file(self, url: str, path: Path) -> Path:
        async with session.get(url) as response:
            # BLOCKING: Stalls event loop during write
            with open(path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)  # Sync write blocks event loop
```

### After

```python
import aiofiles

class DownloadService:
    async def download_file(self, url: str, path: Path) -> Path:
        async with session.get(url) as response:
            # NON-BLOCKING: Event loop remains responsive
            async with aiofiles.open(path, mode="wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)  # Async write
```

### Fallback Mechanism

When aiofiles is unavailable, the system falls back to executor-based sync I/O:

```python
HAS_AIOFILES = True
try:
    import aiofiles
except ImportError:
    HAS_AIOFILES = False

async def download_file(self, url: str, path: Path) -> Path:
    if HAS_AIOFILES:
        await self._download_with_aiofiles(url, path)
    else:
        await self._download_with_executor(url, path)

async def _download_with_executor(self, url: str, path: Path) -> Path:
    loop = asyncio.get_event_loop()
    with open(path, "wb") as f:
        async for chunk in response.content.iter_chunked(8192):
            await loop.run_in_executor(None, f.write, chunk)
```

### Async Hash Computation

For large files (>100MB), hash computation runs in a thread pool:

```python
from my_unicorn.core.verification.verifier import Verifier, LARGE_FILE_THRESHOLD

class Verifier:
    LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB

    async def compute_hash_async(self, file_path: Path, algorithm: str = "sha256") -> str:
        file_size = file_path.stat().st_size
        
        if file_size >= LARGE_FILE_THRESHOLD:
            # Offload to thread pool for large files
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                self._compute_hash_sync,
                file_path,
                algorithm,
            )
        else:
            # Direct computation for small files (avoid executor overhead)
            return self._compute_hash_sync(file_path, algorithm)
```

### Performance Expectations

| Operation | Before | After |
|-----------|--------|-------|
| Event loop blocking (per chunk) | 0-50ms | <1ms |
| Large file hash computation | Blocks entirely | Offloaded to executor |
| Download progress updates | May stutter | Smooth |

---

## Breaking Changes

### Internal Changes (Non-Breaking for External Users)

The following changes are internal implementation details and do not affect external API consumers:

1. **Parameter Renaming**: `progress_service` → `progress_reporter` in core services
2. **Import Paths**: Core services no longer import from `ui/` package
3. **Exception Types**: More specific exceptions raised internally

### Potentially Breaking Changes

1. **Direct Service Instantiation**: If you directly instantiate core services (not recommended), you need to update parameter names:

   ```python
   # Old
   DownloadService(session, progress_service=progress)
   
   # New
   DownloadService(session, progress_reporter=progress)
   ```

2. **Exception Catching**: If you catch specific exception types, update to use the new hierarchy:

   ```python
   # Old
   except Exception as e:  # Too broad
   
   # New
   except (InstallError, VerificationError) as e:  # Specific
   ```

3. **ProgressDisplay Method**: `get_task_info()` now returns `dict[str, object]` instead of `TaskInfo`. Use `get_task_info_full()` for the original `TaskInfo` object.

---

## Step-by-Step Migration

### For Core Service Developers

1. Update imports to use protocol instead of UI classes
2. Rename `progress_service` to `progress_reporter`
3. Apply null object pattern: `self.progress = progress or NullProgressReporter()`
4. Replace generic exceptions with domain exceptions
5. Run ruff check and format: `ruff check --fix && ruff format`
6. Update tests to use `NullProgressReporter` or mocks

### For CLI Command Developers

1. Create `ProgressDisplay` in CLI layer
2. Use `ServiceContainer` for service wiring
3. Call factory methods instead of direct instantiation
4. Always call `container.cleanup()` in finally block

### For Test Developers

1. Use `NullProgressReporter` for services that need progress reporting
2. Use mocks that implement `ProgressReporter` protocol for verification
3. Expect domain exceptions instead of generic `Exception`
4. Test retry logic for `NetworkError` with `is_retryable=True`

---

## Quick Reference

### Import Cheatsheet

```python
# Protocols
from my_unicorn.core.protocols.progress import (
    ProgressReporter,
    ProgressType,
    NullProgressReporter,
)

# Container
from my_unicorn.cli.container import ServiceContainer

# Exceptions
from my_unicorn.exceptions import (
    MyUnicornError,
    VerificationError,
    HashMismatchError,
    HashUnavailableError,
    WorkflowError,
    InstallError,
    UpdateError,
    NetworkError,
    DownloadError,
    GitHubAPIError,
    ConfigurationError,
)

# UI (CLI layer only)
from my_unicorn.ui.display import ProgressDisplay
```

### Testing Patterns

```python
import pytest
from unittest.mock import Mock, AsyncMock

from my_unicorn.core.protocols.progress import NullProgressReporter, ProgressReporter

# Null reporter for simple tests
def test_with_null_reporter():
    reporter = NullProgressReporter()
    service = MyService(progress_reporter=reporter)
    # reporter is a no-op, safe for testing

# Mock reporter for verification
def test_progress_updates():
    reporter = Mock(spec=ProgressReporter)
    reporter.is_active.return_value = True
    reporter.add_task.return_value = "task-123"
    
    service = MyService(progress_reporter=reporter)
    service.do_work()
    
    reporter.add_task.assert_called_once()
    reporter.finish_task.assert_called_with("task-123", success=True)
```

---

## Related Documentation

- [Architecture Review](../../plan/code-review/core-architecture-review.md)
- [Developer Guide](../../docs/developers.md)
- [Requirements](../../plan/current/requirements.md)
- [Design Document](../../plan/current/design.md)
- [Task Tracking](../../plan/current/tasks.md)

---

**Last Updated:** February 2, 2026
