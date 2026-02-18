"""Tests for PostDownloadProcessor install workflow.

This module tests the complete install workflow in PostDownloadProcessor
.process() covering happy paths and error scenarios for 100% coverage.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.post_download import (
    PostDownloadContext,
    PostDownloadProcessor,
)
from my_unicorn.exceptions import VerificationError


class TestInstallWorkflowSuccess:
    """Tests for successful install workflows."""

    @pytest.mark.asyncio
    async def test_install_workflow_success_with_verification(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_verification_service_post: AsyncMock,
    ) -> None:
        """Test full install workflow with hash verification enabled.

        Verifies that a complete installation workflow executes successfully
        when all services return expected results with verification enabled.
        """
        # Arrange
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )

        mock_verification_service_post.verify_file.return_value = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash": "abc123def456",
                    "algorithm": "SHA256",
                }
            },
        }

        with (
            patch(
                "my_unicorn.core.post_download.verify_appimage_download",
                new_callable=AsyncMock,
                return_value={
                    "passed": True,
                    "methods": {
                        "digest": {
                            "passed": True,
                            "hash": "abc123def456",
                            "algorithm": "SHA256",
                        }
                    },
                },
            ) as mock_verify,
            patch(
                "my_unicorn.core.post_download.rename_appimage",
                return_value=Path("/opt/appimages/test-app.AppImage"),
            ),
            patch(
                "my_unicorn.core.post_download.setup_appimage_icon",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "path": "/opt/icons/test-app.png",
                    "source": "extracted",
                },
            ) as mock_icon,
            patch(
                "my_unicorn.core.post_download.create_app_config_v2",
                return_value={
                    "success": True,
                    "operation": "install",
                },
            ) as mock_config,
            patch(
                "my_unicorn.core.post_download.create_desktop_entry",
                return_value={
                    "success": True,
                    "path": "/home/user/.local/share/",
                },
            ) as mock_desktop,
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is True
            assert result.install_path == Path(
                "/opt/appimages/test-app.AppImage"
            )
            assert result.verification_result is not None
            assert result.icon_result is not None
            assert result.config_result is not None
            assert result.desktop_result is not None
            assert result.error is None

            # Verify service calls
            mock_verify.assert_called_once()
            mock_icon.assert_called_once()
            mock_config.assert_called_once()
            mock_desktop.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_workflow_success_without_verification(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
    ) -> None:
        """Test install workflow without hash verification.

        Verifies installation succeeds when verification is disabled
        in the context.
        """
        # Arrange
        install_context.verify_downloads = False
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )

        with (
            patch(
                "my_unicorn.core.post_download.rename_appimage",
                return_value=Path("/opt/appimages/test-app.AppImage"),
            ),
            patch(
                "my_unicorn.core.post_download.setup_appimage_icon",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "path": "/opt/icons/test-app.png",
                    "source": "extracted",
                },
            ),
            patch(
                "my_unicorn.core.post_download.create_app_config_v2",
                return_value={
                    "success": True,
                    "operation": "install",
                },
            ),
            patch(
                "my_unicorn.core.post_download.create_desktop_entry",
                return_value={
                    "success": True,
                    "path": "/home/user/.local/share/",
                },
            ),
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is True
            assert result.verification_result is None
            assert result.error is None


class TestInstallWorkflowErrors:
    """Tests for error scenarios in install workflow."""

    @pytest.mark.asyncio
    async def test_install_workflow_verification_failure(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
    ) -> None:
        """Test install workflow fails with verification error.

        Verifies that hash mismatch raises VerificationError and
        the workflow returns failure result.
        """
        # Arrange
        install_context.verify_downloads = True

        with patch(
            "my_unicorn.core.post_download.verify_appimage_download",
            new_callable=AsyncMock,
            side_effect=VerificationError("Hash mismatch detected"),
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is False
            assert result.install_path is None
            assert result.verification_result is None
            assert "Hash mismatch" in result.error

    @pytest.mark.asyncio
    async def test_install_workflow_download_failure(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
    ) -> None:
        """Test install workflow when download operation fails.

        Verifies that download errors during install_and_rename
        are properly caught and return failure result.
        """
        # Arrange
        download_error = OSError("Failed to write file")
        mock_storage_service_post.move_to_install_dir.side_effect = (
            download_error
        )

        with patch(
            "my_unicorn.core.post_download.verify_appimage_download",
            new_callable=AsyncMock,
            return_value={
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "abc123def456",
                        "algorithm": "SHA256",
                    }
                },
            },
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is False
            assert result.install_path is None
            assert "Failed to write file" in result.error

    @pytest.mark.asyncio
    async def test_install_workflow_file_operation_failure(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
    ) -> None:
        """Test install workflow when file operations fail.

        Verifies that file operation errors are caught and the
        workflow returns a failure result.
        """
        # Arrange
        file_error = PermissionError("Cannot write to install directory")
        mock_storage_service_post.make_executable.side_effect = file_error

        with patch(
            "my_unicorn.core.post_download.verify_appimage_download",
            new_callable=AsyncMock,
            return_value={
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "abc123def456",
                        "algorithm": "SHA256",
                    }
                },
            },
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is False
            assert "Cannot write to install directory" in result.error


class TestInstallWorkflowNonFatalErrors:
    """Tests for non-fatal errors that don't stop the workflow."""

    @pytest.mark.asyncio
    async def test_install_workflow_desktop_entry_failure_non_fatal(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
    ) -> None:
        """Test install workflow continues when desktop entry fails.

        Verifies that desktop entry creation failures are non-fatal
        and the workflow still completes successfully.
        """
        # Arrange
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )

        desktop_error = RuntimeError("Failed to create desktop entry")

        with (
            patch(
                "my_unicorn.core.post_download.verify_appimage_download",
                new_callable=AsyncMock,
                return_value={
                    "passed": True,
                    "methods": {
                        "digest": {
                            "passed": True,
                            "hash": "abc123def456",
                            "algorithm": "SHA256",
                        }
                    },
                },
            ),
            patch(
                "my_unicorn.core.post_download.rename_appimage",
                return_value=Path("/opt/appimages/test-app.AppImage"),
            ),
            patch(
                "my_unicorn.core.post_download.setup_appimage_icon",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "path": "/opt/icons/test-app.png",
                    "source": "extracted",
                },
            ),
            patch(
                "my_unicorn.core.post_download.create_app_config_v2",
                return_value={
                    "success": True,
                    "operation": "install",
                },
            ),
            patch(
                "my_unicorn.core.post_download.create_desktop_entry",
                side_effect=desktop_error,
            ),
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is True
            assert result.install_path == Path(
                "/opt/appimages/test-app.AppImage"
            )
            assert result.desktop_result is not None
            assert result.desktop_result["success"] is False


class TestInstallWorkflowProgressTracking:
    """Tests for progress tracking during install."""

    @pytest.mark.asyncio
    async def test_install_workflow_progress_tracking(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_progress_reporter_post: MagicMock,
    ) -> None:
        """Test that progress reporter methods are called during install.

        Verifies that progress tracking is set up and updated throughout
        the installation workflow.
        """
        # Arrange
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )
        mock_progress_reporter_post.is_active.return_value = False

        with (
            patch(
                "my_unicorn.core.post_download.verify_appimage_download",
                new_callable=AsyncMock,
                return_value={
                    "passed": True,
                    "methods": {
                        "digest": {
                            "passed": True,
                            "hash": "abc123def456",
                            "algorithm": "SHA256",
                        }
                    },
                },
            ),
            patch(
                "my_unicorn.core.post_download.rename_appimage",
                return_value=Path("/opt/appimages/test-app.AppImage"),
            ),
            patch(
                "my_unicorn.core.post_download.setup_appimage_icon",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "path": "/opt/icons/test-app.png",
                    "source": "extracted",
                },
            ),
            patch(
                "my_unicorn.core.post_download.create_app_config_v2",
                return_value={
                    "success": True,
                    "operation": "install",
                },
            ),
            patch(
                "my_unicorn.core.post_download.create_desktop_entry",
                return_value={
                    "success": True,
                    "path": "/home/user/.local/share/",
                },
            ),
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is True
            # Verify progress reporter was checked
            mock_progress_reporter_post.is_active.assert_called()


class TestInstallWorkflowConfigCreation:
    """Tests for config creation in install workflow."""

    @pytest.mark.asyncio
    async def test_install_workflow_config_creation(
        self,
        install_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
    ) -> None:
        """Test that create_app_config_v2 is called during install.

        Verifies that configuration is properly created via
        create_app_config_v2 with correct parameters.
        """
        # Arrange
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )

        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash": "abc123def456",
                    "algorithm": "SHA256",
                }
            },
        }

        with (
            patch(
                "my_unicorn.core.post_download.verify_appimage_download",
                new_callable=AsyncMock,
                return_value=verify_result,
            ),
            patch(
                "my_unicorn.core.post_download.rename_appimage",
                return_value=Path("/opt/appimages/test-app.AppImage"),
            ),
            patch(
                "my_unicorn.core.post_download.setup_appimage_icon",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "path": "/opt/icons/test-app.png",
                    "source": "extracted",
                },
            ),
            patch(
                "my_unicorn.core.post_download.create_app_config_v2",
                return_value={
                    "success": True,
                    "operation": "install",
                },
            ) as mock_config,
            patch(
                "my_unicorn.core.post_download.create_desktop_entry",
                return_value={
                    "success": True,
                    "path": "/home/user/.local/share/",
                },
            ),
        ):
            # Act
            result = await processor_instance.process(install_context)

            # Assert
            assert result.success is True
            mock_config.assert_called_once()
            # Verify config call has correct parameters
            call_kwargs = mock_config.call_args[1]
            assert call_kwargs["app_name"] == "test-app"
            assert call_kwargs["app_path"] == Path(
                "/opt/appimages/test-app.AppImage"
            )
            assert call_kwargs["verify_result"] == verify_result
