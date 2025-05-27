#!/usr/bin/env python3
"""AppImage selection logic module.

This module provides functionality for selecting appropriate AppImage assets
from GitHub releases based on system architecture.
"""

import logging
import re
from typing import Dict, List, Optional

from src.utils import arch_utils, ui_utils

logger = logging.getLogger(__name__)


class AppImageSelector:
    """Handles selection of appropriate AppImage assets."""

    def __init__(self, arch_keyword: Optional[str] = None):
        """Initialize AppImage selector.

        Args:
            arch_keyword: Previously saved architecture keyword for matching

        """
        self.arch_keyword = arch_keyword
        self.arch_keywords = arch_utils.get_arch_keywords(arch_keyword)

    def find_appimage_asset(self, assets: List[Dict]) -> Optional[Dict]:
        """Find and select appropriate AppImage asset based on system architecture.

        Args:
            assets: List of release assets from GitHub API

        Returns:
            dict: Selected AppImage asset or None if not found

        """
        current_arch = arch_utils.get_current_arch()
        logger.info(f"Current arch_keyword: {self.arch_keyword}")
        logger.info(f"Current system architecture: {current_arch}")

        filtered_appimages = self._filter_compatible_appimages(assets, current_arch)
        if not filtered_appimages:
            raise ValueError("No AppImage files found in release")

        logger.info(f"Found {len(filtered_appimages)} potentially compatible AppImages")

        # Try different selection strategies in order of preference
        selected_asset = (
            self._try_exact_arch_keyword_match(filtered_appimages)
            or self._try_arch_specific_match(filtered_appimages, current_arch)
            or self._try_generic_linux_match(filtered_appimages)
            or self._handle_single_appimage(filtered_appimages)
        )

        if selected_asset:
            return selected_asset

        # Fallback to user selection
        logger.info("No automatic match found, requesting user selection")
        return self._prompt_user_selection(filtered_appimages)

    def _filter_compatible_appimages(self, assets: List[Dict], current_arch: str) -> List[Dict]:
        """Filter AppImages by removing incompatible architectures."""
        appimages = [a for a in assets if a["name"].lower().endswith(".appimage")]
        incompatible_archs = arch_utils.get_incompatible_archs(current_arch)
        logger.info(f"Filtering out incompatible architectures: {incompatible_archs}")

        compatible_appimages = [
            appimage
            for appimage in appimages
            if not any(arch in appimage["name"].lower() for arch in incompatible_archs)
        ]

        return compatible_appimages if compatible_appimages else appimages

    def _try_exact_arch_keyword_match(self, appimages: List[Dict]) -> Optional[Dict]:
        """Try to match based on previously saved arch_keyword."""
        if not self.arch_keyword:
            return None

        pattern = re.compile(re.escape(self.arch_keyword.strip().lower()) + r"\Z")
        logger.info(f"Trying to find match with arch keyword: {self.arch_keyword}")

        for asset in appimages:
            asset_name = asset["name"].strip().lower()
            logger.info(f"Checking asset: {asset_name}")
            if pattern.search(asset_name):
                logger.info(f"Found exact arch keyword match: {asset['name']}")
                return asset
        return None

    def _try_arch_specific_match(self, appimages: List[Dict], current_arch: str) -> Optional[Dict]:
        """Try to match based on current system architecture."""
        # Look for exact architecture match first
        for asset in appimages:
            if current_arch in asset["name"].lower():
                logger.info(f"Found exact architecture match: {asset['name']}")
                return asset

        # Then try architecture keywords
        candidates = [
            asset
            for asset in appimages
            if any(kw in asset["name"].lower() for kw in self.arch_keywords)
        ]

        if len(candidates) == 1:
            return candidates[0]
        elif candidates:
            logger.info(f"Found {len(candidates)} architecture-matched AppImages")
            return self._prompt_user_selection(candidates, "architecture-matched AppImages")

        return None

    def _try_generic_linux_match(self, appimages: List[Dict]) -> Optional[Dict]:
        """Try to find generic Linux builds without specific architecture."""
        generic_linux_builds = [
            asset
            for asset in appimages
            if "linux" in asset["name"].lower()
            and not any(
                arch in asset["name"].lower()
                for arch in [
                    "arm",
                    "arm64",
                    "aarch64",
                    "armhf",
                    "arm32",
                    "x86_64",
                    "amd64",
                    "i686",
                    "i386",
                ]
            )
        ]

        if len(generic_linux_builds) == 1:
            logger.info(f"Found generic Linux build: {generic_linux_builds[0]['name']}")
            return generic_linux_builds[0]
        elif generic_linux_builds:
            logger.info(f"Found {len(generic_linux_builds)} generic Linux builds")
            return self._prompt_user_selection(generic_linux_builds, "generic Linux builds")

        return None

    def _handle_single_appimage(self, appimages: List[Dict]) -> Optional[Dict]:
        """Handle case where only one AppImage is available."""
        if len(appimages) == 1:
            return appimages[0]
        return None

    def _prompt_user_selection(
        self, appimages: List[Dict], description: str = "AppImages"
    ) -> Optional[Dict]:
        """Prompt user to select from available AppImages."""
        print(f"Please select from available {description}:")
        selected_asset = None

        def select_callback(asset):
            nonlocal selected_asset
            selected_asset = asset

        ui_utils.select_from_list(appimages, "Select AppImage", callback=select_callback)
        return selected_asset

    def extract_arch_keyword_from_name(self, filename: str) -> str:
        """Extract architecture keyword from filename.

        Args:
            filename: AppImage filename

        Returns:
            str: Extracted architecture keyword

        """
        lower_name = filename.lower()

        # Define architecture patterns in order of preference
        arch_patterns = [
            (r"(-arm64[^.]*\.appimage)$", "arm64"),
            (r"(-aarch64[^.]*\.appimage)$", "aarch64"),
            (r"(-amd64[^.]*\.appimage)$", "amd64"),
            (r"(-x86_64[^.]*\.appimage)$", "x86_64"),
            (r"(-x86[^.]*\.appimage)$", "x86"),
            (r"(-i686[^.]*\.appimage)$", "i686"),
            (r"(-i386[^.]*\.appimage)$", "i386"),
            (r"(-linux(?:64)?\.appimage)$", "linux"),
        ]

        for pattern, _ in arch_patterns:
            match = re.search(pattern, lower_name)
            if match:
                return match.group(1)

        # Fallback to generic AppImage extension
        return ".appimage"
