# my-unicorn

> [!NOTE]
> my-unicorn is a command-line tool designed to manage AppImages, including downloading, installing, and updating them.
>
> It simplifies the process of automated process of managing AppImages by leveraging the GitHub API for release information.

# Features

- Install via URL: Download and install AppImages directly from their GitHub repository URLs.
- Install from Catalog: Install AppImages from a catalog of compatible applications.
- Update Management: Automatically check for updates and apply them to installed AppImages.
- Token Management: Securely manage GitHub API tokens. Save them in the GNOME keyring for secure storage.
- Backup Management: Create and manage backups of AppImages before updates.
- Desktop Entry Creation: Automatically create desktop entry files for AppImages to integrate them into the system menu.
- App Configuration: Use JSON configuration files to save AppImage version, appimage name for update checks.
- Global Configuration: Manage global settings such as maximum concurrent updates and backup limits.

# Detail explanation of features

## Install via URL

This feature allows you to download and install AppImages directly from their GitHub repository URLs.

### download command (Choice 1)

To download a new AppImage, use the command:

```bash
my-unicorn download <app_name>
my-unicorn download https://github.com/laurent22/joplin
```

## Install from Catalog

- Basically, you can install apps with their repository names, like `joplin`, `freetube`, `siyuan`, `super-productivity`, etc.
- Some of the apps are use specific repository names like `standard-notes` uses `app` as its repository name,
 so you can install it with `standardnotes`. So, check the catalog to find the correct repository names.

### install command (Choice 2)

To install a new AppImage from a catalog of compatible apps, use the command:

```bash
my-unicorn install <app_name>
# example
my-unicorn install joplin
```

## Update Management

- Supports updating all installed AppImages with a single command.
- Supports updating all specific AppImages by their names with comma separated values.

### update command (Choice 3)

- This would update all the appimages you have installed with my-unicorn.
- Basicly, this command will check the configuration files of the apps you have installed
and update them if there is a new version available.
- To update an existing AppImage with --all flag to update all apps, use the command:

```bash
my-unicorn update --all
```

### update command with specific apps

To update specific AppImages, you can specify their names separated by commas:

```bash
my-unicorn update --apps <app_name1>,<app_name2>
# example
my-unicorn update --apps joplin,freetube
```

## Global Configuration

- Global configuration is stored in a JSON file, allowing users to customize the behavior of the tool.

### settings.json

This file contains global settings for the application, such as backup management, locale, and storage paths.

- keep_backup: Whether to keep backups of AppImages.
- max_backups: Maximum number of backups to keep for each AppImage.
- batch_mode: Whether to run the application in batch mode.
  - This means, without user interaction which it won't ask for confirmation on updates, only important messages will be shown.
- (Currently only english available)locale: The locale to use for the application.
- max_concurrent_updates: Maximum number of AppImages to update concurrently.
- app_storage_path: Path where AppImages are stored.
- app_backup_storage_path: Path where backups of AppImages are stored.
- app_download_path: Path where AppImages are downloaded.

```json
{
	"keep_backup": true,
	"max_backups": 1,
	"batch_mode": true,
	"locale": "en",
	"max_concurrent_updates": 5,
	"app_storage_path": "~/.local/share/myunicorn",
	"app_backup_storage_path": "~/.local/share/myunicorn/backups",
	"app_download_path": "~/Downloads"
}
```

## Backup Management

Automatically create backups of AppImages before updating them.
Automatically delete old backups based on a maximum backup limit.

## Desktop Entry Creation

## App Configuration

### app_config.json

This file contains the configuration for each AppImage, including the version and appimage name.

- version: The version of the AppImage.
- appimage_name: The exact name of the AppImage file developers provided.

```json
{
	"version": "3.197.0",
	"appimage_name": "standard-notes-3.197.0-linux-x86_64.AppImage"
}
```

## Token Management

Token management has been simplified to use only the GNOME keyring for secure storage.

### token commands (Choice 7)

To manage GitHub API tokens, you can use the following commands:

```bash

# for saving a new token
my-unicorn token --save
# remove the token
my-unicorn token --remove
# check the token rate limits
my unicorn token --check
# check the token status for expiration and storage
my-unicorn token --expiration
my-unicorn token --storage
# rotate the token
my-unicorn token --rotate

```
