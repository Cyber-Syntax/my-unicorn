"""Simplified verification service for AppImage integrity checking.

This module provides the main VerificationService that handles file
verification using digest and checksum file methods.

Logging Strategy:
- logger.debug(): Developer debugging (method details, hashes, etc.)
- logger.info(): User-facing verification milestones (for log files)
- logger.warning(): Issues users should know about
- Progress display uses finish_task() only - intermediate percentage updates
  are not shown in the simplified KISS-compliant progress display.
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
from my_unicorn.progress import ProgressDisplay
from my_unicorn.verification.verifier import Verifier

logger = get_logger(__name__, enable_file_logging=True)


@dataclass(slots=True, frozen=True)
class VerificationConfig:
    """Verification configuration data."""

    skip: bool = False
    checksum_file: str | None = None
    checksum_hash_type: str = "sha256"
    digest_enabled: bool = False

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> VerificationConfig:
        """Create VerificationConfig from a dictionary.

        Args:
            config: Dictionary with configuration values

        Returns:
            VerificationConfig instance

        """
        return cls(
            skip=config.get("skip", False),
            checksum_file=config.get("checksum_file"),
            checksum_hash_type=config.get("checksum_hash_type", "sha256"),
            digest_enabled=config.get("digest", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary with configuration values

        """
        return {
            "skip": self.skip,
            "checksum_file": self.checksum_file,
            "checksum_hash_type": self.checksum_hash_type,
            "digest": self.digest_enabled,
        }


@dataclass(slots=True, frozen=True)
class MethodResult:
    """Result of a single verification method attempt."""

    passed: bool
    hash: str
    details: str
    computed_hash: str | None = None
    url: str | None = None
    hash_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility.

        Returns:
            Dictionary representation

        """
        result: dict[str, Any] = {
            "passed": self.passed,
            "hash": self.hash,
            "details": self.details,
        }
        if self.computed_hash:
            result["computed_hash"] = self.computed_hash
        if self.url:
            result["url"] = self.url
        if self.hash_type:
            result["hash_type"] = self.hash_type
        return result


@dataclass(slots=True, frozen=True)
class VerificationResult:
    """Result of verification attempt."""

    passed: bool
    methods: dict[str, Any]
    updated_config: dict[str, Any]
    warning: str | None = None  # Warning message if applicable


@dataclass(slots=True)
class VerificationContext:
    """Internal context for verification state management.

    Holds mutable state during verification process to reduce
    parameter passing.
    """

    file_path: Path
    asset: Asset
    config: dict[str, Any]
    owner: str
    repo: str
    tag_name: str
    app_name: str
    assets: list[Asset] | None
    progress_task_id: Any | None
    # Computed during preparation
    has_digest: bool = False
    checksum_files: list[ChecksumFileInfo] | None = None
    verifier: Verifier | None = None
    updated_config: dict[str, Any] | None = None
    # Results
    verification_passed: bool = False
    verification_methods: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize mutable state after dataclass creation."""
        if self.verification_methods is None:
            self.verification_methods = {}
        if self.updated_config is None:
            self.updated_config = self.config.copy()


class VerificationService:
    """Service for file verification with multiple methods."""

    def __init__(
        self,
        download_service: DownloadService,
        progress_service: ProgressDisplay | None = None,
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
        assets: list[Asset] | None = None,
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
        # Create context for verification state
        context = VerificationContext(
            file_path=file_path,
            asset=asset,
            config=config,
            owner=owner,
            repo=repo,
            tag_name=tag_name,
            app_name=app_name,
            assets=assets,
            progress_task_id=progress_task_id,
        )

        # Phase 1: Prepare verification
        skip_result = await self._prepare_verification(context)
        if skip_result:
            return skip_result

        # Phase 2: Execute verification methods
        await self._execute_verification(context)

        # Phase 3: Finalize and return result
        return await self._finalize_verification(context)

    async def _prepare_verification(
        self, context: VerificationContext
    ) -> VerificationResult | None:
        """Prepare verification: detect methods, check skip conditions.

        Args:
            context: Verification context

        Returns:
            VerificationResult if should skip, None otherwise

        """
        logger.debug("🔍 Starting verification for %s", context.app_name)
        logger.debug(
            "   📋 Configuration: skip=%s, checksum_file='%s', "
            "digest_enabled=%s",
            context.config.get("skip", False),
            context.config.get("checksum_file", ""),
            context.config.get("digest", False),
        )
        logger.debug("   📦 Asset digest: %s", context.asset.digest or "None")
        logger.debug(
            "   📂 Assets provided: %s (%d items)",
            bool(context.assets),
            len(context.assets) if context.assets else 0,
        )

        # Create progress task if needed
        if (
            self.progress_service
            and context.progress_task_id is None
            and self.progress_service.is_active()
        ):
            context.progress_task_id = (
                await self.progress_service.create_verification_task(
                    context.app_name
                )
            )

        # Detect available methods
        context.has_digest, context.checksum_files = (
            self._detect_available_methods(
                context.asset,
                context.config,
                context.assets,
                context.owner,
                context.repo,
                context.tag_name,
            )
        )
        has_checksum_files = bool(context.checksum_files)

        logger.debug(
            "   Available methods: digest=%s, checksum_files=%d",
            context.has_digest,
            len(context.checksum_files) if context.checksum_files else 0,
        )
        logger.info(
            "Verifying %s: digest=%s, checksum_files=%d",
            context.app_name,
            context.has_digest,
            len(context.checksum_files) if context.checksum_files else 0,
        )

        # Check if verification should be skipped
        should_skip, context.updated_config = self._should_skip_verification(
            context.config, context.has_digest, has_checksum_files
        )
        if should_skip:
            await self._finish_progress(
                context.progress_task_id, True, "verification skipped"
            )
            return VerificationResult(
                passed=True,
                methods={},
                updated_config=context.updated_config,
            )

        # Create verifier
        context.verifier = Verifier(context.file_path)

        return None

    async def _execute_verification(
        self, context: VerificationContext
    ) -> None:
        """Execute verification methods: digest and checksum files.

        Args:
            context: Verification context (modified in place)

        """
        skip_configured = context.config.get("skip", False)

        # Try digest verification first if available
        if context.has_digest:
            await self._execute_digest_verification(context, skip_configured)

        # Try checksum file verification
        if context.checksum_files:
            await self._execute_checksum_verification(context)

    async def _execute_digest_verification(
        self, context: VerificationContext, skip_configured: bool
    ) -> None:
        """Execute digest verification.

        Args:
            context: Verification context (modified in place)
            skip_configured: Whether skip was configured

        """
        logger.debug("🔐 Digest verification available - attempting...")

        digest_result = await self._verify_digest(
            context.verifier,
            context.asset.digest,
            context.app_name,
            skip_configured,
        )
        if digest_result:
            context.verification_methods["digest"] = digest_result.to_dict()
            if digest_result.passed:
                context.verification_passed = True
                logger.debug("✅ Digest verification succeeded")
                logger.info(
                    "Digest verification passed for %s", context.app_name
                )
                context.updated_config["digest"] = True
            else:
                logger.warning("❌ Digest verification failed")
                logger.info(
                    "Digest verification failed for %s", context.app_name
                )
        else:
            logger.debug("i  No digest available for verification")

    async def _execute_checksum_verification(
        self, context: VerificationContext
    ) -> None:
        """Execute checksum file verification.

        Args:
            context: Verification context (modified in place)

        """
        logger.debug(
            "🔍 Checksum file verification available - found %d files",
            len(context.checksum_files),
        )
        for cf in context.checksum_files:
            logger.debug(
                "   📄 Available: %s (%s format)",
                cf.filename,
                cf.format_type,
            )

        # Use original asset name for checksum lookups
        original_asset_name = (
            context.asset.name
            if context.asset.name
            else context.file_path.name
        )
        logger.debug(
            "🔍 Using original asset name for checksum verification: %s",
            original_asset_name,
        )

        # Prioritize checksum files
        prioritized_files = self._prioritize_checksum_files(
            context.checksum_files, original_asset_name
        )

        for i, checksum_file in enumerate(prioritized_files):
            logger.debug(
                "🔍 Attempting checksum verification with: %s",
                checksum_file.filename,
            )
            method_key = f"checksum_file_{i}" if i > 0 else "checksum_file"

            checksum_result = await self._verify_checksum_file(
                context.verifier,
                checksum_file,
                original_asset_name,
                context.app_name,
            )

            if checksum_result:
                context.verification_methods[method_key] = (
                    checksum_result.to_dict()
                )
                if checksum_result.passed:
                    context.verification_passed = True
                    logger.debug(
                        "✅ Checksum verification succeeded with: %s",
                        checksum_file.filename,
                    )
                    logger.info(
                        "Checksum verification passed for %s using %s",
                        context.app_name,
                        checksum_file.filename,
                    )
                    context.updated_config["checksum_file"] = (
                        checksum_file.filename
                    )
                    break
                logger.warning(
                    "❌ Checksum verification failed with: %s",
                    checksum_file.filename,
                )

    async def _finalize_verification(
        self, context: VerificationContext
    ) -> VerificationResult:
        """Finalize verification: check results, update progress.

        Args:
            context: Verification context

        Returns:
            VerificationResult with final status

        Raises:
            Exception: If strong methods available but none passed

        """
        has_checksum_files = bool(context.checksum_files)
        strong_methods_available = context.has_digest or has_checksum_files

        # If strong methods available but none passed, fail
        if strong_methods_available and not context.verification_passed:
            await self._finish_progress(
                context.progress_task_id, False, "verification failed"
            )
            available_methods = []
            if context.has_digest:
                available_methods.append("digest")
            if has_checksum_files:
                available_methods.append("checksum_files")
            raise Exception(
                f"Available verification methods failed: "
                f"{', '.join(available_methods)}"
            )

        # Determine overall result
        # If no verification methods available, allow installation with warning
        if not strong_methods_available:
            overall_passed = True  # Allow installation to proceed
            # Log for debugging only (not shown in terminal during progress)
            logger.debug(
                "No verification methods available for %s - "
                "developer did not provide checksums or digest. "
                "Installation will proceed without verification. "
                "Security risk: File integrity cannot be verified.",
                context.app_name,
            )
        else:
            overall_passed = context.verification_passed

        # Log final verification summary
        self._log_verification_summary(
            context, strong_methods_available, overall_passed
        )

        # Update progress with appropriate message and status
        warning_message = None
        if overall_passed and strong_methods_available:
            await self._finish_progress(
                context.progress_task_id, True, "verification passed"
            )
            logger.debug("✅ Verification completed successfully")
            logger.info(
                "Verification completed for %s: passed",
                context.app_name,
            )
        elif overall_passed and not strong_methods_available:
            # Mark as finished with warning message
            warning_message = (
                "Not verified - developer did not provide checksums"
            )
            await self._finish_progress(
                context.progress_task_id,
                True,
                "not verified (dev did not provide checksums)",
            )
            logger.info(
                "Verification completed for %s: "
                "skipped (no checksums provided)",
                context.app_name,
            )
        else:
            await self._finish_progress(
                context.progress_task_id,
                False,
                "verification completed with warnings",
            )
            logger.warning("⚠️  Verification completed with warnings")
            logger.info(
                "Verification completed for %s: failed",
                context.app_name,
            )

        return VerificationResult(
            passed=overall_passed,
            methods=context.verification_methods or {},
            updated_config=context.updated_config or context.config,
            warning=warning_message,
        )

    def _log_verification_summary(
        self,
        context: VerificationContext,
        strong_methods_available: bool,
        overall_passed: bool,
    ) -> None:
        """Log verification summary for debugging.

        Args:
            context: Verification context
            strong_methods_available: Whether strong methods were available
            overall_passed: Overall verification result

        """
        logger.debug("📊 Verification summary for %s:", context.app_name)
        logger.debug(
            "   🔐 Strong methods available: %s", strong_methods_available
        )
        logger.debug("   ✅ Verification passed: %s", overall_passed)
        methods = context.verification_methods or {}
        logger.debug("   📋 Methods used: %s", list(methods.keys()))
        for method, result in methods.items():
            logger.debug(
                "      %s: %s",
                method,
                "✅ PASS" if result.get("passed") else "❌ FAIL",
            )

    async def _finish_progress(
        self,
        task_id: Any | None,
        success: bool,
        description: str,
    ) -> None:
        """Finish progress task if available.

        Args:
            task_id: Progress task ID (may be None)
            success: Whether task succeeded
            description: Final status description

        """
        if task_id and self.progress_service:
            await self.progress_service.finish_task(
                task_id,
                success=success,
                description=description,
            )

    def _detect_available_methods(
        self,
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
        has_digest = self._check_digest_availability(asset, config)
        checksum_files = self._resolve_checksum_files(
            asset, config, assets, owner, repo, tag_name
        )
        return has_digest, checksum_files

    def _check_digest_availability(
        self, asset: Asset, config: dict[str, Any]
    ) -> bool:
        """Check if digest verification is available.

        Args:
            asset: GitHub asset information
            config: Verification configuration

        Returns:
            True if digest is available

        """
        digest_value = asset.digest or ""
        has_digest = bool(digest_value and digest_value.strip())
        digest_requested = config.get("digest", False)

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

        return has_digest

    def _resolve_checksum_files(
        self,
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
        if manual_checksum_file and manual_checksum_file.strip():
            return self._resolve_manual_checksum_file(
                manual_checksum_file, asset, owner, repo, tag_name
            )

        # Auto-detect if conditions are met
        if (
            assets
            and owner
            and repo
            and tag_name
            and not config.get("digest", False)
        ):
            return self._auto_detect_checksum_files(assets, tag_name)

        if assets and config.get("digest", False):
            logger.debug(
                "i  Skipping auto-detection: "
                "digest verification explicitly enabled"
            )

        return []

    def _resolve_manual_checksum_file(
        self,
        manual_checksum_file: str,
        asset: Asset,
        owner: str | None,
        repo: str | None,
        tag_name: str | None,
    ) -> list[ChecksumFileInfo]:
        """Resolve manually configured checksum file with template support.

        Args:
            manual_checksum_file: Configured checksum filename
                (may have templates)
            asset: GitHub asset information
            owner: Repository owner
            repo: Repository name
            tag_name: Release tag name

        Returns:
            List with single checksum file info, or empty list

        """
        resolved_name = manual_checksum_file
        try:
            if "{" in manual_checksum_file and tag_name:
                resolved_name = manual_checksum_file.replace(
                    "{version}", tag_name
                ).replace("{tag}", tag_name)
            if (
                "{asset_name}" in resolved_name
                and asset
                and hasattr(asset, "name")
            ):
                resolved_name = resolved_name.replace(
                    "{asset_name}", asset.name
                )
        except Exception:
            resolved_name = manual_checksum_file

        if not (owner and repo and tag_name):
            return []

        url = self._build_checksum_url(owner, repo, tag_name, resolved_name)
        format_type = (
            "yaml"
            if resolved_name.lower().endswith((".yml", ".yaml"))
            else "traditional"
        )
        return [
            ChecksumFileInfo(
                filename=resolved_name,
                url=url,
                format_type=format_type,
            )
        ]

    def _auto_detect_checksum_files(
        self, assets: list[Asset], tag_name: str
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
            checksum_files = AssetSelector.detect_checksum_files(
                assets, tag_name
            )
            logger.debug(
                "🔍 Auto-detected %d checksum files from assets",
                len(checksum_files),
            )
            return checksum_files
        except Exception as e:
            logger.warning("Failed to auto-detect checksum files: %s", e)
            return []

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
        if catalog_skip and (has_digest or has_checksum_files):
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
            return MethodResult(
                passed=True,
                hash=digest,
                computed_hash=actual_digest,
                details="GitHub API digest verification",
            )
        except Exception as e:
            logger.error("❌ Digest verification failed: %s", e)
            logger.error("   Expected: %s", digest)
            logger.error("   AppImage: %s", verifier.file_path.name)
            return MethodResult(
                passed=False,
                hash=digest,
                details=str(e),
            )

    async def _verify_checksum_file(
        self,
        verifier: Verifier,
        checksum_file: ChecksumFileInfo,
        target_filename: str,
        app_name: str,
    ) -> MethodResult | None:
        """Verify file using checksum file.

        Args:
            verifier: Verifier instance
            checksum_file: Checksum file information
            target_filename: Target filename to look for
            app_name: Application name for logging

        Returns:
            MethodResult or None if failed

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
                return MethodResult(
                    passed=False,
                    hash="",
                    details=(
                        f"Hash not found for {target_filename} "
                        f"in checksum file"
                    ),
                )

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
                return MethodResult(
                    passed=True,
                    hash=f"{hash_type}:{computed_hash}",
                    details=(
                        f"Verified against {checksum_file.format_type} "
                        f"checksum file"
                    ),
                    url=checksum_file.url,
                    hash_type=hash_type,
                )
            logger.error("❌ Checksum file verification FAILED!")
            logger.error(
                "   📄 Checksum file: %s (%s format)",
                checksum_file.filename,
                checksum_file.format_type,
            )
            logger.error("   🔢 Expected hash: %s", expected_hash)
            logger.error("   🧮 Computed hash: %s", computed_hash)
            logger.error("   ❌ Hash mismatch detected")
            return MethodResult(
                passed=False,
                hash=f"{hash_type}:{computed_hash}",
                details=f"Hash mismatch (expected: {expected_hash})",
            )

        except Exception as e:
            logger.error("❌ Checksum file verification failed: %s", e)
            return MethodResult(
                passed=False,
                hash="",
                details=str(e),
            )
