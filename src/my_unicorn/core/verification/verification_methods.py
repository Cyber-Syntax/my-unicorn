"""Verification method implementations.

This module provides the actual verification implementation functions
for digest and checksum file verification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    SUPPORTED_HASH_ALGORITHMS,
    YAML_DEFAULT_HASH,
    HashType,
)
from my_unicorn.core.github import ChecksumFileInfo
from my_unicorn.core.verification.checksum_parser import (
    ChecksumFileResult,
    parse_all_checksums,
)
from my_unicorn.core.verification.results import MethodResult
from my_unicorn.core.verification.verifier import Verifier
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from my_unicorn.core.cache import ReleaseCacheManager
    from my_unicorn.core.download import DownloadService
    from my_unicorn.core.verification.context import VerificationContext

logger = get_logger(__name__, enable_file_logging=True)


async def verify_digest(
    verifier: Verifier,
    digest: str,
    app_name: str,
    skip_configured: bool,
) -> MethodResult | None:
    """Verify file using GitHub API digest.

    Args:
        verifier: Verifier instance
        digest: Expected digest hash
        app_name: Application name for logging
        skip_configured: Whether skip was configured

    Returns:
        MethodResult or None if failed

    """
    try:
        logger.debug("Attempting digest verification from GitHub API")
        logger.debug("AppImage file: %s", verifier.file_path.name)
        logger.debug("Expected digest: %s", digest)
        if skip_configured:
            logger.debug("Note: Using digest despite skip=true setting")

        # Get actual file hash to compare
        actual_digest = verifier.compute_hash("sha256")
        logger.debug("   🧮 Computed digest: %s", actual_digest)

        verifier.verify_digest(digest)
        logger.debug("✓ Digest verification passed")
        logger.debug("✓ Digest match confirmed")
        return MethodResult(
            passed=True,
            hash=digest,
            computed_hash=actual_digest,
            details="GitHub API digest verification",
        )
    except Exception as e:
        logger.error("Digest verification failed: %s", e)
        logger.error("Expected: %s", digest)
        logger.error("AppImage: %s", verifier.file_path.name)
        return MethodResult(
            passed=False,
            hash=digest,
            details=str(e),
        )


async def verify_checksum_file(
    verifier: Verifier,
    checksum_file: ChecksumFileInfo,
    target_filename: str,
    app_name: str,
    download_service: DownloadService,
    cache_manager: ReleaseCacheManager | None = None,
    context: VerificationContext | None = None,
) -> MethodResult | None:
    """Verify file using checksum file.

    Args:
        verifier: Verifier instance
        checksum_file: Checksum file information
        target_filename: Target filename to look for
        app_name: Application name for logging
        download_service: Service for downloading checksum files
        cache_manager: Optional cache manager for storing checksum files
        context: Verification context for cache storage

    Returns:
        MethodResult or None if failed

    """
    try:
        logger.debug(
            "Verifying using checksum file: %s (%s format)",
            checksum_file.filename,
            checksum_file.format_type,
        )

        # Download checksum file content
        content = await download_service.download_checksum_file(
            checksum_file.url
        )

        # Determine hash type
        hash_type: HashType
        if checksum_file.format_type == "yaml":
            hash_type = YAML_DEFAULT_HASH
        else:
            detected_hash = verifier.detect_hash_type_from_filename(
                checksum_file.filename
            )
            valid_hashes = list(SUPPORTED_HASH_ALGORITHMS)
            hash_type = (
                detected_hash
                if detected_hash in valid_hashes
                else DEFAULT_HASH_TYPE
            )

        # Parse checksum file
        expected_hash = verifier.parse_checksum_file(
            content, target_filename, hash_type
        )
        if not expected_hash:
            logger.error("Checksum file verification FAILED - hash not found!")
            logger.error(
                "   📄 Checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )
            logger.error("Looking for: %s", target_filename)
            return MethodResult(
                passed=False,
                hash="",
                details=(
                    f"Hash not found for {target_filename} in checksum file"
                ),
            )

        logger.debug("Starting hash comparison for checksum file verification")
        logger.debug(
            "   📄 Checksum file: %s (%s format)",
            checksum_file.filename,
            checksum_file.format_type,
        )
        logger.debug("   🔍 Target file: %s", target_filename)
        logger.debug(
            "   📋 Expected hash (%s): %s",
            hash_type.upper(),
            expected_hash,
        )

        # Compute actual hash and compare
        computed_hash = verifier.compute_hash(hash_type)
        logger.debug(
            "   🧮 Computed hash (%s): %s",
            hash_type.upper(),
            computed_hash,
        )

        # Perform comparison
        hashes_match = computed_hash.lower() == expected_hash.lower()
        logger.debug(
            "Hash comparison: %s == %s → %s",
            computed_hash.lower()[:32] + "...",
            expected_hash.lower()[:32] + "...",
            "MATCH" if hashes_match else "MISMATCH",
        )

        if hashes_match:
            logger.debug(
                "✓ Checksum file verification PASSED! (%s)",
                hash_type.upper(),
            )
            logger.debug(
                "Checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )
            logger.debug("✓ Hash match confirmed")

            # Cache checksum file data after successful verification
            await cache_checksum_file_data(
                content,
                checksum_file,
                hash_type,
                cache_manager,
                context,
            )

            return MethodResult(
                passed=True,
                hash=expected_hash,
                computed_hash=computed_hash,
                details=(
                    f"Verified against {checksum_file.format_type} "
                    f"checksum file"
                ),
                url=checksum_file.url,
                hash_type=hash_type,
            )
        logger.error("Checksum file verification FAILED")
        logger.error(
            "Checksum file: %s (%s format)",
            checksum_file.filename,
            checksum_file.format_type,
        )
        logger.error("Expected hash: %s", expected_hash)
        logger.error("Computed hash: %s", computed_hash)
        logger.error("Hash mismatch detected")
        return MethodResult(
            passed=False,
            hash=f"{hash_type}:{computed_hash}",
            details=f"Hash mismatch (expected: {expected_hash})",
        )

    except Exception as e:
        logger.error("Checksum file verification failed: %s", e)
        return MethodResult(
            passed=False,
            hash="",
            details=str(e),
        )


async def cache_checksum_file_data(
    content: str,
    checksum_file: ChecksumFileInfo,
    hash_type: HashType,
    cache_manager: ReleaseCacheManager | None,
    context: VerificationContext | None,
) -> None:
    """Cache checksum file data after successful verification.

    Parses all hashes from the checksum file and stores them in cache
    for future use.

    Args:
        content: Downloaded checksum file content.
        checksum_file: Checksum file information.
        hash_type: Detected hash algorithm type.
        cache_manager: Cache manager for storing data.
        context: Verification context with owner/repo/version.

    """
    if not cache_manager or not context:
        return

    try:
        all_hashes = parse_all_checksums(content)
        if not all_hashes:
            logger.debug(
                "No hashes parsed from checksum file: %s",
                checksum_file.filename,
            )
            return

        algorithm = hash_type.upper()
        if algorithm not in ("SHA256", "SHA512"):
            algorithm = "SHA256"

        checksum_result = ChecksumFileResult(
            source=checksum_file.url,
            filename=checksum_file.filename,
            algorithm=algorithm,
            hashes=all_hashes,
        )

        stored = await cache_manager.store_checksum_file(
            context.owner,
            context.repo,
            context.tag_name,
            checksum_result.to_cache_dict(),
        )

        if stored:
            logger.debug(
                "Cached checksum file: %s with %d hashes",
                checksum_file.filename,
                len(all_hashes),
            )
        else:
            logger.debug(
                "Failed to cache checksum file: %s (cache may be missing)",
                checksum_file.filename,
            )

    except Exception as e:
        logger.debug(
            "Error caching checksum file %s: %s",
            checksum_file.filename,
            e,
        )
