"""SHA asset selection module.

This module handles finding and selecting the appropriate SHA checksum file
for an AppImage from GitHub release assets.
"""

import logging
import re

from src.app_catalog import AppInfo

logger = logging.getLogger(__name__)


class SHAAssetFinder:
    """Finds and selects SHA checksum files from release assets."""

    def find_best_match(
        self,
        selected_appimage_name: str,
        definitive_app_info: AppInfo,
        assets: list[dict],
    ) -> dict | None:
        """Find the best SHA asset match for the selected AppImage.

        Args:
            selected_appimage_name: Name of the selected AppImage file
            definitive_app_info: App information from catalog (can be None for URL-based installs)
            assets: List of release assets from GitHub API

        Returns:
            dict: Selected SHA asset if found, None otherwise. For asset digest,
            returns a special dict with asset digest information.

        """
        logger.info(f"Looking for SHA file matching: {selected_appimage_name}")
        
        # Handle case where definitive_app_info is None (URL-based installs)
        if definitive_app_info is None:
            logger.info("No app definition found - using automatic SHA detection")
        else:
            logger.info(f"Using SHA name from definitive info: {definitive_app_info.sha_name}")

            # Skip SHA search if verification is disabled
            if definitive_app_info.skip_verification:
                logger.info("Skipping SHA file search as verification is disabled")
                return None

            # Priority 1: Check if app uses asset digest verification
            if definitive_app_info.use_asset_digest:
                logger.info(f"App {selected_appimage_name} prefers asset digest verification")
                asset_digest_info = self._try_extract_asset_digest(selected_appimage_name, assets)
                if asset_digest_info:
                    logger.info(f"Successfully found asset digest for {selected_appimage_name}")
                    return asset_digest_info
                else:
                    logger.warning(
                        f"Asset digest not available for {selected_appimage_name}, falling back to SHA files"
                    )

            # Priority 2: Try exact match from definitive app info
            if definitive_app_info.sha_name:
                for asset in assets:
                    if asset["name"].lower() == definitive_app_info.sha_name.lower():
                        logger.info(f"Found exact SHA name match: {asset['name']}")
                        return asset

        # Priority 3: Try pattern matching (for both catalog and URL-based installs)

        # Priority 3: Look for SHA files that might contain our AppImage's hash
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

    def _try_extract_asset_digest(self, appimage_name: str, assets: list[dict]) -> dict | None:
        """Try to extract asset digest information from GitHub API asset metadata.

        Args:
            appimage_name: Name of the AppImage file
            assets: list of release assets from GitHub API

        Returns:
            dict: Special asset info with digest data if found, None otherwise
        """
        # Look for the AppImage asset that matches our selected file
        for asset in assets:
            if asset.get("name") == appimage_name and asset.get("digest"):
                digest = asset["digest"]
                logger.info(f"Found asset digest for {appimage_name}: {digest}")

                # Validate digest format (should be like "sha256:hash_value")
                if ":" in digest:
                    digest_type, digest_hash = digest.split(":", 1)
                    if digest_type in ["sha256", "sha512"] and len(digest_hash) > 0:
                        # Return a special asset dict that indicates asset digest usage
                        return {
                            "name": "asset_digest",
                            "browser_download_url": None,
                            "digest": digest,
                            "hash_type": "asset_digest",
                            "asset_digest_hash": digest_hash,
                            "asset_digest_type": digest_type,
                        }
                    else:
                        logger.warning(f"Invalid digest format or unsupported type: {digest}")
                else:
                    logger.warning(f"Invalid digest format (missing colon): {digest}")

        logger.debug(f"No asset digest found for {appimage_name} in assets")
        return None

    def _filter_sha_assets(self, assets: list[dict]) -> list[dict]:
        """Filter release assets to only SHA/checksum files."""
        sha_patterns = [
            r"\.sha\d+$",
            r"\.sha\d+sum$",
            r"sha\d+sums?\.txt$",
            r"checksums?\.txt$",
            r"\.sum$",
        ]

        sha_assets = []
        for asset in assets:
            name = asset["name"].lower()
            if any(re.search(pattern, name) for pattern in sha_patterns):
                sha_assets.append(asset)

        return sha_assets
