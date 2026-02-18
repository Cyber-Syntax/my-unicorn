"""Tests for config management and cleanup in PostDownloadProcessor.

Tests the _create_or_update_config, _create_desktop_entry, and
_cleanup_after_update private methods with comprehensive edge case coverage.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.core.post_download import (
    OperationType,
    PostDownloadContext,
    PostDownloadProcessor,
)


class TestCreateOrUpdateConfig:
    """Test suite for _create_or_update_config method."""

    @pytest.mark.asyncio
    async def test_create_config_for_install_operation(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Uses create_app_config_v2 for INSTALL."""
        assert install_context.operation_type == OperationType.INSTALL
        install_path = Path("/opt/appimages/test-app.AppImage")
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash": "abc123",
                    "algorithm": "SHA256",
                }
            },
        }
        icon_result = {
            "success": True,
            "path": "/opt/icons/test-app.png",
            "source": "extracted",
        }

        with patch(
            "my_unicorn.core.post_download.create_app_config_v2",
            return_value={"success": True, "operation": "install"},
        ) as mock_create:
            result = await processor_instance._create_or_update_config(
                install_context, install_path, verify_result, icon_result
            )

            mock_create.assert_called_once_with(
                app_name=install_context.app_name,
                app_path=install_path,
                app_config=install_context.app_config,
                release=install_context.release,
                verify_result=verify_result,
                icon_result=icon_result,
                source=install_context.source,
                config_manager=processor_instance.config_manager,
            )
            assert result["success"] is True
            assert result["operation"] == "install"

    @pytest.mark.asyncio
    async def test_update_config_for_update_operation(
        self,
        processor_instance: PostDownloadProcessor,
        update_context: PostDownloadContext,
    ) -> None:
        """Uses update_app_config for UPDATE."""
        assert update_context.operation_type == OperationType.UPDATE
        install_path = Path("/opt/appimages/test-app.AppImage")
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash": "def456",
                    "algorithm": "SHA512",
                }
            },
        }
        icon_result = {
            "success": True,
            "path": "/opt/icons/test-app-new.png",
            "source": "extracted",
        }

        with (
            patch(
                "my_unicorn.core.post_download.update_app_config"
            ) as mock_update,
            patch(
                "my_unicorn.core.post_download.get_stored_hash",
                return_value="def456",
            ),
        ):
            result = await processor_instance._create_or_update_config(
                update_context, install_path, verify_result, icon_result
            )

            mock_update.assert_called_once()
            assert result["success"] is True
            assert result["operation"] == "update"

    @pytest.mark.asyncio
    async def test_create_config_with_verification_hash(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Hash stored in config when verification enabled."""
        install_path = Path("/opt/appimages/test-app.AppImage")
        verify_result = {
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash": "hash123abc456def",
                    "algorithm": "SHA256",
                }
            },
        }
        icon_result = {"success": True, "path": "/opt/icons/test-app.png"}

        with patch(
            "my_unicorn.core.post_download.create_app_config_v2",
            return_value={"success": True, "operation": "install"},
        ) as mock_create:
            await processor_instance._create_or_update_config(
                install_context, install_path, verify_result, icon_result
            )

            # Verify create_app_config_v2 was called with verification result
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["verify_result"] == verify_result

    @pytest.mark.asyncio
    async def test_create_config_without_verification_hash(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """No hash stored when verification disabled."""
        install_context.verify_downloads = False
        install_path = Path("/opt/appimages/test-app.AppImage")
        icon_result = {"success": True, "path": "/opt/icons/test-app.png"}

        with patch(
            "my_unicorn.core.post_download.create_app_config_v2",
            return_value={"success": True, "operation": "install"},
        ) as mock_create:
            await processor_instance._create_or_update_config(
                install_context, install_path, None, icon_result
            )

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["verify_result"] is None


class TestCreateDesktopEntry:
    """Test suite for _create_desktop_entry method."""

    @pytest.mark.asyncio
    async def test_create_desktop_entry_success(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Desktop entry created successfully."""
        install_path = Path("/opt/appimages/test-app.AppImage")
        icon_result = {"success": True, "path": "/opt/icons/test-app.png"}

        with patch(
            "my_unicorn.core.post_download.create_desktop_entry"
        ) as mock_create_desktop:
            mock_create_desktop.return_value = {
                "success": True,
                "path": (
                    "/home/user/.local/share/applications/test-app.desktop"
                ),
            }

            result = await processor_instance._create_desktop_entry(
                install_context, install_path, icon_result
            )

            assert result["success"] is True
            mock_create_desktop.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_desktop_entry_failure_non_fatal(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Failure logged but doesn't raise exception."""
        install_path = Path("/opt/appimages/test-app.AppImage")
        icon_result = {"success": True, "path": "/opt/icons/test-app.png"}

        with patch(
            "my_unicorn.core.post_download.create_desktop_entry"
        ) as mock_create_desktop:
            mock_create_desktop.side_effect = RuntimeError(
                "Cannot create desktop file"
            )

            result = await processor_instance._create_desktop_entry(
                install_context, install_path, icon_result
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_create_desktop_entry_with_icon(
        self,
        processor_instance: PostDownloadProcessor,
        install_context: PostDownloadContext,
    ) -> None:
        """Icon path passed correctly."""
        install_path = Path("/opt/appimages/test-app.AppImage")
        icon_result = {
            "success": True,
            "path": "/opt/icons/test-app-icon.png",
            "source": "extracted",
        }

        with patch(
            "my_unicorn.core.post_download.create_desktop_entry"
        ) as mock_create_desktop:
            mock_create_desktop.return_value = {"success": True}

            await processor_instance._create_desktop_entry(
                install_context, install_path, icon_result
            )

            call_kwargs = mock_create_desktop.call_args.kwargs
            assert call_kwargs["icon_result"] == icon_result


class TestCleanupAfterUpdate:
    """Test suite for _cleanup_after_update method."""

    @pytest.mark.asyncio
    async def test_cleanup_after_update_success(
        self, processor_instance: PostDownloadProcessor
    ) -> None:
        """Backup cleanup called successfully."""
        processor_instance.backup_service.cleanup_old_backups = MagicMock()

        await processor_instance._cleanup_after_update("test-app")

        processor_instance.backup_service.cleanup_old_backups.assert_called_once_with(
            "test-app"
        )

    @pytest.mark.asyncio
    async def test_cleanup_after_update_failure_non_fatal(
        self, processor_instance: PostDownloadProcessor
    ) -> None:
        """Cleanup failure logged but not fatal."""
        processor_instance.backup_service.cleanup_old_backups.side_effect = (
            OSError("Cannot cleanup backups")
        )

        # Should not raise exception
        await processor_instance._cleanup_after_update("test-app")

        processor_instance.backup_service.cleanup_old_backups.assert_called_once_with(
            "test-app"
        )

    @pytest.mark.asyncio
    async def test_cleanup_after_update_app_name_passed(
        self, processor_instance: PostDownloadProcessor
    ) -> None:
        """App name passed to backup service correctly."""
        processor_instance.backup_service.cleanup_old_backups = MagicMock()

        await processor_instance._cleanup_after_update("myapp-123")

        processor_instance.backup_service.cleanup_old_backups.assert_called_once_with(
            "myapp-123"
        )

    @pytest.mark.asyncio
    async def test_cleanup_after_update_no_backup_service(
        self, processor_instance: PostDownloadProcessor
    ) -> None:
        """Works when backup service is None."""
        processor_instance.backup_service = None

        # Should not raise exception
        await processor_instance._cleanup_after_update("test-app")
