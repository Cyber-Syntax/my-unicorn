#!/usr/bin/env python3
"""Asset data models.

This module defines data structures for GitHub release assets.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReleaseAsset:
    """Represents a GitHub release asset."""

    name: str
    browser_download_url: str
    size: int
    content_type: str


@dataclass
class AppImageAsset:
    """Represents an AppImage asset from a GitHub release."""

    name: str
    browser_download_url: str
    size: int | None = None
    content_type: str | None = None

    @classmethod
    def from_github_asset(cls, asset: dict) -> "AppImageAsset":
        """Create an AppImageAsset from a GitHub API asset dictionary.

        Args:
            asset: GitHub API asset information dictionary

        Returns:
            AppImageAsset: New AppImageAsset instance

        """
        return cls(
            name=asset["name"],
            browser_download_url=asset["browser_download_url"],
            size=asset.get("size"),
            content_type=asset.get("content_type"),
        )


@dataclass
class SHAAsset:
    """Represents a SHA checksum asset from a GitHub release."""

    name: str
    browser_download_url: str
    hash_type: str
    size: int | None = None

    @classmethod
    def from_github_asset(cls, asset: dict, hash_type: str = "sha256") -> "SHAAsset":
        """Create a SHAAsset from a GitHub API asset dictionary.

        Args:
            asset: GitHub API asset information dictionary
            hash_type: Type of hash algorithm used (sha256, sha512, etc.)

        Returns:
            SHAAsset: New SHAAsset instance

        """
        return cls(
            name=asset["name"],
            browser_download_url=asset["browser_download_url"],
            hash_type=hash_type,
            size=asset.get("size"),
        )


@dataclass
class ArchitectureInfo:
    """Represents architecture information for asset selection."""

    name: str
    keywords: list[str]
    incompatible_archs: list[str]

    @classmethod
    def from_current_system(cls) -> "ArchitectureInfo":
        """Create an ArchitectureInfo based on the current system architecture.

        Returns:
            ArchitectureInfo: New ArchitectureInfo instance for current system

        """
        from src.utils import arch_utils

        current_arch = arch_utils.get_current_arch()
        return cls(
            name=current_arch,
            keywords=arch_utils.get_arch_keywords(current_arch),
            incompatible_archs=arch_utils.get_incompatible_archs(current_arch),
        )


@dataclass
class ReleaseInfo:
    """Represents processed GitHub release information."""

    owner: str
    repo: str
    version: str
    appimage_name: str
    app_download_url: str
    sha_name: str | None = None
    sha_download_url: str | None = None
    hash_type: str | None = None
    arch_keyword: str | None = None
    release_notes: str | None = None
    release_url: str | None = None
    is_prerelease: bool = False
    published_at: str | None = None
    extracted_hash_from_body: str | None = None  # For hash extracted from release body
    asset_digest: str | None = None  # For GitHub API asset digest verification

    @classmethod
    def from_release_data(cls, release_data: dict, asset_info: dict) -> "ReleaseInfo":
        """Create a ReleaseInfo from GitHub release data and processed asset information.

        Args:
            release_data: Raw release data from GitHub API
            asset_info: Dictionary with processed asset information

        Returns:
            ReleaseInfo: New ReleaseInfo instance

        """
        return cls(
            owner=asset_info["owner"],
            repo=asset_info["repo"],
            version=asset_info["version"],
            appimage_name=asset_info["appimage_name"],
            app_download_url=asset_info["app_download_url"],
            sha_name=asset_info.get("sha_name"),
            sha_download_url=asset_info.get("sha_download_url"),
            hash_type=asset_info.get("hash_type"),
            extracted_hash_from_body=asset_info.get("extracted_hash_from_body"),  # Get new field
            asset_digest=asset_info.get("asset_digest"),  # Get asset digest field
            arch_keyword=asset_info.get("arch_keyword"),
            release_notes=release_data.get("body", ""),
            release_url=release_data.get("html_url", ""),
            is_prerelease=release_data.get("prerelease", False),
            published_at=release_data.get("published_at", ""),
        )
