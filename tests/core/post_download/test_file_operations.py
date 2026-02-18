"""Tests for file operations in PostDownloadProcessor.

Tests the _install_and_rename and _setup_icon private methods
with comprehensive edge case coverage.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from my_unicorn.core.post_download import (
    PostDownloadContext,
    PostDownloadProcessor,
)


class TestInstallAndRename:
    """Test suite for _install_and_rename method."""

    @pytest.mark.asyncio
    async def test_install_and_rename_success(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """File moved and renamed successfully."""
        expected_path = Path("/opt/appimages/test-app.AppImage")
        processor_instance.storage_service.move_to_install_dir.return_value = (
            expected_path
        )

        with patch(
            "my_unicorn.core.post_download.rename_appimage",
            return_value=expected_path,
        ):
            result = await processor_instance._install_and_rename(
                install_context
            )

            processor_instance.storage_service.make_executable.assert_called_once_with(
                install_context.downloaded_path
            )
            processor_instance.storage_service.move_to_install_dir.assert_called_once_with(
                install_context.downloaded_path
            )
            assert result == expected_path

    @pytest.mark.asyncio
    async def test_install_and_rename_file_operation_error(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """File operation error propagates."""
        processor_instance.storage_service.make_executable.side_effect = (
            OSError("Permission denied")
        )

        with pytest.raises(OSError, match="Permission denied"):
            await processor_instance._install_and_rename(install_context)

    @pytest.mark.asyncio
    async def test_install_and_rename_path_returned(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Verify new path returned correctly."""
        moved_path = Path("/opt/appimages/test-app-moved.AppImage")
        renamed_path = Path("/opt/appimages/test-app-final.AppImage")

        processor_instance.storage_service.move_to_install_dir.return_value = (
            moved_path
        )

        with patch(
            "my_unicorn.core.post_download.rename_appimage",
            return_value=renamed_path,
        ) as mock_rename:
            result = await processor_instance._install_and_rename(
                install_context
            )

            assert result == renamed_path
            mock_rename.assert_called_once_with(
                appimage_path=moved_path,
                app_name=install_context.app_name,
                app_config=install_context.app_config,
                catalog_entry=install_context.catalog_entry,
                storage_service=processor_instance.storage_service,
            )


class TestSetupIcon:
    """Test suite for _setup_icon method."""

    @pytest.mark.asyncio
    async def test_setup_icon_success(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Icon extracted successfully."""
        install_path = Path("/opt/appimages/test-app.AppImage")

        with patch(
            "my_unicorn.core.post_download.setup_appimage_icon",
            new_callable=AsyncMock,
        ) as mock_setup_icon:
            mock_setup_icon.return_value = {
                "success": True,
                "path": "/opt/icons/test-app.png",
                "source": "extracted",
            }

            result = await processor_instance._setup_icon(
                install_context, install_path
            )

            assert result["success"] is True
            assert result["path"] == "/opt/icons/test-app.png"
            mock_setup_icon.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_icon_extraction_error_logged(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Icon extraction error logged but doesn't raise exception."""
        install_path = Path("/opt/appimages/test-app.AppImage")

        with patch(
            "my_unicorn.core.post_download.setup_appimage_icon",
            new_callable=AsyncMock,
        ) as mock_setup_icon:
            # Icon extraction errors propagate, not caught silently
            mock_setup_icon.side_effect = RuntimeError(
                "Icon extraction failed"
            )

            with pytest.raises(RuntimeError, match="Icon extraction"):
                await processor_instance._setup_icon(
                    install_context, install_path
                )

    @pytest.mark.asyncio
    async def test_setup_icon_with_active_reporter(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Works with active progress reporter."""
        install_path = Path("/opt/appimages/test-app.AppImage")
        processor_instance.progress_reporter.is_active.return_value = True

        with patch(
            "my_unicorn.core.post_download.setup_appimage_icon",
            new_callable=AsyncMock,
        ) as mock_setup_icon:
            mock_setup_icon.return_value = {
                "success": True,
                "path": "/opt/icons/test-app.png",
            }

            result = await processor_instance._setup_icon(
                install_context, install_path
            )

            assert result["success"] is True
