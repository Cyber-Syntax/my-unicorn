"""SHA Manager module.

This module handles SHA-related operations for GitHub releases.
"""

import asyncio
import logging
import re  # For hash validation
from pathlib import Path

from src.api.sha_asset_finder import SHAAssetFinder
from src.utils import sha_utils, ui_utils
from src.utils.checksums.extractor import ReleaseChecksumExtractor  # Added import

logger = logging.getLogger(__name__)


class SHAManager:
    """Handles SHA-related operations for GitHub releases."""

    def __init__(
        self,
        owner: str,
        repo: str,
        sha_name: str,
        appimage_name: str | None = None,
        is_batch: bool = False,
    ):
        """Initialize the SHAManager.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            sha_name: Name of the SHA algorithm used in the release assets
            appimage_name: Name of the selected AppImage
            is_batch: True if running in a non-interactive batch mode

        """
        self.owner = owner
        self.repo = repo
        self.sha_name = sha_name
        self.appimage_name = appimage_name
        self.is_batch = is_batch  # Store the flag
        self.sha_url = None
        self.hash_type = None
        self.extracted_hash_from_body: str | None = None  # For hash from release body
        self.asset_digest: str | None = None  # For GitHub API asset digest verification

    def _try_extract_sha_from_release_body(self) -> bool:
        """Tries to extract the SHA256 checksum for the current AppImage
        from the GitHub release description.
        Sets instance attributes if successful.

        Returns:
            True if a checksum was successfully extracted, False otherwise.

        """
        if not self.appimage_name:
            logger.warning("Cannot extract SHA from release body: AppImage name not set.")
            return False

        logger.info(
            f"Attempting to extract SHA for {self.appimage_name} from release description..."
        )
        extractor = ReleaseChecksumExtractor(self.owner, self.repo)

        try:
            appimage_base_name = Path(self.appimage_name).name
            checksum_lines = extractor.extract_checksums(target_filename=appimage_base_name)

            if checksum_lines:
                best_match_hash = None
                for line in checksum_lines:
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2:
                        hash_value, f_name = parts
                        if f_name.strip() == appimage_base_name:  # Exact filename match
                            best_match_hash = hash_value.strip()
                            logger.info(
                                f"Found exact filename match in release description checksums: {f_name}"
                            )
                            break
                        if (
                            appimage_base_name.lower() in f_name.strip().lower()
                            and not best_match_hash
                        ):  # Substring match as fallback
                            best_match_hash = hash_value.strip()
                            logger.info(
                                f"Found substring match in release description checksums: {f_name}"
                            )

                if best_match_hash:
                    if re.fullmatch(
                        r"[0-9a-f]{64}", best_match_hash, re.IGNORECASE
                    ):  # Validate SHA256
                        self.hash_type = "sha256"
                        self.extracted_hash_from_body = best_match_hash
                        self.sha_name = "extracted_checksum"  # Use the specified name
                        self.sha_url = None
                        logger.info(
                            f"Successfully extracted SHA256 hash '{self.extracted_hash_from_body}' for {self.appimage_name} from release body."
                        )
                        return True
                    else:
                        logger.warning(
                            f"Extracted hash '{best_match_hash}' for {self.appimage_name} from body does not look like SHA256."
                        )
                else:
                    logger.info(
                        f"Checksum lines found for {appimage_base_name}, but no specific hash could be isolated from lines: {checksum_lines}"
                    )
            else:
                logger.info(
                    f"No checksums found for {appimage_base_name} in the release description."
                )

        except ValueError as e:
            logger.warning(f"Could not extract checksums from release description: {e}")
        except Exception as e:
            logger.error(f"Error during SHA extraction from release body: {e}", exc_info=True)

        return False

    def find_sha_asset(self, assets: list[dict]) -> None:
        """Find and select appropriate SHA file for verification.

        Args:
            assets: List of release assets from GitHub API

        """
        if self.sha_name == "no_sha_file":
            logger.info("Skipping SHA verification per configuration")
            # Skip the entire SHA search process when no_sha_file is specified
            self.hash_type = "no_hash"  # Set hash_type to no_hash to skip verification
            return

        if not self.appimage_name:
            logger.error("Cannot find SHA asset: AppImage name not set")
            return

        # Create a minimal AppInfo object for SHA finding
        from src.app_catalog import AppInfo

        app_info = AppInfo(
            owner=self.owner,
            repo=self.repo,
            app_rename=self.repo,
            description="",
            category="",
            tags=[],
            hash_type="sha256",
            appimage_name_template="",
            sha_name=self.sha_name,
            preferred_characteristic_suffixes=[],
            icon_info=None,
            icon_file_name=None,
            icon_repo_path=None,
        )

        # First priority: Try to use asset digest if available
        if self._try_extract_digest_from_assets(assets):
            logger.info(f"Using asset digest verification for {self.appimage_name}")
            return

        # Second priority: Try to find SHA asset file
        finder = SHAAssetFinder()
        sha_asset = finder.find_best_match(self.appimage_name, app_info, assets)

        if sha_asset:
            self._select_sha_asset(sha_asset)
        else:
            logger.info(f"No SHA asset file found for {self.appimage_name} via SHAAssetFinder.")
            # Third priority: Try to extract from release body
            if self._try_extract_sha_from_release_body():
                logger.info(
                    f"Successfully used SHA extracted for {self.appimage_name} from release description."
                )
                return  # SHA found from body, no need for further file-based fallback
            else:
                logger.warning(
                    f"Could not extract SHA for {self.appimage_name} from release description."
                )
                self._handle_sha_fallback(assets)  # Proceed to manual fallback

    def _select_sha_asset(self, asset: dict) -> None:
        """Select a SHA asset and set instance attributes.

        Args:
            asset: GitHub API asset information dictionary

        """
        detected_hash_type = sha_utils.detect_hash_type(asset["name"])
        self.hash_type = detected_hash_type or "sha256"
        self.sha_name = asset["name"]
        self.sha_url = asset["browser_download_url"]

        if not detected_hash_type:
            logger.info(f"Could not detect hash type from {self.sha_name}")
            # Always ask for hash type if not detected, regardless of is_batch
            self.hash_type = ui_utils.get_user_input("Enter hash type", default="sha256")

        logger.info(f"Selected SHA file: {self.sha_name} (hash type: {self.hash_type})")

    def _try_extract_digest_from_assets(self, assets: list[dict]) -> bool:
        """Try to extract digest information from GitHub API asset metadata.

        Args:
            assets: List of release assets from GitHub API

        Returns:
            True if digest was successfully extracted, False otherwise
        """
        if not self.appimage_name:
            return False

        # Look for the AppImage asset that matches our selected file
        for asset in assets:
            if asset.get("name") == self.appimage_name and asset.get("digest"):
                digest = asset["digest"]
                logger.info(f"Found asset digest for {self.appimage_name}: {digest}")
                
                # Validate digest format (should be like "sha256:hash_value")
                if ":" in digest:
                    digest_type, digest_hash = digest.split(":", 1)
                    if digest_type in ["sha256", "sha512"] and len(digest_hash) > 0:
                        self.asset_digest = digest
                        self.hash_type = "asset_digest"
                        self.sha_name = "asset_digest"
                        self.sha_url = None
                        logger.info(f"Using asset digest verification for {self.appimage_name}")
                        return True
                    else:
                        logger.warning(f"Invalid digest format or unsupported type: {digest}")
                else:
                    logger.warning(f"Invalid digest format (missing colon): {digest}")

        logger.debug(f"No digest found for {self.appimage_name} in assets")
        return False

    def _handle_sha_fallback(self, assets: list[dict]) -> None:
        """Handle fallback when SHA file couldn't be automatically determined.

        Args:
            assets: List of release assets from GitHub API

        """
        return self._handle_sha_fallback_sync(assets)

    async def _handle_sha_fallback_async(self, assets: list[dict]) -> None:
        """Async version of SHA fallback handler.

        Args:
            assets: List of release assets from GitHub API

        """
        logger.warning("Could not find SHA file automatically")
        print(f"Could not find SHA file automatically for {self.appimage_name}")
        print("1. Enter filename manually")
        print("2. Skip verification")

        try:
            # Use asyncio.to_thread for input operations
            choice = await asyncio.to_thread(ui_utils.get_user_input, "Your choice (1-2)")

            if choice == "1":
                self.sha_name = await asyncio.to_thread(
                    ui_utils.get_user_input, "Enter exact SHA filename"
                )
                for asset in assets:
                    if asset["name"] == self.sha_name:
                        self._select_sha_asset(asset)
                        return
                raise ValueError(f"SHA file {self.sha_name} not found")
            else:
                self.sha_name = "no_sha_file"
                self.hash_type = "no_hash"
                logger.info("User chose to skip SHA verification")

        except KeyboardInterrupt:
            logger.info("SHA fallback cancelled by user")
            raise

    def _handle_sha_fallback_sync(self, assets: list[dict]) -> None:
        """Synchronous version of SHA fallback handler.

        Args:
            assets: List of release assets from GitHub API

        """
        logger.warning("Could not find SHA file automatically")
        print(f"Could not find SHA file automatically for {self.appimage_name}")
        print("1. Enter filename manually")
        print("2. Skip verification")

        try:
            choice = ui_utils.get_user_input("Your choice (1-2)")

            if choice == "1":
                self.sha_name = ui_utils.get_user_input("Enter exact SHA filename")
                for asset in assets:
                    if asset["name"] == self.sha_name:
                        self._select_sha_asset(asset)
                        return
                raise ValueError(f"SHA file {self.sha_name} not found")
            else:
                self.sha_name = "no_sha_file"
                self.hash_type = "no_hash"
                logger.info("User chose to skip SHA verification")

        except KeyboardInterrupt:
            logger.info("SHA fallback cancelled by user")
            raise
