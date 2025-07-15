"""Configuration and validation for AppImage verification.

This module handles the configuration and validation logic for verification
parameters, including path resolution and hash type validation.
"""

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path


# Supported hash types
# TODO: delete non hash types here, create different logic for them
SUPPORTED_checksum_hash_typeS = [
    "sha256",
    "sha512",
    "no_hash",
    "extracted_checksum",
    "asset_digest",
]

logger = logging.getLogger(__name__)


@dataclass
class VerificationConfig:
    """Configuration for AppImage verification operations.

    This class handles initialization and validation of verification parameters,
    including path resolution and hash type validation.
    """

    checksum_file_name: str | None = None
    checksum_file_download_url: str | None = None
    appimage_name: str | None = None
    checksum_hash_type: str = "sha256"
    appimage_path: str | None = None
    direct_expected_hash: str | None = None
    asset_digest: str | None = None
    use_asset_digest: bool = False

    def __post_init__(self) -> None:
        """Initialize and validate the configuration."""
        self._resolve_appimage_path()
        self._resolve_sha_path()
        self._normalize_checksum_hash_type()
        self._set_asset_digest_flag()
        self._validate_checksum_hash_type()

    def _resolve_appimage_path(self) -> None:
        """Resolve the AppImage path if not explicitly set."""
        if self.appimage_path is None and self.appimage_name is not None:
            from my_unicorn.global_config import GlobalConfigManager

            downloads_dir = GlobalConfigManager().expanded_app_download_path
            self.appimage_path = str(Path(downloads_dir) / self.appimage_name)

    def _resolve_sha_path(self) -> None:
        """Resolve the SHA file path and make it app-specific."""
        if not self.checksum_file_name or os.path.isabs(self.checksum_file_name):
            return

        # Skip resolution for special values
        if self.checksum_file_name in ("extracted_checksum", "asset_digest"):
            return

        from my_unicorn.global_config import GlobalConfigManager

        downloads_dir = GlobalConfigManager().expanded_app_download_path
        sha_stem = Path(self.checksum_file_name).stem
        sha_suffix = Path(self.checksum_file_name).suffix
        app_specific_checksum_file_name = f"{self.appimage_name}_{sha_stem}{sha_suffix}"
        self.checksum_file_name = str(Path(downloads_dir) / app_specific_checksum_file_name)

    def _normalize_checksum_hash_type(self) -> None:
        """Normalize hash type to lowercase."""
        if self.checksum_hash_type:
            self.checksum_hash_type = self.checksum_hash_type.lower()

    def _set_asset_digest_flag(self) -> None:
        """set asset digest flag if hash type is asset_digest."""
        if self.checksum_hash_type == "asset_digest":
            self.use_asset_digest = True

    def _validate_checksum_hash_type(self) -> None:
        """Validate that the hash type is supported and available."""
        if self.checksum_hash_type not in SUPPORTED_checksum_hash_typeS:
            raise ValueError(
                f"Unsupported hash type: {self.checksum_hash_type}. "
                f"Supported types are: {', '.join(SUPPORTED_checksum_hash_typeS)}"
            )

        # Skip hashlib validation for special verification types
        if self._is_special_checksum_hash_type():
            return

        if self.checksum_hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Hash type {self.checksum_hash_type} not available in this system")

    def _is_special_checksum_hash_type(self) -> bool:
        """Check if this is a special hash type that doesn't use hashlib."""
        return (
            self.checksum_hash_type == "no_hash"
            or self.checksum_hash_type == "asset_digest"
            or self.checksum_file_name == "extracted_checksum"
            or self.checksum_file_name == "no_sha_file"
        )

    def set_appimage_path(self, full_path: str) -> None:
        """set the full path to the AppImage file for verification.

        Args:
            full_path: The complete path to the AppImage file
        """
        self.appimage_path = full_path
        logger.info("set AppImage path for verification: %s", full_path)

    def is_verification_skipped(self) -> bool:
        """Check if verification should be skipped."""
        return (
            self.checksum_hash_type == "no_hash" or not self.checksum_file_name or self.checksum_file_name == self.appimage_name
        )

    def is_asset_digest_verification(self) -> bool:
        """Check if this is asset digest verification."""
        return self.checksum_hash_type == "asset_digest" or self.use_asset_digest

    def is_extracted_checksum_verification(self) -> bool:
        """Check if this is extracted checksum verification."""
        return self.checksum_file_name == "extracted_checksum"

    def has_direct_hash(self) -> bool:
        """Check if a direct hash is available for verification."""
        return self.direct_expected_hash is not None

    def validate_for_verification(self) -> None:
        """Validate that all required fields are set for verification."""
        if not self.appimage_path:
            raise ValueError(f"AppImage path not set for {self.appimage_name}")

        if not os.path.exists(self.appimage_path):
            raise FileNotFoundError(f"AppImage file not found: {self.appimage_path}")
