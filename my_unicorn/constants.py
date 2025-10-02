"""Centralized constants module for my-unicorn application.

This module serves as the single source of truth for all shared constants
across the my-unicorn codebase. Constants are organized by logical categories
and use typing.Final annotations to ensure immutability.

Usage:
    from my_unicorn.constants import CONFIG_VERSION
"""

from typing import Final, Literal

# =============================================================================
# Configuration Constants
# =============================================================================

# Configuration version - single source of truth for config versioning
CONFIG_VERSION: Final[str] = "1.0.2"

# Configuration directory and file names
CONFIG_FILE_NAME: Final[str] = "settings.conf"

# Default config directory name under the user's home directory
CONFIG_DIR_NAME: Final[str] = ".config"

# Application-specific subdirectory under the config directory
DEFAULT_CONFIG_SUBDIR: Final[str] = "my-unicorn"

# Default apps dir name under config
DEFAULT_APPS_DIR_NAME: Final[str] = "apps"

# Configuration defaults
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_BACKUP_COUNT: Final[int] = 3

# Defaults used by the global config manager
DEFAULT_MAX_CONCURRENT_DOWNLOADS: Final[int] = 5
DEFAULT_MAX_BACKUP: Final[int] = 1
DEFAULT_BATCH_MODE: Final[bool] = True
DEFAULT_LOCALE: Final[str] = "en_US"
DEFAULT_CONSOLE_LOG_LEVEL: Final[str] = "WARNING"

# Date/time formats used in config headers and saved timestamps
ISO_DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# Config section and key names
SECTION_DEFAULT: Final[str] = "DEFAULT"
SECTION_NETWORK: Final[str] = "network"
SECTION_DIRECTORY: Final[str] = "directory"

KEY_CONFIG_VERSION: Final[str] = "config_version"
KEY_MAX_CONCURRENT_DOWNLOADS: Final[str] = "max_concurrent_downloads"
KEY_MAX_BACKUP: Final[str] = "max_backup"
KEY_BATCH_MODE: Final[str] = "batch_mode"
KEY_LOCALE: Final[str] = "locale"
KEY_LOG_LEVEL: Final[str] = "log_level"
KEY_CONSOLE_LOG_LEVEL: Final[str] = "console_log_level"

# Known directory keys expected in the directory section
DIRECTORY_KEYS: Final[tuple[str, ...]] = (
    "repo",
    "package",
    "download",
    "storage",
    "backup",
    "icon",
    "settings",
    "logs",
    "cache",
    "tmp",
)

# =============================================================================
# Configuration migration constants
# =============================================================================

# Timestamp format used when creating backup filenames for configs
CONFIG_BACKUP_TIMESTAMP_FORMAT: Final[str] = "%Y%m%d_%H%M%S"

# Backup filename extension and glob pattern pieces
CONFIG_BACKUP_EXTENSION: Final[str] = ".backup"

# Template for backup suffix (used with timestamp)
CONFIG_BACKUP_SUFFIX_TEMPLATE: Final[str] = ".{timestamp}.backup"

# Fallback versions used by migration checks
CONFIG_FALLBACK_OLD_VERSION: Final[str] = "0.0.0"
CONFIG_FALLBACK_PREVIOUS_VERSION: Final[str] = "1.0.0"

# Config migration print prefix for console fallback messages
CONFIG_MIGRATION_PRINT_PREFIX: Final[str] = "Config Migration"

# Network and directory key names used in migration/validation
KEY_RETRY_ATTEMPTS: Final[str] = "retry_attempts"
KEY_TIMEOUT_SECONDS: Final[str] = "timeout_seconds"

KEY_REPO: Final[str] = "repo"
KEY_STORAGE: Final[str] = "storage"

# =============================================================================
# Logging Constants
# =============================================================================

# Maximum size for rotated log files (bytes)
LOG_MAX_FILE_SIZE_BYTES: Final[int] = 1024 * 1024  # 1 MB

# Number of backup files to keep for rotated logs (defaults to global backup)
LOG_BACKUP_COUNT: Final[int] = DEFAULT_BACKUP_COUNT

# Console and file format strings used by the logger
LOG_CONSOLE_FORMAT: Final[str] = (
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOG_CONSOLE_DATE_FORMAT: Final[str] = "%H:%M:%S"
LOG_FILE_FORMAT: Final[str] = (
    "%(asctime)s - %(name)s - %(levelname)s - "
    "%(funcName)s:%(lineno)d - %(message)s"
)
LOG_FILE_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# Color mapping for console output levels
LOG_COLORS: Final[dict[str, str]] = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",
}

# =============================================================================
# Desktop (.desktop) file related constants
# =============================================================================

# User-specific applications subpath under the home directory, expressed as
# path parts so callers can join with Path.home(). Example: (~, .local, share,
# applications)
DESKTOP_USER_APPLICATIONS_SUBPATH: Final[tuple[str, ...]] = (
    ".local",
    "share",
    "applications",
)

# System application directories to check (in order of preference)
DESKTOP_SYSTEM_APPLICATION_DIRS: Final[tuple[str, ...]] = (
    "/usr/local/share/applications",
    "/usr/share/applications",
)

# Desktop file section header and version
DESKTOP_SECTION_HEADER: Final[str] = "[Desktop Entry]"
DESKTOP_FILE_VERSION: Final[str] = "1.0"
DESKTOP_FILE_TYPE: Final[str] = "Application"

# Exec parameter to append for browsers to accept a URL
DESKTOP_BROWSER_EXEC_PARAM: Final[str] = "%u"

# Default categories used for desktop entries
DESKTOP_BROWSER_CATEGORIES: Final[tuple[str, ...]] = ("Network", "WebBrowser")
DESKTOP_DEFAULT_CATEGORIES: Final[tuple[str, ...]] = ("Utility",)

# Default keywords for browsers
DESKTOP_BROWSER_KEYWORDS: Final[tuple[str, ...]] = (
    "web",
    "browser",
    "internet",
)

# Common browser MIME types
DESKTOP_BROWSER_MIME_TYPES: Final[tuple[str, ...]] = (
    "text/html",
    "text/xml",
    "application/xhtml+xml",
    "application/xml",
    "application/rss+xml",
    "application/rdf+xml",
    "image/gif",
    "image/jpeg",
    "image/png",
    "x-scheme-handler/http",
    "x-scheme-handler/https",
    "x-scheme-handler/ftp",
    "x-scheme-handler/chrome",
    "video/webm",
    "application/x-xpinstall",
)

# Known browser executable names to help auto-detection
DESKTOP_BROWSER_NAMES: Final[tuple[str, ...]] = (
    "zen-browser",
    "firefox",
    "chrome",
    "chromium",
    "brave",
    "vivaldi",
    "opera",
    "edge",
    "safari",
    "tor-browser",
    "librewolf",
    "waterfox",
)

# Icon file extensions to probe when resolving icons
DESKTOP_ICON_EXTENSIONS: Final[tuple[str, ...]] = (
    ".png",
    ".svg",
    ".ico",
    ".xpm",
)

# =============================================================================
# Icon acquisition related constants
# =============================================================================

# Default icon extension used when none can be inferred from a URL
DEFAULT_ICON_EXTENSION: Final[str] = "png"

# Supported icon file extensions (used when extracting/extensions detection)
SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".svg", ".png", ".ico"}
)

# Icon source identifiers used by the icon acquisition service
ICON_SOURCE_EXTRACTION: Final[str] = "extraction"
ICON_SOURCE_GITHUB: Final[str] = "github"
ICON_SOURCE_NONE: Final[str] = "none"

# =============================================================================
# Backup service constants
# =============================================================================

# Filename for backup metadata stored per-app
BACKUP_METADATA_FILENAME: Final[str] = "metadata.json"

# Suffix used for corrupted metadata backups
BACKUP_METADATA_CORRUPTED_SUFFIX: Final[str] = ".json.corrupted"

# Temporary file naming for atomic metadata writes
BACKUP_METADATA_TMP_PREFIX: Final[str] = ".metadata_"
BACKUP_METADATA_TMP_SUFFIX: Final[str] = ".json.tmp"

# Temporary file suffix used when creating temp backup copies
BACKUP_TEMP_SUFFIX: Final[str] = ".tmp"

# Default datetime format used in backup metadata created timestamps
BACKUP_METADATA_DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S"

# Old flat backup filename glob for migration
OLD_FLAT_BACKUP_GLOB: Final[str] = "*.backup.AppImage"

# New AppImage filename suffix used when migrating (case sensitive)
APPIMAGE_SUFFIX: Final[str] = ".AppImage"

# =============================================================================
# Hashing / verification constants
# =============================================================================

# Supported hash algorithms across verification code
SUPPORTED_HASH_ALGORITHMS: Final[tuple[str, ...]] = (
    "sha1",
    "sha256",
    "sha512",
    "md5",
)

# Default hash algorithm when none is specified/detected
DEFAULT_HASH_TYPE: Final[str] = "sha256"

# Default hash to prefer for YAML checksum files
YAML_DEFAULT_HASH: Final[str] = "sha512"

# Preferred order when checking multiple hash types
HASH_PREFERENCE_ORDER: Final[tuple[str, ...]] = (
    "sha512",
    "sha256",
    "sha1",
    "md5",
)

# Type alias for supported hash types used across verification modules
HashType = Literal["sha1", "sha256", "sha512", "md5"]
