"""Tests for VerificationService orchestration and coordination.

This module focuses on high-level VerificationService.verify_file()
orchestration tests that verify end-to-end verification flows and
service-level error handling.

Individual verification methods (digest, checksum file) are tested in
test_verification_methods.py. Lower-level components are tested in their
respective modules (detection, verification_methods, etc).
"""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.protocols.progress import NullProgressReporter
from my_unicorn.core.verification.context import VerificationContext
from my_unicorn.core.verification.service import VerificationService
from my_unicorn.exceptions import VerificationError

# Test data constant for YAML checksum
LEGCORD_YAML_CONTENT = (
    "version: 1.1.5\n"
    "path: test.AppImage\n"
    "sha512: DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4"
    "IcwAHkbMl6cEmIKXGFpN9+mWAg=="
)


class TestVerificationServiceOrchestration:
    """Tests for VerificationService end-to-end orchestration."""

    @pytest.mark.asyncio
    async def test_verify_file_digest_priority(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        sample_assets: list[Asset],
    ) -> None:
        """Digest verification is prioritized over checksum files."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/test/repo/releases/download/v1.0.0/"
                "test.AppImage"
            ),
            digest=(
                "sha256:6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f"
                "76863140143ff72"
            ),
        )
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test.AppImage",
            assets=sample_assets,
        )

        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_fallback_to_checksum(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        sample_assets: list[Asset],
    ) -> None:
        """Fallback to checksum file when digest is not available."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/Legcord/Legcord/releases/download/"
                "v1.1.5/test.AppImage"
            ),
            digest="",
        )
        config = {"skip": False}

        verification_service.download_service.download_checksum_file = (  # type: ignore[method-assign]
            AsyncMock(return_value=LEGCORD_YAML_CONTENT)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="Legcord",
            repo="Legcord",
            tag_name="v1.1.5",
            app_name="test.AppImage",
            assets=sample_assets,
        )

        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_file_skip_verification(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Verification is skipped when configured."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/test/repo/releases/download/v1.0.0/"
                "test.AppImage"
            ),
            digest="",
        )
        config = {"skip": True}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test.AppImage",
        )

        assert result.passed is True
        assert result.methods == {}  # No methods attempted

    @pytest.mark.asyncio
    async def test_verify_file_backward_compatibility(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
    ) -> None:
        """Verify file without assets parameter (backward compatibility)."""
        content = b"test content"
        correct_hash = hashlib.sha256(content).hexdigest()

        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/test/repo/releases/download/v1.0.0/"
                "test.AppImage"
            ),
            digest=f"sha256:{correct_hash}",
        )
        config = {"skip": False, "checksum_file": "manual.txt"}

        # Call without assets parameter (old API)
        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0.0",
            app_name="test.AppImage",
        )

        assert result.passed is True
        assert "digest" in result.methods


class TestVerificationServiceProtocolUsage:
    """Tests for VerificationService protocol compliance."""

    def test_accepts_progress_reporter_protocol(
        self, mock_download_service: MagicMock
    ) -> None:
        """VerificationService accepts ProgressReporter protocol."""
        mock_reporter = MagicMock()
        service = VerificationService(
            download_service=mock_download_service,
            progress_reporter=mock_reporter,
        )

        assert service.progress_reporter is mock_reporter

    def test_uses_null_progress_reporter_when_none_provided(
        self, mock_download_service: MagicMock
    ) -> None:
        """NullProgressReporter is used when none provided."""
        service = VerificationService(download_service=mock_download_service)

        assert isinstance(service.progress_reporter, NullProgressReporter)

    @pytest.mark.asyncio
    async def test_null_progress_reporter_no_errors(
        self, mock_download_service: MagicMock
    ) -> None:
        """NullProgressReporter: verification completes without errors."""
        service = VerificationService(download_service=mock_download_service)

        context = VerificationContext(
            file_path=Path("/tmp/test.AppImage"),
            asset=Asset(
                name="test.AppImage",
                size=100,
                browser_download_url="https://example.com/test.AppImage",
                digest="",
            ),
            config={"skip": True},
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="test",
            assets=None,
            progress_task_id=None,
        )

        result = await service._prepare_verification(context)
        assert result is not None
        assert result.passed is True


class TestVerificationServiceErrorHandling:
    """Tests for VerificationService error handling."""

    @pytest.mark.asyncio
    async def test_verification_error_raised_when_all_methods_fail(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        mock_download_service: MagicMock,
    ) -> None:
        """VerificationError is raised when all verification methods fail."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/test/test/releases/download/v1.0.0/"
                "test.AppImage"
            ),
            digest="sha256:wrong_hash_that_will_fail",
        )
        config = {"skip": False}

        with pytest.raises(VerificationError) as exc_info:
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="testapp",
                assets=None,
            )

        assert isinstance(exc_info.value, VerificationError)

    @pytest.mark.asyncio
    async def test_verification_error_not_raised_when_method_passes(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
    ) -> None:
        """VerificationError not raised when at least one method passes."""
        content = b"test content"
        correct_hash = hashlib.sha256(content).hexdigest()

        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/test/test/releases/download/v1.0.0/"
                "test.AppImage"
            ),
            digest=f"sha256:{correct_hash}",
        )
        config = {"skip": False}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="testapp",
            assets=None,
        )

        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_verification_error_not_raised_when_skip_configured(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
    ) -> None:
        """VerificationError not raised when skip=True."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/test/test/releases/download/v1.0.0/"
                "test.AppImage"
            ),
            digest="",
        )
        config = {"skip": True}

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="test",
            tag_name="v1.0.0",
            app_name="testapp",
            assets=None,
        )

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_verification_error_includes_context_fields(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        mock_download_service: MagicMock,
    ) -> None:
        """VerificationError includes app_name, file_path, and method info."""
        asset = Asset(
            name="test.AppImage",
            size=12,
            browser_download_url=(
                "https://github.com/test/test/releases/download/v1.0.0/"
                "test.AppImage"
            ),
            digest="sha256:invalid_hash",
        )
        config = {"skip": False}

        with pytest.raises(VerificationError) as exc_info:
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset,
                config=config,
                owner="test",
                repo="test",
                tag_name="v1.0.0",
                app_name="testapp",
                assets=None,
            )

        error = exc_info.value
        # Check context dictionary contains expected fields
        assert hasattr(error, "context")
        assert "app_name" in error.context
        assert "file_path" in error.context
        assert "available_methods" in error.context
        assert "failed_methods" in error.context

        # Verify context values
        assert error.context["app_name"] == "testapp"
        assert str(test_file_path) in error.context["file_path"]  # type: ignore[operator]
        assert "digest" in error.context["available_methods"]  # type: ignore[operator]
