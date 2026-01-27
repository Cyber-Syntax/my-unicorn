# Helper Scripts

Helper scripts for managing the my-unicorn project.

- Updater: `scripts/update.bash` is automate the my-unicorn cli usage with one command. It can be used in window manager widgets, cron jobs, or manually.
- Installer: `./install.sh` is the main installation script for my-unicorn. Default use uv package manager to install my-unicorn. It also copy the update.bash script to `~/.local/bin/my-unicorn-update` for easy access.
- Autocomplete: `scripts/autocomplete.bash` provides shell completion snippets.
- Tests:
    - `scripts/test.py` - Python-based manual test suite (recommended) with colored output, better logging, and test result tracking
    - `scripts/test.bash` - Legacy bash-based manual test suite (deprecated)

## Manual Test Suite

The manual test suite (`test.py`) provides comprehensive CLI testing for my-unicorn:

### Features

- **Colored Console Output**: ANSI color codes for better readability
- **Structured Logging**: Both console and file logging with timestamps
- **Environment Detection**: Auto-detects container vs normal machine
- **Smart CLI Runner**: Uses installed `my-unicorn` in containers, `uv run my-unicorn` elsewhere
- **No External Dependencies**: Pure Python, no jq required
- **Test Result Tracking**: Pass/fail tracking with summary

### Usage

```bash
# Run quick tests (qownnotes only)
./scripts/test.py --quick

# Run all comprehensive tests
./scripts/test.py --all

# Enable debug logging
./scripts/test.py --debug --quick
```

### Test Coverage

**Quick Test** (qownnotes):

1. Remove qownnotes
2. Install via URL
3. Remove qownnotes
4. Install from catalog
5. Update qownnotes

**Comprehensive Tests**:

1. URL installs: neovim + keepassxc
2. Catalog installs: legcord + flameshot + appflowy + standard-notes
3. Updates: All installed apps

See also: `docs/wiki.md` for full documentation.
