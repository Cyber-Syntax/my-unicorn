# AGENTS.md

This file provides guidance to agents when working with code in this repository.

- API usage is currently GitHub-only; see [`docs/developers.md`](docs/developers.md:5) for future extensibility.
- Catalog entries are JSON files in [`my_unicorn/catalog/`](my_unicorn/catalog/) with metadata for each app (see [`docs/wiki.md`](docs/wiki.md:276)).
- App-specific configs are stored in `~/.config/my-unicorn/apps/` as JSON (see [`docs/wiki.md`](docs/wiki.md:335)).
- Backup metadata for each app is in `~/Applications/backups/<app>/metadata.json` (see [`docs/wiki.md`](docs/wiki.md:491,505)).
- Batch mode and concurrency are controlled via `~/.config/my-unicorn/settings.conf` (see [`docs/wiki.md`](docs/wiki.md:218,227)).
- Verification requires digest/checksum fields in config/catalog; always use the public parse method for YAML/traditional formats ([`my_unicorn/services/verification_service.py`](my_unicorn/services/verification_service.py:233,263)).
- For verification, if no strong methods and size check fails, raise error ([`my_unicorn/services/verification_service.py`](my_unicorn/services/verification_service.py:569,643)).
- Always log full traceback on verification failures ([`my_unicorn/update.py`](my_unicorn/update.py:1100)).
- CLI commands support install via URL, catalog, update, backup, cache, config, and auth (see [`docs/wiki.md`](docs/wiki.md:41)).
- Manual CLI tests are run via [`scripts/test.bash`](scripts/test.bash:1); some require config files in `$HOME/.config/my-unicorn/apps/`.
- Code style: line length 95, indent 4 spaces, double quotes for strings ([`pyproject.toml`](pyproject.toml:111,141)).
- Pytest uses custom addopts and import mode: `-ra -q --strict-markers --import-mode=importlib--import-mode=importlib` ([`pyproject.toml`](pyproject.toml:67)).