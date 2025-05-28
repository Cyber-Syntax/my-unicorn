"""SHA asset selection module.

This module handles finding and selecting the appropriate SHA checksum file
for an AppImage from GitHub release assets.
"""

import logging
import re
from typing import Dict, List, Optional

from src.app_catalog import AppInfo

logger = logging.getLogger(__name__)


class SHAAssetFinder:
    """Finds and selects SHA checksum files from release assets."""

    def find_best_match(
        self,
        selected_appimage_name: str,
        definitive_app_info: AppInfo,
        assets: List[Dict],
    ) -> Optional[Dict]:
        """Find the best matching SHA asset for an AppImage.

        Args:
            selected_appimage_name: Name of the AppImage file to find SHA for
            definitive_app_info: Base app metadata from repository JSON
            assets: List of release assets from GitHub API

        Returns:
            dict: Selected SHA asset if found, None otherwise
        """
        logger.info(f"Looking for SHA file matching: {selected_appimage_name}")
        logger.info(f"Using SHA name from definitive info: {definitive_app_info.sha_name}")

        # 1. Try exact match from definitive app info
        if definitive_app_info.sha_name != "no_sha_file":
            for asset in assets:
                if asset["name"].lower() == definitive_app_info.sha_name.lower():
                    logger.info(f"Found exact SHA name match: {asset['name']}")
                    return asset

        # 2. Look for SHA files that might contain our AppImage's hash
        sha_assets = self._filter_sha_assets(assets)
        if not sha_assets:
            logger.warning("No SHA files found in release assets")
            return None

        # Sort by length to prefer more specific matches
        sha_assets.sort(key=lambda x: len(x["name"]))

        # Try to find a SHA file specifically for our AppImage
        appimage_base = selected_appimage_name.replace(".AppImage", "").lower()
        for asset in sha_assets:
            asset_name = asset["name"].lower()
            if appimage_base in asset_name:
                logger.info(f"Found SHA file specific to AppImage: {asset['name']}")
                return asset

        # Fallback to a generic SHA file if available
        logger.info("Using first available SHA file as fallback")
        return sha_assets[0]

    def _filter_sha_assets(self, assets: List[Dict]) -> List[Dict]:
        """Filter release assets to only SHA/checksum files."""
        sha_patterns = [
            r"\.sha\d+$",
            r"\.sha\d+sum$",
            r"sha\d+sums?\.txt$",
            r"checksums?\.txt$",
            r"\.sum$"
        ]

        sha_assets = []
        for asset in assets:
            name = asset["name"].lower()
            if any(re.search(pattern, name) for pattern in sha_patterns):
                sha_assets.append(asset)

        return sha_assets
