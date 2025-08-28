"""Shared verification service to eliminate code duplication."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_unicorn.download import DownloadService
from my_unicorn.github_client import ChecksumFileInfo, GitHubReleaseFetcher
from my_unicorn.services.progress import ProgressService
from my_unicorn.verify import Verifier

logger = logging.getLogger(__name__)


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
    """Shared service for file verification with multiple methods."""

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

    def _detect_available_methods(
        self,
        asset: dict[str, Any],
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
        has_digest = bool(asset.get("digest"))

        # Check for manually configured checksum file
        manual_checksum_file = config.get("checksum_file")
        checksum_files = []

        if manual_checksum_file and manual_checksum_file.strip():
            # Use manually configured checksum file
            if owner and repo and tag_name:
                url = self._build_checksum_url(owner, repo, tag_name, manual_checksum_file)
                format_type = (
                    "yaml"
                    if manual_checksum_file.lower().endswith((".yml", ".yaml"))
                    else "traditional"
                )
                checksum_files.append(
                    ChecksumFileInfo(
                        filename=manual_checksum_file, url=url, format_type=format_type
                    )
                )
        elif assets and owner and repo and tag_name:
            # Auto-detect checksum files from assets using GitHub client logic
            try:
                # Convert assets to the format expected by GitHubReleaseFetcher
                github_assets = []
                for asset_data in assets:
                    github_assets.append(
                        {
                            "name": asset_data.get("name", ""),
                            "browser_download_url": asset_data.get("browser_download_url", ""),
                            "size": asset_data.get("size", 0),
                            "digest": asset_data.get("digest", ""),
                        }
                    )

                # Use GitHubReleaseFetcher to detect checksum files
                checksum_files = GitHubReleaseFetcher.detect_checksum_files(
                    github_assets, tag_name
                )
                logger.debug(
                    "🔍 Auto-detected %d checksum files from assets", len(checksum_files)
                )
            except Exception as e:
                logger.warning("Failed to auto-detect checksum files: %s", e)

        return has_digest, checksum_files

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
            has_checksum_files: Whether checksum file verification is available

        Returns:
            Tuple of (should_skip, updated_config)

        """
        catalog_skip = config.get("skip", False)
        updated_config = config.copy()

        # Only skip if configured AND no strong verification methods available
        if catalog_skip and not has_digest and not has_checksum_files:
            logger.debug(
                "⏭️ Verification skipped (configured skip, no strong methods available)"
            )
            return True, updated_config
        elif catalog_skip and (has_digest or has_checksum_files):
            logger.debug("🔄 Overriding skip setting - strong verification methods available")
            # Update config to reflect that we're now using verification
            updated_config["skip"] = False

        return False, updated_config

    async def _verify_digest(
        self,
        verifier: Verifier,
        digest: str,
        app_name: str,
        skip_configured: bool,
    ) -> dict[str, Any] | None:
        """Attempt digest verification.

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
            if skip_configured:
                logger.debug("   Note: Using digest despite skip=true setting")
            verifier.verify_digest(digest)
            logger.debug("✅ Digest verification passed")
            return {
                "passed": True,
                "hash": digest,
                "details": "GitHub API digest verification",
            }
        except Exception as e:
            logger.error("❌ Digest verification failed: %s", e)
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
        """Attempt checksum file verification.

        Args:
            verifier: Verifier instance
            checksum_file: Checksum file information
            target_filename: Original filename for checksum lookup
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

            # Download checksum file content using existing download service method
            content = await self.download_service.download_checksum_file(checksum_file.url)

            # Use Verifier's parse_checksum_file method which handles both formats
            if checksum_file.format_type == "yaml":
                # For YAML files, use sha512 as default hash type (common for Electron apps)
                hash_type = "sha512"
            else:
                # For traditional files, detect hash type from filename
                hash_type = verifier.detect_hash_type_from_filename(checksum_file.filename)

            # Parse using the public method that handles both YAML and traditional formats
            expected_hash = verifier.parse_checksum_file(content, target_filename, hash_type)
            if not expected_hash:
                return {
                    "passed": False,
                    "hash": "",
                    "details": f"Hash not found for {target_filename} in checksum file",
                }

            # Compute actual hash and compare
            computed_hash = verifier.compute_hash(hash_type)

            if computed_hash.lower() == expected_hash.lower():
                logger.debug("✅ Checksum file verification passed (%s)", hash_type)
                return {
                    "passed": True,
                    "hash": f"{hash_type}:{computed_hash}",
                    "details": f"Verified against {checksum_file.format_type} checksum file",
                    "url": checksum_file.url,
                    "hash_type": hash_type,
                }
            else:
                logger.error(
                    "❌ Hash mismatch: expected %s, got %s", expected_hash, computed_hash
                )
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

    def _verify_file_size(
        self,
        verifier: Verifier,
        expected_size: int | None,
    ) -> dict[str, Any]:
        """Perform file size verification.

        Args:
            verifier: Verifier instance
            expected_size: Expected file size in bytes (can be None)

        Returns:
            Verification result dict

        """
        try:
            file_size = verifier.get_file_size()
            if expected_size is not None and expected_size > 0:
                verifier.verify_size(expected_size)
            return {
                "passed": True,
                "details": f"File size: {file_size:,} bytes",
            }
        except Exception as e:
            logger.warning("⚠️  Size verification failed: %s", e)
            return {"passed": False, "details": str(e)}

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
            f"https://github.com/{owner}/{repo}/releases/download/{tag_name}/{checksum_file}"
        )

    def _prioritize_checksum_files(
        self,
        checksum_files: list[ChecksumFileInfo],
        target_filename: str,
    ) -> list[ChecksumFileInfo]:
        """Prioritize checksum files to try the most relevant one first.

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

        def get_priority(checksum_file: ChecksumFileInfo) -> tuple[int, str]:
            """Get priority score for checksum file (lower = higher priority)."""
            filename = checksum_file.filename

            # Priority 1: Exact match (e.g., app.AppImage.DIGEST)
            if (
                filename == f"{target_filename}.DIGEST"
                or filename == f"{target_filename}.digest"
            ):
                logger.debug("   📌 Priority 1 (exact .DIGEST): %s", filename)
                return (1, filename)

            # Priority 2: Platform-specific hash files (e.g., app.AppImage.sha256)
            target_extensions = [".sha256", ".sha512", ".sha1", ".md5"]
            for ext in target_extensions:
                if filename == f"{target_filename}{ext}":
                    logger.debug("   📌 Priority 2 (platform-specific): %s", filename)
                    return (2, filename)

            # Priority 3: YAML files (usually most comprehensive)
            if checksum_file.format_type == "yaml":
                logger.debug("   📌 Priority 3 (YAML): %s", filename)
                return (3, filename)

            # Priority 4: Other .DIGEST files (might contain multiple files)
            if filename.lower().endswith((".digest",)):
                logger.debug("   📌 Priority 4 (other .DIGEST): %s", filename)
                return (4, filename)

            # Priority 5: Generic checksum files
            logger.debug("   📌 Priority 5 (generic): %s", filename)
            return (5, filename)

        # Sort by priority (lower number = higher priority)
        prioritized = sorted(checksum_files, key=get_priority)

        logger.debug("   📋 Final priority order:")
        for i, cf in enumerate(prioritized, 1):
            logger.debug("      %d. %s", i, cf.filename)

        return prioritized

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
        """Perform comprehensive file verification.

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

        # Detect available methods (with backward compatibility)
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

        # Try digest verification first if available
        if has_digest:
            # Update progress - digest verification
            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=40.0,
                    description=f"🔍 Verifying digest for {app_name}...",
                )

            digest_result = await self._verify_digest(
                verifier, asset["digest"], app_name, skip_configured
            )
            if digest_result:
                verification_methods["digest"] = digest_result
                if digest_result["passed"]:
                    verification_passed = True
                    # Enable digest verification in config for future use
                    updated_config["digest"] = True

        # Try checksum file verification with smart prioritization
        if checksum_files:
            # Update progress - checksum verification
            if progress_task_id and self.progress_service:
                await self.progress_service.update_task(
                    progress_task_id,
                    completed=60.0,
                    description=f"🔍 Verifying checksum for {app_name}...",
                )

            # Prioritize checksum files to try the most likely match first
            prioritized_files = self._prioritize_checksum_files(checksum_files, file_path.name)

            for i, checksum_file in enumerate(prioritized_files):
                method_key = f"checksum_file_{i}" if i > 0 else "checksum_file"

                checksum_result = await self._verify_checksum_file(
                    verifier,
                    checksum_file,
                    file_path.name,
                    app_name,
                )

                if checksum_result:
                    verification_methods[method_key] = checksum_result
                    if checksum_result["passed"]:
                        verification_passed = True
                        # Update config with successful checksum file
                        updated_config["checksum_file"] = checksum_file.filename
                        break  # Stop trying other checksum files once one succeeds

        # Always perform basic file size verification
        if progress_task_id and self.progress_service:
            await self.progress_service.update_task(
                progress_task_id,
                completed=80.0,
                description=f"🔍 Verifying file size for {app_name}...",
            )

        expected_size = asset.get("size")
        size_result = self._verify_file_size(verifier, expected_size)
        verification_methods["size"] = size_result

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

        # If no strong methods and size check failed, that's also an error
        if not strong_methods_available and not size_result["passed"]:
            raise Exception(
                "File verification failed - no strong verification methods available and size check failed"
            )

        # Success if any strong method passed, or if no strong methods but size passed
        overall_passed = verification_passed or (
            not strong_methods_available and size_result["passed"]
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
