# Config Management

> [!IMPORTANT]
> **Config Version 2.0.0** - This document describes the v2 configuration format introduced in my-unicorn 2.0.0.
> If you're upgrading from v1.x, run `my-unicorn migrate` to convert your configs.

My Unicorn uses a hybrid configuration structure where:

- **Catalog apps**: Store minimal state (version, verification, icon) + reference to catalog file
- **URL-installed apps**: Store complete configuration in overrides section

This reduces duplication and makes catalog apps easier to maintain.

## Global Config (settings.conf)

**Version**: 1.0.2  
**Location**: `~/.config/my-unicorn/settings.conf`

```INI
# Configuration version for migration support
config_version = 1.0.2

# This is the maximum number of concurrent downloads allowed.
# Please note that this value shouldn't be too high, as it may trigger rate limiting.
# The GitHub API allows around 30–50 concurrent requests, but this limit may change in the future.
max_concurrent_downloads = 5

# Maximum number of backups to keep for each AppImage.
max_backup = 1

# Logging level for the application.
# Supported levels: DEBUG, INFO, WARNING, ERROR
log_level = "INFO"

[network]
# Number of retry attempts for failed downloads
retry_attempts = 3

# Timeout for network requests.
timeout_seconds = 10

[directory]
# Directory for storing the code repository.
# The CLI script uses this directory to store the latest code files for updating packages.
repo = "~/.local/share/my-unicorn-repo/"

# Directory for storing package-related files, including virtual environments (.venv).
package = "~/.local/share/my-unicorn/"

# Default directory for downloaded AppImages, checksum files, and icons.
download = "~/Downloads"

# Directory for storing AppImages, backups, and icons after installation.
storage = "~/Applications"
backup = "~/Applications/backups"
icon = "~/Applications/icons"

# Directory for storing configuration files, logs, cache, and temporary files.
settings = "~/.config/my-unicorn/"
logs = "~/.config/my-unicorn/logs"
cache = "~/.config/my-unicorn/cache"
tmp = "~/.config/my-unicorn/tmp"
```

## Catalog Configuration (v2)

**Version**: 2.0.0  
**Location**: `src/my_unicorn/catalog/*.json` (bundled in package)

Catalog entries define metadata for supported applications. These are maintained by the project and distributed with my-unicorn.

### Catalog Entry JSON Structure

```jsonc
{
  "config_version": "2.0.0",
  "metadata": {
    "name": "appflowy",  // Used as catalog_ref in app configs
    "display_name": "AppFlowy",
    "description": "Open source Notion alternative with offline-first approach"
  },
  "source": {
    "type": "github",
    "owner": "AppFlowy-IO",
    "repo": "AppFlowy",
    "prerelease": false  // true to use beta/prerelease versions
  },
  "appimage": {
    "naming": {
      // Template for renaming AppImage after download
      "template": "{name}-{version}-linux-{arch}.AppImage",
      "target_name": "appflowy",  // Final name without extension
      "architectures": ["x86_64", "amd64"]  // Preferred architecture suffixes
    }
  },
  "verification": {
    "method": "digest",  // "digest", "checksum_file", or "skip"
    // For checksum_file method:
    "checksum_files": [
      {
        "filename": "latest-linux.yml",
        "hash_type": "sha512"
      }
    ]
  },
  "icon": {
    "method": "extraction",  // "extraction" or "download"
    "name": "appflowy.png",
    // For download method:
    "url": ""  // URL to icon file
  }
}
```

**Key Fields**:

- `metadata.name`: Used as `catalog_ref` in app state configs (must match filename)
- `metadata.description`: Shown in `catalog --available` command
- `verification.method`:
    - `digest`: Use GitHub API digest (SHA256 from release assets)
    - `checksum_file`: Download and parse checksum file (SHA256SUMS.txt, latest-linux.yml)
    - `skip`: No verification (not recommended)

#### App State Configuration (v2)

**Version**: 2.0.0  
**Location**: `~/.config/my-unicorn/apps/*.json`

App state configs track installed applications. The structure differs based on installation source.

##### Catalog App State (Minimal)

Apps installed from catalog store only state + reference to catalog file:

```json
{
  "config_version": "2.0.0",
  "source": "catalog",
  "catalog_ref": "appflowy",  // Maps to catalog/appflowy.json
  "state": {
    "version": "0.9.5",
    "installed_date": "2025-12-27T15:30:07.003745",
    "installed_path": "/home/developer/Applications/appflowy.AppImage",
    "verification": {
      "passed": true,
      "methods": [
        {
          "type": "digest",
          "status": "passed",
          "algorithm": "SHA256",
          "expected": "sha256:bd8b9374ec9c59fa98b08080fa7f96696d135e6173213d039939f94cc757c587",
          "computed": "bd8b9374ec9c59fa98b08080fa7f96696d135e6173213d039939f94cc757c587",
          "source": "github_api"
        }
      ]
    },
    "icon": {
      "installed": true,
      "method": "extraction",  // or "download"
      "path": "/home/developer/Applications/icons/appflowy.svg"
    }
  }
}
```

**Effective Config**: At runtime, my-unicorn merges catalog file + state to get complete configuration via `get_effective_config()`.

### URL App State (Full Config)

Apps installed via URL store complete configuration in overrides:

```json
{
  "config_version": "2.0.0",
  "source": "url",
  "catalog_ref": null,
  "state": {
    "version": "0.6.48",
    "installed_date": "2025-12-27T12:38:28.387230",
    "installed_path": "/home/developer/Applications/nuclear.AppImage",
    "verification": {
      "passed": true,
      "methods": [
        {
          "type": "digest",
          "status": "passed",
          "algorithm": "SHA256",
          "expected": "sha256:937a8658f9fe3b891acecaeb64060722f4abae2c7d2cd9e726064626a9496c91",
          "computed": "937a8658f9fe3b891acecaeb64060722f4abae2c7d2cd9e726064626a9496c91",
          "source": "github_api"
        }
      ]
    },
    "icon": {
      "installed": true,
      "method": "extraction",
      "path": "/home/developer/Applications/icons/nuclear.png"
    }
  },
  "overrides": {
    "metadata": {
      "name": "nuclear",
      "display_name": "nuclear",
      "description": ""
    },
    "source": {
      "type": "github",
      "owner": "nukeop",
      "repo": "nuclear",
      "prerelease": false
    },
    "appimage": {
      "naming": {
        "template": "",
        "target_name": "nuclear",
        "architectures": ["x86_64", "amd64"]
      }
    },
    "verification": {
      "method": "digest"
    },
    "icon": {
      "method": "extraction",
      "name": "nuclear.png"
    }
  }
}
```

**Effective Config**: For URL apps, `get_effective_config()` merges overrides + state.

### Verification State Details

The `verification` object in state tracks all verification attempts:

```json
"verification": {
  "passed": true,  // Overall verification result
  "methods": [
    {
      "type": "digest",           // digest, checksum_file, or skip
      "status": "passed",         // passed, failed, skipped
      "algorithm": "SHA256",      // SHA1, SHA256, SHA512, MD5
      "expected": "sha256:...",   // Expected hash with prefix
      "computed": "...",          // Computed hash (no prefix)
      "source": "github_api"      // github_api, checksum_file, or skip
    }
  ]
}
```

**When no verification available**:

```json
"verification": {
  "passed": false,
  "methods": [
    {
      "type": "skip",
      "status": "skipped",
      "message": "No verification methods available (dev did not provide checksums)"
    }
  ]
}
```

#### Migration from v1 to v2

**Migration Command**:

```bash
my-unicorn migrate
```

**What it does**:

1. Detects v1 configs (config_version="1.0.0") in `~/.config/my-unicorn/apps/`
2. Creates backup files (`.json.backup`) before migration
3. Converts to v2 format:
   - Catalog apps: Creates minimal config with catalog_ref
   - URL apps: Moves full config to overrides section
4. Validates migrated configs against JSON schema
5. Reports success/failure for each app

**Backup location**: `~/.config/my-unicorn/apps/backups/`

**Automatic migration**: Not performed automatically. You must run `my-unicorn migrate` manually.

#### Config Version Detection

**Catalog Config**:

- v2: Has `config_version="2.0.0"`
- v1: No `config_version`, has `owner`/`repo` at top level

**App State Config**:

- v2: `config_version="2.0.0"`, has `state` object
- v1: `config_version="1.0.0"`, flat structure with `appimage.version`

#### JSON Schema Validation

My Unicorn validates all configs against JSON schemas:

- Schemas location: `src/my_unicorn/schemas/`
- Validation points: Load/save operations, post-migration
- Error messages: Include JSON path and description

**Example error**:

```
Config validation failed at '/state/verification/methods/0/type': 
'invalid_type' is not one of ['digest', 'checksum_file', 'skip']
```

For complete examples, see [docs/example_app_state_configs/](example_app_state_configs/).

#### Backup metadata.json implementation

##### 1. **Backup Storage Structure** ✅

```
~/Applications/backups/
  ├── appflowy/
  │   ├── appflowy-1.2.3.AppImage
  │   ├── appflowy-1.3.0.AppImage
  │   └── metadata.json
  └── obsidian/
      ├── obsidian-1.9.1.AppImage
      ├── obsidian-1.9.10.AppImage
      └── metadata.json
```

##### 2. **Metadata Structure (metadata.json)** ✅

> [!NOTE]
> file path: `~/Applications/backups/obsidian/metadata.json`

```json
{
 "versions": {
  "1.9.1": {
   "created": "2025-08-19T14:36:49.868125",
   "filename": "obsidian-1.9.1.AppImage",
   "sha256": "24471d25ed4d7d797a20a8ddf7b81ec43ae337f9ce495514dfdbb893307472b7",
   "size": 125682911
  },
  "1.9.10": {
   "created": "2025-08-19T14:01:21.787195",
   "filename": "obsidian-1.9.10.AppImage",
   "sha256": "24471d25ed4d7d797a20a8ddf7b81ec43ae337f9ce495514dfdbb893307472b7",
   "size": 125682911
  }
 }
}
```

### Cache Management

Example zen browser cache:

```bash
{
  "cached_at": "2025-08-30T16:55:48.294102+00:00",
  "ttl_hours": 24,
  "release_data": {
    "owner": "zen-browser",
    "repo": "desktop",
    "version": "1.15.2b",
    "prerelease": false,
    "assets": [
      {
        "name": "zen-x86_64.AppImage",
        "digest": "sha256:9035c485921102f77fdfaa37536200fd7ce61ec9ae8f694c0f472911df182cbd",
        "size": 109846928,
        "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.2b/zen-x86_64.AppImage"
      }
    ],
    "original_tag_name": "1.15.2b"
  }
}
```
