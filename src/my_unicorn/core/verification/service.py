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

import asyncio
from typing import TYPE_CHECKING, Any

from my_unicorn.constants import VerificationMethod
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)
from my_unicorn.core.verification.context import VerificationContext
from my_unicorn.core.verification.detection import (
    detect_available_methods,
    should_skip_verification,
)
from my_unicorn.core.verification.execution import (
    execute_all_verification_methods,
)
from my_unicorn.core.verification.results import VerificationResult
from my_unicorn.core.verification.verifier import Verifier
from my_unicorn.exceptions import VerificationError
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from my_unicorn.core.cache import ReleaseCacheManager
    from my_unicorn.core.download import DownloadService
    from my_unicorn.core.github import Asset

logger = get_logger(__name__, enable_file_logging=True)


class VerificationService:
    """Service for file verification with multiple methods."""

    def __init__(
        self,
        download_service: DownloadService,
        progress_reporter: ProgressReporter | None = None,
        cache_manager: ReleaseCacheManager | None = None,
    ) -> None:
        """Initialize verification service.

        Args:
            download_service: Service for downloading checksum files
            progress_reporter: Optional progress reporter for tracking
            cache_manager: Optional cache manager for storing checksum files

        """
        self.download_service = download_service
        self.progress_reporter = progress_reporter or NullProgressReporter()
        self.cache_manager = cache_manager

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
            VerificationError: If all available verification methods fail

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
        await execute_all_verification_methods(
            context, self.download_service, self.cache_manager
        )

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
        logger.debug(
            "Starting verification: app=%s, skip=%s, checksum_file=%s, digest=%s",
            context.app_name,
            context.config.get("skip", False),
            context.config.get("checksum_file", ""),
            context.config.get(VerificationMethod.DIGEST, False),
        )
        logger.debug("Asset digest: %s", context.asset.digest or "None")
        logger.debug(
            "Assets provided: %s (%d items)",
            bool(context.assets),
            len(context.assets) if context.assets else 0,
        )

        # Create progress task if needed
        is_active = self.progress_reporter.is_active()
        if context.progress_task_id is None and is_active:
            task_id = self.progress_reporter.add_task(
                f"Verifying {context.app_name}",
                ProgressType.VERIFICATION,
            )
            # Handle both sync and async add_task
            if asyncio.iscoroutine(task_id):
                context.progress_task_id = await task_id
            else:
                context.progress_task_id = task_id

        # Detect available methods
        context.has_digest, context.checksum_files = detect_available_methods(
            context.asset,
            context.config,
            context.assets,
            context.owner,
            context.repo,
            context.tag_name,
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
        should_skip, context.updated_config = should_skip_verification(
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

    async def _finalize_verification(
        self, context: VerificationContext
    ) -> VerificationResult:
        """Finalize verification: evaluate all results, determine overall status.

        This method evaluates all verification method results to determine
        the overall pass/fail status. It implements partial success logic
        where installation is allowed if at least one strong method passes,
        but warnings are generated if some methods fail.

        Args:
            context: Verification context

        Returns:
            VerificationResult with final status and optional warning

        Raises:
            VerificationError: If strong methods are available but all fail

        """
        has_checksum_files = bool(context.checksum_files)
        strong_methods_available = context.has_digest or has_checksum_files

        # Collect passed and failed methods
        passed_methods = []
        failed_methods = []

        for method_key, method_result in (
            context.verification_methods or {}
        ).items():
            if method_result.get("passed"):
                passed_methods.append(method_key)
            else:
                failed_methods.append(method_key)

        # Determine overall verification status
        has_passing_method = len(passed_methods) > 0

        # Log method results
        logger.debug(
            "Verification methods summary: passed=%d, failed=%d",
            len(passed_methods),
            len(failed_methods),
        )
        if passed_methods:
            logger.debug("Passed methods: %s", ", ".join(passed_methods))
        if failed_methods:
            logger.debug("Failed methods: %s", ", ".join(failed_methods))

        # Determine overall result and warning message
        warning_message = None
        overall_passed = not strong_methods_available or has_passing_method

        if not strong_methods_available:
            # No verification methods available - allow with warning
            warning_message = (
                "Not verified - developer did not provide checksums"
            )
            logger.debug(
                "No verification methods available for %s - "
                "developer did not provide checksums or digest. "
                "Installation will proceed without verification. "
                "Security risk: File integrity cannot be verified.",
                context.app_name,
            )
        elif has_passing_method and failed_methods:
            # Partial success - some passed, some failed
            warning_message = (
                f"Partial verification: {len(passed_methods)} passed, "
                f"{len(failed_methods)} failed"
            )
            logger.warning(
                "Partial verification success for %s: %s passed, %s failed",
                context.app_name,
                ", ".join(passed_methods),
                ", ".join(failed_methods),
            )
        elif not has_passing_method and strong_methods_available:
            # All methods failed - this is a security failure, raise exception
            warning_message = "All verification methods failed"
            logger.error(
                "All verification methods failed for %s", context.app_name
            )

            # Finish progress before raising
            await self._finish_progress(
                context.progress_task_id,
                success=False,
                description="verification failed",
            )

            # Raise VerificationError with context for callers
            msg = f"All verification methods failed for {context.app_name}"
            raise VerificationError(
                msg,
                context={
                    "app_name": context.app_name,
                    "file_path": str(context.file_path),
                    "available_methods": list(
                        context.verification_methods.keys()
                    )
                    if context.verification_methods
                    else [],
                    "failed_methods": failed_methods,
                },
            )

        # Set context.verification_passed for backward compatibility
        context.verification_passed = has_passing_method
        context.verification_warning = warning_message

        # Log final verification summary
        self._log_verification_summary(
            context, strong_methods_available, overall_passed
        )

        # Update progress with appropriate message and status
        if overall_passed and strong_methods_available and not warning_message:
            # Complete success - all methods passed
            await self._finish_progress(
                context.progress_task_id, True, "verification passed"
            )
            logger.debug(
                "Verification completed: app=%s, status=passed",
                context.app_name,
            )
            logger.info(
                "Verification completed for %s: passed", context.app_name
            )
        elif (
            overall_passed
            and strong_methods_available
            and warning_message
            and "Partial" in warning_message
        ):
            # Partial success - some passed, some failed
            await self._finish_progress(
                context.progress_task_id,
                True,
                "verification passed (with warnings)",
            )
            logger.info(
                "Verification completed for %s: passed with warnings",
                context.app_name,
            )
        elif overall_passed and not strong_methods_available:
            # No verification methods available
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
            # Should not reach here, but handle defensively
            await self._finish_progress(
                context.progress_task_id,
                False,
                "verification completed with warnings",
            )
            logger.warning(
                "Verification completed with warnings: app=%s",
                context.app_name,
            )
            logger.info(
                "Verification completed for %s: failed", context.app_name
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
        logger.debug("Verification summary: app=%s", context.app_name)
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
        if task_id:
            finish_coro = self.progress_reporter.finish_task(
                task_id,
                success=success,
                description=description,
            )
            # Handle both sync and async finish_task
            if asyncio.iscoroutine(finish_coro):
                await finish_coro
            # Otherwise it's None (sync finish_task returns None)
