#!/usr/bin/env python3
"""GitHub API handler module.

Consolidated GitHubAPI class with full release, asset, and SHA handling.
"""

import logging
from typing import Any, Dict, Optional, Tuple, Union

from src.app_catalog import load_app_definition, find_app_by_owner_repo, AppInfo
from src.auth_manager import GitHubAuthManager
from src.icon_manager import IconManager
from src.utils import arch_utils
from src.utils.arch_extraction import get_arch_from_filename
from src.utils.version_utils import extract_version, extract_version_from_filename

from .assets import AppImageAsset, ReleaseInfo
from .release_manager import ReleaseManager
from .release_processor import ReleaseProcessor
from .selector import AppImageSelector
from .sha_manager import SHAManager

logger = logging.getLogger(__name__)


class GitHubAPI:
    """Handler for GitHub API requests, processing releases end-to-end."""

    def __init__(
        self,
        owner: str,
        repo: str,
        sha_name: str = "sha256",  # Suffix hint for SHA file, e.g., "sha256", "sha512.txt"
        hash_type: str = "sha256",  # Default hash algorithm if not determinable
        arch_keyword: Optional[str] = None,  # Legacy parameter, kept for compatibility
    ):
        self.owner = owner
        self.repo = repo
        self.sha_name: Optional[str] = sha_name  # Can be updated by SHAManager
        self.hash_type: Optional[str] = hash_type  # Can be updated by SHAManager
        self._arch_keyword = arch_keyword  # Legacy field
        self.version: Optional[str] = None
        self.appimage_name: Optional[str] = None
        self.appimage_url: Optional[str] = None
        self.sha_url: Optional[str] = None
        self.extracted_hash_from_body: Optional[str] = None  # To store hash from release body
        self.asset_digest: Optional[str] = None  # To store GitHub API asset digest
        self._headers = GitHubAuthManager.get_auth_headers()
        self._icon_manager = IconManager()
        self._release_fetcher = ReleaseManager(owner, repo)
        self._release_info: Optional[ReleaseInfo] = None
        self._app_info: Optional[AppInfo] = None
        self._selector = AppImageSelector()  # Create selector once and reuse
        logger.debug(f"API initialized for {owner}/{repo}")

    @property
    def arch_keyword(self) -> Optional[str]:
        return self._arch_keyword

    @property
    def skip_verification(self) -> bool:
        """Check if verification should be skipped for this app."""
        return self._app_info and getattr(self._app_info, 'skip_verification', False)

    def get_latest_release(self, version_check_only: bool = False, is_batch: bool = False) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Fetch latest stable or fallback to beta release using ReleaseManager, then process it."""
        success, raw_data_or_error = self._release_fetcher.get_latest_release_data(self._headers)

        if not success:
            if (
                isinstance(raw_data_or_error, str)
                and "rate limit exceeded" in raw_data_or_error.lower()
            ):
                logger.warning(
                    "GitHub API rate limit exceeded (reported by ReleaseManager), refreshing authentication."
                )
                self.refresh_auth()
                return False, "Rate limit exceeded. Authentication refreshed. Please try again."
            logger.error(f"Failed to fetch release data via ReleaseManager: {raw_data_or_error}")
            return False, raw_data_or_error

        if not isinstance(raw_data_or_error, dict):
            logger.error(
                f"Type mismatch: Expected dict from ReleaseManager on success, got {type(raw_data_or_error)}"
            )
            return False, "Internal error: Unexpected data type from release fetcher."

        raw_release_json: Dict[str, Any] = raw_data_or_error
        try:
            self._process_release(raw_release_json, version_check_only=version_check_only, is_batch=is_batch)
            return True, raw_release_json
        except ValueError as e:
            logger.error(
                f"Failed to process release data for {self.owner}/{self.repo} (fetched by ReleaseManager): {e}"
            )
            return False, f"Failed to process release data: {e}"

    def _process_release(self, release_data: Dict[str, Any], version_check_only: bool = False, is_batch: bool = False) -> None:
        """Populate version, assets, and release info using normalized version."""
        logger.debug(
            f"Processing release in github_api.py: {release_data.get('tag_name', 'Unknown tag')}, version_check_only: {version_check_only}, is_batch: {is_batch}"
        )

        raw_tag = release_data.get("tag_name", "")
        if not raw_tag:
            raise ValueError("Release data missing tag_name")

        assets = release_data.get("assets", [])
        if not assets:
            logger.warning(
                f"No assets found in release data for tag {raw_tag}. Cannot select AppImage."
            )

        is_beta = release_data.get("prerelease", False)

        normalized_version = extract_version(raw_tag, is_beta)

        # For zen-browser, if the raw_tag matches X.Y.Z[letter], use the raw_tag (cleaned of 'v')
        # as the canonical version, overriding the potentially stripped version from extract_version.
        if self.owner == "zen-browser" and self.repo == "desktop":
            import re

            zen_tag_pattern = re.compile(r"^v?(\d+\.\d+\.\d+)([a-zA-Z])$")
            match = zen_tag_pattern.match(raw_tag)
            if match:
                potential_zen_version = f"{match.group(1)}{match.group(2)}"
                if normalized_version != potential_zen_version:
                    logger.info(
                        f"For zen-browser, overriding extracted version '{normalized_version}' with specific tag format '{potential_zen_version}' from raw tag '{raw_tag}'."
                    )
                normalized_version = potential_zen_version
            elif raw_tag.lstrip("vV") != normalized_version:
                pass

        # Load app info if not already loaded
        if self._app_info is None:
            # First try finding by exact owner/repo match
            self._app_info = find_app_by_owner_repo(self.owner, self.repo)
            # Fall back to repo name lookup if not found
            if self._app_info is None:
                self._app_info = load_app_definition(self.repo)

        # Create config dict for selection - use app definition for preferred characteristic suffixes
        if self._app_info:
            # Use the preferred characteristic suffixes from app definition
            user_local_config_data = {
                "installed_characteristic_suffix": None  # Let selector choose based on app definition
            }
            logger.debug(f"Using app definition for {self.repo} with preferred suffixes: {self._app_info.preferred_characteristic_suffixes}")
        else:
            # Fallback to legacy arch_keyword if no app definition found
            user_local_config_data = {
                "installed_characteristic_suffix": self._arch_keyword
            } if self._arch_keyword else None
            logger.warning(f"No app definition found for {self.repo}, using legacy arch_keyword: {self._arch_keyword}")

        # Use the pre-initialized selector
        selected_asset_result = self._selector.find_appimage_asset(
            assets=assets,
            definitive_app_info=self._app_info,
            user_local_config_data=user_local_config_data
        )

        if not selected_asset_result:
            if self._app_info:
                suffixes_info = f"with preferred suffixes {self._app_info.preferred_characteristic_suffixes}"
            else:
                suffixes_info = f"with arch_keyword '{self._arch_keyword}'"

            logger.error(
                f"No compatible AppImage asset found for {self.owner}/{self.repo} {suffixes_info} in release '{raw_tag}'"
            )
            raise ValueError("No compatible AppImage asset found in release")

        appimage_asset_obj = AppImageAsset.from_github_asset(selected_asset_result.asset)
        self.appimage_name = appimage_asset_obj.name
        self.appimage_url = appimage_asset_obj.browser_download_url
        logger.info(f"Selected AppImage: {self.appimage_name}")

        if not normalized_version and self.appimage_name:
            normalized_version = extract_version_from_filename(self.appimage_name)

        if not normalized_version:
            raise ValueError(
                f"Could not determine version from tag: '{raw_tag}' or filename: '{self.appimage_name}'"
            )

        self.version = normalized_version

        if self.appimage_name:
            extracted_arch = get_arch_from_filename(self.appimage_name)
            if extracted_arch:
                logger.info(
                    f"Extracted architecture keyword from AppImage filename: {extracted_arch}"
                )
                self._arch_keyword = extracted_arch
            else:
                logger.warning(
                    f"Could not extract architecture from AppImage filename: {self.appimage_name}. Current arch_keyword '{self._arch_keyword}' remains."
                )

        if self.appimage_name and not version_check_only:
            logger.debug(f"Processing SHA for {self.appimage_name}, version_check_only={version_check_only}")
            logger.debug(f"App info available: {self._app_info is not None}")
            if self._app_info:
                logger.debug(f"App skip_verification: {getattr(self._app_info, 'skip_verification', False)}")
                logger.debug(f"App use_asset_digest: {getattr(self._app_info, 'use_asset_digest', False)}")
                logger.debug(f"App use_github_release_desc: {getattr(self._app_info, 'use_github_release_desc', False)}")
            
            # Check if verification should be skipped for this app
            if self._app_info and getattr(self._app_info, 'skip_verification', False):
                logger.info(f"Skipping SHA search for {self.appimage_name} - verification disabled for this app")
                self.sha_name = None
                self.sha_url = None
                self.hash_type = None
                self.extracted_hash_from_body = None
                self.asset_digest = None

            else:
                logger.debug(f"Proceeding with SHA processing for {self.appimage_name}")
                # Use SHA name from app definition if available, otherwise use provided sha_name
                if self._app_info and self._app_info.sha_name:
                    initial_sha_name_hint = self._app_info.sha_name
                    logger.debug(f"Using SHA name from app definition: {initial_sha_name_hint}")
                else:
                    initial_sha_name_hint = self.sha_name or "sha256"
                    logger.debug(f"Using fallback SHA name: {initial_sha_name_hint}")

                logger.debug(f"Creating SHAManager with app_info: {self._app_info}")
                sha_mgr = SHAManager(self.owner, self.repo, initial_sha_name_hint, self.appimage_name, is_batch=is_batch, app_info=self._app_info)
                sha_mgr.find_sha_asset(assets)
                
                logger.debug(f"SHAManager results - hash_type: {sha_mgr.hash_type}, sha_name: {sha_mgr.sha_name}, asset_digest: {sha_mgr.asset_digest}")
                
                # Update instance attributes with results from SHAManager
                self.sha_name = sha_mgr.sha_name
                self.sha_url = sha_mgr.sha_url
                self.hash_type = sha_mgr.hash_type
                self.extracted_hash_from_body = sha_mgr.extracted_hash_from_body
                self.asset_digest = sha_mgr.asset_digest
                
                logger.debug(f"GitHub API updated - hash_type: {self.hash_type}, sha_name: {self.sha_name}, asset_digest: {self.asset_digest}")
        else:
            self.sha_name = None
            self.sha_url = None
            self.hash_type = None
            self.extracted_hash_from_body = None
            self.asset_digest = None

        asset_info_dict = {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "appimage_name": self.appimage_name,
            "appimage_url": self.appimage_url,
            "sha_name": self.sha_name,
            "sha_url": self.sha_url,
            "hash_type": self.hash_type,
            "extracted_hash_from_body": self.extracted_hash_from_body,
            "asset_digest": self.asset_digest,
            "arch_keyword": self._arch_keyword,
        }

        self._release_info = ReleaseInfo.from_release_data(release_data, asset_info_dict)

        logger.info(f"Successfully processed release {self.version} for {self.owner}/{self.repo}")
        logger.debug(
            f"AppImage: {self.appimage_name}, SHA: {self.sha_name or 'Not found'} (Type: {self.hash_type or 'N/A'})"
        )

    def check_latest_version(
        self, current_version: Optional[str] = None, version_check_only: bool = False, is_batch: bool = False
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check and return structured update info."""
        ok, data = self.get_latest_release(version_check_only=version_check_only, is_batch=is_batch)

        if not ok:
            return False, {"error": str(data)}

        if not isinstance(data, dict):
            logger.error(
                f"Unexpected data type from get_latest_release. Expected dict, got {type(data)}. Data: {data}"
            )
            return False, {"error": "Internal error: Unexpected data type from release fetch."}

        latest_release_data: Dict[str, Any] = data
        raw_github_tag = latest_release_data.get("tag_name", "")

        if not raw_github_tag:
            logger.error("No tag_name found in release data after successful fetch and process.")
            return False, {"error": "No tag_name found in fetched release data."}

        processor = ReleaseProcessor(self.owner, self.repo, self._arch_keyword)
        try:
            update_available, version_comparison_info = processor.compare_versions(
                current_version or "", raw_github_tag
            )
        except Exception as e:
            logger.error(f"Error during version comparison for {self.owner}/{self.repo}: {e}")
            latest_version_for_error = self.version or raw_github_tag or "unknown"
            return False, {
                "error": f"Error during version comparison: {e!s}",
                "current_version": current_version,
                "latest_version": latest_version_for_error,
            }

        if not self._release_info:
            logger.error("Internal error: _release_info not set after processing release.")
            return False, {"error": "Internal error: Failed to obtain release details."}
        if not self.version:
            logger.error("Internal error: self.version not set after processing release.")
            return False, {"error": "Internal error: Failed to obtain normalized version."}

        assets_from_release = latest_release_data.get("assets", [])
        compatible_assets = [
            asset for asset in assets_from_release
            if self._arch_keyword is None or self._arch_keyword in asset["name"].lower()
        ]

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
