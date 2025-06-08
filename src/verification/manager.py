"""Main verification manager that orchestrates AppImage verification.

This module provides the main VerificationManager class that coordinates
all verification operations by delegating to specialized components.
"""

import os
from dataclasses import dataclass

from src.verification.asset_digest_verifier import AssetDigestVerifier
from src.verification.cleanup import VerificationCleanup
from src.verification.config import VerificationConfig
from src.verification.hash_calculator import HashCalculator
from src.verification.logger import VerificationLogger
from src.verification.sha_file_manager import ShaFileManager


@dataclass
class VerificationManager:
    """Main coordinator for AppImage verification operations.

    This class orchestrates the verification process by delegating to
    specialized components for configuration, hash calculation, SHA file
    management, asset digest verification, cleanup, and logging.
    """

    sha_name: str | None = None
    sha_url: str | None = None
    appimage_name: str | None = None
    hash_type: str = "sha256"
    appimage_path: str | None = None
    direct_expected_hash: str | None = None
    asset_digest: str | None = None
    use_asset_digest: bool = False

    def __post_init__(self) -> None:
        """Initialize the verification manager and its components."""
        # Initialize configuration
        self.config = VerificationConfig(
            sha_name=self.sha_name,
            sha_url=self.sha_url,
            appimage_name=self.appimage_name,
            hash_type=self.hash_type,
            appimage_path=self.appimage_path,
            direct_expected_hash=self.direct_expected_hash,
            asset_digest=self.asset_digest,
            use_asset_digest=self.use_asset_digest,
        )

        # Update our attributes from the validated config
        self._sync_from_config()

        # Initialize components
        self.logger = VerificationLogger()
        self.cleanup = VerificationCleanup()

        # Use appropriate hash type for HashCalculator
        # For asset_digest, we'll use sha256 as default since the actual algorithm
        # is determined from the digest string itself
        calculator_hash_type = (
            "sha256" if self.config.hash_type == "asset_digest" else self.config.hash_type
        )
        self.hash_calculator = HashCalculator(calculator_hash_type)
        self.sha_manager = ShaFileManager(self.config.hash_type)
        self.asset_verifier = AssetDigestVerifier()

    def _sync_from_config(self) -> None:
        """Sync our attributes with the validated configuration."""
        self.sha_name = self.config.sha_name
        self.sha_url = self.config.sha_url
        self.appimage_name = self.config.appimage_name
        self.hash_type = self.config.hash_type
        self.appimage_path = self.config.appimage_path
        self.direct_expected_hash = self.config.direct_expected_hash
        self.asset_digest = self.config.asset_digest
        self.use_asset_digest = self.config.use_asset_digest

    def set_appimage_path(self, full_path: str) -> None:
        """set the full path to the AppImage file for verification.

        Args:
            full_path: The complete path to the AppImage file

        """
        self.config.set_appimage_path(full_path)
        self.appimage_path = full_path

    def verify_appimage(self, cleanup_on_failure: bool = False) -> bool:
        """Verify the AppImage using the appropriate verification method.

        Args:
            cleanup_on_failure: Whether to remove the AppImage if verification fails

        Returns:
            True if verification passed or skipped, False otherwise

        """
        try:
            self.logger.log_verification_start(
                self.config.appimage_name or "Unknown", self.config.hash_type
            )

            # Check if verification should be skipped
            if self.config.is_verification_skipped():
                self.logger.log_verification_skipped("verification disabled or no hash file")
                return True

            # Handle asset digest verification
            if self.config.is_asset_digest_verification():
                return self._verify_with_asset_digest(cleanup_on_failure)

            # Handle extracted checksum verification
            if self.config.is_extracted_checksum_verification():
                return self._verify_extracted_checksum(cleanup_on_failure)

            # Handle standard SHA file verification
            return self._verify_with_sha_file(cleanup_on_failure)

        except Exception as e:
            self.logger.log_error(f"Verification failed for {self.config.appimage_name}", e)
            if cleanup_on_failure and self.config.appimage_path:
                self.cleanup.cleanup_failed_file(self.config.appimage_path)
            return False

    def _verify_with_asset_digest(self, cleanup_on_failure: bool) -> bool:
        """Verify using GitHub API asset digest."""
        try:
            self.config.validate_for_verification()

            if not self.config.asset_digest:
                self.logger.log_error("Asset digest not provided for verification")
                return False

            result = self.asset_verifier.verify_asset_digest(
                self.config.appimage_path, self.config.asset_digest, self.config.appimage_name
            )

            if not result and cleanup_on_failure:
                self.cleanup.cleanup_failed_file(self.config.appimage_path)

            return result

        except Exception as e:
            self.logger.log_error("Asset digest verification failed", e)
            if cleanup_on_failure:
                self.cleanup.cleanup_on_failure(self.config.appimage_path)
            return False

    def _verify_extracted_checksum(self, cleanup_on_failure: bool) -> bool:
        """Verify using extracted checksum (direct hash or legacy method)."""
        if self.config.has_direct_hash():
            return self._verify_with_direct_hash(cleanup_on_failure)
        else:
            return self._verify_with_release_checksums(cleanup_on_failure)

    def _verify_with_direct_hash(self, cleanup_on_failure: bool) -> bool:
        """Verify using directly provided hash."""
        try:
            self.config.validate_for_verification()

            self.logger.log_info(
                f"Verifying {self.config.appimage_name} using directly provided hash "
                f"(type: {self.config.hash_type})"
            )

            result = self.hash_calculator.verify_file_hash(
                self.config.appimage_path, self.config.direct_expected_hash
            )

            actual_hash = self.hash_calculator.calculate_file_hash(self.config.appimage_path)

            self.logger.log_hash_comparison(
                self.config.appimage_name,
                self.config.hash_type,
                actual_hash,
                self.config.direct_expected_hash,
                result,
            )

            if not result and cleanup_on_failure:
                self.cleanup.cleanup_failed_file(self.config.appimage_path)

            return result

        except Exception as e:
            self.logger.log_error("Direct hash verification failed", e)
            if cleanup_on_failure:
                self.cleanup.cleanup_on_failure(self.config.appimage_path)
            return False

    def _verify_with_release_checksums(self, cleanup_on_failure: bool) -> bool:
        """Verify using release description checksums via ReleaseDescVerifier."""
        try:
            from src.verification.release_desc_verifier import ReleaseDescVerifier

            self.logger.log_info("Using GitHub release description for verification")

            if not self.config.appimage_name:
                self.logger.log_error("No AppImage name provided, cannot extract checksums")
                return False

            self.config.validate_for_verification()

            # Use ReleaseDescVerifier with auto-detection
            return ReleaseDescVerifier.verify_appimage_standalone(
                appimage_path=self.config.appimage_path,
                cleanup_on_failure=cleanup_on_failure,
            )

        except Exception as e:
            self.logger.log_error("Release checksums verification failed", e)
            if cleanup_on_failure:
                self.cleanup.cleanup_on_failure(self.config.appimage_path)
            return False

    def _verify_with_sha_file(self, cleanup_on_failure: bool) -> bool:
        """Verify using SHA file."""
        try:
            self.config.validate_for_verification()

            # Handle fallback case where no SHA file is available
            if self.config.sha_name == self.config.appimage_name:
                self.logger.log_verification_skipped("no hash file provided by the developer")
                return True

            # Download SHA file if needed
            if (
                self.config.sha_url
                and self.config.sha_name
                and not os.path.exists(self.config.sha_name)
            ):
                self.sha_manager.download_sha_file(self.config.sha_url, self.config.sha_name)

            # Verify SHA file exists
            if not self.config.sha_name or not os.path.exists(self.config.sha_name):
                self.logger.log_error(f"SHA file not found: {self.config.sha_name}")
                return False

            # Parse SHA file and extract expected hash
            expected_hash = self.sha_manager.parse_sha_file(
                self.config.sha_name, self.config.appimage_name
            )

            # Calculate actual hash and compare
            actual_hash = self.hash_calculator.calculate_file_hash(self.config.appimage_path)
            result = self.hash_calculator.compare_hashes(actual_hash, expected_hash)

            # Log comparison results
            self.logger.log_hash_comparison(
                self.config.appimage_name, self.config.hash_type, actual_hash, expected_hash, result
            )

            # Cleanup SHA file after verification
            self.cleanup.cleanup_verification_file(self.config.sha_name)

            if not result and cleanup_on_failure:
                self.cleanup.cleanup_failed_file(self.config.appimage_path)

            return result

        except Exception as e:
            self.logger.log_error("SHA file verification failed", e)
            if cleanup_on_failure:
                self.cleanup.cleanup_on_failure(self.config.appimage_path, self.config.sha_name)
            return False

    def cleanup_batch_failed_files(
        self,
        app_name: str,
        appimage_name: str | None = None,
        sha_name: str | None = None,
        ask_confirmation: bool = True,
    ) -> list[str]:
        """Clean up AppImage and SHA files for batch operations when update fails.

        Args:
            app_name: Name of the app to clean up files for
            appimage_name: Exact AppImage filename if known, otherwise use patterns
            sha_name: Exact SHA filename if known, otherwise use patterns
            ask_confirmation: Whether to ask user for confirmation before removal

        Returns:
            list of file paths that were successfully removed

        """
        return self.cleanup.cleanup_batch_failed_files(
            app_name=app_name,
            appimage_name=appimage_name,
            sha_name=sha_name,
            ask_confirmation=ask_confirmation,
        )
