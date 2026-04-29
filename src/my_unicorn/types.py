"""Domain types for business logic.

This module contains pure domain types used in business logic without
any IO or infrastructure dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from pathlib import Path


# =============================================================================
# Global Config Types
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


class VerificationMethod(TypedDict, total=False):
    """Single verification method result.

    Attributes:
        type: Verification method type ("skip", "digest", "checksum_file")
        status: Result status ("passed", "failed", "skipped")
        algorithm: Hash algorithm used ("SHA256", "SHA512")
        expected: Expected hash value with algorithm prefix
        computed: Computed hash value without prefix
        source: Source of expected hash ("github_api", "checksum_file")
        filename: Checksum filename for checksum_file method
        digest: Alternative single field for hash
    """

    type: str  # "skip", "digest", "checksum_file"
    status: str  # "passed", "failed", "skipped"
    algorithm: str  # "SHA256", "SHA512"
    expected: str
    computed: str
    source: str  # "github_api", "checksum_file"
    filename: str  # checksum filename (for checksum_file method)
    digest: str  # alternative single field (instead of computed/expected)


class StateVerification(TypedDict, total=False):
    """Verification state tracking.

    Attributes:
        passed: Whether verification passed overall (required)
        overall_passed: Same as passed, for backward compatibility
        actual_method: Primary method used (digest/checksum_file/skip)
        warning: Optional warning message from verification
        methods: Array of verification method results (required)
    """

    passed: bool
    overall_passed: bool
    actual_method: str  # "digest", "checksum_file", "skip"
    warning: str
    methods: list[VerificationMethod]


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


# TODO: url installation method is removed from method in last versions
# extraction is the only method and it is going to be the only supported method
# so remove the method field in both classes. issue #274
class IconConfigV2(TypedDict, total=False):
    """Icon configuration v2."""

    method: str  # "extraction"
    filename: str


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
# Workflow Result Types
# =============================================================================


@dataclass
class InstallPlan:
    """Plan for installation operations.

    Separates targets that need installation from those already installed.
    This provides clear separation of concerns for the installation workflow.
    """

    urls_needing_work: list[str]
    catalog_needing_work: list[str]
    already_installed: list[str]


# =============================================================================
# GitHub API types
# =============================================================================


@dataclass(slots=True, frozen=True)
class ChecksumFileInfo:
    """Information about detected checksum file."""

    filename: str
    url: str
    format_type: str  # 'yaml' or 'traditional'
