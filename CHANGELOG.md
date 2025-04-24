# Changelog
All notable changes to this project will be documented in this file.

## v0.7.1-alpha
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