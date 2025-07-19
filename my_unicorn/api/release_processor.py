#!/usr/bin/env python3
"""Release processor for GitHub API.

This module handles the processing of GitHub release data into structured formats.
"""

import logging
import re
from typing import Any

from packaging.version import parse as parse_version_string

from my_unicorn.api.assets import ReleaseInfo
from my_unicorn.utils import version_utils

logger = logging.getLogger(__name__)


class ReleaseProcessor:
    """Processes GitHub release data into structured formats.

    This class is responsible for extracting and structuring information from
    GitHub release data, including version information, asset selection, and
    architecture compatibility.
    """

    def __init__(self, owner: str, repo: str, arch_keyword: str | None = None):
        """Initialize the ReleaseProcessor.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            arch_keyword: Architecture keyword for filtering assets

        """
        self.owner = owner
        self.repo = repo
        self.arch_keyword = arch_keyword

    def compare_versions(
        self, current_version: str, latest_version: str
    ) -> tuple[bool, dict[str, str]]:
        """Compare two version strings to determine if an update is available."""
        # Normalize versions
        current_normalized = version_utils.normalize_version_for_comparison(current_version)
        latest_normalized = version_utils.normalize_version_for_comparison(latest_version)
        
        # Handle zen-browser special formatting
        current_normalized = version_utils.handle_zen_browser_version(
            current_version, current_normalized, self.owner, self.repo
        )
        latest_normalized = version_utils.handle_zen_browser_version(
            latest_version, latest_normalized, self.owner, self.repo
        )
    
        # For comparison, use base versions without letter suffixes
        current_base = self._get_zen_base_version(current_normalized) if self._is_zen_browser else current_normalized
        latest_base = self._get_zen_base_version(latest_normalized) if self._is_zen_browser else latest_normalized
    
        update_available = False
        is_zen = self._is_zen_browser
    
        try:
            parsed_current = parse_version_string(current_normalized)
            parsed_latest = parse_version_string(latest_normalized)
            parsed_current_base = parse_version_string(current_base)
            parsed_latest_base = parse_version_string(latest_base)
    
            if is_zen:
                # Zen-browser logic: update if base is newer or same base with different suffix
                update_available = (
                    parsed_latest_base > parsed_current_base or 
                    (parsed_latest_base == parsed_current_base and latest_normalized != current_normalized)
                )
            else:
                # Standard logic: update if newer version
                update_available = parsed_latest > parsed_current
    
        except (ValueError, TypeError) as e:
            logger.error("Version parsing error: %s", e)
            # Fallback to string comparison if parsing fails
            update_available = latest_normalized > current_normalized
    
        return update_available, {
            "current_version": current_version,
            "latest_version": latest_version,
            "current_normalized": current_normalized,
            "latest_normalized": latest_normalized,
        }
    
    @property
    def _is_zen_browser(self) -> bool:
        """Check if this is zen-browser repo."""
        return self.owner == "zen-browser" and self.repo == "desktop"
    
    def _get_zen_base_version(self, version: str) -> str:
        """Extract base version number for zen-browser (without letter suffix)."""
        if not self._is_zen_browser:
            return version
        
        # Match patterns like 1.12.28b or 1.12.28
        match = re.match(r"^(\d+\.\d+\.\d+)[a-zA-Z]?$", version)
        return match.group(1) if match else version

    def filter_compatible_assets(
        self, assets: list[dict[str, str]], arch_keywords: list[str] | None = None
    ) -> list[dict[str, str]]:
        """Filter assets based on architecture compatibility.

        Args:
            assets: list of asset dictionaries from GitHub
            arch_keywords: list of architecture keywords to filter by

        Returns:
            list of compatible assets

        """
        if not arch_keywords:
            # Use a default list instead of calling non-existent method
            arch_keywords = [self.arch_keyword] if self.arch_keyword else []

        compatible_assets = []
        for asset in assets:
            asset_name = asset.get("name", "").lower()
            if any(keyword.lower() in asset_name for keyword in arch_keywords):
                compatible_assets.append(asset)

        logger.debug("Found %d compatible assets out of %d", len(compatible_assets), len(assets))
        return compatible_assets

    def process_release_data(
        self, release_data: dict[str, Any], asset_info: dict[str, Any], _is_beta: bool = False
    ) -> ReleaseInfo | None:
        """Process raw release data into a structured ReleaseInfo object.

        Args:
            release_data: Raw release data from GitHub API
            asset_info: Processed asset information dictionary
            _is_beta: Whether this is a beta release (unused but kept for interface compatibility)

        Returns:
            ReleaseInfo object or None if processing failed

        """
        try:
            return ReleaseInfo.from_release_data(release_data, asset_info)
        except KeyError as e:
            logger.error("Missing required key in release data: %s", e)
            return None
        except (ValueError, TypeError) as e:
            logger.error("Error processing release data: %s", e)
            return None

    def create_update_response(
        self,
        update_available: bool,
        current_version: str,
        release_info: ReleaseInfo,
        compatible_assets: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Create a standardized response for update checks.

        Args:
            update_available: Whether an update is available
            current_version: Current version string
            release_info: Processed ReleaseInfo object
            compatible_assets: list of compatible assets

        Returns:
            Dictionary with update information

        """
        return {
            "update_available": update_available,
            "current_version": current_version,
            "latest_version": release_info.version,
            "release_notes": release_info.release_notes,
            "release_url": release_info.release_url,
            "compatible_assets": compatible_assets,
            "prerelease": release_info.prerelease,
            "published_at": release_info.published_at,
            "app_download_url": release_info.app_download_url,
            "appimage_name": release_info.appimage_name,
            "checksum_file_download_url": release_info.checksum_file_download_url,
            "checksum_file_name": release_info.checksum_file_name,
            "checksum_hash_type": release_info.checksum_hash_type,
        }
