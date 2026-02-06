"""GitHub asset model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from my_unicorn.utils.asset_validation import is_appimage_file


@dataclass(slots=True, frozen=True)
class Asset:
    """Represents a GitHub release asset.

    Attributes:
        name: Asset filename
        size: Asset size in bytes
        digest: Asset digest/hash (may be empty)
        browser_download_url: Direct download URL for the asset

    """

    name: str
    size: int
    digest: str
    browser_download_url: str

    @classmethod
    def from_api_response(cls, asset_data: dict[str, Any]) -> Asset | None:
        """Create Asset from GitHub API response data.

        Args:
            asset_data: Raw asset data from GitHub API

        Returns:
            Asset instance or None if required fields are missing

        """
        try:
            name = asset_data.get("name", "")
            size = asset_data.get("size", 0)
            download_url = asset_data.get("browser_download_url", "")
            digest = asset_data.get("digest", "")

            if not name or not download_url:
                return None

            return cls(
                name=name,
                size=int(size),
                digest=digest,
                browser_download_url=download_url,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def is_appimage(self) -> bool:
        """Check if this asset is an AppImage file.

        Returns:
            True if asset is an AppImage, False otherwise

        """
        return is_appimage_file(self.name)
