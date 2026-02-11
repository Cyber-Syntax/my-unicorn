"""Tests for progress tracking and download verification.

Tests the _setup_progress_tracking and _verify_download private methods
of PostDownloadProcessor with comprehensive edge case coverage.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.post_download import (
    PostDownloadContext,
    PostDownloadProcessor,
)
from my_unicorn.core.progress.display import ProgressDisplay
from my_unicorn.core.protocols.progress import NullProgressReporter
from my_unicorn.exceptions import VerificationError


class TestSetupProgressTracking:
    """Test suite for _setup_progress_tracking method."""

    @pytest.mark.asyncio
    async def test_setup_progress_tracking_with_active_reporter(
        self, processor_instance: PostDownloadProcessor
    ) -> None:
        """Verify progress tasks created when reporter is active."""
        processor_instance.progress_reporter.is_active.return_value = True

        # Create a mock ProgressDisplay instance
        mock_display = MagicMock(spec=ProgressDisplay)
        processor_instance.progress_reporter = mock_display

        with patch(
            "my_unicorn.core.progress.display_workflows"
            ".create_installation_workflow",
            new_callable=AsyncMock,
        ) as mock_create_workflow:
            mock_create_workflow.return_value = (
                "ver_task_1",
                "install_task_1",
            )

            (
                ver_task,
                install_task,
            ) = await processor_instance._setup_progress_tracking(
                "test-app", True
            )

            assert ver_task == "ver_task_1"
            assert install_task == "install_task_1"
            mock_create_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_progress_tracking_with_null_reporter(
        self, processor_instance: PostDownloadProcessor
    ) -> None:
        """Verify no tasks created with NullProgressReporter."""
        processor_instance.progress_reporter = NullProgressReporter()

        (
            ver_task,
            install_task,
        ) = await processor_instance._setup_progress_tracking("test-app", True)

        assert ver_task is None
        assert install_task is None

    @pytest.mark.asyncio
    async def test_setup_progress_tracking_task_creation(
        self, processor_instance: PostDownloadProcessor
    ) -> None:
        """Verify task IDs returned correctly."""
        # Create a mock ProgressDisplay instance for isinstance check
        mock_display = MagicMock(spec=ProgressDisplay)
        processor_instance.progress_reporter = mock_display

        with patch(
            "my_unicorn.core.progress.display_workflows"
            ".create_installation_workflow",
            new_callable=AsyncMock,
        ) as mock_create_workflow:
            mock_create_workflow.return_value = ("ver_123", "install_456")

            (
                ver_task,
                install_task,
            ) = await processor_instance._setup_progress_tracking(
                "myapp", False
            )

            assert ver_task == "ver_123"
            assert install_task == "install_456"
            mock_create_workflow.assert_called_once_with(
                processor_instance.progress_reporter,
                "myapp",
                with_verification=False,
            )


class TestVerifyDownload:
    """Test suite for _verify_download method."""

    @pytest.mark.asyncio
    async def test_verify_download_with_verification_enabled_success(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Hash verification succeeds."""
        with patch(
            "my_unicorn.core.post_download.verify_appimage_download",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = {
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "abc123",
                        "algorithm": "SHA256",
                    }
                },
            }

            result = await processor_instance._verify_download(
                install_context, "ver_task_1"
            )

            assert result is not None
            assert result["passed"] is True
            mock_verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_download_with_verification_enabled_failure(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Hash verification fails, raises VerificationError."""
        with patch(
            "my_unicorn.core.post_download.verify_appimage_download",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.side_effect = VerificationError("Hash mismatch")

            with pytest.raises(VerificationError):
                await processor_instance._verify_download(
                    install_context, "ver_task_1"
                )

            mock_verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_download_with_verification_disabled(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Skip verification, no download/verify calls."""
        install_context.verify_downloads = False

        result = await processor_instance._verify_download(
            install_context, "ver_task_1"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_download_hash_file_download(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Verify checksum file downloaded correctly."""
        with patch(
            "my_unicorn.core.post_download.verify_appimage_download",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = {
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "def456",
                        "algorithm": "SHA512",
                    }
                },
            }

            result = await processor_instance._verify_download(
                install_context, None
            )

            assert result["methods"]["digest"]["algorithm"] == "SHA512"
            assert result["methods"]["digest"]["hash"] == "def456"
