# Changelog
All notable changes to this project will be documented in this file.

## v0.10.8-alpha
### Changed
Implements GitHub API asset digest-based verification as the highest priority verification method, falling back to existing SHA file and release body extraction methods when digest is unavailable.

This release will not affect existing functionality, but it will fix the issue with the Zen Browser appimage verification.

Also, QOwnNotes migrate the verification method to the new GitHub API asset digest-based verification method and I can confirm that is also working for the QOwnNotes appimage.

## v0.10.7-alpha
### Fixed
Zen Browser verification issue with the appimage. This release will not affect existing functionality, but it will fix the issue with the Zen Browser appimage verification.

## v0.10.6-alpha
### Changed
Fixes the issue with asyncio event loop in the app and cleanup the failed appimage files. 

## v0.10.5-alpha
### Changed
Updated dependencies to the latest versions. This will not affect existing functionality, but it will improve the performance and security of the app.

## v0.10.4-alpha
### Changed
Fixes github action duplicate commits in release notes. This release will make it workflow to show only PR commits in the release notes. 

## v0.10.3-alpha
### Changed
Fix WeekToDo app 404 error. Also, added a output fix for the appimage who haven't provided by their developers in previous PR(forget to update changelog). This wouldn't require any changes to your existing configuration files.

## v0.10.2-alpha
### Changed
This will not affect existing functionality, but it will change the location of the logs. The logs will now be stored in `~/.local/state/myunicorn/` folder instead of repository dir. This is done to comply with the XDG Base Directory Specification.

## v0.10.1-alpha
### Changed
Added a new feature that allows github workflows to write who committed the changes to the release notes. Also created a test script to test the release notes generation. This will not affect existing functionality.

## v0.10.0-alpha
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
    "hash_type": "sha256",
    "appimage_name_template": "zen-{characteristic_suffix}.AppImage",
    "sha_name": "extracted_checksum",
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

## v0.9.2-alpha
### BREAKING CHANGES
Update your config files with choice 8. This release includes refactoring of the code to improve readability and maintainability. I refactored the variable names to be more readable and meaningful.

## v0.9.1-alpha
### Changed
This release includes a fix for the issue where the standard notes app repo name was `app` which script was using repo name to name the appimage, config, desktop file and backup files. The script now uses app_id to name the appimage and similar files. Changes is not breaking because app_id is still fallback to repo name if app_id is not found. I encourage you to use app_id in your config file to avoid any confusion in the future and solve the standard notes app issue.

## v0.9.0-alpha
### Changed
Added a new feature that allows you to install AppImages from the catalog of compatible apps instead of dealing with URLs. This will not affect existing functionality.

## v0.8.0-alpha
# BREAKING CHANGES
Added download more than 1 app at a time feature. `max_concurrent_updates` is added to the global config file and default value is 3. Migrate with choice migrate to add this default value to your settings.json file to be able to use this feature. 

You can change this value to any number you want, but be cautious of the API rate limits: 60 requests per hour without a token and 5000 requests per hour with one. Also, you cannot update more than 100 apps concurrently due to GitHub's secondary rate limits.

## v0.7.0-alpha
# BREAKING CHANGES
New max_backup parameter in the settings.json file. This will be used to limit the number of backups created for each app. The default value is 3. Use choice migrate to update settings.json with default value. 

Added github token usage for the app to increase the rate limit for the app. Please add your github token with app choice if you want to increase rate limit which would be 5000 requests per hour. If you do not add the token, the app will use the default rate limit of 60 requests per hour. Also if you don't use it, installation speed may be slower.


## v0.6.5-alpha
### Changed
feat: create desktop entry files for AppImages 

- Improved error handling during AppImage updates to ensure the 
  process continues even if one update fails.
- Added functionality to create and update desktop entry files for 
  AppImages.
- Updated .gitignore to include AppImage files.

## v0.6.4-alpha
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

## v0.6.3-alpha
### Changed
  - feat: add unit tests
  - chore: add init files for path
  - refactor: improve better error handling on verify.py
  - chore: add copilot instructions