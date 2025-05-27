#!/usr/bin/env python3
"""SHA asset selection logic module.

This module provides functionality for selecting appropriate SHA files
from GitHub releases for AppImage verification.
"""

import logging
import os
from typing import Dict, List, Optional, Callable, Any # Added Callable, Any

from src.utils import arch_utils, sha_utils, ui_utils

logger = logging.getLogger(__name__)

# import constants
from .constants import ( # Changed from src.api.github_api.constants
    APPIMAGE_EXTENSION,
    NO_SHA_FILE_CONFIG,
    PYTEST_ENV_VAR,
)


class SHAAssetFinder:
    """Handles finding appropriate SHA files for AppImage verification."""

    def __init__(self, assets: List[Dict], appimage_name: str, sha_name: str):
        """Initialize SHA asset finder.

        Args:
            assets: List of release assets from GitHub API
            appimage_name: Name of the selected AppImage
            sha_name: Expected SHA file name or type

        """
        self.assets = assets
        self.appimage_name = appimage_name
        self.sha_name = sha_name
        self.appimage_base_name = os.path.basename(appimage_name) if appimage_name else ""

    def _get_matching_strategies(self, appimage_arch: Optional[str]) -> List[Callable[[], Optional[Dict]]]:
        """Get list of matching strategies in order of preference."""
        # Type hint assumes strategies take no args and return Optional[Dict]
        return [
            self._try_exact_sha_name_match,
            self._try_direct_appimage_sha_match,
            lambda: self._try_arch_specific_match(appimage_arch),
            self._try_common_sha_files,
            self._try_generic_sha_files,
            self._handle_fallback,
        ]

    def find_best_match(self) -> Optional[Dict]:
        """Find the best matching SHA file using multiple strategies.

        Returns:
            Best matching SHA asset or None if not found

        """
        if not self._should_find_sha_file():
            return None

        if not self._validate_appimage_name():
            return None

        appimage_arch = self._extract_appimage_architecture()
        strategies = self._get_matching_strategies(appimage_arch)

        return self._execute_strategies(strategies)

    def _should_find_sha_file(self) -> bool:
        """Check if SHA file finding should be performed."""
        if self.sha_name == NO_SHA_FILE_CONFIG:
            logger.info("Skipping SHA verification per configuration")
            return False
        return True

    def _validate_appimage_name(self) -> bool:
        """Validate that AppImage name is provided."""
        if not self.appimage_name:
            logger.warning("No AppImage name provided for SHA matching")
            return False
        return True

    def _extract_appimage_architecture(self) -> Optional[str]:
        """Extract and log architecture from AppImage name."""
        appimage_arch = arch_utils.extract_arch_from_filename(self.appimage_name)
        logger.info(f"Extracted architecture from AppImage: {appimage_arch}")
        logger.info(f"AppImage base name: {self.appimage_base_name}")
        return appimage_arch

    def _execute_strategies(self, strategies: List[Callable[[], Optional[Dict]]]) -> Optional[Dict]:
        """Execute matching strategies until one succeeds."""
        # Type hint assumes strategies take no args and return Optional[Dict]
        for strategy in strategies:
            result = strategy()
            if result:
                return result
        return None

    def _try_exact_sha_name_match(self) -> Optional[Dict]:
        """Try exact match if SHA name is provided."""
        if self.sha_name and self.sha_name not in {"sha256", "sha512"}:
            for asset in self.assets:
                if asset["name"] == self.sha_name:
                    logger.info(f"Found exact SHA name match: {asset['name']}")
                    return asset
        return None

    def _try_direct_appimage_sha_match(self) -> Optional[Dict]:
        """Try to find direct AppImage SHA file (e.g., AppImage.sha512)."""
        for asset in self.assets:
            if self._is_direct_appimage_sha_match(asset):
                logger.info(f"Found direct AppImage SHA file: {asset['name']}")
                return asset
        return None

    def _is_direct_appimage_sha_match(self, asset: Dict) -> bool:
        """Check if asset is a direct AppImage SHA file match."""
        name = asset["name"].lower()
        base_name_lower = self.appimage_base_name.lower()

        # Skip the AppImage itself
        if name == base_name_lower or name.endswith(".appimage"):
            return False

        # Check for direct AppImage SHA file
        return name.startswith(base_name_lower) and name.endswith((".sha256", ".sha512"))

    def _try_arch_specific_match(self, appimage_arch: Optional[str]) -> Optional[Dict]:
        """Try to find architecture-specific SHA files."""
        if not appimage_arch:
            return None

        arch_specific_candidates = self._collect_arch_specific_candidates(appimage_arch)
        return self._handle_arch_specific_results(arch_specific_candidates)

    def _collect_arch_specific_candidates(self, appimage_arch: str) -> List[Dict]:
        """Collect SHA files that match the given architecture."""
        candidates = []

        for asset in self.assets:
            if not self._is_valid_sha_candidate(asset):
                continue

            asset_arch = arch_utils.extract_arch_from_filename(asset["name"])
            if asset_arch == appimage_arch:
                candidates.append(asset)

        return candidates

    def _is_valid_sha_candidate(self, asset: Dict) -> bool:
        """Check if asset is a valid SHA file candidate."""
        name = asset["name"].lower()
        return not name.endswith(APPIMAGE_EXTENSION) and self._is_sha_file(name)

    def _handle_arch_specific_results(self, candidates: List[Dict]) -> Optional[Dict]:
        """Handle the results of architecture-specific matching."""
        if len(candidates) == 1:
            candidate_name = candidates[0]["name"]
            logger.info(f"Found architecture-specific SHA file: {candidate_name}")
            return candidates[0]
        elif len(candidates) > 1:
            logger.info("Multiple architecture-specific SHA files found")
            return self._prompt_user_selection(candidates, "architecture-specific SHA files")

        return None

    def _try_common_sha_files(self) -> Optional[Dict]:
        """Try common SHA file patterns."""
        common_files = [
            ("sha256sums", "sha256sums.txt"),
            ("latest-linux.yml",),
            ("latest.yml",),
        ]

        for file_names in common_files:
            for asset in self.assets:
                name = asset["name"].lower()
                if name in file_names:
                    logger.info(f"Found common SHA file: {asset['name']}")
                    return asset

        return None

    def _try_generic_sha_files(self) -> Optional[Dict]:
        """Try generic SHA files (excluding platform-specific ones)."""
        generic_candidates = self._collect_generic_sha_candidates()
        return self._handle_generic_results(generic_candidates)

    def _collect_generic_sha_candidates(self) -> List[Dict]:
        """Collect generic SHA file candidates."""
        candidates = []

        for asset in self.assets:
            if not self._is_generic_sha_candidate(asset):
                continue
            candidates.append(asset)

        return candidates

    def _is_generic_sha_candidate(self, asset: Dict) -> bool:
        """Check if asset is a valid generic SHA candidate."""
        name = asset["name"].lower()

        # Skip AppImages and non-SHA files
        if name.endswith(".appimage") or not self._is_sha_file(name):
            return False

        # Skip platform-specific files
        if self._is_platform_specific(name):
            return False

        # Skip architecture-specific files for other architectures
        return not arch_utils.extract_arch_from_filename(name)

    def _is_platform_specific(self, name: str) -> bool:
        """Check if filename indicates platform-specific content."""
        platform_indicators = ["mac", "windows", "win"]
        return any(platform in name for platform in platform_indicators)

    def _handle_generic_results(self, candidates: List[Dict]) -> Optional[Dict]:
        """Handle the results of generic SHA file matching."""
        if len(candidates) == 1:
            logger.info(f"Using generic SHA file: {candidates[0]['name']}")
            return candidates[0]
        elif len(candidates) > 1:
            logger.info("Multiple generic SHA files found")
            return self._prompt_user_selection(candidates, "generic SHA files")

        return None

    def _handle_fallback(self) -> Optional[Dict]:
        """Handle fallback when no automatic match is found."""
        all_sha_files = self._collect_all_sha_files()
        return self._handle_fallback_results(all_sha_files)

    def _collect_all_sha_files(self) -> List[Dict]:
        """Collect all available SHA files."""
        return [
            asset
            for asset in self.assets
            if (
                self._is_sha_file(asset["name"].lower())
                and not asset["name"].lower().endswith(".appimage")
            )
        ]

    def _handle_fallback_results(self, all_sha_files: List[Dict]) -> Optional[Dict]:
        """Handle results when using fallback strategy."""
        if len(all_sha_files) == 1:
            logger.info(f"Using only available SHA file: {all_sha_files[0]['name']}")
            return all_sha_files[0]
        elif len(all_sha_files) > 1:
            logger.info("Found multiple SHA files")
            return self._prompt_user_selection(all_sha_files, "SHA files")

        # No SHA files found
        logger.warning("No SHA files found for verification")
        return None

    def _is_sha_file(self, name: str) -> bool:
        """Check if a file appears to be a SHA file."""
        return (
            sha_utils.is_sha_file(name) or name.endswith(".yml") or "sha" in name or "sum" in name
        )

    def _is_test_environment(self) -> bool:
        """Check if running in test environment."""
        return bool(os.environ.get(PYTEST_ENV_VAR))

    def _select_first_asset_for_test(self, assets: List[Dict]) -> Optional[Dict]:
        """Auto-select first asset during test runs."""
        return assets[0] if assets else None

    def _prompt_user_for_asset_selection(
        self, assets: List[Dict], description: str
    ) -> Optional[Dict]:
        """Display available assets and prompt user selection."""
        print(f"Multiple {description} found:")
        selected_asset = None

        def select_callback(asset):
            nonlocal selected_asset
            selected_asset = asset

        ui_utils.select_from_list(assets, "Select SHA file", callback=select_callback)
        return selected_asset

    def _prompt_user_selection(self, assets: List[Dict], description: str) -> Optional[Dict]:
        """Handle asset selection based on environment and user input."""
        if not assets:
            return None

        if self._is_test_environment():
            return self._select_first_asset_for_test(assets)

        return self._prompt_user_for_asset_selection(assets, description)
