"""Verification strategies for different verification methods."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from my_unicorn.download import DownloadService
from my_unicorn.github_client import ChecksumFileInfo
from my_unicorn.logger import get_logger
from my_unicorn.verification.verify import Verifier

logger = get_logger(__name__, enable_file_logging=True)

# Type alias for hash types
HashType = Literal["sha1", "sha256", "sha512", "md5"]


class VerificationStrategy(ABC):
    """Base strategy interface for file verification methods."""

    @abstractmethod
    async def verify(
        self,
        verifier: Verifier,
        verification_data: Any,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Perform verification using this strategy.

        Args:
            verifier: Verifier instance for the file
            verification_data: Strategy-specific data needed for verification
            context: Additional context information

        Returns:
            Verification result dict or None if verification failed

        """

    @abstractmethod
    def can_verify(self, verification_data: Any, context: dict[str, Any]) -> bool:
        """Check if this strategy can perform verification with given data.

        Args:
            verification_data: Strategy-specific data
            context: Additional context information

        Returns:
            True if strategy can verify, False otherwise

        """


class DigestVerificationStrategy(VerificationStrategy):
    """Strategy for verifying files using GitHub API digest."""

    async def verify(
        self,
        verifier: Verifier,
        verification_data: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Verify file using GitHub API digest.

        Args:
            verifier: Verifier instance
            verification_data: Expected digest hash
            context: Context with app_name and skip_configured

        Returns:
            Verification result dict or None if failed

        """
        digest = verification_data
        skip_configured = context.get("skip_configured", False)

        try:
            logger.debug("🔐 Attempting digest verification (from GitHub API)")
            logger.debug("   📄 AppImage file: %s", verifier.file_path.name)
            logger.debug("   🔢 Expected digest: %s", digest)
            if skip_configured:
                logger.debug("   Note: Using digest despite skip=true setting")

            # Get actual file hash to compare
            actual_digest = verifier.compute_hash("sha256")  # Digest is usually SHA-256
            logger.debug("   🧮 Computed digest: %s", actual_digest)

            verifier.verify_digest(digest)
            logger.debug("✅ Digest verification passed")
            logger.debug("   ✓ Digest match confirmed")
            return {
                "passed": True,
                "hash": digest,
                "computed_hash": actual_digest,
                "details": "GitHub API digest verification",
            }
        except Exception as e:  # Keep broad for backward compatibility
            logger.error("❌ Digest verification failed: %s", e)
            logger.error("   Expected: %s", digest)
            logger.error("   AppImage: %s", verifier.file_path.name)
            return {
                "passed": False,
                "hash": digest,
                "details": str(e),
            }

    def can_verify(self, verification_data: str, context: dict[str, Any]) -> bool:
        """Check if digest verification is possible.

        Args:
            verification_data: Expected digest hash
            context: Additional context

        Returns:
            True if digest is available and non-empty

        """
        return bool(verification_data and verification_data.strip())


class ChecksumFileVerificationStrategy(VerificationStrategy):
    """Strategy for verifying files using checksum files."""

    def __init__(self, download_service: DownloadService) -> None:
        """Initialize checksum file verification strategy.

        Args:
            download_service: Service for downloading checksum files

        """
        self.download_service = download_service

    async def verify(
        self,
        verifier: Verifier,
        verification_data: ChecksumFileInfo,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Verify file using checksum file.

        Args:
            verifier: Verifier instance
            verification_data: Checksum file information
            context: Context with target_filename and app_name

        Returns:
            Verification result dict or None if failed

        """
        checksum_file = verification_data
        target_filename = context.get("target_filename", verifier.file_path.name)

        try:
            logger.debug(
                "🔍 Verifying using checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )

            # Download checksum file content using existing download service method
            content = await self.download_service.download_checksum_file(checksum_file.url)

            # Use Verifier's parse_checksum_file method which handles both formats
            if checksum_file.format_type == "yaml":
                # For YAML files, use sha512 as default hash type (common for Electron apps)
                hash_type: HashType = "sha512"
            else:
                # For traditional files, detect hash type from filename
                detected_hash = verifier.detect_hash_type_from_filename(checksum_file.filename)
                # Ensure we get a valid hash type
                valid_hashes = ["sha1", "sha256", "sha512", "md5"]
                hash_type = detected_hash if detected_hash in valid_hashes else "sha256"

            # Parse using the public method that handles both YAML and traditional formats
            expected_hash = verifier.parse_checksum_file(content, target_filename, hash_type)
            if not expected_hash:
                logger.error("❌ Checksum file verification FAILED - hash not found!")
                logger.error(
                    "   📄 Checksum file: %s (%s format)",
                    checksum_file.filename,
                    checksum_file.format_type,
                )
                logger.error("   🔍 Looking for: %s", target_filename)
                return {
                    "passed": False,
                    "hash": "",
                    "details": f"Hash not found for {target_filename} in checksum file",
                }

            logger.debug("🔍 Starting hash comparison for checksum file verification")
            logger.debug(
                "   📄 Checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )
            logger.debug("   🔍 Target file: %s", target_filename)
            logger.debug("   📋 Expected hash (%s): %s", hash_type.upper(), expected_hash)

            # Compute actual hash and compare
            computed_hash = verifier.compute_hash(hash_type)
            logger.debug("   🧮 Computied hash (%s): %s", hash_type.upper(), computed_hash)

            # Perform comparison
            hashes_match = computed_hash.lower() == expected_hash.lower()
            logger.debug(
                "   🔄 Hash comparison: %s == %s → %s",
                computed_hash.lower()[:32] + "...",
                expected_hash.lower()[:32] + "...",
                "MATCH" if hashes_match else "MISMATCH",
            )

            if hashes_match:
                logger.debug("✅ Checksum file verification PASSED! (%s)", hash_type.upper())
                logger.debug(
                    "   📄 Checksum file: %s (%s format)",
                    checksum_file.filename,
                    checksum_file.format_type,
                )
                logger.debug("   ✓ Hash match confirmed")
                return {
                    "passed": True,
                    "hash": f"{hash_type}:{computed_hash}",
                    "details": f"Verified against {checksum_file.format_type} checksum file",
                    "url": checksum_file.url,
                    "hash_type": hash_type,
                }
            else:
                logger.error("❌ Checksum file verification FAILED!")
                logger.error(
                    "   📄 Checksum file: %s (%s format)",
                    checksum_file.filename,
                    checksum_file.format_type,
                )
                logger.error("   🔢 Expected hash: %s", expected_hash)
                logger.error("   🧮 Computed hash: %s", computed_hash)
                logger.error("   ❌ Hash mismatch detected")
                return {
                    "passed": False,
                    "hash": f"{hash_type}:{computed_hash}",
                    "details": f"Hash mismatch (expected: {expected_hash})",
                }

        except Exception as e:  # Keep broad for backward compatibility
            logger.error("❌ Checksum file verification failed: %s", e)
            return {
                "passed": False,
                "hash": "",
                "details": str(e),
            }

    def can_verify(self, verification_data: ChecksumFileInfo, context: dict[str, Any]) -> bool:
        """Check if checksum file verification is possible.

        Args:
            verification_data: Checksum file information
            context: Additional context

        Returns:
            True if checksum file info is valid

        """
        return bool(
            verification_data
            and verification_data.filename
            and verification_data.url
            and verification_data.format_type
        )
