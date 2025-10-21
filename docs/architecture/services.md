---
title: Services
slug: services
sidebar_label: Services
toc: true
---

# Service layer (download, storage, verification, icon, cache, progress)

Purpose

- Document the service abstractions used by the CLI and templates.
- Show API signatures, configuration options, realistic usage examples tied to code, testing guidance and troubleshooting steps.

Quickstart (CLI-level)

```bash
# Typical command that exercises services (download, verify, icon extraction, storage)
my-unicorn install appflowy
```

This flow ultimately uses services implemented in:

- Download service: [`my_unicorn/download.py`](../my_unicorn/download.py:1)
- Storage service: [`my_unicorn/storage.py`](../my_unicorn/storage.py:1)
- Verification services: [`my_unicorn/verification/verify.py`](../my_unicorn/verification/verify.py:1) and [`my_unicorn/verification/strategies.py`](../my_unicorn/verification/strategies.py:1)
- Icon service: [`my_unicorn/services/icon_service.py`](../my_unicorn/services/icon_service.py:1)
- Cache service: [`my_unicorn/services/cache.py`](../my_unicorn/services/cache.py:1)
- Progress service: [`my_unicorn/services/progress.py`](../my_unicorn/services/progress.py:1)

Service responsibilities and API (short)

- DownloadService
    - Purpose: download release assets and checksum files, expose typed assets (e.g., IconAsset).
    - Typical instantiation: created with optional progress service in [`my_unicorn/commands/install.py:66-74`](../my_unicorn/commands/install.py:66)
    - Key methods (observed usage):
        - async download_asset(asset: dict, dest: Path) -> Path
        - async download_url(url: str, dest: Path) -> Path
    - Config: uses network timeouts and connector limits set in CLI handler (see session creation at [`my_unicorn/commands/install.py:416-421`](../my_unicorn/commands/install.py:416))

- StorageService
    - Purpose: perform installation steps (move AppImage to storage, set exec bit, write desktop entries).
    - Constructed in `InstallCommand` via: `StorageService(install_dir)` — [`my_unicorn/commands/install.py:57`](../my_unicorn/commands/install.py:57)
    - Key methods:
        - install_appimage(src: Path, name: str) -> Path
        - backup_installed(app_name: str) -> Path

- VerificationService (and strategies)
    - Purpose: verify downloaded AppImages via digest or checksum files.
    - Entry point: verification factory and service under [`my_unicorn/verification/`](../my_unicorn/verification/:1)
    - Typical flow: detection -> strategy -> verify (see [`my_unicorn/verification/detection.py`](../my_unicorn/verification/detection.py:1))
    - Config: catalog and app-config flags `verification.digest`, `verification.checksum_file`, `checksum_hash_type` (see catalog examples in [`docs/catalog-format.md`](../docs/catalog-format.md:1)).

- IconService
    - Purpose: extract icon from AppImage or fetch icon URL and save to icons dir.
    - Used by installer templates; imports: [`my_unicorn/download.py`](../my_unicorn/download.py:1) and implemented in [`my_unicorn/services/icon_service.py`](../my_unicorn/services/icon_service.py:1).
    - Key methods:
        - async ensure_icon(app_name: str, appimage_path: Path, icon_conf: dict) -> Path

- CacheService
    - Purpose: cache release metadata to avoid hitting GitHub rate limits.
    - CLI cache commands implemented in parser (`cache clear`, `cache stats`) — see [`my_unicorn/cli/parser.py:421-447`](../my_unicorn/cli/parser.py:421).
    - Implementation: [`my_unicorn/services/cache.py`](../my_unicorn/services/cache.py:1)

- ProgressService
    - Purpose: provide progress bars and an API task abstraction used across templates and GitHub client.
    - Created via helper: `get_progress_service()` used in install flow when show_progress enabled — see [`my_unicorn/commands/install.py:69-73`](../my_unicorn/commands/install.py:69).
    - Key API (observed usage):
        - async with progress_service.session(total_ops): ...
        - await progress_service.create_api_fetching_task(endpoint=..., total_requests=...)
        - await progress_service.finish_task(task_id, success=True)

Realistic usage example (install path)

- Handler constructs dependencies and services then passes them into templates:
    - See construction: [`my_unicorn/commands/install.py:275-283`](../my_unicorn/commands/install.py:275)
    - Example snippet in code:
        - Dependencies dict passed to factory:
            - "download_service": self.download_service
            - "storage_service": self.storage_service
            - "session": self.session
            - "config_manager": self.config_manager
            - "github_client": self.github_client
            - "catalog_manager": self.catalog_manager

Minimal reproducible example (programmatic)

```python
# python
import asyncio
from pathlib import Path
from aiohttp import ClientSession
from my_unicorn.commands.install import InstallCommand
from my_unicorn.config import ConfigManager

async def demo():
    cfg = ConfigManager()
    g = cfg.load_global_config()
    install_dir = g["directory"].storage
    timeout = aiohttp.ClientTimeout(total=600)
    async with ClientSession(timeout=timeout) as session:
        from my_unicorn.github_client import GitHubClient
        github_client = GitHubClient(session)
        catalog_manager = cfg.catalog_manager
        cmd = InstallCommand(session, github_client, catalog_manager, cfg, install_dir)
        results = await cmd.execute(["appflowy"], show_progress=False)
        print(results)

asyncio.run(demo())
```

(See `InstallCommand` constructor at [`my_unicorn/commands/install.py:27-35`](../my_unicorn/commands/install.py:27) and its `execute()` signature at [`my_unicorn/commands/install.py:76`](../my_unicorn/commands/install.py:76).)

Testing

- Unit tests for services located under `tests/services/` (e.g., `tests/services/test_icon_service.py`) — run:

```bash
source .venv/bin/activate
pytest -q tests/services/ -q
```

- Use mocks for network-dependent services (see tests which patch DownloadService and GitHub fetchers in `tests/test_update.py`).

Troubleshooting

- Common errors:
    - Network timeouts: tune `timeout_seconds` in global config (`my_unicorn/config.py:391` defaults).
    - Missing catalog or app config: `DirectoryManager.validate_catalog_directory()` will raise — [`my_unicorn/config.py:318`](../my_unicorn/config.py:318).
    - Verification failures: inspect verification config in app file under `~/.config/my-unicorn/apps/` or catalog entry; check digest vs checksum source.

Diagnostics to collect when filing issues

- Verbose logs (set `log_level` to DEBUG in global config) and capture:
    - CLI command + args
    - Logs from configured logs directory (see `global_cfg["directory"].logs` in [`my_unicorn/config.py:391`](../my_unicorn/config.py:391))
    - Cached release file (if cache used): path in `global_cfg["directory"].cache`
    - Repro script (minimal example above), and full stack trace.

Cross references

- CLI mapping and examples: [`docs/cli.md`](../docs/cli.md:1)
- Templates (how services are injected): [`docs/templates.md`](../docs/templates.md:1)
- Verification strategies: [`my_unicorn/verification/strategies.py`](../my_unicorn/verification/strategies.py:1)
- Icon service tests: [`tests/services/test_icon_service.py`](../tests/services/test_icon_service.py:1)

End
