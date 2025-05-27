#!/usr/bin/env python3
"""Release processor for GitHub API.

This module handles the processing of GitHub release data into structured formats.
"""

import logging
import re # Import the 're' module
from typing import Any, Dict, List, Optional, Tuple, Union
from packaging.version import parse as parse_version_string # Added import

from src.api.assets import ReleaseInfo # Corrected import path
from src.utils import arch_utils, version_utils

logger = logging.getLogger(__name__)


class ReleaseProcessor:
    """Processes GitHub release data into structured formats.

    This class is responsible for extracting and structuring information from
    GitHub release data, including version information, asset selection, and
    architecture compatibility.
    """

    def __init__(self, owner: str, repo: str, arch_keyword: Optional[str] = None):
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
    ) -> Tuple[bool, Dict[str, str]]:
        """Compare two version strings to determine if an update is available.

        Args:
            current_version: Current version string
            latest_version: Latest version string from GitHub

        Returns:
            Tuple containing update available flag and version information

        """
        # Normalize original versions first (e.g., remove 'v' prefix)
        current_normalized_initial = version_utils.normalize_version_for_comparison(current_version)
        latest_normalized_initial = version_utils.normalize_version_for_comparison(latest_version)

        # For zen-browser, for comparison logic *only*, strip the trailing letter.
        # The actual latest_version (e.g., "1.12.28b") is kept for storage/display.
        current_for_comparison = current_normalized_initial
        latest_for_comparison = latest_normalized_initial

        if self.owner == "zen-browser" and self.repo == "desktop":
            zen_pattern_strip = re.compile(r"^(\d+\.\d+\.\d+)([a-zA-Z])$") # Matches X.Y.Z[letter]

            current_match_strip = zen_pattern_strip.match(current_for_comparison)
            if current_match_strip:
                base_current = current_match_strip.group(1)
                logger.debug(f"Zen-browser: stripping suffix for comparison. Current '{current_for_comparison}' -> '{base_current}'")
                current_for_comparison = base_current

            latest_match_strip = zen_pattern_strip.match(latest_for_comparison)
            if latest_match_strip:
                base_latest = latest_match_strip.group(1)
                logger.debug(f"Zen-browser: stripping suffix for comparison. Latest '{latest_for_comparison}' -> '{base_latest}'")
                latest_for_comparison = base_latest

        # These strings (potentially with suffixes stripped for zen-browser) are used for base version comparison
        current_parseable_str = current_for_comparison # Corrected typo
        latest_parseable_str = latest_for_comparison

        # However, for the actual parsing by packaging.version to check is_prerelease flags etc.,
        # we should use the versions that have NOT been stripped of their suffixes,
        # because "1.12.28b" is a pre-release according to packaging.version.
        # The comparison of base versions (stripped) determines if we *consider* an update.
        # The comparison of full versions (unstripped) by packaging.version then refines this.

        # Let's define what gets parsed for the full comparison (with suffixes if any)
        # These are the original normalized versions, before any zen-browser specific stripping for base comparison.
        current_full_parseable_str = current_normalized_initial
        latest_full_parseable_str = latest_normalized_initial


        logger.debug(f"Base versions for comparison: Current base '{current_parseable_str}' vs Latest base '{latest_parseable_str}'")
        logger.debug(f"Full versions for parsing: Current full '{current_full_parseable_str}' vs Latest full '{latest_full_parseable_str}'")

        update_available = False

        if not current_parseable_str: # Use the correct variable name
            # No current version installed, so any latest version is technically not an "update"
            # in the sense of replacing something. However, if latest_parseable_str exists,
            # it implies a version is available for new install.
            # For the purpose of "update_available" flag, if no current version, no update is "pending".
            pass
        elif not latest_parseable_str: # Use the correct variable name
            # No latest version found online, so no update available.
            pass
        else:
            try:
                # Parse the full versions (e.g., "1.12.28b") to respect their pre-release/etc flags
                parsed_current_full_version = parse_version_string(current_full_parseable_str)
                parsed_latest_full_version = parse_version_string(latest_full_parseable_str)

                # Parse the (potentially stripped for zen-browser) versions for base comparison
                parsed_current_base_for_compare = parse_version_string(current_parseable_str) # current_parseable_str was latest_for_comparison, fixed
                parsed_latest_base_for_compare = parse_version_string(latest_parseable_str)


                # For zen-browser, we want to accept these suffixed versions as updates
                # if their base versions are equivalent or newer.
                # The original latest_version (e.g. 1.12.28b) is what we'd update to.
                # packaging.version("1.12.28b") is a pre-release of 1.12.28.
                # So, the existing logic for repo_uses_beta might be okay,
                # or we might need to ensure zen-browser is treated as "repo_uses_beta=True"
                # or that the non-beta path correctly handles these post-releases.
                # Version("1.0.post1").is_prerelease is False.

                repo_accepts_prerelease_like_updates = version_utils.repo_uses_beta(self.repo)
                if self.owner == "zen-browser" and self.repo == "desktop":
                    # For zen-browser, consider these transformed versions as primary for update checks
                    repo_accepts_prerelease_like_updates = True


                if repo_accepts_prerelease_like_updates:
                    # If repo accepts pre-releases (or it's zen-browser where we force this path),
                    # an update is available if the latest full version is strictly newer than the current full version.
                    # This handles 1.12.28 -> 1.12.28b (since 1.12.28b is parsed as < 1.12.28, this alone isn't enough)
                    # AND 1.12.28a -> 1.12.28b (correctly)
                    # AND 1.12.28 -> 1.13.0 (correctly)

                    # For zen-browser, the primary condition is if the base versions are different,
                    # OR if base versions are same, but the full latest (e.g. 1.12.28b) is different from current full (e.g. 1.12.28 or 1.12.28a)
                    if self.owner == "zen-browser" and self.repo == "desktop":
                        if parsed_latest_base_for_compare > parsed_current_base_for_compare:
                            update_available = True
                        elif parsed_latest_base_for_compare == parsed_current_base_for_compare:
                            # Base versions are the same (e.g. both 1.12.28).
                            # Now check if the full latest version (e.g. 1.12.28b) is different from current full (e.g. 1.12.28 or 1.12.28a)
                            # We want to update from 1.12.28 to 1.12.28b, or 1.12.28a to 1.12.28b.
                            # The actual comparison of parsed_latest_full_version > parsed_current_full_version
                            # might be tricky if 1.12.28b < 1.12.28.
                            # So, if bases are same, and latest_full is different from current_full, consider it an update.
                            if latest_full_parseable_str != current_full_parseable_str:
                                # This ensures if current is 1.12.28 and latest is 1.12.28b, it's an update.
                                # If current is 1.12.28a and latest is 1.12.28b, it's an update.
                                # If current is 1.12.28b and latest is 1.12.28b, it's not.
                                update_available = True
                    elif parsed_latest_full_version > parsed_current_full_version: # Standard logic for beta-accepting repos
                        update_available = True
                else: # Standard logic for non-beta repos
                    if parsed_latest_full_version > parsed_current_full_version:
                        if parsed_latest_full_version.is_prerelease:
                            if not parsed_current_full_version.is_prerelease:
                                if parse_version_string(parsed_latest_full_version.base_version) > parsed_current_full_version:
                                    update_available = True
                            else: # Both are pre-releases
                                update_available = True
                        else: # Latest is stable
                            update_available = True
            except Exception as e:
                # Log with the strings that were attempted to be parsed by packaging.version
                logger.error(f"Error parsing versions for comparison (current_full='{current_full_parseable_str}', latest_full='{latest_full_parseable_str}'): {e}")
                # Keep update_available = False on error, or handle as appropriate

        if update_available: # Log only if an update is actually flagged
            # Log with original latest_version (e.g., 1.12.28b), not the transformed one
            logger.info(f"Update available: {current_version} → {latest_version}")

        return update_available, {
            "current_version": current_version,
            "latest_version": latest_version, # This is the raw tag like "1.12.28b"
            "current_normalized": current_full_parseable_str, # What was parsed by packaging.version
            "latest_normalized": latest_full_parseable_str,   # What was parsed by packaging.version
        }

    def filter_compatible_assets(
        self, assets: List[Dict], arch_keywords: Optional[List[str]] = None
    ) -> List[Dict]:
        """Filter assets based on architecture compatibility.

        Args:
            assets: List of asset dictionaries from GitHub
            arch_keywords: List of architecture keywords to filter by

        Returns:
            List of compatible assets

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
        self, release_data: Dict, asset_info: Dict, is_beta: bool = False
    ) -> Optional[ReleaseInfo]:
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
        compatible_assets: List[Dict],
    ) -> Dict[
        str, Union[bool, Optional[str], Optional[List[Dict[Any, Any]]], Optional[Dict[Any, Any]]]
    ]:
        """Create a standardized response for update checks.

        Args:
            update_available: Whether an update is available
            current_version: Current version string
            release_info: Processed ReleaseInfo object
            compatible_assets: List of compatible assets

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
            "is_prerelease": release_info.is_prerelease,
            "published_at": release_info.published_at,
            "appimage_url": release_info.appimage_url,
            "appimage_name": release_info.appimage_name,
            "sha_url": release_info.sha_url,
            "sha_name": release_info.sha_name,
            "hash_type": release_info.hash_type,
        }
