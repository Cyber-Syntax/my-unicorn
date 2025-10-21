---
title: CLI Reference
slug: cli
sidebar_label: CLI
toc: true
---

# CLI reference for my-unicorn

This document describes the command-line interface, commands, flags, and examples tied to the code.

Purpose

- Quick reference for contributors and power users implementing or debugging CLI behavior.

Quick start

```bash
# Run interactive CLI
my-unicorn
# Show help
my-unicorn --help
```

Entry point
The application entry point is implemented in [`main()`](../my_unicorn/main.py:20) at [`my_unicorn/main.py`](../my_unicorn/main.py:14). See [`async_main()`](../my_unicorn/main.py:14) for async startup.

Parser and command registration
The argument parser lives in [`CLIParser`](../my_unicorn/cli/parser.py:12). Key methods:

- [`CLIParser.__init__()`](../my_unicorn/cli/parser.py:15) — initialize with global_config.
- [`CLIParser.parse_args()`](../my_unicorn/cli/parser.py:24) — produce parsed Namespace.
- Subcommand registration is in [`_add_subcommands()`](../my_unicorn/cli/parser.py:93).

Example: install command flags (defined at parser file)
See parser lines where install args are created: [`my_unicorn/cli/parser.py`](../my_unicorn/cli/parser.py:121).

- --concurrency (default read from global config) — parser sets default from global_config at [`my_unicorn/cli/parser.py:144-148`](../my_unicorn/cli/parser.py:144).
- --no-icon / --no-verify / --no-desktop — flags at [`my_unicorn/cli/parser.py:150-163`](../my_unicorn/cli/parser.py:150).

Command handlers

- Install: implemented by [`InstallHandler.execute()`](../my_unicorn/commands/install.py:395) which uses `InstallCommand` (`my_unicorn/commands/install.py:24`).
- Update: handled by [`UpdateHandler.execute()`](../my_unicorn/commands/update.py:23).

Install flow (how CLI maps to code)

1. User runs `my-unicorn install ...` (parser registers command) — see [`my_unicorn/cli/parser.py:121`](../my_unicorn/cli/parser.py:121).
2. `InstallHandler` builds session and dependencies and constructs `InstallCommand` (`my_unicorn/commands/install.py:429-436`).
3. `InstallCommand.execute(targets, **options)` performs checks and delegates to templates — signature at [`my_unicorn/commands/install.py:76-93`](../my_unicorn/commands/install.py:76).

Install API signature

```python
async def execute(self, targets: list[str], **options: Any) -> list[dict[str, Any]]:
    ...
```

The method is defined at [`my_unicorn/commands/install.py:76`](../my_unicorn/commands/install.py:76).

Update API signature

```python
async def execute(self, args: Namespace) -> None:
    ...
```

Implemented in [`my_unicorn/commands/update.py:23`](../my_unicorn/commands/update.py:23).

Practical examples (mapped to code)

1) Install appflowy from catalog (uses CatalogManagerAdapter)

```bash
my-unicorn install appflowy
```

This triggers `CatalogManagerAdapter` in [`my_unicorn/commands/install.py:475`](../my_unicorn/commands/install.py:475) and `InstallCommand` (`my_unicorn/commands/install.py:24`).

2) Install via URL with concurrency and skip verify:

```bash
my-unicorn install https://github.com/pbek/QOwnNotes --concurrency 4 --no-verify
```

Maps to `InstallCommand.execute(..., verify_downloads=False)` — parser sets flag at [`my_unicorn/cli/parser.py:155`](../my_unicorn/cli/parser.py:155) and handler converts args to options at [`my_unicorn/commands/install.py:440-448`](../my_unicorn/commands/install.py:440).

How defaults are sourced

- Global defaults stored and parsed by [`ConfigManager`][`my_unicorn/config.py`](../my_unicorn/config.py:869). The parser uses `global_config["max_concurrent_downloads"]` when built.

Quick debugging & troubleshooting

- If commands raise a validation error, look at [`my_unicorn/commands/install.py:332-339`](../my_unicorn/commands/install.py:332) which raises ValidationError for unknown targets.
- For unexpected exceptions during main startup see startup at [`my_unicorn/main.py:20-31`](../my_unicorn/main.py:20).

Tests and running locally

- Unit tests for CLI commands live under `tests/commands/`. Example: [`tests/commands/test_install.py`](../tests/commands/test_install.py:1).
- Run tests:

```bash
# Activate venv then run pytest (see docs/wiki.md for setup.sh)
source .venv/bin/activate
pytest -q tests/commands/test_install.py -q
```

Minimal reproducible example (programmatic)
Use the `InstallCommand` directly in a small async script to reproduce behavior without the full CLI:

```python
import asyncio
from pathlib import Path
from aiohttp import ClientSession
from my_unicorn.commands.install import InstallCommand
from my_unicorn.config import ConfigManager

async def run():
    cfg = ConfigManager()
    global_cfg = cfg.load_global_config()
    install_dir = global_cfg["directory"].storage
    timeout = aiohttp.ClientTimeout(total=1200)
    async with ClientSession(timeout=timeout) as session:
        github_client = __import__("my_unicorn.github_client", fromlist=["GitHubClient"]).GitHubClient(session)
        catalog_manager = __import__("my_unicorn.config", fromlist=["CatalogManager"]).CatalogManager(cfg.directory_manager)
        cmd = InstallCommand(session, github_client, catalog_manager, cfg.directory_manager.catalog_dir)  # note: pass install_dir Path in real usage
        results = await cmd.execute(["appflowy"], show_progress=False)
        print(results)

asyncio.run(run())
```

Cross references

- Catalog format and entries: [`docs/catalog-format.md`](../docs/catalog-format.md:1) (to be created)
- Configuration: [`docs/configuration.md`](../docs/configuration.md:1) (to be created) and code: [`my_unicorn/config.py`](../my_unicorn/config.py:357).

Troubleshooting tips

- Logs: configured in global config `directory.logs` (see [`my_unicorn/config.py:391-403`](../my_unicorn/config.py:391)).
- Cache: manage with `my-unicorn cache` subcommands (see parser cache commands at [`my_unicorn/cli/parser.py:421-447`](../my_unicorn/cli/parser.py:421)).

See Also

- [`docs/wiki.md`](../docs/wiki.md:1)
- [`docs/developers.md`](../docs/developers.md:1)

End
