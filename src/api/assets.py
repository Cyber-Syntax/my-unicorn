#!/usr/bin/env python3
"""Asset data models.

This module defines data structures for GitHub release assets.
"""

from dataclasses import dataclass, field # Added field
from typing import Dict, List, Optional, Any # Added Any

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
    size: Optional[int] = None
    content_type: Optional[str] = None

    @classmethod
    def from_github_asset(cls, asset: Dict) -> "AppImageAsset":
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
    size: Optional[int] = None

    @classmethod
    def from_github_asset(cls, asset: Dict, hash_type: str = "sha256") -> "SHAAsset":
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
    keywords: List[str]
    incompatible_archs: List[str]

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
    appimage_url: str
    sha_name: Optional[str] = None
    sha_url: Optional[str] = None
    hash_type: Optional[str] = None
    arch_keyword: Optional[str] = None
    release_notes: Optional[str] = None
    release_url: Optional[str] = None
    is_prerelease: bool = False
    published_at: Optional[str] = None
    extracted_hash_from_body: Optional[str] = None # For hash extracted from release body
    raw_assets: List[Dict[str, Any]] = field(default_factory=list) # Added for storing all assets

    @classmethod
    def from_release_data(cls, release_data: Dict, asset_info: Dict) -> "ReleaseInfo":
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
            appimage_url=asset_info["appimage_url"],
            sha_name=asset_info.get("sha_name"),
            sha_url=asset_info.get("sha_url"),
            hash_type=asset_info.get("hash_type"),
            extracted_hash_from_body=asset_info.get("extracted_hash_from_body"), # Get new field
            arch_keyword=asset_info.get("arch_keyword"),
            release_notes=release_data.get("body", ""),
            release_url=release_data.get("html_url", ""),
            is_prerelease=release_data.get("prerelease", False),
            published_at=release_data.get("published_at", ""),
            raw_assets=release_data.get("assets", []), # Populate raw_assets
        )
