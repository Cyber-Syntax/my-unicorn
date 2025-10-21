---
title: Troubleshooting
slug: troubleshooting
sidebar_label: Troubleshooting
toc: true
---

# Troubleshooting

Purpose

- Practical steps to diagnose and recover from common issues when using or developing my-unicorn.
- Commands to collect diagnostics for issue reports and links to relevant code locations.

Quick checks (first 60 seconds)

```bash
# Show CLI help to ensure binary is runnable
my-unicorn --help

# Check Python entry point and version
python -c "import sys; print(sys.version)"
```

Where logs and state live

- Global config and paths are defined in the code: see [`my_unicorn/config.py`](../my_unicorn/config.py:373) and defaults at [`my_unicorn/config.py:391`](../my_unicorn/config.py:391).
- Config file: path from [`DirectoryManager.settings_file`](../my_unicorn/config.py:286).
- Apps config: `~/.config/my-unicorn/apps/` (see [`my_unicorn/config.py`](../my_unicorn/config.py:727)).
- Logs directory: configured via `global_cfg["directory"].logs` (default created by `GlobalConfigManager.get_default_global_config()` — [`my_unicorn/config.py`](../my_unicorn/config.py:391)).
- Cache directory: configured by `global_cfg["directory"].cache` (check cache files when API issues occur).

Common problems and fixes

1) "Bundled catalog not found" on startup

- Symptom: CLI raises FileNotFoundError referencing bundled catalog.
- Cause: Installation/packaging omitted `my_unicorn/catalog/*.json`.
- Fix:
    - Confirm catalog dir: `python -c "from my_unicorn.config import ConfigManager; print(ConfigManager().catalog_dir)"`
    - Ensure files exist in that directory. Validation occurs in [`DirectoryManager.validate_catalog_directory()`](../my_unicorn/config.py:318).

2) Network timeouts or rate limiting from GitHub

- Symptom: downloads fail, or API returns 403/429.
- Causes:
    - Default timeout too low for slow networks.
    - No GitHub token; rate limits hit.
- Fixes:
    - Increase `timeout_seconds` in global config (see [`docs/configuration.md`](../docs/configuration.md:1) and [`my_unicorn/config.py`](../my_unicorn/config.py:631)).
    - Save a GitHub token with `my-unicorn auth --save-token` (parser for auth: [`my_unicorn/cli/parser.py`](../my_unicorn/cli/parser.py:374)).
    - For scripting, use `--refresh-cache` to force fresh metadata only when needed.

3) Verification failures (digest/checksum mismatch)

- Symptom: Verification service rejects downloaded file.
- Cause: Asset does not provide digest or checksum file differs.
- Investigation:
    - Check release asset metadata via the GitHub API or cached release file.
    - Code paths involved: [`my_unicorn/verification/detection.py`](../my_unicorn/verification/detection.py:1) and [`my_unicorn/verification/verify.py`](../my_unicorn/verification/verify.py:1).
- Fix:
    - If upstream provides checksum files, update catalog entry `verification.checksum_file` or set `verification.skip` for known cases (edit catalog entry at [`my_unicorn/catalog/<app>.json`](../my_unicorn/catalog/:1)).
    - If digest is present in asset metadata but mismatch occurs, re-download or check for proxy corruption.

4) Icon extraction fails or icons missing

- Symptom: Desktop entries created without icons.
- Cause: Extraction tool failed, or icon URL missing.
- Investigation:
    - Icon logic: [`my_unicorn/services/icon_service.py`](../my_unicorn/services/icon_service.py:1) and download helper in [`my_unicorn/download.py`](../my_unicorn/download.py:1).
- Fix:
    - Use `--no-icon` to skip in automation, or inspect the installed app config under `~/.config/my-unicorn/apps/<app>.json` for `icon` fields (see `AppConfig` in [`my_unicorn/config.py`](../my_unicorn/config.py:189)).

5) Install command reports "Unknown applications or invalid URLs"

- Symptom: ValidationError raised when running `my-unicorn install ...`.
- Cause: Target not in bundled catalog and not a GitHub URL.
- Investigation:
    - See separation and validation in [`InstallCommand._separate_targets()`](../my_unicorn/commands/install.py:305).
- Fix:
    - Use exact catalog name (list available: `my-unicorn list --available`) or provide full `https://github.com/owner/repo` URL.

Collecting diagnostics for issues

- Capture verbose logs (set log level to DEBUG in config), reproduce the problem, then collect:
    - CLI command used and full args
    - Contents of the settings file: path printed by:

    ```bash
    python -c "from my_unicorn.config import ConfigManager; print(ConfigManager().settings_file)"
    ```

    - Relevant app config: `~/.config/my-unicorn/apps/<app>.json`
    - Logs directory listing:

    ```bash
    ls -la $(python -c "from my_unicorn.config import ConfigManager; print(ConfigManager().load_global_config()['directory'].logs)")
    ```

    - Cached release metadata (if applicable): `global_cfg['directory'].cache` path (see [`my_unicorn/config.py`](../my_unicorn/config.py:391))

How to run a reproducible minimal script to surface an error

- Use the InstallCommand directly to reproduce without the CLI wrapper:

```python
# python
import asyncio
from pathlib import Path
from aiohttp import ClientSession
from my_unicorn.commands.install import InstallCommand
from my_unicorn.config import ConfigManager

async def reproduce():
    cfg = ConfigManager()
    g = cfg.load_global_config()
    install_dir = g["directory"].storage
    timeout = aiohttp.ClientTimeout(total=600)
    async with ClientSession(timeout=timeout) as session:
        from my_unicorn.github_client import GitHubClient
        github_client = GitHubClient(session)
        catalog_manager = cfg.catalog_manager
        cmd = InstallCommand(session, github_client, catalog_manager, cfg, install_dir)
        # Turn off progress for deterministic output
        results = await cmd.execute(["appflowy"], show_progress=False)
        print(results)

asyncio.run(reproduce())
```

- File locations referenced in this snippet:
    - `InstallCommand` constructor: [`my_unicorn/commands/install.py`](../my_unicorn/commands/install.py:27)
    - `ConfigManager`: [`my_unicorn/config.py`](../my_unicorn/config.py:869)

Reporting an issue

- Provide:
    - Steps to reproduce (command or snippet above)
    - Full logs from the configured logs directory
    - Relevant app config and catalog entry if applicable
    - Python version and OS
    - Minimal reproducible script output and full stack trace

Further reading & code links

- CLI parser and commands: [`my_unicorn/cli/parser.py`](../my_unicorn/cli/parser.py:38) and [`my_unicorn/commands/install.py`](../my_unicorn/commands/install.py:24)
- Configuration and defaults: [`my_unicorn/config.py`](../my_unicorn/config.py:357)
- Verification implementation: [`my_unicorn/verification/verify.py`](../my_unicorn/verification/verify.py:1)

End of troubleshooting guide
