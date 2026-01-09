# Developers wiki for my-unicorn 🦄

> [!NOTE]
> This document provides an overview of the architecture and key components of the My Unicorn project for developers.

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
        - `commands/` - Individual command handlers (install, update, remove, list, etc.)
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

[raw_api_returned_data.json](/docs/data/raw_api_returned_data.json)
