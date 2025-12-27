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

- `my_unicorn/` - Main application directory (e.g. src)
    - `catalog/` - AppImage catalog data (owner, repo, verification logic etc.)
        - `appflowy.json` - AppFlowy catalog config
        - `zen-browser.json` - Zen Browser catalog config
    - `cli/` - CLI interface (parser, runner)
    - `commands/` - Command handlers
        - `auth.py` - Auth command handler
        - `backup.py` - Backup command handler
        - `base.py` - Base command handler
        - `cache.py` - Cache command handler
        - `catalog.py` - Catalog command handler (renamed from list.py)
        - `config.py` - Config command handler
        - `install.py` - Install command handler
        - `migrate.py` - Migration command handler (v1→v2 config migration)
        - `remove.py` - Remove command handler
        - `update.py` - Update command handler
        - `upgrade.py` - Upgrade command handler
    - `migration/` - Config migration modules
        - `base.py` - Common migration utilities
        - `app_config.py` - App config v1→v2 migration
        - `global_config.py` - Global config migration
    - `schemas/` - JSON schemas for config validation
    - `utils/` - Utility functions
    - `verification/` - Checksum verification logic
    - auth.py: Authentication handler module for github token management
    - backup.py: Backup configuration module
    - cache.py: Cache management module
    - config.py: Configuration management module
    - config_migration.py: Configuration migration module
    - constants.py: Constants module
    - desktop_entry.py: Desktop entry creation module
    - download.py: Download module that downloads AppImage, checksum files
    - exceptions.py: Exception handling module
    - file_ops.py: File operations module
    - github_client.py: GitHub API client module for requests
    - icon.py: Icon management module
    - install.py: Installation module
    - logger.py: Logging module
    - main.py: Main entry point for the application
    - progress.py: Progress bar module using ASCII backend
    - update.py: Update module that updates AppImages
    - upgrade.py: Upgrade module that upgrades my-unicorn
- `scripts/`: Scripts for various tasks
- `tests/`: Test files written in Python using pytest
- setup.sh: Setup script for installation my-unicorn
- run.py: my-unicorn development entry point

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

[raw_api_returned_data.json](/docs/raw_api_returned_data.json)
