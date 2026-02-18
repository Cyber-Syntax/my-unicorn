# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0-alpha] - 2026-02-18

### Added

- Created `ProgressReporter` protocol for UI decoupling from core modules
- Introduced `ServiceContainer` for dependency injection and service lifecycle management
- Implemented domain-specific exception hierarchy with `MyUnicornError` base class:
    - `VerificationError` with `HashMismatchError`, `HashUnavailableError`, `HashComputationError`
    - `WorkflowError` with `InstallError`, `UpdateError`, `PostProcessingError`
    - `NetworkError` with `DownloadError`, `GitHubAPIError`
    - Added `is_retryable` and `retry_after` attributes for retry logic
- Added async file I/O support using `aiofiles` library for non-blocking downloads
- Added `NullProgressReporter` implementing null object pattern for optional progress tracking
- Added comprehensive Raises sections to all public method docstrings in workflow modules for better error documentation
- Added async safety documentation to class docstrings explaining thread safety and concurrent access patterns
- Enhanced in-memory caching documentation with performance metrics and thread safety notes
- Extended `app_state_v2.schema.json` with new verification fields for enhanced state tracking:
    - `overall_passed`: Boolean indicating if any verification method succeeded
    - `actual_method`: Enum (`digest`|`checksum_file`|`skip`) indicating which method was used
    - `warning`: Optional warning message for unverified installations
    - `methods[].digest`: Alternative single hash field (replaces separate computed/expected)
- Extended `cache_release.schema.json` with `checksum_files[]` array for caching downloaded checksum files:
    - Stores source URL, filename, algorithm, and hash mappings
    - Enables verification reuse without re-downloading checksum files
- Added `get_checksum_files()`, `has_checksum_files()`, and `get_checksum_file_for_asset()` methods to `CacheManager`
- Test support for bulk updates and stronger CLI coverage
    - Added `test_update_all_cmd` and a `--update-all` test flag in `scripts/test.py` to validate "update all" workflows.
- Significant test coverage increases and reorganization
    - Dozens of focused unit tests added across progress, verification, update and utils (representative files: `tests/core/progress/test_ascii_format.py`, `test_ascii_sections.py`, `test_ascii_output.py`, `test_display_id.py`).
    - Tests reorganized for clearer scopes and faster discovery (see `tests/cli/`, `tests/core/`, `tests/config/`, `tests/utils/`).
    - Added 100+ tests covering schema validation, cache operations, and verification workflows

### Changed

- setup.sh script renamed to install.sh and updated installation commands:
    - Production install command updated:
        - Use `./install.sh -i` or `./install.sh --install` to perform a standard installation.
    - Development install command updated:
        - Use `./install.sh -e` or `./install.sh --editable` to install in editable mode.
- Refactored core architecture to use dependency injection via `ServiceContainer`
- Replaced UI dependencies in core modules with protocol-based abstractions (`ProgressReporter`)
- Refactored `DownloadService` and `VerificationService` to use `ProgressReporter` protocol
- Replaced generic exceptions with domain-specific error types across all workflow modules
- Added retry logic for transient network errors using `is_retryable` exception attribute
- Moved blocking I/O operations to executor threads for non-blocking async execution
- Improved docstring quality across install.py and update.py workflow modules
- Standardized exception documentation with detailed error conditions and scenarios
- Implemented async file I/O for improved download performance with `aiofiles`
- Reduced event loop blocking during downloads and verification operations
- Moved hash computation to executor threads for large files (>100MB threshold)
- Improved progress reporting smoothness with non-blocking updates
- `VerificationService` now passes checksum file data to `CacheManager` for persistence
- Update workflow recalculates verification state with fresh hashes instead of preserving stale data
- Enhanced `StateVerification` and `VerificationMethod` TypedDicts with comprehensive docstrings
- Large internal refactors to improve modularity and maintainability
    - Verification: replaced the monolithic checksum parser with a `checksum_parser/` package (specialized parsers + detector/normalizer) and split the verification service into focused modules (detection, helpers, execution, verification methods).
        - Result: `service.py` shrank from ~1322 → 437 lines; multiple mypy issues fixed.
    - Update & logging subsystems decomposed into smaller modules:
        - `update.py` split into `context.py`, `catalog_cache.py`, `manager.py`, `workflows.py`.
        - `logger.py` split into 6 focused modules while preserving the singleton API via re-exports.
        - Fixes and test updates made during the split (no behavioral changes to public CLI).
    - Progress/display rework — moved from `ui` to `core/progress` and extracted many helpers (`ascii_format`, `ascii_sections`, `ascii_output`, `display_id`, `display_registry`, `display_logger`, `display_session`, `display_workflows`).
        - Keeps prior public behavior while improving SRP, testability and code size.
        - Import paths updated throughout CLI and tests.
- Documentation & housekeeping
    - UI docs clarified and examples expanded (`docs/ui.md`).
    - Minor repo maintenance: `.gitignore` and `AGENTS.md` improved for clarity.

### Fixed

- **Critical Bug Fix: Hash Detection in Checksum Verification**
    - Fixed a critical bug where hexadecimal checksums were incorrectly processed as base64, causing hash detection failure called `binascii.Error: Incorrect padding` during verification for certain apps (e.g., Heroic, QOwnNotes) that use latest-linux.yml file with hex hashes.
    - This fix ensures that the normalization function correctly detects and processes both hex and base64 encodings, preventing corruption of hex hashes and allowing all verification methods to function properly.
    - Hex hashes (e.g., from Heroic, QOwnNotes) are now preserved without corruption
    - Base64 hashes (e.g., from Legcord, Superproductivity) continue to work correctly
- Fixed update command not refreshing verification data when updating to new versions
- Fixed `VerificationError` not being raised when all verification methods fail
- Fixed checksum file references not persisting to cache JSON files
- Corrected asynchronous and protocol issues in progress reporting
    - `ProgressReporter` protocol methods made `async def`; `NullProgressReporter` and related callers updated; added protocol-compliance tests.
- Reliability fixes in post-download and verification flows
    - Guarded hash-retrieval in `PostDownloadProcessor` and improved null-safety checks.
- Test and typing fixes uncovered by the refactors
    - Multiple test failures resolved (including patched instantiation sites for `DownloadService` / `PostDownloadProcessor`); `test_update.py` suite fully passing after fixes.

### Removed

- Legacy venv-wrapper.bash script and install functionality removed from install.sh.
- Removed legacy/monolithic and obsolete modules
    - Deleted legacy `checksum_parser.py` (replaced by the new `checksum_parser/` package).
    - Removed old monolithic `update.py` / `logger.py` implementations (functionality preserved in new modules).
    - Deleted obsolete UI helper `src/my_unicorn/ui/display_common.py` and other unused legacy files.
    - Removed several deprecated test-package `__init__` files as the test layout was modernized.

### Notes

- All new schema fields are optional for backward compatibility
- Existing app state configurations continue to work without migration
- Legacy verification format (passed + methods only) remains valid

## [2.2.1-alpha] - 2026-02-05

### Fixed

- Fixed issue with remove command not handling missing app configs gracefully.

## [2.2.0-alpha] - 2026-01-25

### Added

- Added mypy to development dependencies for type checking.
- Added tests for SHA1 and MD5 verification across multiple checksum file formats.
- Added unit tests for CLI command helpers and display functions.

### Changed

- Replaced custom version comparison logic with the packaging library.
- Updated command references from 'list' to 'catalog' for consistency.
- Updated catalog loading methods in tests for better alignment.
- Cleaned up catalog and configuration management code.
- Streamlined verification and checksum parsing logic.
- Moved infrastructure modules to the core package for better organization.
- Enhanced command handlers with shared helper functions.
- Moved remove service to core/remove.py for better modularity.
- Moved display_remove.py service to remove.py for simplification.
- Enhanced remove service with dataclass for structured results.

### Fixed

- Fixed remove command by adding v2 config support.
- Fixed attribute error in install command by adding explicit keyword argument to progress_service.

### Removed

- Removed unused imports and redundant code in various modules.
- Eliminated deprecated methods and classes related to removal logic.

## [2.1.0-alpha] - 2026-01-10

### Added

- Implemented copy_update_script function to copy the update script to a shared location.
- Integrated the script copying into installation and update processes for UV tool.
- Added warnings for missing autocomplete helper and update script.

### Changed

- Change upgrade command options from `--check-only` to `--check`.
- Update bash and zsh autocomplete scripts to reflect new option.
- Modify update script to remove automatic upgrade handling.
- Enhance upgrade command to check for updates without installing.
- Refactor version comparison logic to improve accuracy.
- Moved asset validation functions to utils/asset_validation.py for better modularity.
- Consolidated version extraction logic into infrastructure/github/version_utils.py.
- Updated domain types to use shared utility functions for file type checks.
- Removed redundant utility functions from utils.py to streamline the codebase.
- Clarified testing instructions to specify CLI code changes.
- Added note about the `my-unicorn-update` script for UV installations.
- Updated installation commands to reflect the correct repository.

## [2.0.0-alpha] - 2026-01-09

### Breaking Changes

- **Config Module Refactor**: Removed backward compatibility classes from config module
    - `DirectoryManager` class removed - use `Paths` class instead
    - `CatalogManager` alias removed - use `CatalogLoader` directly
    - Import paths remain the same: `from my_unicorn.config import Paths, CatalogLoader`
    - All functionality preserved through `Paths` class static methods
- **Config Format Migration**: Application configuration format changed from v1.0.0 to v2.0.0
    - Manual migration required via `my-unicorn migrate` command before use
    - Automatic backups created during migration (.json.backup files)
    - Config v2 uses hybrid structure: catalog apps store only state + catalog_ref, URL apps store full config in overrides
- **Global Config**: Global configuration version updated to 1.0.2
- **Command Rename**: `list` command deprecated in favor of `catalog` command (removed entirely)

### Added

- **JSON Schema Validation**: Comprehensive validation for catalog and app state configurations
    - Auto-detection of v1 vs v2 config formats
    - Runtime validation at load/save operations
    - Clear error messages with JSON path references
    - IDE support via .schema.json files
- **App Descriptions**: Added descriptions for all 27 catalog applications
- **Catalog Command**: Enhanced `catalog` command with app descriptions
    - `catalog --available` shows apps with descriptions
    - `catalog --info <app-name>` displays detailed app information
- **Migration Infrastructure**: Complete v1→v2 migration system
    - Dedicated `migration/` package with modular structure
    - Automatic backup creation before migration
    - Support for both catalog and URL-installed apps
    - Post-migration validation with schema checking
- **Verification Warnings**: Installation proceeds with warnings when no verification methods available
    - Clear security warnings for users
    - Progress display shows ⚠ symbol for unverified installs
    - Detailed logging for debugging

### Changed

- **Setup.sh Update**: Remove editable mode on legacy installation from setup.sh
- **Upgrade Process Update**: Use 'uv tool upgrade' command and enhance test coverage
- **Documentation Enhancement**: Enhanced readme, updated todo.md, and added comprehensive config documentation
- **Config Structure**: New hybrid v2 configuration format
    - Catalog apps: Minimal config (state + catalog_ref pointing to catalog filename)
    - URL apps: Full config stored in overrides section
    - Improved separation of concerns and reduced duplication
- **Verification State**: Enhanced verification tracking in app state
    - Multiple verification methods tracked per installation
    - Detailed status for each method (type, algorithm, hashes, source)
    - Properly saves `passed: false` when no verification occurs
- **Icon State**: Improved icon state tracking
    - Method field indicates extraction vs download
    - Accurate migration from v1 extraction boolean
- **Icon Handling**: Refactored to extract icons from AppImage only (no external download)
    - Removed download method from icon handling
    - Catalog JSON files updated to remove download_url entries
    - New extract_icon_from_appimage() function in file_ops.py
- **Migration Organization**: Refactored migration code into dedicated package
    - `migration/base.py` - Common utilities
    - `migration/app_config.py` - App config migration
    - `migration/catalog_config.py` - Catalog config migration
    - `migration/global_config.py` - Global config migration
    - Eliminated code duplication
- **Command Refactoring**: Renamed deprecated `list` command to `catalog` with enhanced features
    - Use new `catalog` command instead of `list`
- **Logging Improvements**: Replaced print statements with logger for CLI output
    - Introduced SimpleConsoleFormatter for clean console messages
    - Improved logging consistency and error reporting

### Fixed

- **Icon Migration**: Fixed v1→v2 migration incorrectly setting icon.method to "download"
    - Now correctly checks source field first, then falls back to extraction boolean
    - Affects apps like tagspaces, super-productivity with extraction+URL
- **Catalog App Verification**: Fixed checksum_file verification not preserved during migration
    - Migration now consults catalog for correct verification method
    - Apps like standard-notes properly migrated
- **URL Install Config**: Fixed URL-installed apps creating empty overrides in source fields
    - Now properly populates source section in overrides
- **Migration Command**: Fixed migrate command failing on v1 configs
    - Now reads raw JSON directly instead of using load_app_config validation
- **Catalog Reference**: Fixed catalog apps incorrectly migrated as URL apps
    - catalog_ref now maps to catalog filename (app_name), not repo name
    - No overrides added to catalog apps during migration
- **Beekeeper Studio Naming**: Fixed wrong catalog filename from beekeper-studio to beekeeper-studio
- **Icon Method Mapping**: Fixed deprecated download method mapping during migration
- **Backup Migration**: Removed automatic migration, now fully folder-based structure
- **Install Verification Source**: Fixed verification source field to use lowercase

### Removed

- **Legacy Config Support**: Removed support for v1 configuration format
    - Post-migration, only v2 configs accepted
    - Simplifies codebase and maintenance
- **List Command Alias**: Completely removed `list` command
    - Use new `catalog` command instead
    - No backward compatible alias maintained
- **Old Migration Code**: Removed legacy migration code from main modules
    - All migration logic now in dedicated `migration/` package
    - Cleaner separation of concerns
- **Icon Download Logic**: Completely removed icon download functionality
    - Now extracts icons directly from AppImage files
    - Removed download_url entries from all catalog configurations
- **Backup Migration**: Removed automatic migration from old flat backup format to folder-based structure
    - Users with old backups (*.backup.AppImage) should manually reorganize them if needed
    - New installations and users who already migrated are unaffected
    - Backup system now exclusively uses folder-based structure with metadata.json
- **Show Progress Parameter**: Removed show_progress parameter from download methods
    - Progress always enabled for install/update operations
    - Download progress conditionally shown based on file size
- **Deprecated Classes**: Removed old icon handler classes and unused tool scripts
- **Deprecated Progress Methods**: Removed deprecated task creation methods from progress service

### Migration Guide

#### Migrating from v1.x to v2.0.0

1. **beekeeper-studio name**:
    - (Recommended) If you use beekeeper-studio, remove the app before migration to v2.0.0 and reinstall after migration to avoid issues.
    - You can manually rename your config and desktop files for Beekeeper Studio if you migrated before reinstalling:
      1. Rename `~/.config/my-unicorn/apps/beekeper-studio.json` to `beekeeper-studio.json`.
      2. Rename `~/.local/share/applications/beekeper-studio.desktop` to `beekeeper-studio.desktop`.
      3. Update `catalog_ref` field in the config file to `beekeeper-studio`.

2. **Run migration command**:

   ```bash
   my-unicorn migrate
   ```

3. **Migration process**:
   - Automatically detects v1 configs in `~/.config/my-unicorn/apps/`
   - Creates `.json.backup` files before migration
   - Converts to v2 format with appropriate structure
   - Validates migrated configs against JSON schema

4. **After migration**:
   - Review migrated configs in `~/.config/my-unicorn/apps/`
   - Backups available in `~/.config/my-unicorn/apps/backups/`
   - Use `catalog` command instead of `list` (alias still works)

5. **Config structure changes**:
   - Catalog apps: Only state + catalog_ref stored (metadata from catalog)
   - URL apps: Full config in overrides section
   - See docs/config.md for detailed v2 format documentation

For detailed migration information, see [docs/config.md](docs/config.md).

## [1.12.2-alpha]

### Fixed

- Use correct uv command for upgrade.

## [1.12.1-alpha]

### Fixed

- Fixed my-unicorn cli module not found after uv installation via git+ URL.

## [1.12.0-alpha]

### Added

- Added support to install cli via uv package manager.

### Changed

- Update README
- Migrate to src layout

### Deprecated

- Direct pip installation and venv-wrapper usage is going to be deprecated in future releases in favor of uv package manager for better performance and dependency management.

### Migration guide

To migrate to the new uv-based installation, please follow these steps:

1. Uninstall the existing folders:

- Remove `~/.local/bin/my-unicorn` if it exists.
- Remove `~/.local/share/my-unicorn/` directory if it exists.
- Remove `~/.local/share/my-unicorn-repo/` directory if it exists.

1. Install via setup.sh script:

```bash
./setup.sh uv-install
```

## [1.11.1-alpha]

### Added

- Added better tool support to pyproject.toml for ruff, uv and pytest.

### Changed

- Enhanced verification module with new configuration and result handling classes.
- Enhanced progress display logic and added speed calculation utility.
- Improved docstrings for clarity and consistency across auth, cli, and main modules.
- Streamlined target separation and installation logic in InstallHandler and InstallCommand.
- Enhanced installation logic by delegating target separation to utils and app status checks to InstallHandler.
- Extracted removal logic into RemoveService.
- Unified release fetching methods in InstallHandler and cleaned up debug logs in UpdateManager.
- Streamlined download and installation logic, enhanced type safety, and improved asset handling.
- Improved version sorting and backup logic in BackupService.
- Extracted rate limit info extraction and config creation logic into separate methods.
- Cleaned up unused constants and comments.
- Extracted inline comment stripping logic into a separate function.
- Centralized and streamlined type definitions, removed unused classes.

### Fixed

- Added checksum file handling with templating support and relaxed filename matching.

### Removed

- Removed default, unused settings on pyproject.toml.
- Removed version constraints on pyproject.toml, now we use uv.lock for dependency management.

## [1.11.0-alpha]

### Added

- ASCII progress bar backend to replace rich progress UI.
- Network retry and rate-limit support for GitHub API requests, including
  configurable retry/backoff and improved resilience.

### Changed

- Reorganized and updated documentation.
- Improved progress task names and progress handling in `install` and
  `update` commands.

### Removed

- Removed the rich library to reduce dependencies and code maintainability.

### Fixed

- Delegate AppImage rename in install command to the storage service to fix
  incorrect extension names during renames.

### Migration guide

Please reinstall (remove and install again) all of your apps after upgrading to this version to avoid any issues with the appimage extension naming issue from previous versions.

## [1.10.1-alpha]

### Added

- **UV Support**: Added support for UV (Astral's fast Python package manager) with automatic detection and seamless fallback to pip.
  UV is used to install the venv, which is faster and more efficient than pip.

### Changed

- Enhanced setup.sh with UV detection and conditional usage
- Improved upgrade logging to indicate whether UV or pip is being used

### Fixed

- Fixed a bug where the venv installation process could fail due to wrong directory usage on upgrade module.
  Now, the package upgrade process is uses setup.sh instead of upgrade module for better simplified installation process.

### Removed

- Locale and batch_mode on configuration which they was violate YAGNI. May be added back in the future if needed
- Commit history writing to release notes

## [1.10.0-alpha]

### Changed

- Large refactor and reorganization across core modules to simplify command flows and reduce template overhead.
  Services were consolidated and many modules were moved or renamed for clarity (install/update flows, icon handling, file operations, and verification service).
- GitHub client rewritten using dataclasses and clearer API abstractions to improve maintainability and testability.
- Improved caching and asset selection/filtering logic to reduce redundant API calls and improve release data handling.
- Logging improvements: added manual log rotation, centralized constants, and safer handling of rotating log handlers.
- Update/install UX: update process optimized and summaries improved to show detailed error reasons in install/update summaries.
- Tests: expanded and adapted test coverage to match refactors and new APIs.

### Fixed

- Support for root-level hash in checksum YAML parsing.
- Various bug fixes surfaced during refactors (see commit history for details).

### Migration guide

No manual migration steps are required for most users. If you have a custom setup that relies on deprecated module paths or templates,
review your configuration and follow the repository README for update instructions.

## [1.9.1-alpha]

### Fixed

Fixed wrong source directory path in the upgrade command which caused upgrade to fail.

### Migration guide

Please manually update with setup.sh script. Run the following commands in your terminal:

```bash
git clone https://github.com/Cyber-Syntax/my-unicorn.git
cd my-unicorn
./setup.sh install
```

## [1.9.0-alpha]

### Changed

- Centralized configuration and constants for better maintainability. This included
  moving commonly used values into `my_unicorn/constants.py` and updating
  modules to consume the centralized constants.
- Major refactors to logging and progress handling to simplify the implementation
  and avoid duplicated handlers; improved reliability of log rotation.
- Added configuration migration logic to automatically update user configs when
  the internal configuration version changes.
- Large documentation additions: CLI reference, catalog format, configuration,
  services, templates, testing guides, and troubleshooting documentation.
- Expanded test coverage and updated many tests to match refactors.

### Fixed

- Prevent duplicate RotatingFileHandler instances and related log rotation
  corruption issues.
- Fix progress session warnings in install templates.

### Added

- `tools/generate_pip_freeze.py` and utilities to help with dependency generation.

## [1.8.0-alpha]

### BREAKING CHANGES

This release removes the `self-update` command to use `upgrade` command instead for better clarity and consistency. Also, upgrade command now removed the rich progress bar and use simple text-based progress updates to improve performance and reduce resource consumption.

### Migration guide

Please update manually with setup.sh script. Run the following commands in your terminal:

```bash
git clone https://github.com/Cyber-Syntax/my-unicorn.git
cd my-unicorn
./setup.sh
```

## [1.7.4-alpha]

## [1.7.3-alpha]

## [1.7.2-alpha]

## [1.7.1-alpha]

## [1.7.0-alpha]

# CHANGES

This release refactors the codebase for improved code readability, maintainability and performance.

- Removed size verification logic which it was not best practice to verify app integrity.

## [1.6.0-alpha]

# BREAKING CHANGES

This release introduces a comprehensive caching mechanism for GitHub release data, enhancing performance and reducing redundant API calls. The caching system is designed to store release information persistently, with a configurable time-to-live (TTL) to ensure data freshness. Additionally, the release includes significant improvements to the logging capabilities of the verification service, providing detailed insights into the verification process and asset handling.

## [1.5.1-alpha]

## [1.5.0-alpha]

# BREAKING CHANGES

This release implement new library rich for progress bar instead of tqdm.
Please update my-unicorn via `my-unicorn self-update` to get the latest version.

## [1.4.0-alpha]

## [1.3.0-alpha]

## [1.2.0-alpha]

### CHANGES

This release implement new icon extraction feature and implement new verfication service.

## [1.1.3-alpha]

## [1.1.2-alpha]

## [1.1.0-alpha]

### BREAKING CHANGES

This release implement new backup commands and features.
Please read [wiki.md](docs/wiki.md) for more information how to use the new feature and how to migrate old backups to new format.

- Added support for `backup app_name --restore-last` restore last backup
- Added support for `backup app_name --restore-version <version>` restore backup by version
- Added support for `backup app_name --info` show backup info
- Added support for `backup app_name --list-backups` list all backups
- Added support for `backup app_name --cleanup` to clean up old backups manualy(This already automaticly works when the script used tough)
- Added support for `backup app_name --migrate` to migrate old backups to new format

#### Migration guide

- Keep in mind that the migration process is irreversible and will cause data loss.
- Run `backup app_name --migrate` to migrate old backups to new format.
- If something goes wrong, migrate manually by moving the `~/Applications/backups` directory to `~/Applications/backups.old`
  than make sure to run migrate command again to migrate the new backups to the new format.

## [1.0.1-alpha]

## [1.0.0-alpha]

### BREAKING CHANGES

This release written from scratch to simplify the code and maintainability.
Please read the [wiki.md](docs/wiki.md) for more information.

#### What is new?

1. Global config now use INI format
2. App specific configs now use better structured Json format
3. We now use new libraries for better performance
    - orjson instead of json
    - uvloop instead of asyncio for running
    - aiohttp instead of requests
    - tqdm.asyncio instead of manual progress bar
4. Authentication is simplified for better security and performance
5. Locale support, migration and other similar features removed for the simplicity of the code
   but they might be implemented in the future.

#### Migration guide

- Remove anything related to the old version, including old appimages, versions and configs.
- Install the new version of the app with the instructions provided in the README.md.
- Check the [wiki.md](docs/wiki.md) for more information how to use the app.

## [0.15.2-alpha]

## [0.15.1-alpha]

## [0.15.0-alpha]

## [0.14.1-alpha]

## [0.14.0-alpha]

## [0.13.9-alpha]

## [0.13.8-alpha]

## [0.13.7-alpha]

## [0.13.6-alpha]

## [0.13.5-alpha]

## [0.13.4-alpha]

## [0.13.3-alpha]

## [0.13.2-alpha]

## [0.13.1-alpha]

## [0.13.0-alpha]

### BREAKING CHANGES

This release remove compability with kdewallet and salting for the tokens. Tokens are now stored in the gnome keyring only. This is done to simplify the code and improve security.

## [0.12.3-alpha]

### Changed

## [0.12.2-alpha]

### Changed

## [0.12.1-alpha]

### Changed

This release fixes the cli command issues.

## [0.12.0-alpha]

### Changed

This release add cli support and package support for python 3.12 and higher.

## [0.11.1-alpha]

### Changed

This release fixed the super-productivity(14.0.3) appimage verification issue. There was a extarnal problem on the app itself while creating the .yml checksum file and it was a problem sometimes happens. Currently, the app is started to provide asset_digest which this fix is add the use_asset_digest method to verify the appimage. This will not affect existing functionality, but it will fix the issue with the super-productivity appimage verification.

## [0.11.0-alpha]

### Changed

Cleaning up the codebase for better readability and maintainability.

## [0.10.10-alpha]

### BREAKING CHANGES

Fixes the performance issue and concurrent issues. After this release we are no longer
support python 3.11 and lower. This release completely switches to python 3.12 and higher.

## [0.10.9-alpha]

### Changed

This release will not affect existing functionality, but it will fix the issue with the catalog module.

## [0.10.8-alpha]

### Changed

Implements GitHub API asset digest-based verification as the highest priority verification method, falling back to existing SHA file and release body extraction methods when digest is unavailable.
This will fix the issue with the zen browser appimage verification.
Also, QOwnNotes migrate the verification method to the new GitHub API asset digest-based verification method and I can confirm that is also working for the QOwnNotes appimage.

## [0.10.7-alpha]

### Fixed

Zen Browser verification issue with the appimage. This release will not affect existing functionality, but it will fix the issue with the Zen Browser appimage verification.

## [0.10.6-alpha]

### Changed

Fixes the issue with asyncio event loop in the app and cleanup the failed appimage files.

## [0.10.5-alpha]

### Changed

Updated dependencies to the latest versions. This will not affect existing functionality, but it will improve the performance and security of the app.

## [0.10.4-alpha]

### Changed

Fixes github action duplicate commits in release notes. This release will make it workflow to show only PR commits in the release notes.

## [0.10.3-alpha]

### Changed

Fix WeekToDo app 404 error. Also, added a output fix for the appimage who haven't provided by their developers in previous PR(forget to update changelog). This wouldn't require any changes to your existing configuration files.

## [0.10.2-alpha]

### Changed

This will not affect existing functionality, but it will change the location of the logs. The logs will now be stored in `~/.local/state/myunicorn/` folder instead of repository dir. This is done to comply with the XDG Base Directory Specification.

## [0.10.1-alpha]

### Changed

Added a new feature that allows github workflows to write who committed the changes to the release notes. Also created a test script to test the release notes generation. This will not affect existing functionality.

## [0.10.0-alpha]

### BREAKING CHANGES

This release add new app catalog feature to use a new format. The new format is as follows to `apps/<app_id>.json`:

```json
{
    "owner": "zen-browser",
    "repo": "desktop",
    "app_display_name": "Zen Browser",
    "description": "A content-focused browser for distraction-free browsing",
    "category": "Productivity",
    "tags": ["browser", "focus", "distraction-free", "privacy"],
    "checksum_hash_type": "sha256",
    "appimage_name_template": "zen-{characteristic_suffix}.AppImage",
    "checksum_file_name": "extracted_checksum",
    "preferred_characteristic_suffixes": ["x86_64", "amd64"],
    "icon_info": "https://raw.githubusercontent.com/zen-browser/desktop/main/docs/assets/zen-black.svg",
    "icon_file_name": "zen_browser_icon.png",
    "icon_repo_path": "docs/assets/zen-black.svg"
}
```

That example is for the Zen Browser appimage. That json file contains all the correct information about the appimage

User specific configurations are still used but with minor changes:

```json
{
    "version": "1.12.8b",
    "appimage_name": "zen-x86_64.AppImage"
}
```

This variables are used for comparing versions and handling the appimage exact name for file operations. The `appimage_name` is now used to store the exact name of the appimage file, which is derived from the `appimage_name_template` in the app config

This change is not backward compatible, so you will need to update your existing app configs to the new format. You can use the `choice migrate` command to help with this migration

## [0.9.2-alpha]

### BREAKING CHANGES

Update your config files with choice 8. This release includes refactoring of the code to improve readability and maintainability. I refactored the variable names to be more readable and meaningful.

## [0.9.1-alpha]

### Changed

This release includes a fix for the issue where the standard notes app repo name was `app` which script was using repo name to name the appimage, config, desktop file and backup files. The script now uses app_id to name the appimage and similar files. Changes is not breaking because app_id is still fallback to repo name if app_id is not found. I encourage you to use app_id in your config file to avoid any confusion in the future and solve the standard notes app issue.

## [0.9.0-alpha]

### Changed

Added a new feature that allows you to install AppImages from the catalog of compatible apps instead of dealing with URLs. This will not affect existing functionality.

## [0.8.0-alpha]

# BREAKING CHANGES

Added download more than 1 app at a time feature. `max_concurrent_updates` is added to the global config file and default value is 3. Migrate with choice migrate to add this default value to your settings.json file to be able to use this feature.

You can change this value to any number you want, but be cautious of the API rate limits: 60 requests per hour without a token and 5000 requests per hour with one. Also, you cannot update more than 100 apps concurrently due to GitHub's secondary rate limits.

## [0.7.0-alpha]

# BREAKING CHANGES

New max_backup parameter in the settings.json file. This will be used to limit the number of backups created for each app. The default value is 3. Use choice migrate to update settings.json with default value.

Added github token usage for the app to increase the rate limit for the app. Please add your github token with app choice if you want to increase rate limit which would be 5000 requests per hour. If you do not add the token, the app will use the default rate limit of 60 requests per hour. Also if you don't use it, installation speed may be slower.

## [0.6.5-alpha]

### Changed

feat: create desktop entry files for AppImages

- Improved error handling during AppImage updates to ensure the
  process continues even if one update fails.
- Added functionality to create and update desktop entry files for
  AppImages.
- Updated .gitignore to include AppImage files.

## [0.6.4-alpha]

### BREAKING CHANGES

Please change your current configuration files to the new format. The new format is as follows XDG Base Directory Specification which you need to move your current configuration files to the new location `~/.config/my-unicorn/` with the following structure:

```bash
~/.config/my-unicorn/
├── apps
│   ├── FreeTube.json
│   ├── joplin.json
├── settings.json
```

- feat!: Updated the global and app configuration paths to use XDG compliant directories.feat!: add

## [0.6.3-alpha]

### Changed

- feat: add unit tests
- chore: add init files for path
- refactor: improve better error handling on verify.py
- chore: add copilot instructions

[2.2.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v2.1.0-alpha...v2.2.0-alpha
[2.1.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v2.0.0-alpha...v2.1.0-alpha
[2.0.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.12.1-alpha...v2.0.0-alpha
[1.12.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.12.1-alpha...v1.12.2-alpha
[1.12.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.12.0-alpha...v1.12.1-alpha
[1.12.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.11.1-alpha...v1.12.0-alpha
[1.11.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.11.0-alpha...v1.11.1-alpha
[1.11.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.10.1-alpha...v1.11.0-alpha
[1.10.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.10.0-alpha...v1.10.1-alpha
[1.10.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.9.1-alpha...v1.10.0-alpha
[1.9.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.9.0-alpha...v1.9.1-alpha
[1.9.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.8.0-alpha...v1.9.0-alpha
[1.8.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.7.4-alpha...v1.8.0-alpha
[1.7.4-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.7.3-alpha...v1.7.4-alpha
[1.7.3-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.7.2-alpha...v1.7.3-alpha
[1.7.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.7.1-alpha...v1.7.2-alpha
[1.7.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.7.0-alpha...v1.7.1-alpha
[1.7.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.6.0-alpha...v1.7.0-alpha
[1.6.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.5.1-alpha...v1.6.0-alpha
[1.5.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.5.0-alpha...v1.5.1-alpha
[1.5.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.4.0-alpha...v1.5.0-alpha
[1.4.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.3.0-alpha...v1.4.0-alpha
[1.3.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.2.0-alpha...v1.3.0-alpha
[1.2.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.1.3-alpha...v1.2.0-alpha
[1.1.3-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.1.2-alpha...v1.1.3-alpha
[1.1.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.1.0-alpha...v1.1.2-alpha
[1.1.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.0.1-alpha...v1.1.0-alpha
[1.0.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.0.0-alpha...v1.0.1-alpha
[1.0.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.15.2-alpha...v1.0.0-alpha
[0.15.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.15.1-alpha...v0.15.2-alpha
[0.15.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.15.0-alpha...v0.15.1-alpha
[0.15.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.14.1-alpha...v0.15.0-alpha
[0.14.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.14.0-alpha...v0.14.1-alpha
[0.14.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.9-alpha...v0.14.0-alpha
[0.13.9-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.8-alpha...v0.13.9-alpha
[0.13.8-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.7-alpha...v0.13.8-alpha
[0.13.7-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.6-alpha...v0.13.7-alpha
[0.13.6-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.5-alpha...v0.13.6-alpha
[0.13.5-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.4-alpha...v0.13.5-alpha
[0.13.4-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.3-alpha...v0.13.4-alpha
[0.13.3-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.2-alpha...v0.13.3-alpha
[0.13.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.1-alpha...v0.13.2-alpha
[0.13.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.13.0-alpha...v0.13.1-alpha
[0.13.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.12.3-alpha...v0.13.0-alpha
[0.12.3-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.12.2-alpha...v0.12.3-alpha
[0.12.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.12.1-alpha...v0.12.2-alpha
[0.12.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.12.0-alpha...v0.12.1-alpha
[0.12.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.11.1-alpha...v0.12.0-alpha
[0.11.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.11.0-alpha...v0.11.1-alpha
[0.11.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.10-alpha...v0.11.0-alpha
[0.10.10-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.9-alpha...v0.10.10-alpha
[0.10.9-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.8-alpha...v0.10.9-alpha
[0.10.8-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.7-alpha...v0.10.8-alpha
[0.10.7-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.6-alpha...v0.10.7-alpha
[0.10.6-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.5-alpha...v0.10.6-alpha
[0.10.5-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.4-alpha...v0.10.5-alpha
[0.10.4-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.3-alpha...v0.10.4-alpha
[0.10.3-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.2-alpha...v0.10.3-alpha
[0.10.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.1-alpha...v0.10.2-alpha
[0.10.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.10.0-alpha...v0.10.1-alpha
[0.10.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.9.2-alpha...v0.10.0-alpha
[0.9.2-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.9.1-alpha...v0.9.2-alpha
[0.9.1-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.9.0-alpha...v0.9.1-alpha
[0.9.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.8.0-alpha...v0.9.0-alpha
[0.8.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.7.0-alpha...v0.8.0-alpha
[0.7.0-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.6.5-alpha...v0.7.0-alpha
[0.6.5-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.6.4-alpha...v0.6.5-alpha
[0.6.4-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.6.3-alpha...v0.6.4-alpha
[0.6.3-alpha]: https://github.com/Cyber-Syntax/my-unicorn/compare/v0.6.2-alpha...v0.6.3-alpha
