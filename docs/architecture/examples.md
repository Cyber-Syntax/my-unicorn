---
title: Examples & Minimal Reproducibles
slug: examples
sidebar_label: Examples
toc: true
---

# Examples and minimal reproducible snippets

Purpose

- Provide runnable examples that exercise core flows (install, update, backup) without needing the full CLI.
- Each example references the relevant code locations.

Prereqs

- Create and activate virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1) Programmatic install (minimal)

- Uses `InstallCommand` directly. See constructor at [`my_unicorn/commands/install.py:27`](../my_unicorn/commands/install.py:27).

```python
# python
import asyncio
from pathlib import Path
from aiohttp import ClientSession, ClientTimeout
from my_unicorn.commands.install import InstallCommand
from my_unicorn.config import ConfigManager

async def quick_install():
    cfg = ConfigManager()
    g = cfg.load_global_config()
    install_dir = g["directory"].storage
    timeout = ClientTimeout(total=600)
    async with ClientSession(timeout=timeout) as session:
        from my_unicorn.github_client import GitHubClient
        github_client = GitHubClient(session)
        catalog_manager = cfg.catalog_manager
        cmd = InstallCommand(session, github_client, catalog_manager, cfg, install_dir)
        results = await cmd.execute(["appflowy"], show_progress=False)
        print(results)

asyncio.run(quick_install())
```

2) Check updates programmatically

- Update flow uses `UpdateTemplateFactory` and `UpdateContext` (`my_unicorn/commands/update.py:64`).

```python
# python
import asyncio
from argparse import Namespace
from my_unicorn.commands.update import UpdateHandler
from my_unicorn.config import ConfigManager

# Reuse CLI handler programmatically (less common). Prefer templates directly for advanced scripts.
```

3) Read an app config

- App configs are JSON files in `~/.config/my-unicorn/apps/` and loaded with `ConfigManager.load_app_config()` (`my_unicorn/config.py:714`).

```python
# python
from my_unicorn.config import ConfigManager
cfg = ConfigManager()
print(cfg.load_app_config("joplin"))
```

4) Inspect catalog entry used by installer

```python
# python
from my_unicorn.config import ConfigManager
cfg = ConfigManager()
print(cfg.load_catalog_entry("appflowy"))  # See catalog: my_unicorn/catalog/appflowy.json
```

5) Reproduce a backup/restore operation

- Backup commands implemented under [`my_unicorn/commands/backup.py`](../my_unicorn/commands/backup.py:1). Use CLI examples:

```bash
# Create backup
my-unicorn backup appflowy
# Restore last backup
my-unicorn backup appflowy --restore-last
```

Testing these snippets

- Run them inside the project's virtual environment to ensure imports resolve.
- Where network calls occur, tests in CI mock the GitHub client; for local runs, provide a GitHub token if rate limits are hit (see `my-unicorn auth --save-token`).

Cross references

- CLI mapping: [`docs/cli.md`](../docs/cli.md:1)
- Config manager: [`my_unicorn/config.py`](../my_unicorn/config.py:869)
- InstallCommand: [`my_unicorn/commands/install.py`](../my_unicorn/commands/install.py:24)

End of examples
