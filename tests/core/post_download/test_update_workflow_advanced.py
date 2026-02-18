"""Tests for PostDownloadProcessor update workflow - Advanced scenarios.

This module tests advanced update workflow scenarios including non-fatal
errors, config updates, and progress tracking.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.post_download import (
    PostDownloadContext,
    PostDownloadProcessor,
)


class TestUpdateWorkflowNonFatalErrors:
    """Tests for non-fatal errors in update workflow."""

    @pytest.mark.asyncio
    async def test_update_workflow_desktop_entry_failure_non_fatal(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_backup_service_post: MagicMock,
    ) -> None:
        """Test update workflow continues when desktop entry fails.

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
                side_effect=desktop_error,
            ),
        ):
            # Act
            result = await processor_instance.process(update_context)

            # Assert
            assert result.success is True
            assert result.install_path == Path(
                "/opt/appimages/test-app.AppImage"
            )
            assert result.desktop_result is not None
            assert result.desktop_result["success"] is False


class TestUpdateWorkflowConfigUpdate:
    """Tests for config update in update workflow."""

    @pytest.mark.asyncio
    async def test_update_workflow_config_update(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
    ) -> None:
        """Test that update_app_config is called during update.

        Verifies that configuration is properly updated via
        update_app_config with correct parameters.
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
                    "hash": "def456abc123",
                    "algorithm": "SHA256",
                }
            },
        }

        icon_result = {
            "success": True,
            "path": "/opt/icons/test-app.png",
            "source": "extracted",
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
                return_value=icon_result,
            ),
            patch(
                "my_unicorn.core.post_download.update_app_config",
            ) as mock_config,
            patch(
                "my_unicorn.core.post_download.get_stored_hash",
                return_value="abc123def456",
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
            mock_config.assert_called_once()
            # Verify config call has correct parameters
            call_kwargs = mock_config.call_args[1]
            assert call_kwargs["app_name"] == "test-app"
            assert call_kwargs["appimage_path"] == Path(
                "/opt/appimages/test-app.AppImage"
            )
            assert call_kwargs["verify_result"] == verify_result


class TestUpdateWorkflowProgressTracking:
    """Tests for progress tracking during update."""

    @pytest.mark.asyncio
    async def test_update_workflow_progress_tracking(
        self,
        update_context: PostDownloadContext,
        processor_instance: PostDownloadProcessor,
        mock_storage_service_post: MagicMock,
        mock_progress_reporter_post: MagicMock,
        mock_backup_service_post: MagicMock,
    ) -> None:
        """Test that progress reporter methods are called during update.

        Verifies that progress tracking is set up and updated throughout
        the update workflow.
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
            # Verify progress reporter was checked
            mock_progress_reporter_post.is_active.assert_called()
