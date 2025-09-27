"""Shared verification service to eliminate code duplication."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_unicorn.download import DownloadService
from my_unicorn.logger import get_logger
from my_unicorn.services.progress import ProgressService
from my_unicorn.verification import VerificationServiceFacade
from my_unicorn.verification.verify import Verifier

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


# TODO: Refactor to use strategy pattern for better design
class VerificationService:
    """Shared service for file verification with multiple methods using strategy pattern."""

    def __init__(
        self,
        download_service: DownloadService,
        progress_service: ProgressService | None = None,
    ) -> None:
        """Initialize verification service.

        Args:
            download_service: Service for downloading checksum files
            progress_service: Optional progress service for tracking verification

        """
        self.download_service = download_service
        self.progress_service = progress_service

        # Initialize the facade with strategy pattern implementation
        self.facade = VerificationServiceFacade(download_service, progress_service)

    async def verify_file(
        self,
        file_path: Path,
        asset: dict[str, Any],
        config: dict[str, Any],
        owner: str,
        repo: str,
        tag_name: str,
        app_name: str,
        assets: list[dict[str, Any]] | None = None,
        progress_task_id: Any | None = None,
    ) -> VerificationResult:
        """Perform comprehensive file verification using strategy pattern.

        Args:
            file_path: Path to file to verify
            asset: GitHub asset information
            config: Verification configuration
            owner: Repository owner
            repo: Repository name
            tag_name: Release tag name
            app_name: Application name for logging
            assets: All GitHub release assets (optional, enables auto-detection)
            progress_task_id: Optional progress task ID for tracking

        Returns:
            VerificationResult with success status and methods used

        Raises:
            Exception: If verification fails and strong methods were available

        """
        logger.debug("🔍 Starting verification for %s", app_name)
        logger.debug(
            "   📋 Configuration: skip=%s, checksum_file='%s', digest_enabled=%s",
            config.get("skip", False),
            config.get("checksum_file", ""),
            config.get("digest", False),
        )
        logger.debug("   📦 Asset digest: %s", asset.get("digest", "None"))
        logger.debug(
            "   📂 Assets provided: %s (%d items)", bool(assets), len(assets) if assets else 0
        )

        # Create progress task if progress service is available but no task ID provided
        create_own_task = False
        if (
            self.progress_service
            and progress_task_id is None
            and self.progress_service.is_active()
        ):
            progress_task_id = await self.progress_service.create_verification_task(app_name)
            create_own_task = True

        # Update progress - starting verification
        if progress_task_id and self.progress_service:
            await self.progress_service.update_task(
                progress_task_id, completed=10.0, description=f"🔍 Analyzing {app_name}..."
            )

        # Detect available methods using strategy pattern
        has_digest, checksum_files = self.facade.detection_service.detect_available_methods(
            asset, config, assets, owner, repo, tag_name
        )
        has_checksum_files = bool(checksum_files)

        logger.debug(
            "   Available methods: digest=%s, checksum_files=%d",
            has_digest,
            len(checksum_files),
        )

        # Check if verification should be skipped using facade
        should_skip, updated_config = self.facade.should_skip_verification(
            config, has_digest, has_checksum_files
        )
        if should_skip:
            # Update progress - skipped (only finish task if we created it)
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
                progress_task_id, completed=25.0, description=f"🔍 Reading {app_name}..."
            )

        # Get strategies from factory
        strategies = self.facade.factory.get_available_strategies()

        # Try digest verification first if available
        if has_digest:
            logger.debug("🔐 Digest verification available - attempting...")
            # Update progress - digest verification
            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=40.0,
                    description=f"🔍 Verifying digest for {app_name}...",
                )

            digest_strategy = strategies["digest"]
            context = {
                "app_name": app_name,
                "skip_configured": skip_configured,
            }

            digest_result = await digest_strategy.verify(verifier, asset["digest"], context)
            if digest_result:
                verification_methods["digest"] = digest_result
                if digest_result["passed"]:
                    verification_passed = True
                    logger.debug("✅ Digest verification succeeded")
                    # Enable digest verification in config for future use
                    updated_config["digest"] = True
                else:
                    logger.warning("❌ Digest verification failed")
        else:
            logger.debug("i  No digest available for verification")

        # Try checksum file verification with smart prioritization
        if checksum_files:
            logger.debug(
                "🔍 Checksum file verification available - found %d files", len(checksum_files)
            )
            for cf in checksum_files:
                logger.debug("   📄 Available: %s (%s format)", cf.filename, cf.format_type)

            # Update progress - checksum verification
            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=60.0,
                    description=f"🔍 Verifying checksum for {app_name}...",
                )

            # Use original asset name for checksum lookups (not the local renamed file)
            original_asset_name = asset.get("name", file_path.name)
            logger.debug(
                "🔍 Using original asset name for checksum verification: %s",
                original_asset_name,
            )

            # Prioritize checksum files using strategy pattern
            prioritized_files = self.facade.prioritization_service.prioritize_checksum_files(
                checksum_files, original_asset_name
            )

            checksum_strategy = strategies["checksum_file"]
            for i, checksum_file in enumerate(prioritized_files):
                logger.debug(
                    "🔍 Attempting checksum verification with: %s", checksum_file.filename
                )
                method_key = f"checksum_file_{i}" if i > 0 else "checksum_file"

                context = {
                    "target_filename": original_asset_name,
                    "app_name": app_name,
                }

                checksum_result = await checksum_strategy.verify(
                    verifier, checksum_file, context
                )

                if checksum_result:
                    verification_methods[method_key] = checksum_result
                    if checksum_result["passed"]:
                        verification_passed = True
                        logger.debug(
                            "✅ Checksum verification succeeded with: %s",
                            checksum_file.filename,
                        )
                        # Update config with successful checksum file
                        updated_config["checksum_file"] = checksum_file.filename
                        break  # Stop trying other checksum files once one succeeds
                    else:
                        logger.warning(
                            "❌ Checksum verification failed with: %s", checksum_file.filename
                        )
        else:
            logger.debug("i  No checksum files available for verification")

        # Determine overall verification result
        strong_methods_available = has_digest or has_checksum_files

        # If we have strong verification methods available but none passed, fail
        if strong_methods_available and not verification_passed:
            # Update progress - verification failed (only finish task if we created it)
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
                f"Available verification methods failed: {', '.join(available_methods)}"
            )

        # Success if any strong method passed
        overall_passed = verification_passed

        # Log final verification summary
        logger.debug("📊 Verification summary for %s:", app_name)
        logger.debug("   🔐 Strong methods available: %s", strong_methods_available)
        logger.debug("   ✅ Verification passed: %s", overall_passed)
        logger.debug("   📋 Methods used: %s", list(verification_methods.keys()))
        for method, result in verification_methods.items():
            logger.debug(
                "      %s: %s", method, "✅ PASS" if result.get("passed") else "❌ FAIL"
            )

        # Update progress - verification completed (only finish task if we created it)
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
                    final_description=f"⚠️ {app_name} verification completed with warnings",
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

    # Backward compatibility methods for tests - delegate to strategy pattern
    def _detect_available_methods(
        self,
        asset: dict[str, Any],
        config: dict[str, Any],
        assets: list[dict[str, Any]] | None = None,
        owner: str | None = None,
        repo: str | None = None,
        tag_name: str | None = None,
    ) -> tuple[bool, list[Any]]:
        """Backward compatibility: delegate to detection service."""
        return self.facade.detection_service.detect_available_methods(
            asset, config, assets, owner, repo, tag_name
        )

    def _should_skip_verification(
        self,
        config: dict[str, Any],
        has_digest: bool,
        has_checksum_files: bool,
    ) -> tuple[bool, dict[str, Any]]:
        """Backward compatibility: delegate to facade."""
        return self.facade.should_skip_verification(config, has_digest, has_checksum_files)

    async def _verify_digest(
        self,
        verifier: Verifier,
        digest: str,
        app_name: str,
        skip_configured: bool,
    ) -> dict[str, Any] | None:
        """Backward compatibility: delegate to digest strategy."""
        strategy = self.facade.factory.create_digest_strategy()
        context = {
            "app_name": app_name,
            "skip_configured": skip_configured,
        }
        return await strategy.verify(verifier, digest, context)

    async def _verify_checksum_file(
        self,
        verifier: Verifier,
        checksum_file: Any,
        target_filename: str,
        app_name: str,
    ) -> dict[str, Any] | None:
        """Backward compatibility: delegate to checksum file strategy."""
        strategy = self.facade.factory.create_checksum_file_strategy()
        context = {
            "target_filename": target_filename,
            "app_name": app_name,
        }
        return await strategy.verify(verifier, checksum_file, context)

    def _build_checksum_url(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        checksum_file: str,
    ) -> str:
        """Backward compatibility: delegate to detection service."""
        return self.facade.detection_service._build_checksum_url(
            owner, repo, tag_name, checksum_file
        )

    def _prioritize_checksum_files(
        self,
        checksum_files: list[Any],
        target_filename: str,
    ) -> list[Any]:
        """Backward compatibility: delegate to prioritization service."""
        return self.facade.prioritization_service.prioritize_checksum_files(
            checksum_files, target_filename
        )
