"""GitHub release model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from my_unicorn.core.github.version_utils import extract_and_validate_version

if TYPE_CHECKING:
    from my_unicorn.core.github.models.asset import Asset


@dataclass(slots=True, frozen=True)
class Release:
    """Represents a GitHub release with its metadata and assets.

    Attributes:
        owner: Repository owner
        repo: Repository name
        version: Normalized version string
        prerelease: Whether this is a prerelease
        assets: List of release assets
        original_tag_name: Original tag name from GitHub

    """

    owner: str
    repo: str
    version: str
    prerelease: bool
    assets: list[Asset]
    original_tag_name: str

    @classmethod
    def from_api_response(
        cls, owner: str, repo: str, api_data: dict[str, Any]
    ) -> Release:
        """Create Release from GitHub API response data.

        Args:
            owner: Repository owner
            repo: Repository name
            api_data: Raw release data from GitHub API

        Returns:
            Release instance

        """
        from my_unicorn.core.github.models.asset import Asset  # noqa: PLC0415

        tag_name = api_data.get("tag_name", "")
        version = cls._normalize_version(tag_name)
        prerelease = api_data.get("prerelease", False)

        # Convert assets
        assets = []
        for asset_data in api_data.get("assets", []):
            asset = Asset.from_api_response(asset_data)
            if asset:
                assets.append(asset)

        return cls(
            owner=owner,
            repo=repo,
            version=version,
            prerelease=prerelease,
            assets=assets,
            original_tag_name=tag_name,
        )

    @staticmethod
    def _normalize_version(tag_name: str) -> str:
        """Normalize version by extracting and sanitizing version string.

        Args:
            tag_name: Version tag that may have 'v' prefix or package format

        Returns:
            Sanitized version string

        """
        if not tag_name:
            return ""

        normalized = extract_and_validate_version(tag_name)
        if normalized is None:
            return tag_name.lstrip("v")

        return normalized

    def to_dict(self) -> dict[str, Any]:
        """Convert Release to dictionary for caching.

        Returns:
            Dictionary representation suitable for JSON serialization

        """
        return {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "prerelease": self.prerelease,
            "assets": [
                {
                    "name": asset.name,
                    "size": asset.size,
                    "digest": asset.digest,
                    "browser_download_url": asset.browser_download_url,
                }
                for asset in self.assets
            ],
            "original_tag_name": self.original_tag_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Release:
        """Create Release from dictionary (e.g., from cache).

        Args:
            data: Dictionary representation of a release

        Returns:
            Release instance

        """
        from my_unicorn.core.github.models.asset import Asset  # noqa: PLC0415

        assets = [
            Asset(
                name=a["name"],
                size=a["size"],
                digest=a.get("digest", ""),
                browser_download_url=a["browser_download_url"],
            )
            for a in data.get("assets", [])
        ]

        return cls(
            owner=data["owner"],
            repo=data["repo"],
            version=data["version"],
            prerelease=data["prerelease"],
            assets=assets,
            original_tag_name=data["original_tag_name"],
        )

    def get_appimages(self) -> list[Asset]:
        """Get all AppImage assets from this release.

        Returns:
            List of AppImage assets

        """
        return [asset for asset in self.assets if asset.is_appimage()]

    def filter_for_platform(self) -> Release:
        """Return new Release with only platform-relevant assets.

        Filters assets to include only:
        - Linux x86_64 AppImages (excludes Windows, macOS, ARM)
        - Checksum files for compatible AppImages

        This method uses AssetSelector.filter_for_cache() for consistent
        filtering across the application.

        Returns:
            New Release instance with filtered assets

        """
        # Import here to avoid circular imports
        from my_unicorn.core.github.models import (  # noqa: PLC0415
            AssetSelector,
        )

        filtered_assets = AssetSelector.filter_for_cache(self.assets)
        return replace(self, assets=filtered_assets)
