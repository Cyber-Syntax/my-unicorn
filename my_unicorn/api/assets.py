#!/usr/bin/env python3
"""Asset data models.

This module defines data structures for GitHub release assets.
"""

from dataclasses import dataclass
from typing import NotRequired, TypedDict


@dataclass
class github_asset(TypedDict):
    """GitHub API asset information dictionary.

    This make sure that the release information is come with correct types and values.
    """

    name: str
    browser_download_url: str
    size: int
    content_type: NotRequired[str]


@dataclass
class AppImageAsset:
    """Represents an AppImage asset from a GitHub release."""

    name: str
    browser_download_url: str
    size: int
    content_type: str | None = None

    @classmethod
    def from_github_asset(cls, asset: github_asset) -> "AppImageAsset":
        """Create an AppImageAsset from a GitHub API asset dictionary.

        Args:
            asset: GitHub API asset information dictionary

        Returns:
            AppImageAsset: New AppImageAsset instance

        """
        return cls(
            name=asset["name"],
            browser_download_url=asset["browser_download_url"],
            size=asset.get("size", 0),
            content_type=asset.get("content_type"),
        )


@dataclass
class SHAAsset:
    """Represents a SHA checksum asset from a GitHub release."""

    name: str
    browser_download_url: str
    checksum_hash_type: str

    @classmethod
    def from_github_asset(
        cls, asset: dict[str, str], checksum_hash_type: str = "sha256"
    ) -> "SHAAsset":
        """Create a SHAAsset from a GitHub API asset dictionary.

        Args:
            asset: GitHub API asset information dictionary
            checksum_hash_type: Type of hash algorithm used (sha256, sha512, etc.)

        Returns:
            SHAAsset: New SHAAsset instance

        """
        return cls(
            name=asset["name"],
            browser_download_url=asset["browser_download_url"],
            checksum_hash_type=checksum_hash_type,
        )


@dataclass
class ReleaseData(TypedDict):
    """GitHub API release information dictionary.

    This make sure that the release information is come with correct types and values.
    """

    prerelease: bool


@dataclass
class ReleaseInfo:
    """Represents processed GitHub release information."""

    owner: str
    repo: str
    version: str
    appimage_name: str
    app_download_url: str
    prerelease: bool = False

    arch_keyword: str | None = None
    checksum_file_name: str | None = None
    checksum_file_download_url: str | None = None
    checksum_hash_type: str | None = None
    asset_digest: str | None = None
    extracted_hash_from_body: str | None = None

    release_notes: str | None = None
    release_url: str | None = None
    published_at: str | None = None

    @classmethod
    def from_release_data(
        cls, release_data: ReleaseData, asset_info: dict[str, str]
    ) -> "ReleaseInfo":
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
            checksum_file_name=asset_info.get("checksum_file_name"),
            checksum_file_download_url=asset_info.get("checksum_file_download_url"),
            checksum_hash_type=asset_info.get("checksum_hash_type"),
            extracted_hash_from_body=asset_info.get("extracted_hash_from_body"),
            asset_digest=asset_info.get("asset_digest"),
            arch_keyword=asset_info.get("arch_keyword"),
            release_notes=asset_info.get("body", ""),
            release_url=asset_info.get("html_url", ""),
            published_at=asset_info.get("published_at", ""),
            prerelease=release_data.get("prerelease", False),
        )
