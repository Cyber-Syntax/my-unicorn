---
title: Configuration
slug: configuration
sidebar_label: Configuration
toc: true
---

# Configuration (Global & per-app)

Purpose

- Describe global INI settings and per-app JSON configs used by the CLI.
- Show where defaults come from and how to change them safely.

Quickstart — view or create defaults

```bash
# Print the path where the CLI will place settings (creates defaults on first use)
python -c "from my_unicorn.config import config_manager; print(config_manager.settings_file)"
```

Where the code lives

- Global and per-app configuration implementation: [`my_unicorn/config.py`](../my_unicorn/config.py:1)  
- ConfigManager facade: [`my_unicorn/config.py`](../my_unicorn/config.py:869)  
- DirectoryManager (path resolution): [`my_unicorn/config.py`](../my_unicorn/config.py:255)  
- GlobalConfigManager.load_global_config(): [`my_unicorn/config.py`](../my_unicorn/config.py:406)  
- AppConfigManager.load_app_config(): [`my_unicorn/config.py`](../my_unicorn/config.py:714)  

Global INI file format

- Location: the default settings file is produced under the path returned by [`DirectoryManager.settings_file`](../my_unicorn/config.py:286).
- The file contains three logical groups: [DEFAULT], [network], [directory].

Default values and where they are defined

- Defaults are produced by `GlobalConfigManager.get_default_global_config()` — see implementation at [`my_unicorn/config.py`](../my_unicorn/config.py:373).
- Example defaults include:

```INI
config_version = 1.0.0
max_concurrent_downloads = 5
max_backup = 1
batch_mode = true
locale = en_US
log_level = INFO
console_log_level = WARNING
[network]
retry_attempts = 3
timeout_seconds = 10
[directory]
repo = ~/.local/share/my-unicorn-repo
package = ~/.local/share/my-unicorn
download = ~/Downloads
storage = ~/Applications
backup = ~/Applications/backups
icon = ~/Applications/icons
settings = ~/.config/my-unicorn/settings.conf
logs = ~/.config/my-unicorn/logs
cache = ~/.config/my-unicorn/cache
tmp = ~/.config/my-unicorn/tmp
```

Editing the INI safely

- The parser strips inline comments using `CommentAwareConfigParser` — see [`my_unicorn/config.py`](../my_unicorn/config.py:49).
- Use the CLI to inspect current values: `my-unicorn config --show` (parser entry: [`my_unicorn/cli/parser.py`](../my_unicorn/cli/parser.py:399)).
- If migration is needed the code attempts to migrate existing config and will fall back to defaults (see `GlobalConfigManager.load_global_config()` at [`my_unicorn/config.py`](../my_unicorn/config.py:406)).

Programmatic API

- Load the global configuration:

```python
# python
from my_unicorn.config import ConfigManager
cfg = ConfigManager()
global_cfg = cfg.load_global_config()  # see [`my_unicorn/config.py`](my_unicorn/config.py:406)
print(global_cfg["directory"].storage)
```

- Save updated config:

```python
# python
cfg.save_global_config(global_cfg)  # see [`my_unicorn/config.py`](my_unicorn/config.py:923)
```

Per-app JSON configuration

- Stored under directory: [`DirectoryManager.apps_dir`](../my_unicorn/config.py:291)  
- Managed by `AppConfigManager` — see [`my_unicorn/config.py`](../my_unicorn/config.py:702)  
- Example app config structure:

```json
{
 "config_version": "1.0.0",
 "source": "catalog",
 "appimage": {
  "version": "0.9.5",
  "name": "appflowy.AppImage",
  "rename": "appflowy",
  "name_template": "{rename}-{latest_version}-linux-{characteristic_suffix}",
  "characteristic_suffix": ["x86_64","amd64"],
  "installed_date": "2025-08-03T14:57:00.204029",
  "digest": "sha256:..."
 },
 "owner": "AppFlowy-IO",
 "repo": "AppFlowy",
 "verification": { "digest": true, "skip": false, "checksum_file": "", "checksum_hash_type": "sha256" },
 "icon": { "extraction": true, "url": "", "name": "appflowy.svg", "installed": true, "path": "/home/user/Applications/icons/appflowy.svg" }
}
```

How app configs are loaded and migrated

- Loading: `AppConfigManager.load_app_config(app_name)` — [`my_unicorn/config.py`](../my_unicorn/config.py:714)  
- Migration: old `hash` field (if present) is migrated to `digest` by `_migrate_app_config()` — see [`my_unicorn/config.py`](../my_unicorn/config.py:796).

Catalog entries

- Bundled catalog files live in: [`my_unicorn/catalog/`](../my_unicorn/catalog/:1)  
- Catalog access occurs through `CatalogManager.load_catalog_entry()` — implementation at [`my_unicorn/config.py`](../my_unicorn/config.py:839).

Testing & validation

- Unit tests around configuration live in `tests/test_config.py` and `tests/test_config_migration.py`.
- Run a focused test:

```bash
source .venv/bin/activate
pytest -q tests/test_config.py -q
```

Troubleshooting

- If bundled catalog files are missing the app will raise on startup. `DirectoryManager.validate_catalog_directory()` checks presence — see [`my_unicorn/config.py`](../my_unicorn/config.py:318).
- If loading fails, the CLI will attempt migration then fall back to defaults and write a new settings file — see error-handling around [`my_unicorn/config.py`](../my_unicorn/config.py:456).
- Logs are written to the configured logs directory (`global_cfg["directory"].logs`) — see the default path creation in `GlobalConfigManager.get_default_global_config()` at [`my_unicorn/config.py`](../my_unicorn/config.py:391).

Minimal reproducible example

```python
# python
from my_unicorn.config import ConfigManager
cfg = ConfigManager()
g = cfg.load_global_config()
print("Download dir:", g["directory"].download)
```

Cross references

- CLI reference: [`docs/cli.md`](../docs/cli.md:1)
- Catalog format: [`docs/catalog-format.md`](../docs/catalog-format.md:1) (to be created)
- Templates & install flow: [`my_unicorn/template`](../my_unicorn/template/:1)

End of configuration guide
