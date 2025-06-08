#!/usr/bin/env python3
"""GitHub API handler module.

This module provides the primary interface for interacting with GitHub's API to handle releases, 
assets, and SHA verification. It consolidates all GitHub-related operations into a single class 
for consistent access patterns.
"""

import logging
from typing import Any

from src.catalog import AppInfo, find_app_by_owner_repo, load_app_definition
from src.auth_manager import GitHubAuthManager
from src.icon_manager import IconManager
from src.utils import arch_utils
from src.utils.arch_extraction import extract_arch_from_filename
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
        sha_name: str,
        hash_type: str,
        arch_keyword: str | None = None,
    ):
        """Initialize GitHub API handler.
        
        Args:
            owner: Repository owner/organization name
            repo: Repository name
            sha_name: Name of SHA file for verification
            hash_type: Type of hash to use (sha256, sha512)
            arch_keyword: Optional architecture keyword for filtering
        """
        self.owner = owner
        self.repo = repo
        self.sha_name: str | None = sha_name  # Can be updated by SHAManager
        self.hash_type: str | None = hash_type  # Can be updated by SHAManager
        self._arch_keyword = arch_keyword
        self.version: str = None
        self.appimage_name: str = None
        self.appimage_url: str = None
        self.sha_url: str | None = None
        self.extracted_hash_from_body: str | None = None
        self.asset_digest: str | None = None
        self._headers = GitHubAuthManager.get_auth_headers()
        self._icon_manager = IconManager()
        self._release_fetcher = ReleaseManager(owner, repo)
        self._release_info: ReleaseInfo | None = None

        # Load app info from catalog to get beta preference and other settings
        self._app_info: AppInfo | None = find_app_by_owner_repo(owner, repo)
        if self._app_info:
            logger.debug(f"Loaded app info for {owner}/{repo}, beta={self._app_info.beta}")
        else:
            logger.debug(f"No app info found for {owner}/{repo} in catalog")

        self._selector = AppImageSelector()  # Create selector once and reuse
        logger.debug(f"API initialized for {owner}/{repo}")

    @property
    def arch_keyword(self) -> str | None:
        """Get the architecture keyword for this API instance."""
        return self._arch_keyword

    @property
    def skip_verification(self) -> bool:
        """Check if verification should be skipped for this app."""
        return self._app_info and getattr(self._app_info, "skip_verification", False)

    def get_latest_release(
        self, version_check_only: bool = False, is_batch: bool = False
    ) -> tuple[bool, dict[str, Any], str]:
        """Fetch latest stable or beta release based on app configuration.
        
        Uses ReleaseManager to fetch the appropriate release version (stable or beta) based on the
        app's configuration in the catalog.
        Processes the release data and extracts relevant information.

        Args:
            version_check_only: If True, only check version without downloading assets
            is_batch: Whether this is part of a batch operation
            
        Returns:
            Tuple containing (success flag, release data or error message, additional info)
        """
        # Check if app prefers beta releases from catalog configuration
        prefer_beta = self._app_info.beta if self._app_info else False

        if prefer_beta:
            logger.debug(
                f"App {self.owner}/{self.repo} configured for beta releases, fetching directly"
            )
            success, raw_data_or_error = self._release_fetcher.get_latest_beta_release_data(
                self._headers
            )
        else:
            # Fetch stable release for non-beta apps
            success, raw_data_or_error = self._release_fetcher.get_latest_release_data(
                self._headers
            )

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
            error_msg = (
                f"Type mismatch: Expected dict from ReleaseManager, got {type(raw_data_or_error)}"
            )
            logger.error(error_msg)
            return False, {}, "Internal error: Unexpected data type from release fetcher"

        raw_release_json: dict[str, Any] = raw_data_or_error
        try:
            self._process_release(
                raw_release_json, version_check_only=version_check_only, is_batch=is_batch
            )
            return True, raw_release_json
        except ValueError as e:
            logger.error(
                f"Failed to process release data for {self.owner}/{self.repo} (fetched by ReleaseManager): {e}"
            )
            return False, f"Failed to process release data: {e}"

    def _process_release(
        self,
        release_data: dict[str, Any],
        version_check_only: bool = False,
        is_batch: bool = False
    ) -> None:
        """Process release data and populate instance attributes.

        Extracts version information, release details, and asset metadata from GitHub release data.
        Updates instance attributes with normalized version strings and architecture-specific assets
        For zen-browser, handles special version format including letter suffixes (e.g., 1.2.3b).

        Args:
            release_data: Raw release data dictionary from GitHub API response
            version_check_only: If True, only process version without downloading assets
            is_batch: Whether this operation is part of a batch update

        Raises:
            ValueError: If required release data is missing or tag format is invalid
        """
        logger.debug(
            f"Processing release in github_api.py: {release_data.get('tag_name', 'Unknown tag')}, version_check_only: {version_check_only}, is_batch: {is_batch}"
        )

        raw_tag = release_data.get("tag_name", "")
        if not raw_tag:
            raise ValueError("Release data missing tag_name")

        is_beta = release_data.get("prerelease", False)
        normalized_version = extract_version(raw_tag, is_beta)

        # Handle zen-browser's special version format (X.Y.Z[letter])
        if self.owner == "zen-browser" and self.repo == "desktop":
            import re
            
            zen_tag_pattern = re.compile(r"^v?(\d+\.\d+\.\d+)([a-zA-Z])$")
            match = zen_tag_pattern.match(raw_tag)
            if match:
                version_base, letter_suffix = match.group(1), match.group(2)
                potential_zen_version = f"{version_base}{letter_suffix}"
                if normalized_version != potential_zen_version:
                    logger.info(
                        f"zen-browser: using version format {potential_zen_version} "
                        f"instead of {normalized_version} from tag {raw_tag}"
                    )
                    normalized_version = potential_zen_version

        if not normalized_version:
            raise ValueError(f"Could not determine version from tag: '{raw_tag}'")

        self.version = normalized_version

        # Skip asset processing for version-only checks to optimize performance
        if version_check_only:
            logger.debug(
                f"Version check only: skipping asset processing for {self.owner}/{self.repo}"
            )
            # Clear asset-related attributes for version-only checks
            self.appimage_name = None
            self.appimage_url = None
            self.sha_name = None
            self.sha_url = None
            self.hash_type = None
            self.extracted_hash_from_body = None
            self.asset_digest = None

            # Create minimal asset info dict for version-only release info
            asset_info_dict = {
                "owner": self.owner,
                "repo": self.repo,
                "version": self.version,
                "appimage_name": None,
                "appimage_url": None,
                "sha_name": None,
                "sha_url": None,
                "hash_type": None,
                "extracted_hash_from_body": None,
                "asset_digest": None,
                "arch_keyword": self._arch_keyword,
            }  # Minimal info for version-only checks

            self._release_info = ReleaseInfo.from_release_data(release_data, asset_info_dict)
            logger.info(
                f"Successfully processed version-only release {self.version} for {self.owner}/{self.repo}"
            )
            return

        # Process assets for installation/download
        assets: list[dict[str, Any]] = release_data.get("assets", [])
        if not assets:
            logger.warning(
                f"No assets found in release {raw_tag} for {self.owner}/{self.repo}"
            )

        # Ensure app info is loaded for asset selection
        if self._app_info is None:
            # Try exact owner/repo match first
            self._app_info = find_app_by_owner_repo(self.owner, self.repo)
            if self._app_info is None:
                # Fall back to repo name lookup
                self._app_info = load_app_definition(self.repo)
                logger.debug(f"Loaded app info via repo name for {self.repo}")

        # Create config dict for selection - use app definition for preferred characteristic suffixes
        if self._app_info:
            # Use app definition's preferred characteristic suffixes
            user_local_config_data = {
                "installed_characteristic_suffix": None  # Let app definition guide selection
            }
            logger.debug(
                f"Using preferred suffixes for {self.repo}: "
                f"{self._app_info.preferred_characteristic_suffixes}"
            )
        else:
            # Fallback to legacy arch_keyword if no app definition found
            user_local_config_data = (
                {"installed_characteristic_suffix": self._arch_keyword}
                if self._arch_keyword
                else None
            )
            logger.warning(
                f"No app definition found for {self.repo}, using legacy arch_keyword: {self._arch_keyword}"
            )

        # Use the pre-initialized selector
        selected_asset_result = self._selector.find_appimage_asset(
            assets=assets,
            definitive_app_info=self._app_info,
            user_local_config_data=user_local_config_data,
        )

        if not selected_asset_result:
            if self._app_info:
                suffixes_info = (
                    f"with preferred suffixes {self._app_info.preferred_characteristic_suffixes}"
                )
            else:
                suffixes_info = f"with arch_keyword '{self._arch_keyword}'"

            error_msg = (
                f"No compatible AppImage asset found for {self.owner}/{self.repo} "
                f"{suffixes_info} in release '{raw_tag}'"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        appimage_asset_obj = AppImageAsset.from_github_asset(selected_asset_result.asset)
        self.appimage_name = appimage_asset_obj.name
        self.appimage_url = appimage_asset_obj.browser_download_url
        logger.info(f"Selected AppImage: {self.appimage_name}")

        # Try extracting version from filename if not found in tag
        if not normalized_version and self.appimage_name:
            if extracted_version := extract_version_from_filename(self.appimage_name):
                logger.debug(f"Using version from filename: {extracted_version}")
                self.version = normalized_version = extracted_version

        if self.appimage_name:
            extracted_arch = extract_arch_from_filename(self.appimage_name)
            if extracted_arch:
                logger.info(
                    f"Extracted architecture keyword from AppImage filename: {extracted_arch}"
                )
                self._arch_keyword = extracted_arch
            else:
                logger.warning(
                    f"No architecture found in {self.appimage_name}, keeping {self._arch_keyword}"
                )

        if self.appimage_name:
            logger.debug(f"Processing SHA verification for {self.appimage_name}")
            if self._app_info:
                # Log verification settings from app info
                app_settings = {
                    "skip_verification": self._app_info.skip_verification,
                    "use_asset_digest": self._app_info.use_asset_digest,
                    "use_github_release_desc": self._app_info.use_github_release_desc,
                }
                for setting, value in app_settings.items():
                    logger.debug(f"{setting}: {value}")

            # Check if verification should be skipped for this app
            if self._app_info and getattr(self._app_info, "skip_verification", False):
                logger.info(
                    f"Skipping SHA search for {self.appimage_name} - verification disabled for this app"
                )
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
                sha_mgr = SHAManager(
                    self.owner,
                    self.repo,
                    initial_sha_name_hint,
                    self.appimage_name,
                    is_batch=is_batch,
                    app_info=self._app_info,
                )
                sha_mgr.find_sha_asset(assets)

                logger.debug(
                    f"SHAManager results - hash_type: {sha_mgr.hash_type}, sha_name: {sha_mgr.sha_name}, asset_digest: {sha_mgr.asset_digest}"
                )

                # Update instance attributes with results from SHAManager
                self.sha_name = sha_mgr.sha_name
                self.sha_url = sha_mgr.sha_url
                self.hash_type = sha_mgr.hash_type
                self.extracted_hash_from_body = sha_mgr.extracted_hash_from_body
                self.asset_digest = sha_mgr.asset_digest

                logger.debug(
                    f"GitHub API updated - hash_type: {self.hash_type}, sha_name: {self.sha_name}, asset_digest: {self.asset_digest}"
                )
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
        self,
        current_version: str | None = None,
        version_check_only: bool = False,
        is_batch: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """Check and return structured update info."""
        ok, data = self.get_latest_release(version_check_only=version_check_only, is_batch=is_batch)

        if not ok:
            return False, {"error": str(data)}

        if not isinstance(data, dict):
            logger.error(
                f"Unexpected data type from get_latest_release. Expected dict, got {type(data)}. Data: {data}"
            )
            return False, {"error": "Internal error: Unexpected data type from release fetch."}

        latest_release_data: dict[str, Any] = data
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
            asset
            for asset in assets_from_release
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

    def find_app_icon(self) -> dict[str, Any] | None:
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
