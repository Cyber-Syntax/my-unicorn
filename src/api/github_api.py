#!/usr/bin/env python3
"""
GitHub API handler module.

Consolidated GitHubAPI class with full release, asset, and SHA handling.
"""

import logging
from dataclasses import dataclass # Not used directly, but kept for context if other dataclasses are added
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from .release_manager import ReleaseManager # Added import
from api.appimage_selector import AppImageSelector
from src.auth_manager import GitHubAuthManager
from src.icon_manager import IconManager
from api.sha_manager import SHAManager
from src.utils import arch_utils, version_utils
from src.utils.arch_extraction import get_arch_from_filename # Added import
from api.release_processor import ReleaseProcessor
from api.assets import ReleaseInfo, AppImageAsset, SHAAsset # SHAAsset not directly used here but good for context

logger = logging.getLogger(__name__)

class GitHubAPI:
    """Handler for GitHub API requests, processing releases end-to-end."""

    def __init__(
        self,
        owner: str,
        repo: str,
        sha_name: str = "sha256", # Suffix hint for SHA file, e.g., "sha256", "sha512.txt"
        hash_type: str = "sha256", # Default hash algorithm if not determinable
        arch_keyword: Optional[str] = None,
    ):
        self.owner = owner
        self.repo = repo
        self.sha_name: Optional[str] = sha_name # Can be updated by SHAManager
        self.hash_type: Optional[str] = hash_type # Can be updated by SHAManager
        self._arch_keyword = arch_keyword
        self.version: Optional[str] = None
        self.appimage_name: Optional[str] = None
        self.appimage_url: Optional[str] = None
        self.sha_url: Optional[str] = None
        self.extracted_hash_from_body: Optional[str] = None # To store hash from release body
        self._headers = GitHubAuthManager.get_auth_headers()
        self._icon_manager = IconManager()
        self._release_fetcher = ReleaseManager(owner, repo) # Added ReleaseManager instance
        self._release_info: Optional[ReleaseInfo] = None # Initialize _release_info
        logger.debug(f"API initialized for {owner}/{repo}")

    @property
    def arch_keyword(self) -> Optional[str]:
        return self._arch_keyword

    def get_latest_release(self) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Fetch latest stable or fallback to beta release using ReleaseManager, then process it."""
        success, raw_data_or_error = self._release_fetcher.get_latest_release_data(self._headers)

        if not success:
            if isinstance(raw_data_or_error, str) and "rate limit exceeded" in raw_data_or_error.lower():
                logger.warning("GitHub API rate limit exceeded (reported by ReleaseManager), refreshing authentication.")
                self.refresh_auth() # Refresh auth using its own method
                # Optionally, could add a single retry attempt here after auth refresh
                # For now, inform user to try again.
                return False, "Rate limit exceeded. Authentication refreshed. Please try again."
            logger.error(f"Failed to fetch release data via ReleaseManager: {raw_data_or_error}")
            return False, raw_data_or_error # Other errors from ReleaseManager
        else:
            # At this point, success is True, so raw_data_or_error should be Dict[str, Any]
            if not isinstance(raw_data_or_error, dict):
                # This case should ideally not be reached if ReleaseManager's typing is correct
                # and success is True, but it's a safeguard.
                logger.error(f"Type mismatch: Expected dict from ReleaseManager on success, got {type(raw_data_or_error)}")
                return False, "Internal error: Unexpected data type from release fetcher."

            raw_release_json: Dict[str, Any] = raw_data_or_error
            try:
                self._process_release(raw_release_json) # Existing processing logic
                # self._release_info should now be populated by _process_release
                return True, raw_release_json # Return the raw JSON as per original logic
            except ValueError as e:
                logger.error(f"Failed to process release data for {self.owner}/{self.repo} (fetched by ReleaseManager): {e}")
                return False, f"Failed to process release data: {e}"

    # The get_all_releases() method is now effectively covered by get_latest_release(),
    # as ReleaseManager's get_latest_release_data() handles the fallback to fetching all releases
    # and picking the latest if /releases/latest returns a 404.
    # Thus, get_all_releases() can be removed.

    def _process_release(self, release_data: Dict[str, Any]) -> None:
        """Populate version, assets, and release info using normalized version."""
        logger.debug(f"Processing release in github_api.py: {release_data.get('tag_name', 'Unknown tag')}")

        raw_tag = release_data.get("tag_name", "")
        if not raw_tag:
            raise ValueError("Release data missing tag_name")

        assets = release_data.get("assets", [])
        if not assets: # Some releases might not have assets yet (e.g. draft just published tag)
            logger.warning(f"No assets found in release data for tag {raw_tag}. Cannot select AppImage.")
            # Depending on requirements, this could be an error or handled gracefully.
            # For now, if AppImage is mandatory, this will lead to an error later.
            # raise ValueError("No assets found in release data") # Uncomment if assets are strictly required

        is_beta = release_data.get("prerelease", False)

        normalized_version = version_utils.extract_version(raw_tag, is_beta)

        # For zen-browser, if the raw_tag matches X.Y.Z[letter], use the raw_tag (cleaned of 'v')
        # as the canonical version, overriding the potentially stripped version from extract_version.
        if self.owner == "zen-browser" and self.repo == "desktop":
            # Use a local import of re to avoid class-level or global import if not broadly needed
            import re
            zen_tag_pattern = re.compile(r"^v?(\d+\.\d+\.\d+)([a-zA-Z])$") # Matches vX.Y.Z[letter] or X.Y.Z[letter]
            match = zen_tag_pattern.match(raw_tag)
            if match:
                # Construct the version like "1.12.28b"
                potential_zen_version = f"{match.group(1)}{match.group(2)}"
                if normalized_version != potential_zen_version:
                    logger.info(f"For zen-browser, overriding extracted version '{normalized_version}' with specific tag format '{potential_zen_version}' from raw tag '{raw_tag}'.")
                normalized_version = potential_zen_version
            elif raw_tag.lstrip("vV") != normalized_version: # If not the special pattern but extract_version changed it
                 # This case handles if extract_version was too aggressive for other zen-browser tags.
                 # We prefer the raw_tag if extract_version changed it significantly, unless it was just 'v' stripping.
                 # However, the primary goal is to preserve X.Y.Z[letter].
                 # If the tag is just "1.12.28" and extract_version gets "1.12.28", this is fine.
                 pass


        selected_asset_data = AppImageSelector(self._arch_keyword).find_appimage_asset(assets)
        if not selected_asset_data:
            logger.error(f"No compatible AppImage asset found for {self.owner}/{self.repo} with arch_keyword '{self._arch_keyword}' in release '{raw_tag}'")
            raise ValueError("No compatible AppImage asset found in release")

        appimage_asset_obj = AppImageAsset.from_github_asset(selected_asset_data)
        self.appimage_name = appimage_asset_obj.name
        self.appimage_url = appimage_asset_obj.browser_download_url
        logger.info(f"Selected AppImage: {self.appimage_name}")

        if not normalized_version and self.appimage_name:
            normalized_version = version_utils.extract_version_from_filename(self.appimage_name)

        if not normalized_version:
            raise ValueError(f"Could not determine version from tag: '{raw_tag}' or filename: '{self.appimage_name}'")

        self.version = normalized_version

        if self.appimage_name:
            extracted_arch = get_arch_from_filename(self.appimage_name)
            if extracted_arch:
                logger.info(f"Extracted architecture keyword from AppImage filename: {extracted_arch}")
                self._arch_keyword = extracted_arch
            else:
                logger.warning(f"Could not extract architecture from AppImage filename: {self.appimage_name}. Current arch_keyword '{self._arch_keyword}' remains.")

        if self.appimage_name:
            # self.sha_name is Optional[str], but at this point (first call to _process_release),
            # it holds the initial hint from __init__ which is str.
            # SHAManager expects sha_name: str for its initial hint.
            initial_sha_name_hint: str
            if self.sha_name is None:
                # This case should not be hit on the first processing pass due to __init__
                # It might be hit if _process_release is called again after sha_name was set to None by a previous run.
                logger.warning(f"GitHubAPI.sha_name was None prior to SHAManager call for {self.appimage_name}. Using default 'sha256' hint.")
                initial_sha_name_hint = "sha256"
            else:
                initial_sha_name_hint = self.sha_name # This is str here

            sha_mgr = SHAManager(self.owner, self.repo, initial_sha_name_hint, self.appimage_name)
            sha_mgr.find_sha_asset(assets)
            # Update instance attributes with results from SHAManager
            self.sha_name = sha_mgr.sha_name # Now self.sha_name can become "from_release_description" or None
            self.sha_url = sha_mgr.sha_url
            self.hash_type = sha_mgr.hash_type
            self.extracted_hash_from_body = sha_mgr.extracted_hash_from_body # Get the extracted hash
        else: # No AppImage name, so no SHA to find related to it
            self.sha_name = None
            self.sha_url = None
            self.extracted_hash_from_body = None
            # self.hash_type could remain from a previous call or __init__, or be set to None too.
            # For clarity, if no appimage, no specific sha type.
            self.hash_type = None

        asset_info_dict = {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "appimage_name": self.appimage_name,
            "appimage_url": self.appimage_url,
            "sha_name": self.sha_name,
            "sha_url": self.sha_url,
            "hash_type": self.hash_type,
            "extracted_hash_from_body": self.extracted_hash_from_body, # Add to dict
            "arch_keyword": self._arch_keyword,
        }

        self._release_info = ReleaseInfo.from_release_data(release_data, asset_info_dict)

        logger.info(f"Successfully processed release {self.version} for {self.owner}/{self.repo}")
        logger.debug(f"AppImage: {self.appimage_name}, SHA: {self.sha_name or 'Not found'} (Type: {self.hash_type or 'N/A'})")

    def check_latest_version(self, current_version: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Check and return structured update info."""
        ok, data = self.get_latest_release()

        if not ok:
            return False, {"error": str(data)}

        if not isinstance(data, dict):
            logger.error(f"Unexpected data type from get_latest_release. Expected dict, got {type(data)}. Data: {data}")
            return False, {"error": "Internal error: Unexpected data type from release fetch."}

        latest_release_data: Dict[str, Any] = data
        raw_github_tag = latest_release_data.get("tag_name", "")

        if not raw_github_tag: # Should be caught by _process_release, but defensive check
             logger.error("No tag_name found in release data after successful fetch and process.")
             return False, {"error": "No tag_name found in fetched release data."}

        # Instance attributes (self.version, self._release_info) are populated by _process_release

        processor = ReleaseProcessor(self.owner, self.repo, self._arch_keyword)
        try:
            update_available, version_comparison_info = processor.compare_versions(current_version or "", raw_github_tag)
        except Exception as e:
            logger.error(f"Error during version comparison for {self.owner}/{self.repo}: {e}")
            # Ensure self.version is populated if possible, or use a placeholder
            # The test expects "error during version comparison" in the error message.
            latest_version_for_error = self.version or raw_github_tag or "unknown" # Provide context
            return False, {"error": f"Error during version comparison: {e!s}", "current_version": current_version, "latest_version": latest_version_for_error}

        if not self._release_info:
            logger.error("Internal error: _release_info not set after processing release.")
            return False, {"error": "Internal error: Failed to obtain release details."}
        if not self.version:
            logger.error("Internal error: self.version not set after processing release.")
            return False, {"error": "Internal error: Failed to obtain normalized version."}

        assets_from_release = latest_release_data.get("assets", [])
        arch_keywords_for_filtering = arch_utils.get_arch_keywords(self._arch_keyword)
        compatible_assets = processor.filter_compatible_assets(assets_from_release, arch_keywords_for_filtering)

        return update_available, {
            "current_version": current_version,
            "latest_version": self.version,
            "release_notes": self._release_info.release_notes,
            "release_url": self._release_info.release_url,
            "compatible_assets": compatible_assets,
            "is_prerelease": self._release_info.is_prerelease,
            "published_at": self._release_info.published_at,
        }

    def find_app_icon(self) -> Optional[Dict[str, Any]]:
        try:
            icon_info = self._icon_manager.find_icon(self.owner, self.repo, headers=self._headers)
            if icon_info:
                logger.info(f"Found app icon: {icon_info.get('name')}")
            return icon_info
        except Exception as e:
            logger.error(f"Error finding app icon: {e!s}")
            return None

    def refresh_auth(self) -> None:
        logger.debug("Refreshing authentication headers")
        GitHubAuthManager.clear_cached_headers()
        self._headers = GitHubAuthManager.get_auth_headers()
        logger.info("Authentication headers refreshed")
