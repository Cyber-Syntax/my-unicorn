"""Tests for PostDownloadProcessor update workflow.

This module tests the complete update workflow in PostDownloadProcessor
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


class TestUpdateWorkflowSuccess:
    """Tests for successful update workflows."""

    @pytest.mark.asyncio
    async def test_update_workflow_success_with_verification(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_backup_service_post: MagicMock,
    ) -> None:
        """Test full update workflow with hash verification enabled.

        Verifies that a complete update workflow executes successfully
        when all services return expected results with verification enabled.
        """
        # Arrange
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )
        mock_backup_service_post.cleanup_old_backups.return_value = None

        with (
            patch(
                "my_unicorn.core.post_download.verify_appimage_download",
                new_callable=AsyncMock,
                return_value={
                    "passed": True,
                    "methods": {
                        "digest": {
                            "passed": True,
                            "hash": "def456abc123",
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
            ),
            patch(
                "my_unicorn.core.post_download.update_app_config",
                return_value=None,
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
            result = await processor_instance.process(update_context)

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
            mock_config.assert_called_once()
            mock_desktop.assert_called_once()
            # Verify cleanup was called
            mock_backup_service_post.cleanup_old_backups.assert_called_once_with(
                "test-app"
            )

    @pytest.mark.asyncio
    async def test_update_workflow_success_without_verification(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_backup_service_post: MagicMock,
    ) -> None:
        """Test update workflow without hash verification.

        Verifies update succeeds when verification is disabled
        in the context.
        """
        # Arrange
        update_context.verify_downloads = False
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )
        mock_backup_service_post.cleanup_old_backups.return_value = None

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
                "my_unicorn.core.post_download.update_app_config",
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
            result = await processor_instance.process(update_context)

            # Assert
            assert result.success is True
            assert result.verification_result is None
            assert result.error is None
            mock_backup_service_post.cleanup_old_backups.assert_called_once()


class TestUpdateWorkflowErrors:
    """Tests for error scenarios in update workflow."""

    @pytest.mark.asyncio
    async def test_update_workflow_verification_failure(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
    ) -> None:
        """Test update workflow fails with verification error.

        Verifies that hash mismatch raises VerificationError and
        the workflow returns failure result.
        """
        # Arrange
        update_context.verify_downloads = True

        with patch(
            "my_unicorn.core.post_download.verify_appimage_download",
            new_callable=AsyncMock,
            side_effect=VerificationError("Hash mismatch in update"),
        ):
            # Act
            result = await processor_instance.process(update_context)

            # Assert
            assert result.success is False
            assert result.install_path is None
            assert result.verification_result is None
            assert "Hash mismatch" in result.error


class TestUpdateWorkflowCleanup:
    """Tests for cleanup operations in update workflow."""

    @pytest.mark.asyncio
    async def test_update_workflow_cleanup_success(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_backup_service_post: MagicMock,
    ) -> None:
        """Test that backup cleanup is called after successful update.

        Verifies that cleanup_old_backups is called with the correct
        app name.
        """
        # Arrange
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )

        with (
            patch(
                "my_unicorn.core.post_download.verify_appimage_download",
                new_callable=AsyncMock,
                return_value={
                    "passed": True,
                    "methods": {
                        "digest": {
                            "passed": True,
                            "hash": "def456abc123",
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
                "my_unicorn.core.post_download.update_app_config",
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
            result = await processor_instance.process(update_context)

            # Assert
            assert result.success is True
            mock_backup_service_post.cleanup_old_backups.assert_called_once_with(
                "test-app"
            )

    @pytest.mark.asyncio
    async def test_update_workflow_cleanup_failure_non_fatal(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_backup_service_post: MagicMock,
    ) -> None:
        """Test update workflow continues when cleanup fails.

        Verifies that backup cleanup failures are non-fatal and the
        workflow still completes successfully.
        """
        # Arrange
        mock_storage_service_post.move_to_install_dir.return_value = Path(
            "/opt/appimages/test-app.AppImage"
        )
        cleanup_error = RuntimeError("Failed to cleanup backups")
        mock_backup_service_post.cleanup_old_backups.side_effect = (
            cleanup_error
        )

        with (
            patch(
                "my_unicorn.core.post_download.verify_appimage_download",
                new_callable=AsyncMock,
                return_value={
                    "passed": True,
                    "methods": {
                        "digest": {
                            "passed": True,
                            "hash": "def456abc123",
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
                "my_unicorn.core.post_download.update_app_config",
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
            result = await processor_instance.process(update_context)

            # Assert
            assert result.success is True
            assert result.install_path == Path(
                "/opt/appimages/test-app.AppImage"
            )
