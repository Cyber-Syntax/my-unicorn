"""Detection logic for verification methods.

This module provides functions for detecting available verification methods,
including digest and checksum file detection, prioritization, and skip logic.
"""

from __future__ import annotations

from typing import Any

from my_unicorn.constants import VerificationMethod
from my_unicorn.core.github import Asset, AssetSelector, ChecksumFileInfo
from my_unicorn.core.verification.helpers import resolve_manual_checksum_file
from my_unicorn.logger import get_logger

logger = get_logger(__name__, enable_file_logging=True)


def detect_available_methods(
    asset: Asset,
    config: dict[str, Any],
    assets: list[Asset] | None = None,
    owner: str | None = None,
    repo: str | None = None,
    tag_name: str | None = None,
) -> tuple[bool, list[ChecksumFileInfo]]:
    """Detect available verification methods.

    Args:
        asset: GitHub asset information
        config: Verification configuration
        assets: All GitHub release assets (optional)
        owner: Repository owner (optional)
        repo: Repository name (optional)
        tag_name: Release tag name (optional)

    Returns:
        Tuple of (has_digest, checksum_files_list)

    """
    has_digest = check_digest_availability(asset, config)
    checksum_files = resolve_checksum_files(
        asset, config, assets, owner, repo, tag_name
    )
    return has_digest, checksum_files


def check_digest_availability(asset: Asset, config: dict[str, Any]) -> bool:
    """Check if digest verification is available.

    Args:
        asset: GitHub asset information
        config: Verification configuration

    Returns:
        True if digest is available

    """
    digest_value = asset.digest or ""
    has_digest = bool(digest_value and digest_value.strip())
    digest_requested = config.get(VerificationMethod.DIGEST, False)

    if digest_requested and not has_digest:
        logger.warning(
            "⚠️  Digest verification requested but no digest available "
            "from GitHub API"
        )
        logger.debug("   📦 Asset digest field: '%s'", digest_value or "None")
    elif has_digest:
        logger.debug(
            "✅ Digest available for verification: %s",
            digest_value[:16] + "...",
        )

    return has_digest


def resolve_checksum_files(
    asset: Asset,
    config: dict[str, Any],
    assets: list[Asset] | None,
    owner: str | None,
    repo: str | None,
    tag_name: str | None,
) -> list[ChecksumFileInfo]:
    """Resolve checksum files from config or auto-detection.

    Args:
        asset: GitHub asset information
        config: Verification configuration
        assets: All GitHub release assets (optional)
        owner: Repository owner (optional)
        repo: Repository name (optional)
        tag_name: Release tag name (optional)

    Returns:
        List of checksum file info

    """
    manual_checksum_file = config.get("checksum_file")

    # Use manually configured checksum file if specified
    # Handle both v1 (string) and v2 (dict) formats
    if manual_checksum_file:
        if isinstance(manual_checksum_file, dict):
            # v2 format: {"filename": "...", "algorithm": "..."}
            filename = manual_checksum_file.get("filename", "")
            if filename and filename.strip():
                return resolve_manual_checksum_file(
                    filename, asset, owner, repo, tag_name
                )
        elif (
            isinstance(manual_checksum_file, str)
            and manual_checksum_file.strip()
        ):
            # v1 format: plain string
            return resolve_manual_checksum_file(
                manual_checksum_file, asset, owner, repo, tag_name
            )

    # Auto-detect if conditions are met
    if (
        assets
        and owner
        and repo
        and tag_name
        and not config.get(VerificationMethod.DIGEST, False)
    ):
        return auto_detect_checksum_files(assets, tag_name)

    if assets and config.get(VerificationMethod.DIGEST, False):
        logger.debug(
            "i  Skipping auto-detection: "
            "digest verification explicitly enabled"
        )

    return []


def auto_detect_checksum_files(
    assets: list[Asset], tag_name: str
) -> list[ChecksumFileInfo]:
    """Auto-detect checksum files from GitHub assets.

    Args:
        assets: GitHub release assets
        tag_name: Release tag name

    Returns:
        List of detected checksum file info

    """
    logger.debug(
        "🔍 Auto-detecting checksum files (digest not explicitly enabled)"
    )
    try:
        checksum_files = AssetSelector.detect_checksum_files(assets, tag_name)
        logger.debug(
            "🔍 Auto-detected %d checksum files from assets",
            len(checksum_files),
        )
        return checksum_files
    except Exception as e:
        logger.warning("Failed to auto-detect checksum files: %s", e)
        return []


def should_skip_verification(
    config: dict[str, Any],
    has_digest: bool,
    has_checksum_files: bool,
) -> tuple[bool, dict[str, Any]]:
    """Determine if verification should be skipped.

    Args:
        config: Verification configuration
        has_digest: Whether digest verification is available
        has_checksum_files: Whether checksum file verification available

    Returns:
        Tuple of (should_skip, updated_config)

    """
    catalog_skip = config.get("skip", False)
    updated_config = config.copy()

    # Only skip if configured AND no strong verification methods available
    if catalog_skip and not has_digest and not has_checksum_files:
        logger.debug(
            "⏭️ Verification skipped "
            "(configured skip, no strong methods available)"
        )
        return True, updated_config
    if catalog_skip and (has_digest or has_checksum_files):
        logger.debug(
            "🔄 Overriding skip setting - "
            "strong verification methods available"
        )
        # Update config to reflect that we're now using verification
        updated_config["skip"] = False

    return False, updated_config


def prioritize_checksum_files(
    checksum_files: list[ChecksumFileInfo],
    target_filename: str,
) -> list[ChecksumFileInfo]:
    """Prioritize checksum files to try most relevant one first.

    For a target file like 'app.AppImage', this will prioritize:
    1. Exact match: 'app.AppImage.DIGEST'
    2. Platform-specific: 'app.AppImage.sha256'
    3. Generic files: 'checksums.txt', etc.

    Args:
        checksum_files: List of detected checksum files
        target_filename: Name of the file being verified

    Returns:
        Reordered list with most relevant checksum files first

    """
    if not checksum_files:
        return checksum_files

    logger.debug(
        "🔍 Prioritizing %d checksum files for target: %s",
        len(checksum_files),
        target_filename,
    )

    def get_priority(
        checksum_file: ChecksumFileInfo,
    ) -> tuple[int, str]:
        """Get priority score (lower = higher priority)."""
        filename = checksum_file.filename

        # Priority 1: Exact match (e.g., app.AppImage.DIGEST)
        digest_names = {
            f"{target_filename}.DIGEST",
            f"{target_filename}.digest",
        }
        if filename in digest_names:
            logger.debug("   📌 Priority 1 (exact .DIGEST): %s", filename)
            return (1, filename)

        # Priority 2: Platform-specific hash files
        target_extensions = [
            ".sha256",
            ".sha512",
            ".sha1",
            ".md5",
            ".sha256sum",
            ".sha512sum",
            ".sha1sum",
            ".md5sum",
        ]
        for ext in target_extensions:
            if filename == f"{target_filename}{ext}":
                logger.debug(
                    "   📌 Priority 2 (platform-specific): %s", filename
                )
                return (2, filename)

        # Priority 3: YAML files (usually most comprehensive)
        if checksum_file.format_type == "yaml":
            logger.debug("   📌 Priority 3 (YAML): %s", filename)
            return (3, filename)

        # Priority 4: Other .DIGEST files
        if filename.lower().endswith((".digest",)):
            logger.debug("   📌 Priority 4 (other .DIGEST): %s", filename)
            return (4, filename)

        # Priority 5: Generic checksum files
        penalty = 0
        lower_filename = filename.lower()
        experimental_variants = [
            "experimental",
            "beta",
            "alpha",
            "preview",
            "rc",
            "dev",
        ]
        if any(variant in lower_filename for variant in experimental_variants):
            penalty = 10
            logger.debug(
                "   📌 Priority 5 (generic + experimental penalty): %s",
                filename,
            )
        else:
            logger.debug("   📌 Priority 5 (generic): %s", filename)
        return (5 + penalty, filename)

    # Sort by priority (lower number = higher priority)
    prioritized = sorted(checksum_files, key=get_priority)

    logger.debug("   📋 Final priority order:")
    for i, cf in enumerate(prioritized, 1):
        logger.debug("      %d. %s", i, cf.filename)

    return prioritized
