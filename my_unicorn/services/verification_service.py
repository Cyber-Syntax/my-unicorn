"""Shared verification service to eliminate code duplication."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_unicorn.download import DownloadService
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

    def __init__(self, download_service: DownloadService) -> None:
        """Initialize verification service.

        Args:
            download_service: Service for downloading checksum files

        """
        self.download_service = download_service

    def _detect_available_methods(
        self,
        asset: dict[str, Any],
        config: dict[str, Any],
    ) -> tuple[bool, bool]:
        """Detect available verification methods.

        Args:
            asset: GitHub asset information
            config: Verification configuration

        Returns:
            Tuple of (has_digest, has_checksum_file)

        """
        has_digest = bool(asset.get("digest"))
        has_checksum_file = bool(config.get("checksum_file"))
        return has_digest, has_checksum_file

    def _should_skip_verification(
        self,
        config: dict[str, Any],
        has_digest: bool,
        has_checksum_file: bool,
    ) -> tuple[bool, dict[str, Any]]:
        """Determine if verification should be skipped.

        Args:
            config: Verification configuration
            has_digest: Whether digest verification is available
            has_checksum_file: Whether checksum file verification is available

        Returns:
            Tuple of (should_skip, updated_config)

        """
        catalog_skip = config.get("skip", False)
        updated_config = config.copy()

        # Only skip if configured AND no strong verification methods available
        if catalog_skip and not has_digest and not has_checksum_file:
            logger.debug(
                "⏭️ Verification skipped (configured skip, no strong methods available)"
            )
            return True, updated_config
        elif catalog_skip and (has_digest or has_checksum_file):
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
        checksum_url: str,
        hash_type: str,
        filename: str,
        app_name: str,
    ) -> dict[str, Any] | None:
        """Attempt checksum file verification.

        Args:
            verifier: Verifier instance
            checksum_url: URL to checksum file
            hash_type: Type of hash algorithm
            filename: Original filename for checksum lookup
            app_name: Application name for logging

        Returns:
            Verification result dict or None if failed

        """
        try:
            logger.debug("🔍 Verifying using checksum file: %s", checksum_url)
            await verifier.verify_from_checksum_file(
                checksum_url, hash_type, self.download_service, filename
            )
            computed_hash = verifier.compute_hash(hash_type)
            logger.debug("✅ Checksum file verification passed")
            return {
                "passed": True,
                "hash": f"{hash_type}:{computed_hash}",
                "details": "Verified against checksum file",
                "url": checksum_url,
                "hash_type": hash_type,
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

    async def verify_file(
        self,
        file_path: Path,
        asset: dict[str, Any],
        config: dict[str, Any],
        owner: str,
        repo: str,
        tag_name: str,
        app_name: str,
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

        Returns:
            VerificationResult with success status and methods used

        Raises:
            Exception: If verification fails and strong methods were available

        """
        logger.debug("🔍 Starting verification for %s", app_name)

        # Detect available methods
        has_digest, has_checksum_file = self._detect_available_methods(asset, config)
        logger.debug(
            "   Available methods: digest=%s, checksum_file=%s", has_digest, has_checksum_file
        )

        # Check if verification should be skipped
        should_skip, updated_config = self._should_skip_verification(
            config, has_digest, has_checksum_file
        )
        if should_skip:
            return VerificationResult(
                passed=True,
                methods={},
                updated_config=updated_config,
            )

        verifier = Verifier(file_path)
        verification_passed = False
        verification_methods = {}
        skip_configured = config.get("skip", False)

        # Try digest verification first if available
        if has_digest:
            digest_result = await self._verify_digest(
                verifier, asset["digest"], app_name, skip_configured
            )
            if digest_result:
                verification_methods["digest"] = digest_result
                if digest_result["passed"]:
                    verification_passed = True
                    # Enable digest verification in config for future use
                    updated_config["digest"] = True

        # Try checksum file verification if configured and digest didn't pass
        if not verification_passed and has_checksum_file:
            checksum_file = config["checksum_file"]
            hash_type = config.get("checksum_hash_type", "sha256")
            checksum_url = self._build_checksum_url(owner, repo, tag_name, checksum_file)

            checksum_result = await self._verify_checksum_file(
                verifier, checksum_url, hash_type, file_path.name, app_name
            )
            if checksum_result:
                verification_methods["checksum_file"] = checksum_result
                if checksum_result["passed"]:
                    verification_passed = True

        # Always perform basic file size verification
        expected_size = asset.get("size")
        size_result = self._verify_file_size(verifier, expected_size)
        verification_methods["size"] = size_result

        # If size check failed and no strong verification passed, that's an error
        if not size_result["passed"] and not verification_passed:
            if has_digest or has_checksum_file:
                raise Exception("File verification failed")

        # If we have strong verification methods available but none passed, fail
        if (has_digest or has_checksum_file) and not verification_passed:
            available_methods = []
            if has_digest:
                available_methods.append("digest")
            if has_checksum_file:
                available_methods.append("checksum_file")
            raise Exception(
                f"Available verification methods failed: {', '.join(available_methods)}"
            )

        logger.debug("✅ Verification completed")
        return VerificationResult(
            passed=verification_passed or size_result["passed"],
            methods=verification_methods,
            updated_config=updated_config,
        )
