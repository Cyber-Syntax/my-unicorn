# My Unicorn Wiki 🦄

> [!NOTE]
> My Unicorn is a command-line tool to manage AppImages on Linux. It allows users to install, update, and manage AppImages from GitHub repositories easily. It's designed to simplify the process of handling AppImages, making it more convenient for users to keep their applications up-to-date.

## Features

- Install via URL: Install AppImages directly via GitHub repository URL.
- Catalog Support:
    - Predefined Catalog: A curated list of popular applications available for installation.
    - Install from Catalog: Install AppImages with a simple name from a predefined catalog of popular applications.
    - List Catalog: List all available applications in the catalog with descriptions.
- Update Management: Update installed AppImages to the latest version available on GitHub.
    - Check for Updates: Check for available updates without installing them.
    - Selective Updates: Update specific applications or all installed applications.
    - Update all: Update all installed AppImages with a single command.
- Remove Appimages: Remove installed AppImages with options to keep or delete configuration files.
- Token Management: Save and manage GitHub tokens for authenticated requests to avoid rate limiting.
- Backup Management: Automatically create and manage backups of installed AppImages before updating.
    - Backup Metadata: Maintain a metadata file for backups to track versions, creation dates, and file sizes.
    - Backup Cleanup: Automatically clean up old backups based on user-defined retention policies.
    - Backup Migration: Migrate old backup formats to the new metadata-based system.
- Verification: Verify the integrity of downloaded AppImages using SHA256 or SHA512 checksums.
- Concurrent Downloads: Support for multiple concurrent downloads to speed up the installation and update process.
- Batch Mode: Non-interactive mode for automated scripts and cron jobs.
- Logging: Detailed logging of operations for troubleshooting and auditing.
- Desktop Entry Creation: Automatically create desktop entries for installed AppImages.
- Icon Management: Extract icons from AppImages or download from specified URLs.
- Progress Indicators: Visual progress bars for downloads and updates using the rich library.
- Configuration Management: Store global and app-specific settings in configuration files for easy customization.
    - App Configuration: Store app-specific configurations in JSON files for easy management such as version, name, and verification settings.
    - Global Configuration: Store global settings in a configuration file for customization such as download directories, logging levels, and more.
- Cache Management: Handle caching of API assets and metadata to improve performance and reduce redundant API requests.

## Helper scripts

- my-unicorn-installer.sh: A script to install my-unicorn and its dependencies.
    - It sets up a virtual environment and installs the required Python packages.
- venv-wrapper.bash: Wrapper script around my-unicorn using the python virtual environment
- update.bash: A script to automate process of checking for updates and updating my-unicorn itself.

## 🛠️ Usage Examples

### my-unicorn self-update

```bash
# Check for update
my-unicorn self-update --check-only

# Update my-unicorn
my-unicorn self-update
```

### Installation

```bash
# Install via URL (Support concurrent installs)
my-unicorn install https://github.com/johannesjo/super-productivity
my-unicorn install https://github.com/nukeop/nuclear https://github.com/keepassxreboot/keepassxc/releases

# Install from catalog
my-unicorn install appflowy,qownotes
my-unicorn install appflowy qownotes

# Install with options
my-unicorn install appflowy --no-icon --no-verify
```

### Updates & Cache

```bash
# Check for updates without installation from cache (it creates cache if not exists)
my-unicorn update --check-only
# --refresh-cache: Bypass cache and fetch latest release data from GitHub (forces cache refresh)
my-unicorn update --check-only --refresh-cache

# This example shows how to force refresh cache and update a specific app.
py run.py update qownnotes --refresh-cache

# Update specific apps (it creates cache if not exists)
my-unicorn update appflowy,joplin
my-unicorn update appflowy joplin

# Update all installed apps
my-unicorn update
```

```bash
# Remove all cache related with qownnotes
my-unicorn cache clear qownnotes

# Remove all cache
my-unicorn cache clear --all 

# Show cache stats
my-unicorn cache --stats
```

### Catalog & Configuration

```bash
# List installed apps
my-unicorn list

# List available catalog apps
my-unicorn list --available

# Remove apps
my-unicorn remove appflowy --keep-config
my-unicorn remove appflowy qownotes

# Show configuration
my-unicorn config --show
```

### Authentication

```bash
# Save GitHub token
my-unicorn auth --save-token

# Check auth status
my-unicorn auth --status

# Remove token
my-unicorn auth --remove-token
```

### Backup

#### Basic Operations

```bash
# Create backup of current version
my-unicorn backup <app_name>

# Restore latest backup version
my-unicorn backup <app_name> --restore-last

# Restore specific version
my-unicorn backup <app_name> --restore-version <version>
```

#### Information & Management

```bash
# List backups for specific app
my-unicorn backup <app_name> --list-backups

# List all apps with backups
my-unicorn backup --list-backups

# Show detailed backup info
my-unicorn backup <app_name> --info

# Clean up old backups
my-unicorn backup --cleanup                 # All apps
my-unicorn backup <app_name> --cleanup      # Specific app

# Migrate old backup format
my-unicorn backup --migrate
```

## 📋 Dependencies

### Core

- Python 3.12+

### Required Dependencies

> [!TIP]
> These dependencies are already installed when you used my-unicorn-installer.sh to install my-unicorn.

```bash
pip install aiohttp uvloop keyring orjson packaging rich
```

### Cache Management

Example zen browser cache:

```bash
{
  "cached_at": "2025-08-30T16:55:48.294102+00:00",
  "ttl_hours": 24,
  "release_data": {
    "owner": "zen-browser",
    "repo": "desktop",
    "version": "1.15.2b",
    "prerelease": false,
    "assets": [
      {
        "name": "zen-aarch64.AppImage",
        "digest": "sha256:d0417f900e1e3af6a13e201cab54e35c4f50200292fef2c613e867de33c0d326",
        "size": 96831888,
        "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.2b/zen-aarch64.AppImage"
      },
      {
        "name": "zen-x86_64.AppImage",
        "digest": "sha256:9035c485921102f77fdfaa37536200fd7ce61ec9ae8f694c0f472911df182cbd",
        "size": 109846928,
        "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.2b/zen-x86_64.AppImage"
      }
    ],
    "original_tag_name": "1.15.2b"
  }
}
```

### Config Management

#### Global Config (settings.conf)

```INI
# Configuration version for migration support
config_version = 1.0.0

# This is the maximum number of concurrent downloads allowed.
# Please note that this value shouldn't be too high, as it may trigger rate limiting.
# The GitHub API allows around 30–50 concurrent requests, but this limit may change in the future.
max_concurrent_downloads = 5

# Maximum number of backups to keep for each AppImage.
max_backup = 1

# Enables batch mode for downloading AppImages without user interaction.
batch_mode = true

# Locale for the user interface and messages.
# Supported languages: English (en_US)
locale = "en_US"

# Logging level for the application.
# Supported levels: DEBUG, INFO, WARNING, ERROR
log_level = "INFO"

[network]
# Number of retry attempts for failed downloads
retry_attempts = 3

# Timeout for network requests.
timeout_seconds = 10

[directory]
# Directory for storing the code repository.
# The CLI script uses this directory to store the latest code files for updating packages.
repo = "~/.local/share/my-unicorn-repo/"

# Directory for storing package-related files, including virtual environments (.venv).
package = "~/.local/share/my-unicorn/"

# Default directory for downloaded AppImages, checksum files, and icons.
download = "~/Downloads"

# Directory for storing AppImages, backups, and icons after installation.
storage = "~/Applications"
backup = "~/Applications/backups"
icon = "~/Applications/icons"

# Directory for storing configuration files, logs, cache, and temporary files.
settings = "~/.config/my-unicorn/"
logs = "~/.config/my-unicorn/logs"
cache = "~/.config/my-unicorn/cache"
tmp = "~/.config/my-unicorn/tmp"
```

#### Catalog Configuration

##### 1. **Catalog Configuration Folder Structure**

> [!NOTE]
> Catalog entries are JSON files that contain metadata about the app, such as its name, version, and download URL.
> It's stored in the repository.

```
my-unicorn/my_unicorn/catalog/
  ├── appflowy.json
  ├── freetube.json
  └── obsidian.json
```

##### Catalog Entry JSON Structure

```jsonc
{
 "owner": "AppFlowy-IO",
 "repo": "AppFlowy",
 "appimage": {
  // default assigned to `repo` and only used for renaming the AppImage file. (good for `standardnotes/app` similar apps)
  "rename": "AppFlowy",
  "name_template": "{rename}-{latest_version}-linux-{characteristic_suffix}.AppImage",
  // List of suffixes that are preferred for the AppImage filename. (e.g `x86_64`, `linux`, `Qt6`)
  "characteristic_suffix": [""]
 },
 "github": {
  // app installed from github repo
  "repo": true,
  // Beta/prerelease used to download the latest beta version of the appimage.
  "prerelease": false
 },
 "verification": {
  // provided by the github api if the developer provides it.
  "digest": true,
  // Skipping the verification process.
  "skip": false,
  // file that contains the checksum of the downloaded file. (e.g "SHA256SUMS.txt", "latest-linux.yml")
  "checksum_file": "",
  // This is the hash type of the checksum file.
  //         - sha256 example files: SHA256SUMS.txt, <appimage_name>.AppImage.sha256sum
  //         - sha512 example files: latest-linux.yml, <appimage_name>.AppImage.sha512sum
  "checksum_hash_type": ""
 },
 "icon": {
  // icon extracted from the appimage after installation
  "extraction": true,
  // direct link to an SVG image file hosted on GitHub's raw content server
  // url is here for only reference because when extraction is true, url is not used and left empty.
  "url": "https://raw.githubusercontent.com/AppFlowy-IO/AppFlowy/main/frontend/resources/flowy_icons/40x/app_logo.svg",
  // used to name the icon file.
  "name": "appflowy.svg"
 }
}
```

#### App-specific Configuration

> [!NOTE]
> Each of these files also represents the state of the installed appimages.
> appimage_version and appimage_name are mandatory fields.
> Other fields are needed only if the user installed unsupported appimage(with URL install)

##### 1. **Configuration Folder Structure**

```
~/.config/my-unicorn/
  ├── tmp/
  ├── cache/
  ├── settings.conf
  ├── apps/
  │   ├── appflowy.json
  │   ├── obsidian.json
  │   └── qownnotes.json
  └── logs/
      ├── my-unicorn.log
      ├── my-unicorn.log.1
      ├── my-unicorn.log.2
      ├── my-unicorn.log.3
```

##### 2. **App-Specific Configuration JSON Structure**

> [!NOTE]
> Directory: `~/.config/my-unicorn/apps`

```jsonc
{
 // Configuration version for future migrations
 "config_version": "1.0.0",
 // source of installation (catalog or url)
 "source": "catalog",
 "appimage": {
  // Latest installed version of the appimage
  "version": "0.9.5",
  "name": "appflowy.AppImage",
  // used to rename installed appimage name (cleaning from version arch etc.)
  "rename": "appflowy",
  // template used on the appimage name
  "name_template": "{rename}-{latest_version}-linux-{characteristic_suffix}.AppImage",
  // suffix used on the appimage name
  "characteristic_suffix": ["x86_64", "amd64"],
  // installed date of the appimage
  "installed_date": "2025-08-03T14:57:00.204029",
  // digest algorithm used to verify the integrity of the appimage, provided by github api assets
  "digest": "sha256:bd8b9374ec9c59fa98b08080fa7f96696d135e6173213d039939f94cc757c587"
 },
 "owner": "AppFlowy-IO",
 "repo": "AppFlowy",
 "github": {
  "repo": true,
  "prerelease": false
 },
 "verification": {
  // Verify the appimage with digest algorithm
  "digest": true,
  // skip verification
  "skip": false,
  // checksum file used to verify the integrity of the appimage
  "checksum_file": "",
  // hash type used to verify the integrity of the appimage
  "checksum_hash_type": "sha256"
 },
 "icon": {
  // icon extracted from the appimage after installation
  "extraction": true,
  // direct link to an SVG image file hosted on GitHub's raw content server
  // url is here for only reference because when extraction is true, url is not used and left empty.
  "url": "https://raw.githubusercontent.com/AppFlowy-IO/AppFlowy/main/frontend/resources/flowy_icons/40x/app_logo.svg",
  // used to name the icon file.
  "name": "appflowy.svg",
  // source of the icon (extraction or url)
  "source": "extraction",
  // icon installed status
  "installed": true,
  // path to the installed icon
  "path": "/home/developer/Applications/icons/appflowy.svg"
 }
}
```

Example joplin.json:

```json
{
 "config_version": "1.0.0",
 "source": "catalog",
 "appimage": {
  "version": "3.3.13",
  "name": "joplin.AppImage",
  "rename": "joplin",
  "name_template": "{rename}-{latest_version}.AppImage",
  "characteristic_suffix": [""],
  "installed_date": "2025-08-30T13:01:35.442363",
  "digest": "sha256:22ff90b3846e2d2c9b2722d325fffa84775e362af9a4567a9fa8672e27c5a5bd"
 },
 "owner": "laurent22",
 "repo": "joplin",
 "github": {
  "repo": true,
  "prerelease": false
 },
 "verification": {
  "digest": true,
  "skip": false,
  "checksum_file": "latest-linux.yml",
  "checksum_hash_type": "sha256"
 },
 "icon": {
  "extraction": true,
  "url": "",
  "name": "joplin.png",
  "source": "extraction",
  "installed": true,
  "path": "/home/developer/Applications/icons/joplin.png"
 }
}
```

Example nuclear.json (installed via URL):

```json
{
 "config_version": "1.0.0",
 "source": "url",
 "appimage": {
  "version": "0.6.48",
  "name": "nuclear.AppImage",
  "rename": "nuclear",
  "name_template": "",
  "characteristic_suffix": [],
  "installed_date": "2025-08-30T12:38:28.387230",
  "digest": "sha256:937a8658f9fe3b891acecaeb64060722f4abae2c7d2cd9e726064626a9496c91"
 },
 "owner": "nukeop",
 "repo": "nuclear",
 "github": {
  "repo": true,
  "prerelease": false
 },
 "verification": {
  "digest": true,
  "skip": false,
  "checksum_file": "",
  "checksum_hash_type": "sha256"
 },
 "icon": {
  "extraction": true,
  "source": "extraction",
  "url": "",
  "name": "nuclear.png",
  "installed": true,
  "path": "/home/developer/Applications/icons/nuclear.png"
 }
}
```

#### Backup metadata.json implementation

##### 1. **Backup Storage Structure** ✅

```
~/Applications/backups/
  ├── appflowy/
  │   ├── appflowy-1.2.3.AppImage
  │   ├── appflowy-1.3.0.AppImage
  │   └── metadata.json
  └── obsidian/
      ├── obsidian-1.9.1.AppImage
      ├── obsidian-1.9.10.AppImage
      └── metadata.json
```

##### 2. **Metadata Structure (metadata.json)** ✅

> [!NOTE]
> file path: `~/Applications/backups/obsidian/metadata.json`

```json
{
 "versions": {
  "1.9.1": {
   "created": "2025-08-19T14:36:49.868125",
   "filename": "obsidian-1.9.1.AppImage",
   "sha256": "24471d25ed4d7d797a20a8ddf7b81ec43ae337f9ce495514dfdbb893307472b7",
   "size": 125682911
  },
  "1.9.10": {
   "created": "2025-08-19T14:01:21.787195",
   "filename": "obsidian-1.9.10.AppImage",
   "sha256": "24471d25ed4d7d797a20a8ddf7b81ec43ae337f9ce495514dfdbb893307472b7",
   "size": 125682911
  }
 }
}
```

## Uninstallation

### Global Uninstallation
>
> [!TIP]
> This would remove the package if you installed globally.

```bash
pip uninstall my-unicorn
```

### Local(venv) Uninstallation

- [ ] Work in progress
