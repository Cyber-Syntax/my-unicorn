#!/usr/bin/env python3
"""AppImage selection logic module.

This module provides functionality for selecting appropriate AppImage assets
from GitHub releases based on system architecture and app characteristics.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from my_unicorn.catalog import AppInfo
from my_unicorn.utils import arch_utils

logger = logging.getLogger(__name__)


@dataclass
class AssetSelectionResult:
    """Result of AppImage asset selection.

    Attributes:
        asset: Selected GitHub release asset
        characteristic_suffix: The suffix that matched this asset

    """

    asset: dict[str, Any]
    characteristic_suffix: str


class AppImageSelector:
    """Handles selection of appropriate AppImage assets."""

    def __init__(self) -> None:
        """Initialize the selector."""
        self._logger = logging.getLogger(__name__)

    def find_appimage_asset(
        self,
        assets: list[dict],
        definitive_app_info: AppInfo | None = None,
        user_local_config_data: dict | None = None,
        release_prerelease: bool = False,
    ) -> AssetSelectionResult | None:
        """Find and select appropriate AppImage asset based on app metadata and system architecture.

        Args:
            assets: list of release assets from GitHub API
            definitive_app_info: Base app metadata from repository JSON (optional)
            user_local_config_data: User's local config data (optional)
            release_prerelease: Whether this is a pre-release

        Returns:
            AssetSelectionResult if an appropriate asset is found, None otherwise

        """
        self._logger.info("Starting AppImage selection process")

        # 1. Determine system architecture
        system_cpu_arch = arch_utils.get_current_arch()
        self._logger.info("System CPU architecture: %s", system_cpu_arch)

        # 2. Determine target characteristic suffix list with priority
        target_suffixes = self._determine_target_suffixes(
            definitive_app_info, user_local_config_data
        )
        self._logger.info("Target characteristic suffixes: %s", target_suffixes)

        # Filter AppImage assets
        appimage_assets = [
            asset for asset in assets if asset.get("content_type") == "application/vnd.appimage"
        ]

        # Fallback to filename extension if no assets found by content_type
        if not appimage_assets:
            self._logger.info("No assets found by content_type, falling back to filename extension")
            appimage_assets = [
                asset for asset in assets if asset["name"].lower().endswith(".appimage")
            ]

        if not appimage_assets:
            self._logger.warning("No AppImage assets found in release")
            return None

        self._logger.info(
            "Available AppImage assets: %s", [asset["name"] for asset in appimage_assets]
        )

        # 3. Try each suffix in priority order
        selected = self._try_suffix_based_selection(
            appimage_assets, target_suffixes, system_cpu_arch, release_prerelease
        )
        if selected:
            return selected

        # 4. Fallback to generic matching if no suffix match
        self._logger.info("No suffix match found, trying generic selection")
        generic_asset = self._try_generic_selection(
            appimage_assets, system_cpu_arch, release_prerelease
        )
        if generic_asset:
            return AssetSelectionResult(asset=generic_asset, characteristic_suffix="")

        self._logger.warning("No suitable AppImage asset found")
        return None

    def _determine_target_suffixes(
        self, definitive_app_info: AppInfo | None, user_local_config_data: dict | None
    ) -> list[str]:
        """Determine the prioritized list of characteristic suffixes to try.

        Priority order:
        1. User's explicit override from local config
        2. Currently installed suffix from local config
        3. Preferred suffixes from definitive app info
        """
        suffixes = []

        if user_local_config_data:
            # Check for user override
            if override := user_local_config_data.get(
                "user_preferred_characteristic_suffix_override"
            ):
                suffixes.append(override)

            # Check currently installed suffix
            if installed := user_local_config_data.get("installed_characteristic_suffix"):
                if installed not in suffixes:
                    suffixes.append(installed)

        # Add preferred suffixes from definitive info if available
        if definitive_app_info and definitive_app_info.preferred_characteristic_suffixes:
            for suffix in definitive_app_info.preferred_characteristic_suffixes:
                if suffix not in suffixes:
                    suffixes.append(suffix)

        return suffixes

    def _try_suffix_based_selection(
        self,
        assets: list[dict],
        target_suffixes: list[str],
        system_cpu_arch: str,
        prerelease: bool,
    ) -> AssetSelectionResult | None:
        """Try to select an asset based on characteristic suffixes."""
        for suffix in target_suffixes:
            self._logger.info("Trying suffix: '%s'", suffix)

            # Skip suffix if not compatible with system architecture
            if not arch_utils.is_keyword_compatible_with_arch(suffix, system_cpu_arch):
                self._logger.debug("Suffix '%s' not compatible with %s", suffix, system_cpu_arch)
                continue

            # Find assets matching this suffix
            matching_assets = []
            for asset in assets:
                asset_name = asset["name"].lower()
                suffix_lower = suffix.lower()

                # Check if this asset matches the suffix
                if self._asset_matches_suffix(asset_name, suffix_lower):
                    self._logger.info("Asset '%s' matched suffix '%s'", asset["name"], suffix)
                    matching_assets.append(asset)

            if matching_assets:
                # Filter by architecture compatibility first
                compatible_assets = []
                for asset in matching_assets:
                    asset_name = asset["name"].lower()
                    if arch_utils.is_keyword_compatible_with_arch(asset_name, system_cpu_arch):
                        compatible_assets.append(asset)
                    else:
                        self._logger.debug(
                            "Asset '%s' filtered out due to architecture incompatibility",
                            asset["name"],
                        )

                if compatible_assets:
                    # Sort by name to ensure consistent selection
                    compatible_assets.sort(key=lambda x: x["name"])
                    self._logger.info(
                        "Found %d architecture-compatible assets matching suffix '%s': %s",
                        len(compatible_assets),
                        suffix,
                        [a["name"] for a in compatible_assets],
                    )

                    # Return first compatible asset
                    selected_asset = compatible_assets[0]
                    self._logger.info("Selected asset: %s", selected_asset["name"])
                    return AssetSelectionResult(asset=selected_asset, characteristic_suffix=suffix)
                else:
                    self._logger.debug(
                        "No architecture-compatible assets found for suffix '%s'", suffix
                    )
            else:
                self._logger.debug("No assets found matching suffix '%s'", suffix)

        return None

    def _asset_matches_suffix(self, asset_name: str, suffix: str) -> bool:
        """Check if an asset name matches a characteristic suffix.

        Args:
            asset_name: Lowercase asset name
            suffix: Lowercase suffix to match

        Returns:
            True if the asset matches the suffix

        """
        # Try exact pattern matching first - suffix should appear before .appimage
        # Pattern: anything-{suffix}.appimage
        pattern = rf"-{re.escape(suffix)}\.appimage$"
        if re.search(pattern, asset_name):
            return True

        # For simple suffixes like "linux", also try without dash
        # Pattern: anything{suffix}.appimage
        if not suffix.startswith("-"):
            pattern_no_dash = rf"{re.escape(suffix)}\.appimage$"
            if re.search(pattern_no_dash, asset_name):
                return True

        # Fallback to simple substring matching
        if suffix in asset_name:
            return True

        return False

    def _try_generic_selection(
        self, assets: list[dict], system_cpu_arch: str, prerelease: bool
    ) -> dict | None:
        """Try to select an asset without specific characteristic suffix."""
        # Filter to only architecture-compatible assets
        compatible_assets = []

        for asset in assets:
            name = asset["name"].lower()
            is_compatible = arch_utils.is_keyword_compatible_with_arch(name, system_cpu_arch)
            if is_compatible:
                compatible_assets.append(asset)

        if not compatible_assets:
            return None

        # Sort by name for consistent selection
        compatible_assets.sort(key=lambda x: x["name"])
        return compatible_assets[0]
