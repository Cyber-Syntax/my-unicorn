# Helper Scripts

Helper scripts for managing the my-unicorn project.

- Updater: `scripts/update.bash` is automate the my-unicorn cli usage with one command. It can be used in window manager widgets, cron jobs, or manually.
- Installer: `./install.sh` is the main installation script for my-unicorn. Default use uv package manager to install my-unicorn. It also copy the update.bash script to `~/.local/bin/my-unicorn-update` for easy access.
- Autocomplete: `scripts/autocomplete.bash` provides shell completion snippets.
- Tests:
    - `scripts/test.py` - Comprehensive test suite with diagnostics and benchmarking (recommended)
    - `scripts/test_diagnostics.py` - Diagnostic validation module
    - `scripts/test_benchmark.py` - Performance benchmarking module
    - `scripts/test.bash` - Legacy bash-based manual test suite (deprecated)

## Comprehensive Test Suite

The test suite (`test.py`) provides comprehensive CLI testing for my-unicorn with diagnostic validation and performance benchmarking.

### Features

- **Diagnostic Validation**: Complete system state validation after operations
- **Benchmark Tracking**: Performance metrics with version comparison
- **Multiple Test Modes**: Quick, all, slow, backup, remove, migrate
- **Colored Console Output**: ANSI color codes for better readability
- **Structured Logging**: Console and file logging with timestamps
- **Environment Detection**: Auto-detects container vs normal machine
- **Smart CLI Runner**: Uses installed `my-unicorn` in containers, `uv run my-unicorn` elsewhere

### Usage

```bash
# Quick test mode (qownnotes only)
uv run scripts/test.py --quick

# All comprehensive tests
uv run scripts/test.py --all

# All tests with benchmarking
uv run scripts/test.py --all --benchmark

# Slow tests (large apps)
uv run scripts/test.py --slow

# Test backup functionality
uv run scripts/test.py --test-backup

# Test remove with verification
uv run scripts/test.py --test-remove

# Test migration
uv run scripts/test.py --test-migrate

# Enable debug logging
uv run scripts/test.py --debug --quick
```

## Other Scripts

- `scripts/migrate_catalogs_v2.py` - Migrate catalog files to v2 format
- `scripts/test_log_rotation.py` - Test log rotation functionality
- `scripts/extract_changelog.sh` - Extract changelog from git history
- `scripts/github_action_test.sh` - Test GitHub Actions workflows locally

### Test Coverage

**Quick Test** (qownnotes):

1. Update qownnotes
2. Remove qownnotes
3. URL install qownnotes with diagnostics
4. Remove with cache verification
5. Catalog install qownnotes with diagnostics

**All Tests**:

1. URL installs: neovim + keepassxc (with validation)
2. Catalog installs: legcord + flameshot + appflowy + standard-notes (with validation)
3. Updates for multiple apps (with validation)
4. Backup creation, listing, and restoration
5. Backup metadata validation

**Slow Tests**:

1. Large app installs (Joplin, Obsidian)
2. Large app updates

**Backup Tests**:

1. Backup creation
2. Backup listing
3. Backup info display
4. Backup restoration
5. Backup cleanup
6. Metadata validation

**Remove Tests**:

1. Remove with cache verification
2. Orphaned file detection
3. Complete cleanup validation

### Diagnostic Validation

The test system validates complete system state:

- **App State**: Config valid, AppImage exists, desktop entry created, icon extracted
- **Cache State**: Cache file exists, valid JSON, matches schema, Linux assets only
- **Backup State**: Metadata valid, all files exist, checksums match, version sorting correct
- **Removal State**: All files deleted, cache cleared, no orphaned files

### Benchmarking

Enable benchmarking to track performance across versions:

```bash
uv run scripts/test.py --all --benchmark
```

Benchmarks saved to: `~/.config/my-unicorn/logs/benchmarks/{version}.json`

Benchmark includes:

- Total core time (excluding network)
- Total network time
- Per-operation breakdown
- Automatic version comparison if previous benchmarks exist

### Logs

- Test log: `~/.config/my-unicorn/logs/comprehensive_test.log`
- Diagnostics log: `~/.config/my-unicorn/logs/test_diagnostics.log`
- Benchmarks: `~/.config/my-unicorn/logs/benchmarks/{version}.json`

### Environment

Auto-detects container vs normal machine:

- **Container**: Uses `my-unicorn` command
- **Normal Machine**: Uses `uv run my-unicorn`

2. Catalog installs: legcord + flameshot + appflowy + standard-notes
2. Updates: All installed apps

See also: `docs/wiki.md` for full documentation.
