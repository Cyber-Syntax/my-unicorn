# My Unicorn first stable release

## Features

- Install via URL: Download and install AppImages directly from their GitHub repository URLs.
- Install from Catalog: Install AppImages from a catalog of compatible applications.
- Update Management: Backup/Remove existing AppImages and install the latest version. (Backup default enabled)
- Token Management: Securely manage GitHub API tokens. Save them in the GNOME keyring for secure storage.
- Backup Management: Create and manage backups of AppImages before updates.
- Desktop Entry Creation: Automatically create desktop entry files for AppImages to integrate them into the system menu.
- App Configuration: Use JSON configuration files to save AppImage version, appimage name for update checks.
- Global Configuration: Manage global settings such as maximum concurrent updates, backup limits and more.

## 🛠️ Usage Examples

### Installation

```bash
# Install via URL
python run.py install https://github.com/johannesjo/super-productivity

# Install from catalog
python run.py install appflowy,qownotes

# Install with options
python run.py install appflowy --no-icon --no-verify
```

### Updates

```bash
# Check for updates
python run.py update --check-only

# Update specific apps
python run.py update appflowy,joplin

# Update all installed apps
python run.py update
```

### Management

```bash
# List installed apps
python run.py list

# List available catalog apps
python run.py list --available

# Remove apps
python run.py remove appflowy --keep-config

# Show configuration
python run.py config --show
```

### Authentication

```bash
# Save GitHub token
python run.py auth --save-token

# Check auth status
python run.py auth --status

# Remove token
python run.py auth --remove-token
```

## 📋 Dependencies

### Core (working now)

- Python 3.12+

### Required Dependencies

```bash
pip install aiohttp uvloop tqdm keyring orjson
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

#### Catalog Entry (catalog/appflowy.json)

```json
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
        // direct link to an SVG image file hosted on GitHub's raw content server
        "url": "https://raw.githubusercontent.com/AppFlowy-IO/AppFlowy/main/frontend/resources/flowy_icons/40x/app_logo.svg",
        // used to name the icon file.
        "name": "appflowy.svg"
    }
}
```

```json
{
    "owner": "FreeTubeApp",
    "repo": "FreeTube",
    "appimage": {
        "rename": "freetube",
        "name_template": "{rename}-{latest_version}-{characteristic_suffix}.AppImage",
        "characteristic_suffix": ["amd64", "x86_64"]
    },
    "github": {
        "repo": true,
        "prerelease": true
    },
    "verification": {
        "digest": false,
        "skip": true,
        "checksum_file": "",
        "checksum_hash_type": "sha256"
    },
    "icon": {
        "url": "https://raw.githubusercontent.com/FreeTubeApp/FreeTube/development/_icons/icon.svg",
        "name": "freetube.svg"
    }
}
```

#### App-specific Config (~/.config/my-unicorn/apps/appflowy.json)

- Each of these files also represents the state of the installed appimages.
- appimage_version and appimage_name are mandatory fields.
- Other fields are needed only if the user installed unsupported appimage(with URL install)

```json
{
    // Configuration version for future migrations
    "config_version": "1.0.0",
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
        "url": "https://raw.githubusercontent.com/AppFlowy-IO/AppFlowy/main/frontend/resources/flowy_icons/40x/app_logo.svg",
        "name": "appflowy.svg",
        "installed": true
    }
}
```

```json
{
    "config_version": "1.0.0",
    "appimage": {
        "version": "v3.3.13",
        "name": "joplin.AppImage",
        "rename": "joplin",
        "name_template": "{rename}-{latest_version}.AppImage",
        "characteristic_suffix": [""],
        "installed_date": "2025-08-03T13:43:58.526732",
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
        "prerelease": false,
        "skip": false,
        "checksum_file": "latest-linux.yml",
        "checksum_hash_type": "sha512"
    },
    "icon": {
        "url": "https://raw.githubusercontent.com/laurent22/joplin/dev/Assets/LinuxIcons/256x256.png",
        "name": "joplin.png",
        "installed": true
    }
}
```

## Remove the package:

> [!TIP]
> This would remove the package if you installed globally.

    ```bash
    pip uninstall my-unicorn
    ```