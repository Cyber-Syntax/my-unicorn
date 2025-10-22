"""Simplified verification service for AppImage integrity checking.

This module provides the main VerificationService that handles file
verification using digest and checksum file methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    SUPPORTED_HASH_ALGORITHMS,
    YAML_DEFAULT_HASH,
    HashType,
)
from my_unicorn.download import DownloadService
from my_unicorn.github_client import (
    Asset,
    AssetSelector,
    ChecksumFileInfo,
)
from my_unicorn.logger import get_logger
from my_unicorn.services.progress import ProgressService
from my_unicorn.verification.verifier import Verifier

logger = get_logger(__name__, enable_file_logging=True)


@dataclass(slots=True, frozen=True)
class VerificationConfig:
    """Verification configuration data."""

    skip: bool = False
    checksum_file: str | None = None
    checksum_hash_type: str = "sha256"
    digest_enabled: bool = False


@dataclass(slots=True, frozen=True)
class VerificationResult:
    """Result of verification attempt."""

    passed: bool
    methods: dict[str, Any]
    updated_config: dict[str, Any]


class VerificationService:
    """Service for file verification with multiple methods."""

    def __init__(
        self,
        download_service: DownloadService,
        progress_service: ProgressService | None = None,
    ) -> None:
        """Initialize verification service.

        Args:
            download_service: Service for downloading checksum files
            progress_service: Optional progress service for tracking

        """
        self.download_service = download_service
        self.progress_service = progress_service

    async def verify_file(
        self,
        file_path: Path,
        asset: Asset,
        config: dict[str, Any],
        owner: str,
        repo: str,
        tag_name: str,
        app_name: str,
        assets: list[dict[str, Any]] | None = None,
        progress_task_id: Any | None = None,
    ) -> VerificationResult:
        """Perform comprehensive file verification.

        Args:
            file_path: Path to file to verify
            asset: GitHub asset information
            config: Verification configuration
            owner: Repository owner
            repo: Repository name
            tag_name: Release tag name
            app_name: Application name for logging
            assets: All GitHub release assets (enables auto-detection)
            progress_task_id: Optional progress task ID for tracking

        Returns:
            VerificationResult with success status and methods used

        Raises:
            Exception: If verification fails and strong methods available

        """
        logger.debug("🔍 Starting verification for %s", app_name)
        logger.debug(
            "   📋 Configuration: skip=%s, checksum_file='%s', "
            "digest_enabled=%s",
            config.get("skip", False),
            config.get("checksum_file", ""),
            config.get("digest", False),
        )
        logger.debug("   📦 Asset digest: %s", asset.digest or "None")
        logger.debug(
            "   📂 Assets provided: %s (%d items)",
            bool(assets),
            len(assets) if assets else 0,
        )

        # Create progress task if needed
        create_own_task = False
        if (
            self.progress_service
            and progress_task_id is None
            and self.progress_service.is_active()
        ):
            progress_task_id = (
                await self.progress_service.create_verification_task(app_name)
            )
            create_own_task = True

        # Update progress - starting verification
        if progress_task_id and self.progress_service:
            await self.progress_service.update_task(
                progress_task_id,
                completed=10.0,
                description=f"🔍 Analyzing {app_name}...",
            )

        # Detect available methods
        has_digest, checksum_files = self._detect_available_methods(
            asset, config, assets, owner, repo, tag_name
        )
        has_checksum_files = bool(checksum_files)

        logger.debug(
            "   Available methods: digest=%s, checksum_files=%d",
            has_digest,
            len(checksum_files),
        )

        # Check if verification should be skipped
        should_skip, updated_config = self._should_skip_verification(
            config, has_digest, has_checksum_files
        )
        if should_skip:
            if progress_task_id and self.progress_service and create_own_task:
                await self.progress_service.finish_task(
                    progress_task_id,
                    success=True,
                    final_description=f"✅ {app_name} verification skipped",
                )
            return VerificationResult(
                passed=True,
                methods={},
                updated_config=updated_config,
            )

        verifier = Verifier(file_path)
        verification_passed = False
        verification_methods = {}
        skip_configured = config.get("skip", False)

        # Update progress - creating verifier
        if progress_task_id and self.progress_service:
            await self.progress_service.update_task(
                progress_task_id,
                completed=25.0,
                description=f"🔍 Reading {app_name}...",
            )

        # Try digest verification first if available
        if has_digest:
            logger.debug("🔐 Digest verification available - attempting...")
            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=40.0,
                    description=f"🔍 Verifying digest for {app_name}...",
                )

            digest_result = await self._verify_digest(
                verifier, asset.digest, app_name, skip_configured
            )
            if digest_result:
                verification_methods["digest"] = digest_result
                if digest_result["passed"]:
                    verification_passed = True
                    logger.debug("✅ Digest verification succeeded")
                    updated_config["digest"] = True
                else:
                    logger.warning("❌ Digest verification failed")
        else:
            logger.debug("i  No digest available for verification")

        # Try checksum file verification with smart prioritization
        if checksum_files:
            logger.debug(
                "🔍 Checksum file verification available - found %d files",
                len(checksum_files),
            )
            for cf in checksum_files:
                logger.debug(
                    "   📄 Available: %s (%s format)",
                    cf.filename,
                    cf.format_type,
                )

            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=60.0,
                    description=f"🔍 Verifying checksum for {app_name}...",
                )

            # Use original asset name for checksum lookups
            original_asset_name = asset.name if asset.name else file_path.name
            logger.debug(
                "🔍 Using original asset name for checksum verification: %s",
                original_asset_name,
            )

            # Prioritize checksum files
            prioritized_files = self._prioritize_checksum_files(
                checksum_files, original_asset_name
            )

            for i, checksum_file in enumerate(prioritized_files):
                logger.debug(
                    "🔍 Attempting checksum verification with: %s",
                    checksum_file.filename,
                )
                method_key = f"checksum_file_{i}" if i > 0 else "checksum_file"

                checksum_result = await self._verify_checksum_file(
                    verifier, checksum_file, original_asset_name, app_name
                )

                if checksum_result:
                    verification_methods[method_key] = checksum_result
                    if checksum_result["passed"]:
                        verification_passed = True
                        logger.debug(
                            "✅ Checksum verification succeeded with: %s",
                            checksum_file.filename,
                        )
                        updated_config["checksum_file"] = (
                            checksum_file.filename
                        )
                        break
                    else:
                        logger.warning(
                            "❌ Checksum verification failed with: %s",
                            checksum_file.filename,
                        )
        else:
            logger.debug("i  No checksum files available for verification")

        # Determine overall verification result
        strong_methods_available = has_digest or has_checksum_files

        # If strong methods available but none passed, fail
        if strong_methods_available and not verification_passed:
            if progress_task_id and self.progress_service and create_own_task:
                await self.progress_service.finish_task(
                    progress_task_id,
                    success=False,
                    final_description=f"❌ {app_name} verification failed",
                )
            available_methods = []
            if has_digest:
                available_methods.append("digest")
            if has_checksum_files:
                available_methods.append("checksum_files")
            raise Exception(
                f"Available verification methods failed: "
                f"{', '.join(available_methods)}"
            )

        overall_passed = verification_passed

        # Log final verification summary
        logger.debug("📊 Verification summary for %s:", app_name)
        logger.debug(
            "   🔐 Strong methods available: %s", strong_methods_available
        )
        logger.debug("   ✅ Verification passed: %s", overall_passed)
        logger.debug(
            "   📋 Methods used: %s", list(verification_methods.keys())
        )
        for method, result in verification_methods.items():
            logger.debug(
                "      %s: %s",
                method,
                "✅ PASS" if result.get("passed") else "❌ FAIL",
            )

        # Update progress - verification completed
        if progress_task_id and self.progress_service and create_own_task:
            if overall_passed:
                await self.progress_service.finish_task(
                    progress_task_id,
                    success=True,
                    final_description=f"✅ {app_name} verification",
                )
            else:
                await self.progress_service.finish_task(
                    progress_task_id,
                    success=False,
                    final_description=(
                        f"⚠️ {app_name} verification completed with warnings"
                    ),
                )

        if overall_passed:
            logger.debug("✅ Verification completed successfully")
        else:
            logger.warning("⚠️  Verification completed with warnings")

        return VerificationResult(
            passed=overall_passed,
            methods=verification_methods,
            updated_config=updated_config,
        )

    def _detect_available_methods(
        self,
        asset: Asset,
        config: dict[str, Any],
        assets: list[dict[str, Any]] | None = None,
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
        digest_value = asset.digest or ""
        has_digest = bool(digest_value and digest_value.strip())
        digest_requested = config.get("digest", False)

        # Log digest availability vs configuration
        if digest_requested and not has_digest:
            logger.warning(
                "⚠️  Digest verification requested but no digest available "
                "from GitHub API"
            )
            logger.debug(
                "   📦 Asset digest field: '%s'", digest_value or "None"
            )
        elif has_digest:
            logger.debug(
                "✅ Digest available for verification: %s",
                digest_value[:16] + "...",
            )

        # Check for manually configured checksum file
        manual_checksum_file = config.get("checksum_file")
        checksum_files = []

        if manual_checksum_file and manual_checksum_file.strip():
            # Use manually configured checksum file
            if owner and repo and tag_name:
                url = self._build_checksum_url(
                    owner, repo, tag_name, manual_checksum_file
                )
                format_type = (
                    "yaml"
                    if manual_checksum_file.lower().endswith((".yml", ".yaml"))
                    else "traditional"
                )
                checksum_files.append(
                    ChecksumFileInfo(
                        filename=manual_checksum_file,
                        url=url,
                        format_type=format_type,
                    )
                )
        elif (
            assets
            and owner
            and repo
            and tag_name
            and not config.get("digest", False)
        ):
            # Auto-detect checksum files if digest not explicitly enabled
            logger.debug(
                "🔍 Auto-detecting checksum files "
                "(digest not explicitly enabled)"
            )
            try:
                # Convert assets to Asset objects
                asset_objects: list[Asset] = []
                for asset_data in assets:
                    asset_obj = Asset.from_api_response(asset_data)
                    if asset_obj:
                        asset_objects.append(asset_obj)

                # Use AssetSelector to detect checksum files
                checksum_files = AssetSelector.detect_checksum_files(
                    asset_objects, tag_name
                )
                logger.debug(
                    "🔍 Auto-detected %d checksum files from assets",
                    len(checksum_files),
                )
            except Exception as e:
                logger.warning("Failed to auto-detect checksum files: %s", e)
        elif assets and config.get("digest", False):
            logger.debug(
                "i  Skipping auto-detection: "
                "digest verification explicitly enabled"
            )

        return has_digest, checksum_files

    def _build_checksum_url(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        checksum_file: str,
    ) -> str:
        """Build URL for checksum file download.

        Args:
            owner: Repository owner
            repo: Repository name
            tag_name: Release tag name
            checksum_file: Checksum filename

        Returns:
            Complete checksum file URL

        """
        return (
            f"https://github.com/{owner}/{repo}/releases/download/"
            f"{tag_name}/{checksum_file}"
        )

    def _should_skip_verification(
        self,
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
        elif catalog_skip and (has_digest or has_checksum_files):
            logger.debug(
                "🔄 Overriding skip setting - "
                "strong verification methods available"
            )
            # Update config to reflect that we're now using verification
            updated_config["skip"] = False

        return False, updated_config

    def _prioritize_checksum_files(
        self,
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
            if any(
                variant in lower_filename for variant in experimental_variants
            ):
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

    async def _verify_digest(
        self,
        verifier: Verifier,
        digest: str,
        app_name: str,
        skip_configured: bool,
    ) -> dict[str, Any] | None:
        """Verify file using GitHub API digest.

        Args:
            verifier: Verifier instance
            digest: Expected digest hash
            app_name: Application name for logging
            skip_configured: Whether skip was configured

        Returns:
            Verification result dict or None if failed

        """
        try:
            logger.debug("🔐 Attempting digest verification (from GitHub API)")
            logger.debug("   📄 AppImage file: %s", verifier.file_path.name)
            logger.debug("   🔢 Expected digest: %s", digest)
            if skip_configured:
                logger.debug("   Note: Using digest despite skip=true setting")

            # Get actual file hash to compare
            actual_digest = verifier.compute_hash("sha256")
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
        except Exception as e:
            logger.error("❌ Digest verification failed: %s", e)
            logger.error("   Expected: %s", digest)
            logger.error("   AppImage: %s", verifier.file_path.name)
            return {
                "passed": False,
                "hash": digest,
                "details": str(e),
            }

    async def _verify_checksum_file(
        self,
        verifier: Verifier,
        checksum_file: ChecksumFileInfo,
        target_filename: str,
        app_name: str,
    ) -> dict[str, Any] | None:
        """Verify file using checksum file.

        Args:
            verifier: Verifier instance
            checksum_file: Checksum file information
            target_filename: Target filename to look for
            app_name: Application name for logging

        Returns:
            Verification result dict or None if failed

        """
        try:
            logger.debug(
                "🔍 Verifying using checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )

            # Download checksum file content
            content = await self.download_service.download_checksum_file(
                checksum_file.url
            )

            # Determine hash type
            if checksum_file.format_type == "yaml":
                hash_type: HashType = YAML_DEFAULT_HASH
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
                logger.error(
                    "❌ Checksum file verification FAILED - hash not found!"
                )
                logger.error(
                    "   📄 Checksum file: %s (%s format)",
                    checksum_file.filename,
                    checksum_file.format_type,
                )
                logger.error("   🔍 Looking for: %s", target_filename)
                return {
                    "passed": False,
                    "hash": "",
                    "details": (
                        f"Hash not found for {target_filename} "
                        f"in checksum file"
                    ),
                }

            logger.debug(
                "🔍 Starting hash comparison for checksum file verification"
            )
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
                "   🔄 Hash comparison: %s == %s → %s",
                computed_hash.lower()[:32] + "...",
                expected_hash.lower()[:32] + "...",
                "MATCH" if hashes_match else "MISMATCH",
            )

            if hashes_match:
                logger.debug(
                    "✅ Checksum file verification PASSED! (%s)",
                    hash_type.upper(),
                )
                logger.debug(
                    "   📄 Checksum file: %s (%s format)",
                    checksum_file.filename,
                    checksum_file.format_type,
                )
                logger.debug("   ✓ Hash match confirmed")
                return {
                    "passed": True,
                    "hash": f"{hash_type}:{computed_hash}",
                    "details": (
                        f"Verified against {checksum_file.format_type} "
                        f"checksum file"
                    ),
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

        except Exception as e:
            logger.error("❌ Checksum file verification failed: %s", e)
            return {
                "passed": False,
                "hash": "",
                "details": str(e),
            }
