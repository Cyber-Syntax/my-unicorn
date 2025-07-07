#!/usr/bin/env python3
"""GitHub API handler module.

This module provides the primary interface for interacting with GitHub's API to handle releases,
assets, and SHA verification. It consolidates all GitHub-related operations into a single class
for consistent access patterns.
"""

import logging
from typing import Any

from my_unicorn.auth_manager import GitHubAuthManager
from my_unicorn.catalog import AppInfo, find_app_by_owner_repo, load_app_definition
from my_unicorn.icon_manager import IconManager
from my_unicorn.utils.arch_extraction import extract_arch_from_filename
from my_unicorn.utils.version_utils import extract_version, extract_version_from_filename

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
        checksum_file_name: str,
        checksum_hash_type: str,
        arch_keyword: str | None = None,
    ):
        """Initialize GitHub API handler.

        Args:
            owner: Repository owner/organization name
            repo: Repository name
            checksum_file_name: Name of SHA file for verification
            checksum_hash_type: Type of hash to use (sha256, sha512)
            arch_keyword: Optional architecture keyword for filtering

        """
        self.owner = owner
        self.repo = repo
        self.checksum_file_name: str | None = checksum_file_name  # Can be updated by SHAManager
        self.checksum_hash_type: str | None = checksum_hash_type  # Can be updated by SHAManager
        self._arch_keyword = arch_keyword
        self.version: str | None = None
        self.appimage_name: str | None = None
        self.app_download_url: str | None = None
        self.checksum_file_download_url: str | None = None
        self.extracted_hash_from_body: str | None = None
        self.asset_digest: str | None = None
        self._headers = GitHubAuthManager.get_auth_headers()
        self._icon_manager = IconManager()
        self._release_fetcher = ReleaseManager(owner, repo)
        self._release_info: ReleaseInfo | None = None

        # Load app info from catalog to get beta preference and other settings
        self._app_info: AppInfo | None = find_app_by_owner_repo(owner, repo)
        if self._app_info:
            logger.debug("Loaded app info for %s/%s, beta=%s", owner, repo, self._app_info.beta)
        else:
            logger.debug("No app info found for %s/%s in catalog", owner, repo)

        self._selector = AppImageSelector()  # Create selector once and reuse
        logger.debug("API initialized for %s/%s", owner, repo)

    @property
    def arch_keyword(self) -> str | None:
        """Get the architecture keyword for this API instance."""
        return self._arch_keyword

    @property
    def skip_verification(self) -> bool:
        """Check if verification should be skipped for this app."""
        if self._app_info is None:
            return False
        return bool(getattr(self._app_info, "skip_verification", False))

    def get_latest_release(
        self, version_check_only: bool = False, is_batch: bool = False
    ) -> tuple[bool, dict[str, Any] | str]:
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
                "App %s/%s configured for beta releases, fetching directly",
                self.owner,
                self.repo,
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
            logger.error("Failed to fetch release data via ReleaseManager: %s", raw_data_or_error)
            return False, str(raw_data_or_error)

        if not isinstance(raw_data_or_error, dict):
            logger.error(
                "Type mismatch: Expected dict from ReleaseManager, got %s", type(raw_data_or_error)
            )
            return False, "Internal error: Unexpected data type from release fetcher"

        raw_release_json: dict[str, Any] = raw_data_or_error
        try:
            self._process_release(
                raw_release_json, version_check_only=version_check_only, is_batch=is_batch
            )
            return True, raw_release_json
        except ValueError as e:
            logger.error(
                "Failed to process release data for %s/%s (fetched by ReleaseManager): %s",
                self.owner,
                self.repo,
                e,
            )
            return False, "Failed to process release data: %s" % e

    def _process_release(
        self, release_data: dict[str, Any], version_check_only: bool = False, is_batch: bool = False
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
            "Processing release in github_api.py: %s, version_check_only: %s, is_batch: %s",
            release_data.get("tag_name", "Unknown tag"),
            version_check_only,
            is_batch,
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
                        f"zen-browser: using version format {potential_zen_version} instead of {normalized_version} from tag {raw_tag}"
                    )
                    normalized_version = potential_zen_version

        if not normalized_version:
            raise ValueError(f"Could not determine version from tag: '{raw_tag}'")

        self.version = normalized_version

        # Skip asset processing for version-only checks to optimize performance
        if version_check_only:
            logger.debug(
                "Version check only: skipping asset processing for %s/%s",
                self.owner,
                self.repo,
            )
            # Clear asset-related attributes for version-only checks
            self.appimage_name = None
            self.app_download_url = None
            self.checksum_file_name = None
            self.checksum_file_download_url = None
            self.checksum_hash_type = None
            self.extracted_hash_from_body = None
            self.asset_digest = None

            # Create minimal asset info dict for version-only release info
            asset_info_dict = {
                "owner": self.owner,
                "repo": self.repo,
                "version": self.version,
                "appimage_name": None,
                "app_download_url": None,
                "checksum_file_name": None,
                "checksum_file_download_url": None,
                "checksum_hash_type": None,
                "extracted_hash_from_body": None,
                "asset_digest": None,
                "arch_keyword": self._arch_keyword,
            }  # Minimal info for version-only checks

            self._release_info = ReleaseInfo.from_release_data(release_data, asset_info_dict)
            logger.info(
                "Successfully processed version-only release %s for %s/%s",
                self.version,
                self.owner,
                self.repo,
            )
            return

        # Process assets for installation/download
        assets: list[dict[str, Any]] = release_data.get("assets", [])
        if not assets:
            logger.warning(
                "No assets found in release %s for %s/%s", raw_tag, self.owner, self.repo
            )

        # Ensure app info is loaded for asset selection
        if self._app_info is None:
            # Try exact owner/repo match first
            self._app_info = find_app_by_owner_repo(self.owner, self.repo)
            if self._app_info is None:
                # Fall back to repo name lookup
                self._app_info = load_app_definition(self.repo)
                logger.debug("Loaded app info via repo name for %s", self.repo)

        # Create config dict for selection - use app definition for preferred characteristic suffixes
        if self._app_info:
            # Use app definition's preferred characteristic suffixes
            user_local_config_data = {
                "installed_characteristic_suffix": None  # Let app definition guide selection
            }
            logger.debug(
                "Using preferred suffixes for %s: %s",
                self.repo,
                self._app_info.preferred_characteristic_suffixes,
            )
        else:
            # Fallback to legacy arch_keyword if no app definition found
            user_local_config_data = (
                {"installed_characteristic_suffix": self._arch_keyword}
                if self._arch_keyword
                else None
            )
            logger.warning(
                "No app definition found for %s, using legacy arch_keyword: %s",
                self.repo,
                self._arch_keyword,
            )

        # Use the pre-initialized selector
        if self._app_info is not None:
            selected_asset_result = self._selector.find_appimage_asset(
                assets=assets,
                definitive_app_info=self._app_info,
                user_local_config_data=user_local_config_data,
            )
        else:
            selected_asset_result = self._selector.find_appimage_asset(
                assets=assets,
                definitive_app_info=None,
                user_local_config_data=user_local_config_data,
            )

        if not selected_asset_result:
            if self._app_info:
                suffixes_info = (
                    "with preferred suffixes %s" % self._app_info.preferred_characteristic_suffixes
                )
            else:
                suffixes_info = "with arch_keyword '%s'" % self._arch_keyword

            logger.error(
                "No compatible AppImage asset found for %s/%s %s in release '%s'",
                self.owner,
                self.repo,
                suffixes_info,
                raw_tag,
            )
            raise ValueError(
                "No compatible AppImage asset found for %s/%s %s in release '%s'"
                % (self.owner, self.repo, suffixes_info, raw_tag)
            )

        appimage_asset_obj = AppImageAsset.from_github_asset(selected_asset_result.asset)
        self.appimage_name = appimage_asset_obj.name
        self.app_download_url = appimage_asset_obj.browser_download_url
        logger.info("Selected AppImage: %s", self.appimage_name)

        # Try extracting version from filename if not found in tag
        if (
            not normalized_version
            and self.appimage_name
            and (extracted_version := extract_version_from_filename(self.appimage_name))
        ):
            logger.debug("Using version from filename: %s", extracted_version)
            self.version = normalized_version = extracted_version

        if self.appimage_name:
            extracted_arch = extract_arch_from_filename(self.appimage_name)
            if extracted_arch:
                logger.info(
                    "Extracted architecture keyword from AppImage filename: %s",
                    extracted_arch,
                )
                self._arch_keyword = extracted_arch
            else:
                logger.warning(
                    "No architecture found in %s, keeping %s",
                    self.appimage_name,
                    self._arch_keyword,
                )

        if self.appimage_name:
            logger.debug("Processing SHA verification for %s", self.appimage_name)
            if self._app_info:
                # Log verification settings from app info
                app_settings = {
                    "skip_verification": self._app_info.skip_verification,
                    "use_asset_digest": self._app_info.use_asset_digest,
                    "use_github_release_desc": self._app_info.use_github_release_desc,
                }
                for setting, value in app_settings.items():
                    logger.debug("%s: %s", setting, value)

            # Check if verification should be skipped for this app
            if self._app_info and getattr(self._app_info, "skip_verification", False):
                logger.info(
                    "Skipping SHA search for %s - verification disabled for this app",
                    self.appimage_name,
                )
                self.checksum_file_name = None
                self.checksum_file_download_url = None
                self.checksum_hash_type = None
                self.extracted_hash_from_body = None
                self.asset_digest = None

            else:
                logger.debug("Proceeding with SHA processing for %s", self.appimage_name)
                # Use SHA name from app definition if available, otherwise use provided checksum_file_name
                if self._app_info and self._app_info.checksum_file_name:
                    initial_checksum_file_name_hint = self._app_info.checksum_file_name
                    logger.debug(
                        "Using SHA name from app definition: %s",
                        initial_checksum_file_name_hint,
                    )
                else:
                    initial_checksum_file_name_hint = self.checksum_file_name or "sha256"
                    logger.debug("Using fallback SHA name: %s", initial_checksum_file_name_hint)

                logger.debug("Creating SHAManager with app_info: %s", self._app_info)
                sha_mgr = SHAManager(
                    self.owner,
                    self.repo,
                    initial_checksum_file_name_hint,
                    self.appimage_name,
                    app_info=self._app_info,
                )
                sha_mgr.find_sha_asset(assets)

                logger.debug(
                    "SHAManager results - checksum_hash_type: %s, checksum_file_name: %s, asset_digest: %s",
                    sha_mgr.checksum_hash_type,
                    sha_mgr.checksum_file_name,
                    sha_mgr.asset_digest,
                )

                # Update instance attributes with results from SHAManager
                self.checksum_file_name = sha_mgr.checksum_file_name
                self.checksum_file_download_url = sha_mgr.checksum_file_download_url
                self.checksum_hash_type = sha_mgr.checksum_hash_type
                self.extracted_hash_from_body = sha_mgr.extracted_hash_from_body
                self.asset_digest = sha_mgr.asset_digest

                logger.debug(
                    "GitHub API updated - checksum_hash_type: %s, checksum_file_name: %s, asset_digest: %s",
                    self.checksum_hash_type,
                    self.checksum_file_name,
                    self.asset_digest,
                )
        else:
            self.checksum_file_name = None
            self.checksum_file_download_url = None
            self.checksum_hash_type = None
            self.extracted_hash_from_body = None
            self.asset_digest = None

        asset_info_dict = {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "appimage_name": self.appimage_name,
            "app_download_url": self.app_download_url,
            "checksum_file_name": self.checksum_file_name,
            "checksum_file_download_url": self.checksum_file_download_url,
            "checksum_hash_type": self.checksum_hash_type,
            "extracted_hash_from_body": self.extracted_hash_from_body,
            "asset_digest": self.asset_digest,
            "arch_keyword": self._arch_keyword,
        }

        self._release_info = ReleaseInfo.from_release_data(release_data, asset_info_dict)

        logger.info(
            "Successfully processed release %s for %s/%s",
            self.version,
            self.owner,
            self.repo,
        )
        logger.debug(
            "AppImage: %s, SHA: %s (Type: %s)",
            self.appimage_name,
            self.checksum_file_name or "Not found",
            self.checksum_hash_type or "N/A",
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
                "Unexpected data type from get_latest_release. Expected dict, got %s. Data: %s",
                type(data),
                data,
            )
            return False, {"error": "Internal error: Unexpected data type from release fetch."}

        latest_release_data: dict[str, Any] = data
        raw_github_tag = latest_release_data.get("tag_name", "")

        if not raw_github_tag:
            logger.error("No tag_name found in release data after successful fetch and process.")
            return False, {"error": "No tag_name found in fetched release data."}

        processor = ReleaseProcessor(self.owner, self.repo, self._arch_keyword)
        try:
            update_available, _version_comparison_info = processor.compare_versions(
                current_version or "", raw_github_tag
            )
        except ValueError as e:
            logger.error(
                "Error during version comparison for %s/%s: %s",
                self.owner,
                self.repo,
                e,
            )
            latest_version_for_error = self.version or raw_github_tag or "unknown"
            return False, {
                "error": "Error during version comparison: %s" % (e,),
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
            "prerelease": self._release_info.prerelease,
            "published_at": self._release_info.published_at,
        }

    def find_app_icon(self) -> dict[str, Any] | None:
        """Find and return app icon information.

        Returns:
            dict[str, Any] | None: Icon information dictionary if found, None otherwise

        """
        try:
            icon_info = self._icon_manager.find_icon(self.owner, self.repo, headers=self._headers)
            if icon_info:
                logger.info("Found app icon: %s", icon_info.get("name"))
            return icon_info
        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Error finding app icon: %s", e)
            return None

    def refresh_auth(self) -> None:
        """Refresh authentication headers by clearing cached headers."""
        logger.debug("Refreshing authentication headers")
        GitHubAuthManager.clear_cached_headers()
        self._headers = GitHubAuthManager.get_auth_headers()
        logger.info("Authentication headers refreshed")
