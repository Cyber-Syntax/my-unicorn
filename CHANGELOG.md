# Changelog
All notable changes to this project will be documented in this file.

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