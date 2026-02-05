# Developers wiki for my-unicorn 🦄

> [!NOTE]
> This document provides an overview of the architecture and key components of the My Unicorn project for developers.

## The Stop Rule for code complexity

If you feel the need to introduce a new pattern, stop and ask:
“Can this just be a function or a service?”

90% of the time, the answer is yes.

## Architecture Overview

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

- `src/my_unicorn/` - Main package source code
    - `catalog/` - Application catalog JSON files
    - `cli/` - CLI argument parsing and command runners
        - `commands/` - Individual command handlers (install, update, remove, catalog, etc.)
        - `parser.py` - Argument parser setup
        - `runner.py` - Command execution orchestration
    - `config/` - Configuration management
        - `global.py` - Global INI configuration
        - `app.py` - Per-app JSON configuration
        - `catalog.py` - Application catalog loader
        - `migration/` - Configuration migration logic
        - `schemas/` - JSON schema validation
    - `domain/` - Domain models and business logic
        - `asset.py` - AppImage asset handling
        - `release.py` - Release information
        - `verification/` - Hash verification logic
        - `constants.py` - Application constants (versions, paths, defaults)
        - `types.py` - Type definitions and dataclasses
    - `infrastructure/` - External integrations and I/O
        - `github/` - GitHub API client
        - `cache.py` - Release cache management
        - `download.py` - File download logic
        - `desktop_entry.py` - Desktop file generation
        - `icon.py` - Icon extraction and management
        - `file_ops.py` - File system operations
        - `auth.py` - Authentication handling
        - `token.py` - Token storage and retrieval
    - `ui/` - User interface and display
        - `progress.py` - Progress bar management
        - `display.py` - Output formatting and rendering
        - `formatters.py` - Text formatters
    - `utils/` - Utility functions and helpers
    - `workflows/` - Business workflows (use cases)
        - `install.py` - Install workflow
        - `update.py` - Update workflow
        - `remove.py` - Remove workflow
        - `services/` - Workflow helper services
    - `exceptions.py` - Custom exception classes
    - `logger.py` - Logging setup and configuration
    - `main.py` - Application entry point
- `tests/` - Comprehensive test suite (Same structure as src/my_unicorn/)
    - `cli/` - CLI tests
    - `commands/` - Command handler tests
    - `integration/` - Integration tests
    - `migration/` - Migration tests
    - `services/` - Service tests
    - `schemas/` - Schema validation tests
- `docs/` - Documentation and design decisions
- `scripts/` - Helper scripts for development

## API

> Currently, the app is use only github api but it will be extended to support other platforms in the future.

### Example of the api usage for the latest release api for zen-browser

<https://api.github.com/repos/zen-browser/desktop/releases/latest>

### Example of the beta api usage for FreeTube

<https://api.github.com/repos/FreeTubeApp/FreeTube/releases>

### What we fetch from the API?

#### Information that we use for downloads

> [!NOTE]
> There is also same name, digest, browser_download_url for checksum_files which we use them if the asset does not provide a digest.

##### Example of asset metadata for AppImage

```json
"tag_name": "v0.23.5-beta",
"prerelease": true,
"assets": [
  {
    "name": "freetube-0.23.5-amd64.AppImage",
    "content_type": "application/vnd.appimage",
    "digest": null,
    "size": 99711480,
    "browser_download_url": "https://github.com/FreeTubeApp/FreeTube/releases/download/v0.23.5-beta/freetube-0.23.5-amd64.AppImage"
  }
```

##### Example of aset metadata for Checksumfile

```json
{
      "url": "https://api.github.com/repos/pbek/QOwnNotes/releases/assets/289339017",
      "id": 289339017,
      "node_id": "RA_kwDOAaKly84RPvaJ",
      "name": "QOwnNotes-x86_64-Qt6-experimental.AppImage.sha256sum",
      "label": "",
      "content_type": "text/plain",
      "state": "uploaded",
      "size": 109,
      "digest": "sha256:076c2cb3731dac2d18c561def67423c01ec1843d6ed3dc815bd6b8c55d972694",
      "download_count": 2,
      "created_at": "2025-09-03T20:47:02Z",
      "updated_at": "2025-09-03T20:47:02Z",
      "browser_download_url": "https://github.com/pbek/QOwnNotes/releases/download/v25.9.1/QOwnNotes-x86_64-Qt6-experimental.AppImage.sha256sum"
    },
```

### Example of raw data from github API for zen-browser

> This example also shows app hashes information on the release description.
>
> This example of latest release but beta is similar to this one. Only changes beta provide all the assets and we use the asset 0 for latest version informations, latest release provide directly to that asset 0.

[raw_api_returned_data.json](/docs/dev/data/raw_api_returned_data.json)

---

## Dependency Injection

My Unicorn uses dependency injection (DI) to decouple service creation from usage. The `ServiceContainer` manages service lifecycles and wires dependencies together.

### ServiceContainer

The `ServiceContainer` class in `cli/container.py` centralizes service instantiation:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ServiceContainer                                │
├─────────────────────────────────────────────────────────────────────────┤
│  Inputs:                                                                │
│  ┌──────────────────┐    ┌────────────────────┐                        │
│  │  ConfigManager   │    │  ProgressReporter  │                        │
│  └────────┬─────────┘    └─────────┬──────────┘                        │
│           │                        │                                    │
│           ▼                        ▼                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Lazy-Loaded Services                          │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │  │
│  │  │  Session   │  │ AuthMgr    │  │ CacheMgr   │  │ FileOps    │  │  │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  │  │
│  │        │               │               │               │         │  │
│  │  ┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐  │  │
│  │  │ Download   │  │ GitHub     │  │ Verify     │  │ PostProc   │  │  │
│  │  │ Service    │  │ Client     │  │ Service    │  │ Processor  │  │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Factory Methods:                                                       │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────┐  │
│  │ create_install_     │  │ create_update_      │  │ create_remove_ │  │
│  │ handler()           │  │ manager()           │  │ service()      │  │
│  └─────────────────────┘  └─────────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

Key characteristics:

- **Lazy initialization**: Services are created only when first accessed
- **Singleton pattern**: Each service exists once per container instance
- **Dependency wiring**: Services receive their dependencies automatically
- **Resource cleanup**: `cleanup()` method releases resources (e.g., HTTP sessions)

### ProgressReporter Protocol

The `ProgressReporter` protocol in `core/protocols/progress.py` decouples core services from UI:

```
┌─────────────────────────────────────────────────────────────────┐
│                      UI Layer                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   ProgressDisplay                        │   │
│  │  (Implements ProgressReporter - shows progress bars)     │   │
│  └──────────────────────────┬──────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────┘
                              │ implements
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ProgressReporter Protocol                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ is_active()  │ │ add_task()   │ │ update_task()            │ │
│  │ -> bool      │ │ -> str       │ │ finish_task()            │ │
│  │              │ │              │ │ get_task_info() -> dict  │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │ implements
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Core/Testing Layer                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 NullProgressReporter                     │   │
│  │  (Null object pattern - all methods are no-ops)          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

Protocol methods:

| Method | Purpose |
|--------|---------|
| `is_active()` | Check if progress reporting is enabled |
| `add_task(name, progress_type, total)` | Start tracking a new task, returns task ID |
| `update_task(task_id, completed, description)` | Update task progress |
| `finish_task(task_id, success, description)` | Mark task complete |
| `get_task_info(task_id)` | Get task state for testing |

`ProgressType` enum categorizes operations: `DOWNLOAD`, `VERIFICATION`, `EXTRACTION`, `API`, `PROCESSING`, `INSTALLATION`, `UPDATE`.

### Usage Examples

#### Creating services via container

```python
from my_unicorn.cli.container import ServiceContainer
from my_unicorn.config import ConfigManager
from my_unicorn.core.protocols.progress import NullProgressReporter

# Create container with dependencies
config = ConfigManager()
progress = NullProgressReporter()  # Or ProgressDisplay for CLI
container = ServiceContainer(config, progress)

try:
    # Get workflow handlers from factory methods
    install_handler = container.create_install_handler()
    await install_handler.install_from_catalog("zen-browser")

    # Or access services directly via properties
    github_client = container.github_client
    releases = await github_client.get_releases("owner", "repo")
finally:
    await container.cleanup()
```

#### Adding a new service to the container

1. Add instance variable in `__init__`:

```python
self._my_service: MyService | None = None
```

1. Add lazy-loading property:

```python
@property
def my_service(self) -> MyService:
    """My service description (singleton, lazy-loaded)."""
    if self._my_service is None:
        self._my_service = MyService(
            dependency=self.some_other_service,
            progress_reporter=self.progress,
        )
    return self._my_service
```

1. Use in factory methods if needed:

```python
def create_my_handler(self) -> MyHandler:
    return MyHandler(
        my_service=self.my_service,
        progress_reporter=self.progress,
    )
```

#### Using ProgressReporter in services

```python
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)

class MyService:
    def __init__(
        self,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        # Null object pattern: no None checks needed
        self.progress = progress_reporter or NullProgressReporter()

    async def do_work(self, items: list[str]) -> None:
        task_id = self.progress.add_task(
            "Processing items",
            ProgressType.PROCESSING,
            total=len(items),
        )

        for i, item in enumerate(items):
            # Do work...
            self.progress.update_task(task_id, completed=i + 1)

        self.progress.finish_task(task_id, success=True)
```

### When to Use DI vs Direct Instantiation

| Scenario | Approach |
|----------|----------|
| CLI commands that need multiple services | Use `ServiceContainer` |
| Services with shared resources (HTTP session) | Use `ServiceContainer` |
| Unit tests needing isolated components | Direct instantiation with mocks |
| Simple scripts or one-off operations | Direct instantiation |
| Services requiring progress reporting | Inject via `ServiceContainer` |

### Resource Cleanup

Always use `cleanup()` in a finally block to release resources:

```python
container = ServiceContainer(config, progress)
try:
    handler = container.create_install_handler()
    await handler.install_from_catalog(app_name)
finally:
    await container.cleanup()  # Closes HTTP session
```

The `cleanup()` method:

- Closes the shared `aiohttp.ClientSession`
- Is idempotent (safe to call multiple times)
- Sets internal references to `None` to prevent reuse
