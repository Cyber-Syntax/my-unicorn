"""Verification strategies using the Strategy pattern.

This module provides different verification strategies for file integrity checking,
following the Strategy design pattern to separate verification approaches.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from my_unicorn.github_client import ChecksumFileInfo
from my_unicorn.logger import get_logger
from my_unicorn.utils import format_bytes
from my_unicorn.verify import HashType, Verifier

if TYPE_CHECKING:
    from my_unicorn.download import DownloadService

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class VerificationContext:
    """Context data for verification strategies."""

    file_path: Path
    asset: dict[str, Any]
    app_name: str
    owner: str
    repo: str
    tag_name: str
    download_service: DownloadService


@dataclass(slots=True, frozen=True)
class StrategyResult:
    """Result of a verification strategy execution."""

    passed: bool
    hash: str = ""
    details: str = ""
    hash_type: str = ""
    url: str = ""


class VerificationStrategy(ABC):
    """Abstract base class for verification strategies."""

    def __init__(self, verifier: Verifier) -> None:
        """Initialize strategy with verifier instance.

        Args:
            verifier: Verifier instance for core hash computation

        """
        self.verifier = verifier

    @abstractmethod
    async def verify(self, context: VerificationContext, **kwargs: Any) -> StrategyResult:
        """Execute verification strategy.

        Args:
            context: Verification context containing file and metadata
            **kwargs: Additional strategy-specific parameters

        Returns:
            StrategyResult with verification outcome

        """

    @abstractmethod
    def is_applicable(self, context: VerificationContext, **kwargs: Any) -> bool:
        """Check if this strategy is applicable for the given context.

        Args:
            context: Verification context
            **kwargs: Additional parameters

        Returns:
            True if strategy can be applied

        """


class DigestVerificationStrategy(VerificationStrategy):
    """Strategy for GitHub API digest verification."""

    def is_applicable(self, context: VerificationContext, **kwargs: Any) -> bool:
        """Check if digest verification is applicable.

        Args:
            context: Verification context
            **kwargs: Additional parameters

        Returns:
            True if digest is available in asset

        """
        digest_value = context.asset.get("digest") or ""
        return bool(digest_value and digest_value.strip())

    async def verify(self, context: VerificationContext, **kwargs: Any) -> StrategyResult:
        """Execute digest verification.

        Args:
            context: Verification context
            **kwargs: Additional parameters (skip_configured for logging)

        Returns:
            StrategyResult with verification outcome

        """
        digest = context.asset.get("digest") or ""
        skip_configured = kwargs.get("skip_configured", False)

        try:
            logger.debug("🔐 Attempting digest verification (from GitHub API)")
            logger.debug("   📄 AppImage file: %s", context.file_path.name)
            logger.debug("   🔢 Expected digest: %s", digest)
            if skip_configured:
                logger.debug("   Note: Using digest despite skip=true setting")

            # Get actual file hash to compare
            actual_digest = self.verifier.compute_hash("sha256")  # Digest is usually SHA-256
            logger.debug("   🧮 Computed digest: %s", actual_digest)

            self.verifier.verify_digest(digest)
            logger.debug("✅ Digest verification passed")
            logger.debug("   ✓ Digest match confirmed")

            return StrategyResult(
                passed=True,
                hash=digest,
                details="GitHub API digest verification",
            )

        except ValueError as e:
            logger.error("❌ Digest verification failed: %s", e)
            logger.error("   Expected: %s", digest)
            logger.error("   AppImage: %s", context.file_path.name)
            return StrategyResult(
                passed=False,
                hash=digest,
                details=str(e),
            )


class ChecksumFileVerificationStrategy(VerificationStrategy):
    """Strategy for checksum file verification (YAML, .txt, AppImage.sha256, AppImage.DIGEST, etc.)."""

    def is_applicable(self, context: VerificationContext, **kwargs: Any) -> bool:
        """Check if checksum file verification is applicable.

        Args:
            context: Verification context
            **kwargs: Should contain 'checksum_file' parameter

        Returns:
            True if checksum file is provided

        """
        checksum_file = kwargs.get("checksum_file")
        return checksum_file is not None

    async def verify(self, context: VerificationContext, **kwargs: Any) -> StrategyResult:
        """Execute checksum file verification.

        Args:
            context: Verification context
            **kwargs: Must contain 'checksum_file' and 'target_filename'

        Returns:
            StrategyResult with verification outcome

        """
        checksum_file: ChecksumFileInfo = kwargs["checksum_file"]
        target_filename: str = kwargs["target_filename"]

        try:
            logger.debug(
                "🔍 Verifying using checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )

            # Download checksum file content
            content = await context.download_service.download_checksum_file(checksum_file.url)

            # Determine hash type based on format
            if checksum_file.format_type == "yaml":
                hash_type_str = "sha512"  # Common for Electron apps
            else:
                hash_type_str = self.verifier.detect_hash_type_from_filename(
                    checksum_file.filename
                )

            # Cast to HashType for type safety
            hash_type = cast(HashType, hash_type_str)

            # Parse checksum file to get expected hash
            expected_hash = self.verifier.parse_checksum_file(
                content, target_filename, hash_type
            )
            if not expected_hash:
                logger.error("❌ Checksum file verification FAILED - hash not found!")
                logger.error(
                    "   📄 Checksum file: %s (%s format)",
                    checksum_file.filename,
                    checksum_file.format_type,
                )
                logger.error("   🔍 Looking for: %s", target_filename)
                return StrategyResult(
                    passed=False,
                    hash="",
                    details=f"Hash not found for {target_filename} in checksum file",
                )

            logger.debug("🔍 Starting hash comparison for checksum file verification")
            logger.debug(
                "   📄 Checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )
            logger.debug("   🔍 Target file: %s", target_filename)
            logger.debug("   📋 Expected hash (%s): %s", hash_type.upper(), expected_hash)

            # Compute actual hash and compare
            computed_hash = self.verifier.compute_hash(hash_type)
            logger.debug("   🧮 Computed hash (%s): %s", hash_type.upper(), computed_hash)

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
                return StrategyResult(
                    passed=True,
                    hash=f"{hash_type}:{computed_hash}",
                    details=f"Verified against {checksum_file.format_type} checksum file",
                    url=checksum_file.url,
                    hash_type=hash_type,
                )
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
                return StrategyResult(
                    passed=False,
                    hash=f"{hash_type}:{computed_hash}",
                    details=f"Hash mismatch (expected: {expected_hash})",
                )

        except (ValueError, OSError) as e:
            logger.error("❌ Checksum file verification failed: %s", e)
            return StrategyResult(
                passed=False,
                hash="",
                details=str(e),
            )
