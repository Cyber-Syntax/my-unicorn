# Writing my-unicorn from scratch for better performance and maintainability

## Basic summary of the script

> Appimage installer and updater package management cli script

This project introduces a Python-based CLI tool that treats AppImages like packages: installable, updatable,
and manageable via a simple interface backed by local JSON metadata and GitHub releases.

## Features wanted:

- Install
    - with github url installation
    - with catalog from the our stored data(json)
- Update
    - with app base saved stored data(json)
    - with catalog from the our stored data(json)
- Icon install
    - with catalog from the our stored data(json)
- Config management
- Progress bar
    - tqdm.asyncio progress bar to display the download progress
- Logging Management
    - Logging the script execution
    - Logging the script errors
    - Logging the script warnings
    - Logging the script info
- Backup Management
    - Backup the old appimage to a specific directory with its version and name
    - Restore the old appimage to a specific directory with its version and name
- Auth Management
    - saving, removing, loading auth token to use for api requests
    - rate limit management
- Desktop entry
    - creation, update, uninstall
- File Management
    - moving appimages to a specific directory
    - renaming appimage for simplify desktop entry creation
    - making executable
- Verification
- Python package management
    - Installing as a python package via .venv usage
    - Updating the script
    - Uninstalling the script

## Architecture

### Language & other features

- Python 3.12+
- Concurrent update support for catalog and update(asyncio library)
    - aiohttp library for network requests for better performance
    - We need for icon installation too(need concurrent)
- Prerelease support for beta releases
- orjson library for config management for better performance
- Without verification support which some apps developers don't provide it
- Basic cache support for auth management
    - cache the rate limit from last request
        - 5000 rate limit in 1 hour
        - 100 concurrent rate limit
- Use pytest with mocks for network/IO
- Appimage version checks without installation
    - Would be beneficial to used on window managers like a notification system with basic bash script

## Milestones

- [X] config management
- [X] catalog management (global + per-app)
- [X] GitHub download and install
- [X] Async update + progress bar
- [X] Auth and rate limit handling
- [X] Verification methods (digest + checksum)
- [X] Icon and desktop entry support
- [X] Logging + error handling
- [X] Full CLI with subcommands
- [] Backup + restore
- [] Packaging as pip module and version updater

## Architecture Improvements & Edge Cases

## Prioritized Task Lists

### Must-Have Features (Priority 1)

#### P1.1 - Core Infrastructure

- [ ] **Config Management** - Add `config_version` field to INI/JSON files, implement validation using `configparser` + Pydantic
- [ ] **Path Security** - Sanitize all user paths with `Path.resolve()`, validate against traversal attacks
- [ ] **Error Handling** - Create `exceptions.py` with typed error hierarchy, structured error messages
- [ ] **Directory Fallbacks** - Handle permission failures with temp directory fallbacks

#### P1.2 - AppImage Selection

- [ ] **Architecture Detection** - Use `platform.machine()` to detect system architecture (x86_64, aarch64)
- [ ] **Selection Algorithm** - Priority-based AppImage selection using architecture and characteristic suffixes
- [ ] **Multi-AppImage Support** - Handle releases with multiple AppImages, choose best match
- [ ] **Name Pattern Matching** - Support regex patterns for non-standard AppImage naming

#### P1.3 - Network Resilience

- [ ] **Retry Logic** - Exponential backoff retry (3 attempts default) for failed downloads
- [ ] **Timeout Configuration** - Network timeouts from INI config (30s default)
- [ ] **Content Validation** - Verify downloaded bytes match Content-Length header
- [ ] **Basic Proxy Support** - Read proxy settings from config

#### P1.4 - File Operations

- [ ] **Atomic Operations** - Use temp files + atomic moves for all file operations
- [ ] **File Locking** - Implement `fcntl` locking to prevent concurrent operations on same AppImage
- [ ] **Basic Backup** - Simple backup before updates with configurable retention

#### P1.5 - Enhanced Verification

- [ ] **Multiple Hash Types** - Support SHA1, SHA256, SHA512, MD5 hash verification
- [ ] **Checksum File Parsing** - Parse common checksum file formats (SHA256SUMS.txt, latest-linux.yml)
- [ ] **Icon Integrity** - Basic hash verification for downloaded icons

### Good-to-Have Features (Priority 2)

#### P2.1 - User Experience

- [ ] **Progress Reporting** - Comprehensive progress bars for all long operations using `tqdm`
- [ ] **Interactive Resolution** - Prompts for conflict resolution using `rich` library
- [ ] **Dry-run Mode** - `--dry-run` flag for testing operations without execution
- [ ] **Verbose/Quiet Modes** - `-v` and `-q` flags for output control

#### P2.2 - CLI Enhancements

- [ ] **Output Formats** - Support `--format json|yaml|table` for scripting
- [ ] **Search Commands** - List and search available AppImages in catalog
- [ ] **Status Commands** - Show installed AppImage status and available updates
- [ ] **Shell Completion** - Auto-completion for bash, zsh, fish using `typer`

#### P2.3 - Advanced Features

- [ ] **Download Resume** - HTTP Range requests for resuming interrupted downloads
- [ ] **GPG Verification** - Optional signature verification using `python-gnupg`
- [ ] **Config Migration** - Automatic migration between config versions
- [ ] **Advanced Caching** - Cache GitHub API responses with rate limit awareness

#### P2.4 - Additional Modules

- [ ] **Validation Module** - Input sanitization and validation helpers
- [ ] **Selection Module** - Centralized AppImage selection logic
- [ ] **Retry Module** - Reusable retry logic with different strategies
- [ ] **Cache Module** - Enhanced caching beyond auth tokens

### Additional Considerations (Priority 3)

#### P3.1 - Future Enhancements

- [ ] **Desktop Notifications** - System notifications for completed operations
- [ ] **Performance Monitoring** - Operation timing and metrics collection
- [ ] **Cross-platform Support** - Abstract platform-specific operations
- [ ] **Plugin System** - Extensible architecture for custom verification methods

### Testing Strategy

- [ ] **Unit Tests** - Each module with >90% coverage using `pytest` and type annotations
- [ ] **Integration Tests** - Real GitHub API with test repositories
- [ ] **Error Injection** - Test failure scenarios and recovery
- [ ] **Type Checking** - Use `mypy` for static type validation
- [ ] **Simple over Complex** - Prefer straightforward implementations over advanced patterns
