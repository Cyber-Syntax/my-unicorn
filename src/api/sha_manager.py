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
        app_info=None,
    ):
        """Initialize the SHAManager.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            sha_name: Name of the SHA algorithm used in the release assets
            appimage_name: Name of the selected AppImage
            is_batch: True if running in a non-interactive batch mode
            app_info: AppInfo object containing app-specific settings

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
        self._app_info = app_info
        self.skip_verification: bool = app_info.skip_verification if app_info else False

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
        if self.skip_verification:
            logger.info("Skipping SHA verification per configuration")
            # Skip the entire SHA search process when skip_verification is enabled
            return

        if not self.appimage_name:
            logger.error("Cannot find SHA asset: AppImage name not set")
            return

        # Priority 1: Asset digest verification is handled by SHAAssetFinder
        # No need for separate check here - let SHAAssetFinder handle it

        # Priority 2: Try to extract from release body description
        if self._try_extract_sha_from_release_body():
            logger.info(f"Successfully extracted SHA for {self.appimage_name} from release description")
            return

        # Priority 3: Try to find SHA asset file using SHAAssetFinder
        finder = SHAAssetFinder()
        sha_asset = finder.find_best_match(self.appimage_name, self._app_info, assets)

        if sha_asset:
            logger.debug(f"SHAAssetFinder returned: {sha_asset}")
            # Check if this is a special asset digest response
            if sha_asset.get("hash_type") == "asset_digest":
                self.hash_type = "asset_digest"
                self.sha_name = "asset_digest"
                self.sha_url = None
                self.asset_digest = sha_asset["digest"]
                logger.info(f"Successfully assigned asset digest verification for {self.appimage_name}")
                logger.debug(f"Asset digest: {self.asset_digest}")
                logger.debug(f"Hash type: {self.hash_type}")
                logger.debug(f"SHA name: {self.sha_name}")
            else:
                self._select_sha_asset(sha_asset)
                logger.info(f"Found SHA file for {self.appimage_name}: {sha_asset['name']}")
            return

        # Priority 4: Manual fallback - ask user
        logger.warning(f"No automatic verification method found for {self.appimage_name}")
        self._handle_sha_fallback(assets)

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
                self.skip_verification = True
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
                self.skip_verification = True
                logger.info("User chose to skip SHA verification")

        except KeyboardInterrupt:
            logger.info("SHA fallback cancelled by user")
            raise
