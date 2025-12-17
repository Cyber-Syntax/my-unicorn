"""Centralized type definitions for my-unicorn.

This module contains all TypedDict definitions used across the application
to ensure consistency and avoid duplication.
"""

from pathlib import Path
from typing import Any, TypedDict

# =============================================================================
# Network and Configuration Types
# =============================================================================


class NetworkConfig(TypedDict):
    """Network configuration options."""

    retry_attempts: int
    timeout_seconds: int


class DirectoryConfig(TypedDict):
    """Directory paths configuration."""

    repo: Path
    package: Path
    download: Path
    storage: Path
    backup: Path
    icon: Path
    settings: Path
    logs: Path
    cache: Path
    tmp: Path


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
# AppImage Configuration Types
# =============================================================================


class AppImageConfig(TypedDict):
    """AppImage specific configuration."""

    version: str
    name: str
    rename: str
    name_template: str
    characteristic_suffix: list[str]
    installed_date: str
    digest: str


class GitHubConfig(TypedDict):
    """GitHub API configuration options."""

    repo: bool
    prerelease: bool


class VerificationConfig(TypedDict):
    """Verification configuration options."""

    digest: bool
    skip: bool
    checksum_file: str
    checksum_hash_type: str


# =============================================================================
# Icon Types (Note: Two different IconAsset types exist)
# =============================================================================


class ConfigIconAsset(TypedDict):
    """Icon configuration in app/catalog config files."""

    url: str
    name: str
    installed: bool


class DownloadIconAsset(TypedDict):
    """Icon asset information for download operations."""

    icon_filename: str
    icon_url: str


# =============================================================================
# Application Configuration Types
# =============================================================================


class AppConfig(TypedDict):
    """Per-application configuration."""

    owner: str
    repo: str
    config_version: str
    appimage: AppImageConfig
    github: GitHubConfig
    verification: VerificationConfig
    icon: ConfigIconAsset


class CatalogAppImageConfig(TypedDict):
    """AppImage configuration within catalog entry."""

    rename: str
    name_template: str
    characteristic_suffix: list[str]


class CatalogEntry(TypedDict):
    """Catalog entry for an application."""

    owner: str
    repo: str
    appimage: CatalogAppImageConfig
    verification: VerificationConfig
    icon: ConfigIconAsset | None


# =============================================================================
# Cache Types
# =============================================================================


class CacheEntry(TypedDict):
    """Cache entry structure for storing release data."""

    cached_at: str  # ISO 8601 timestamp
    ttl_hours: int  # Cache TTL in hours
    release_data: dict[str, Any]  # GitHubReleaseDetails structure
