#!/usr/bin/env python3
"""Release processor for GitHub API.

This module handles the processing of GitHub release data into structured formats.
"""

import logging
import re  # Import the 're' module
from typing import Any

from packaging.version import parse as parse_version_string

from src.api.assets import ReleaseInfo  # Corrected import path
from src.utils import arch_utils, version_utils

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
    ) -> tuple[bool, tuple[str, str]]:
        """Compare two version strings to determine if an update is available.

        Args:
            current_version: Current version string
            latest_version: Latest version string from GitHub

        Returns:
            tuple containing update available flag and version information

        """
        # Normalize original versions first (e.g., remove 'v' prefix)
        current_normalized_initial = version_utils.normalize_version_for_comparison(current_version)
        latest_normalized_initial = version_utils.normalize_version_for_comparison(latest_version)

        # For zen-browser, for comparison logic *only*, strip the trailing letter.
        # The actual latest_version (e.g., "1.12.28b") is kept for storage/display.
        current_for_comparison = current_normalized_initial
        latest_for_comparison = latest_normalized_initial

        if self.owner == "zen-browser" and self.repo == "desktop":
            zen_pattern_strip = re.compile(r"^(\d+\.\d+\.\d+)([a-zA-Z])$")  # Matches X.Y.Z[letter]

            current_match_strip = zen_pattern_strip.match(current_for_comparison)
            if current_match_strip:
                base_current = current_match_strip.group(1)
                logger.debug(
                    f"Zen-browser: stripping suffix for comparison. Current '{current_for_comparison}' -> '{base_current}'"
                )
                current_for_comparison = base_current

            latest_match_strip = zen_pattern_strip.match(latest_for_comparison)
            if latest_match_strip:
                base_latest = latest_match_strip.group(1)
                logger.debug(
                    f"Zen-browser: stripping suffix for comparison. Latest '{latest_for_comparison}' -> '{base_latest}'"
                )
                latest_for_comparison = base_latest

        # These strings (potentially with suffixes stripped for zen-browser) are used for base version comparison
        current_parseable_str = current_for_comparison  # Corrected typo
        latest_parseable_str = latest_for_comparison

        # However, for the actual parsing by packaging.version to check prerelease flags etc.,
        # we should use the versions that have NOT been stripped of their suffixes,
        # because "1.12.28b" is a pre-release according to packaging.version.
        # The comparison of base versions (stripped) determines if we *consider* an update.
        # The comparison of full versions (unstripped) by packaging.version then refines this.

        # Let's define what gets parsed for the full comparison (with suffixes if any)
        # These are the original normalized versions, before any zen-browser specific stripping for base comparison.
        current_full_parseable_str = current_normalized_initial
        latest_full_parseable_str = latest_normalized_initial

        logger.debug(
            f"Base versions for comparison: Current base '{current_parseable_str}' vs Latest base '{latest_parseable_str}'"
        )
        logger.debug(
            f"Full versions for parsing: Current full '{current_full_parseable_str}' vs Latest full '{latest_full_parseable_str}'"
        )

        update_available = False

        if not current_parseable_str:  # Use the correct variable name
            # No current version installed, so any latest version is technically not an "update"
            # in the sense of replacing something. However, if latest_parseable_str exists,
            # it implies a version is available for new install.
            # For the purpose of "update_available" flag, if no current version, no update is "pending".
            pass
        elif not latest_parseable_str:  # Use the correct variable name
            # No latest version found online, so no update available.
            pass
        else:
            try:
                # Parse the full versions (e.g., "1.12.28b") to respect their pre-release/etc flags
                parsed_current_full_version = parse_version_string(current_full_parseable_str)
                parsed_latest_full_version = parse_version_string(latest_full_parseable_str)

                # Parse the (potentially stripped for zen-browser) versions for base comparison
                parsed_current_base_for_compare = parse_version_string(
                    current_parseable_str
                )  # current_parseable_str was latest_for_comparison, fixed
                parsed_latest_base_for_compare = parse_version_string(latest_parseable_str)

                # zen-browser uses a custom versioning scheme with letter suffixes (e.g. 1.12.28b)
                # They don't use GitHub's prerelease flag, marking all releases as "latest" with prerelease: false
                # Historical versions: 1.0.1a (alpha) -> 1.12.28b (current pattern for ~2 years)
                # The letter suffix could be any letter (a, b, c, etc.) and may change in the future
                # If they adopt proper semver, they might switch to v1.15.5 format without suffixes
                # NOTE: While packaging.version treats "1.12.28b" as a prerelease, for zen-browser
                # this is their standard release format, NOT a prerelease (no beta: true in zen-browser.json)
                if self.owner == "zen-browser" and self.repo == "desktop":
                    # Allow updates if base version is newer OR if same base but different suffix
                    # Examples: 1.12.28 -> 1.12.28b, 1.12.28a -> 1.12.28b, 1.12.28 -> 1.13.0
                    if parsed_latest_base_for_compare > parsed_current_base_for_compare or (
                        parsed_latest_base_for_compare == parsed_current_base_for_compare
                        and latest_full_parseable_str != current_full_parseable_str
                    ):
                        update_available = True
                # Standard logic for all other repositories: if latest version is newer, allow update
                elif parsed_latest_full_version > parsed_current_full_version:
                    update_available = True
            except Exception as e:
                # Log with the strings that were attempted to be parsed by packaging.version
                logger.error(
                    f"Error parsing versions for comparison (current_full='{current_full_parseable_str}', latest_full='{latest_full_parseable_str}'): {e}"
                )
                # Keep update_available = False on error, or handle as appropriate

        if update_available:  # Log only if an update is actually flagged
            # Log with original latest_version (e.g., 1.12.28b), not the transformed one
            logger.info(f"Update available: {current_version} → {latest_version}")

        return update_available, {
            "current_version": current_version,
            "latest_version": latest_version,  # This is the raw tag like "1.12.28b"
            "current_normalized": current_full_parseable_str,  # What was parsed by packaging.version
            "latest_normalized": latest_full_parseable_str,  # What was parsed by packaging.version
        }

    def filter_compatible_assets(
        self, assets: list[dict[str, Any]], arch_keywords: list[str] | None = None
    ) -> list[dict]:
        """Filter assets based on architecture compatibility.

        Args:
            assets: list of asset dictionaries from GitHub
            arch_keywords: list of architecture keywords to filter by

        Returns:
            list of compatible assets

        """
        if not arch_keywords:
            arch_keywords = arch_utils.get_arch_keywords(self.arch_keyword)

        compatible_assets = []
        for asset in assets:
            asset_name = asset.get("name", "").lower()
            if any(keyword.lower() in asset_name for keyword in arch_keywords):
                compatible_assets.append(asset)

        logger.debug(f"Found {len(compatible_assets)} compatible assets out of {len(assets)}")
        return compatible_assets

    def process_release_data(
        self, release_data: tuple, asset_info: tuple, is_beta: bool = False
    ) -> ReleaseInfo | None:
        """Process raw release data into a structured ReleaseInfo object.

        Args:
            release_data: Raw release data from GitHub API
            asset_info: Processed asset information dictionary
            is_beta: Whether this is a beta release

        Returns:
            ReleaseInfo object or None if processing failed

        """
        try:
            return ReleaseInfo.from_release_data(release_data, asset_info)
        except KeyError as e:
            logger.error(f"Missing required key in release data: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing release data: {e}")
            return None

    def create_update_response(
        self,
        update_available: bool,
        current_version: str,
        release_info: ReleaseInfo,
        compatible_assets: list[dict],
    ) -> dict[str, bool | str | None | list[tuple[Any, Any]] | tuple[Any, Any]]:
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
