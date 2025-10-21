---
title: Testing
slug: testing
sidebar_label: Testing
toc: true
---

# Testing

Purpose
- How to run unit and integration tests, set up a virtual environment, and debug failures.

Quick start — create and activate virtualenv
```bash
# Create venv and install deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the full test suite
```bash
source .venv/bin/activate
pytest -v -q --strict-markers
```

Run a focused test module
```bash
# Run tests for config only
pytest -q tests/test_config.py -q
```

Test layout & important tests locations
- CLI tests: [`tests/commands/test_install.py`](../tests/commands/test_install.py:1)  
- Service tests: [`tests/services/test_icon_service.py`](../tests/services/test_icon_service.py:1)  
- Integration and end-to-end: [`tests/integration/`](../tests/integration/:1)  
- Model and util tests: [`tests/models/`](../tests/models/:1)  

Running subset with verbose logs
```bash
pytest -k install -vv
```

Quick programmatic test (run single async snippet)
```python
from my_unicorn.config import ConfigManager
cfg = ConfigManager()
print(cfg.load_global_config()["directory"].download)
```

CI and pre-commit
- Use `./setup.sh` to prepare environment for local CI-like runs (see [`setup.sh`](../setup.sh:1)).  
- CI uses the same pytest invocation; ensure you install dev dependencies listed in `requirements.txt`.

Debugging failing tests
1. Re-run failing tests with -x to stop on first failure:
```bash
pytest tests/test_file.py::test_name -q -x -vv
```
2. Run with -s to see print/log output:
```bash
pytest tests/test_file.py -s -q
```
3. Collect verbose tracebacks:
```bash
pytest --showlocals -k test_name -q
```
4. If tests rely on network, use mocks or set environment variables to force offline/mock behavior.

Test-specific notes
- Many tests mock network clients (see how `tests/test_update.py` patches services) — see [`tests/test_update.py`](../tests/test_update.py:1).  
- Icon and download tests import `DownloadService` and `IconAsset` from [`my_unicorn/download.py`](../my_unicorn/download.py:1) — use the same import paths in local scripts.

Generating coverage
```bash
source .venv/bin/activate
pytest --cov=my_unicorn --cov-report=term-missing
```

Capturing logs for an issue
- Increase `log_level` in global config (see [`docs/configuration.md`](../docs/configuration.md:1) and code defaults at [`my_unicorn/config.py`](../my_unicorn/config.py:373)).  
- Attach logs from the configured logs directory (default `~/.config/my-unicorn/logs`) — path created by `GlobalConfigManager.get_default_global_config()` at [`my_unicorn/config.py`](../my_unicorn/config.py:391).

Common failures & fixes
- Missing bundled catalog: run
```bash
python -c "from my_unicorn.config import ConfigManager; print(ConfigManager().catalog_dir)"
```
and ensure JSON files exist; catalog validation is implemented at [`my_unicorn/config.py`](../my_unicorn/config.py:318).  
- Keyring failures on CI: mock keyring in tests or set an alternate backend for CI environments.

End of testing guide