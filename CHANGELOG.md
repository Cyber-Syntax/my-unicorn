# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.11.0-alpha]

### Added

- Network retry support for improved reliability and resilience.

## Changed

- Updated changelog links

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

[unreleased]: https://github.com/Cyber-Syntax/my-unicorn/compare/v1.11.0-alpha...HEAD
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
