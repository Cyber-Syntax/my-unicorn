"""Domain types for business logic.

This module contains pure domain types used in business logic without
any IO or infrastructure dependencies.
"""

import platform
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from my_unicorn.utils.asset_validation import (
    is_appimage_file,
    is_checksum_file,
)


class Platform(Enum):
    """Supported platforms."""

    LINUX_X86_64 = "linux-x86_64"
    LINUX_ARM64 = "linux-arm64"
    LINUX_ARMV7 = "linux-armv7"
    UNKNOWN = "unknown"

    @classmethod
    def current(cls) -> "Platform":
        """Detect current platform."""
        machine = platform.machine().lower()
        system = platform.system().lower()

        if system != "linux":
            return cls.UNKNOWN

        if machine in ("x86_64", "amd64"):
            return cls.LINUX_X86_64
        if machine in ("aarch64", "arm64"):
            return cls.LINUX_ARM64
        if machine.startswith("arm"):
            return cls.LINUX_ARMV7

        return cls.UNKNOWN


class ChecksumType(Enum):
    """Checksum algorithm types."""

    SHA256 = "sha256"
    SHA512 = "sha512"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Asset:
    """Release asset information."""

    name: str
    url: str
    size: int
    content_type: str

    @property
    def is_appimage(self) -> bool:
        """Check if asset is an AppImage.

        Delegates to shared utility function for consistency across codebase.
        """
        return is_appimage_file(self.name)

    @property
    def is_checksum_file(self) -> bool:
        """Check if asset is a checksum file.

        Delegates to shared utility function for consistency across codebase.
        """
        return is_checksum_file(self.name)


@dataclass(frozen=True)
class Release:
    """GitHub release information."""

    tag_name: str
    name: str
    prerelease: bool
    published_at: str
    assets: list[Asset]

    @property
    def version(self) -> str:
        """Extract version from tag name."""
        # Remove 'v' prefix if present
        return self.tag_name.lstrip("v")


@dataclass(frozen=True)
class ReleaseData:
    """Structured release data from GitHub."""

    owner: str
    repo: str
    release: Release
    cached: bool = False
    cached_at: str | None = None


# =============================================================================
# Network and Configuration Types
# =============================================================================


class NetworkConfig(TypedDict):
    """Network configuration options."""

    retry_attempts: int
    timeout_seconds: int


class DirectoryConfig(TypedDict):
    """Directory paths configuration."""

    download: Path
    storage: Path
    backup: Path
    icon: Path
    settings: Path
    logs: Path
    cache: Path


class GlobalConfig(TypedDict):
    """Global application configuration."""

    config_version: str
    max_concurrent_downloads: int
    max_backup: int
    log_level: str
    console_log_level: str
    network: NetworkConfig
    directory: DirectoryConfig


# =============================================================================
# V1 Configuration Types (DEPRECATED - Migration Only)
# These types are only used for detecting and migrating v1 configs.
# Do NOT use in new code.
# =============================================================================

# V1 types removed - see migration code if needed


# =============================================================================
# Icon Types
# =============================================================================


# =============================================================================
# Cache Types
# =============================================================================


class CacheEntry(TypedDict):
    """Cache entry structure for storing release data."""

    cached_at: str  # ISO 8601 timestamp
    ttl_hours: int  # Cache TTL in hours
    release_data: dict[str, Any]  # GitHubReleaseDetails structure


# =============================================================================
# Config V2.0.0 Types
# =============================================================================


class AppMetadata(TypedDict, total=False):
    """Application metadata for v2.0.0 configs."""

    name: str
    display_name: str
    description: str


class SourceConfig(TypedDict):
    """Source configuration for app retrieval."""

    type: str  # "github"
    owner: str
    repo: str
    prerelease: bool


class NamingConfig(TypedDict):
    """AppImage naming configuration."""

    template: str
    target_name: str
    architectures: list[str]


class AppImageConfigV2(TypedDict):
    """AppImage configuration v2."""

    naming: NamingConfig


class VerificationMethod(TypedDict, total=False):
    """Single verification method result."""

    type: str  # "skip", "digest", "checksum_file"
    status: str  # "passed", "failed", "skipped"
    algorithm: str  # "sha256", "sha512"
    expected: str
    computed: str
    source: str  # "github_api", "release_assets"


class StateVerification(TypedDict):
    """Verification state tracking."""

    passed: bool
    methods: list[VerificationMethod]


class StateIcon(TypedDict):
    """Icon state tracking."""

    installed: bool
    method: str  # "extraction" or "none"
    path: str


class AppState(TypedDict):
    """Runtime state for installed app."""

    version: str
    installed_date: str
    installed_path: str
    verification: StateVerification
    icon: StateIcon


class VerificationConfigV2(TypedDict, total=False):
    """Verification configuration v2."""

    method: str  # "skip", "digest", "checksum_file"
    checksum_file: dict[str, Any]  # Only if method == "checksum_file"


class IconConfigV2(TypedDict, total=False):
    """Icon configuration v2."""

    method: str  # "extraction"
    filename: str


class AppOverrides(TypedDict, total=False):
    """User overrides for catalog apps or full config for URL installs."""

    metadata: AppMetadata
    source: SourceConfig
    appimage: AppImageConfigV2
    verification: VerificationConfigV2
    icon: IconConfigV2


class AppStateConfig(TypedDict):
    """App state configuration stored in apps/*.json files.

    This represents the hybrid storage model:
    - Catalog apps: state + catalog_ref + optional overrides
    - URL apps: state + complete config in overrides
    """

    config_version: str
    source: str  # "catalog" or "url"
    catalog_ref: str | None
    state: AppState
    overrides: AppOverrides  # Optional for catalog, required for URL


class CatalogConfig(TypedDict):
    """Catalog entry configuration from catalog/*.json files.

    Defines the default configuration for applications in the catalog.
    Used as base configuration that can be overridden by user settings.
    """

    config_version: str
    metadata: AppMetadata
    source: SourceConfig
    appimage: AppImageConfigV2
    verification: VerificationConfigV2
    icon: IconConfigV2


# =============================================================================
# Workflow Result Types (Phase 2: Type Safety Improvements)
# =============================================================================


@dataclass
class InstallResult:
    """Result of an installation operation.

    Provides type-safe alternative to dictionary return values
    for install operations.
    """

    success: bool
    app_name: str
    version: str
    message: str
    source: str  # "catalog" or "url"
    installed_path: str | None = None
    desktop_entry: str | None = None
    icon_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary representation of install result

        """
        result: dict[str, Any] = {
            "success": self.success,
            "app_name": self.app_name,
            "version": self.version,
            "message": self.message,
            "source": self.source,
        }

        if self.installed_path:
            result["installed_path"] = self.installed_path
        if self.desktop_entry:
            result["desktop"] = self.desktop_entry
        if self.icon_path:
            result["icon"] = self.icon_path
        if self.error:
            result["error"] = self.error

        return result


@dataclass
class UpdateResult:
    """Result of an update operation.

    Provides type-safe alternative to dictionary return values
    for update operations.
    """

    success: bool
    app_name: str
    old_version: str
    new_version: str
    message: str
    updated_path: str | None = None
    backup_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary representation of update result

        """
        result: dict[str, Any] = {
            "success": self.success,
            "app_name": self.app_name,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "message": self.message,
        }

        if self.updated_path:
            result["updated_path"] = self.updated_path
        if self.backup_path:
            result["backup_path"] = self.backup_path
        if self.error:
            result["error"] = self.error

        return result


@dataclass
class InstallPlan:
    """Plan for installation operations.

    Separates targets that need installation from those already installed.
    This provides clear separation of concerns for the installation workflow.
    """

    urls_needing_work: list[str]
    catalog_needing_work: list[str]
    already_installed: list[str]
