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
- Progress Indicators: Visual progress bars for downloads and updates.
- Configuration Management: Store global and app-specific settings in configuration files for easy customization.
    - App Configuration: Store app-specific configurations in JSON files for easy management such as version, name, and verification settings.
    - Global Configuration: Store global settings in a configuration file for customization such as download directories, logging levels, and more.
- Cache Management: Handle caching of API assets and metadata to improve performance and reduce redundant API requests.

## Helper scripts

- setup.sh: A script to install my-unicorn and its dependencies.
    - It sets up a virtual environment and installs the required Python packages.
- venv-wrapper.bash: Wrapper script around my-unicorn using the python virtual environment
- update.bash: A script to automate process of checking for updates and updating my-unicorn itself.

## 🛠️ Usage Examples

### my-unicorn upgrade

```bash
# Check for upgrade
my-unicorn upgrade --check-only

# Upgrade my-unicorn
my-unicorn upgrade
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
my-unicorn catalog

# List available catalog apps with descriptions
my-unicorn catalog --available

# Show detailed information about an app
my-unicorn catalog --info appflowy

# Remove apps
my-unicorn remove appflowy --keep-config
my-unicorn remove appflowy qownotes

# Show configuration
my-unicorn config --show

# Migrate v1 configs to v2
my-unicorn migrate
```

### Authentication

```bash
# Save GitHub token
my-unicorn token --save

# Check auth status
my-unicorn auth --status

# Remove token
my-unicorn token --remove
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

## Uninstallation

### Global Uninstallation
>
> [!TIP]
> This would remove the package if you installed globally.

```bash
pip uninstall my-unicorn
```

### Local Uninstallation

> [!TIP]
> This would remove the package if you installed via the setup.sh uv-install method.

```bash
uv tool uninstall my-unicorn
```
