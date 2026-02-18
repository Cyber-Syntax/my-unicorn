"""Tests for workflows.py - Single App Update Function.

This module tests individual app update orchestration including context
preparation, download, processing, and error handling.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Release
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.core.update.workflows import update_single_app
from my_unicorn.exceptions import UpdateError, VerificationError


class TestUpdateSingleApp:
    """Tests for update_single_app function."""

    @pytest.mark.asyncio
    async def test_update_single_app_skip_scenario(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test update_single_app skips when no update available.

        Verifies that when prepare_context_func returns skip=True,
        the function returns (True, None) without downloading.
        """
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
            },
            "max_concurrent_downloads": 3,
        }

        prepare_func = AsyncMock(
            return_value=(
                {
                    "skip": True,
                    "app_config": sample_app_config,
                },
                None,
            )
        )
        backup_service = MagicMock()
        post_processor = MagicMock()

        success, error = await update_single_app(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=None,
            global_config=global_config,
            prepare_context_func=prepare_func,
            backup_service=backup_service,
            post_download_processor=post_processor,
        )

        assert success is True
        assert error is None
        backup_service.create_backup.assert_not_called()
        post_processor.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_single_app_success(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
        sample_release_data: Release,
    ) -> None:
        """Test update_single_app succeeds with valid data.

        Verifies complete successful update workflow including context
        preparation, backup, download, and post-processing.
        """
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
            },
            "max_concurrent_downloads": 3,
        }

        update_info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="2.0.0",
            has_update=True,
            release_url="https://example.com/release",
            prerelease=False,
            original_tag_name="v2.0.0",
            release_data=sample_release_data,
            app_config=sample_app_config,
        )

        context = {
            "skip": False,
            "app_config": sample_app_config,
            "update_info": update_info,
            "appimage_asset": sample_release_data.assets[0],
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        prepare_func = AsyncMock(return_value=(context, None))

        mock_backup_service = MagicMock()
        mock_backup_service.create_backup.return_value = Path(
            "/test/backup/app.backup"
        )

        mock_post_processor = AsyncMock()
        mock_post_processor.process.return_value = MagicMock(success=True)
        mock_post_processor.progress_reporter = MagicMock()

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_class:
            mock_download_instance = AsyncMock()
            mock_download_instance.download_appimage.return_value = Path(
                "/test/download/app.AppImage"
            )
            mock_download_class.return_value = mock_download_instance

            with patch(
                "my_unicorn.core.update.workflows.Path.exists"
            ) as mock_exists:
                mock_exists.return_value = True

                success, error = await update_single_app(
                    app_name="test-app",
                    session=mock_session,
                    force=False,
                    update_info=update_info,
                    global_config=global_config,
                    prepare_context_func=prepare_func,
                    backup_service=mock_backup_service,
                    post_download_processor=mock_post_processor,
                )

        assert success is True
        assert error is None
        mock_backup_service.create_backup.assert_called_once()
        mock_post_processor.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_single_app_download_failure(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
        sample_release_data: Release,
    ) -> None:
        """Test update_single_app handles download failure.

        Verifies that when DownloadService.download_appimage returns None,
        an UpdateError is raised and caught, returning failure status.
        """
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
            },
            "max_concurrent_downloads": 3,
        }

        update_info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="2.0.0",
            has_update=True,
            release_url="https://example.com/release",
            prerelease=False,
            original_tag_name="v2.0.0",
            release_data=sample_release_data,
            app_config=sample_app_config,
        )

        context = {
            "skip": False,
            "app_config": sample_app_config,
            "update_info": update_info,
            "appimage_asset": sample_release_data.assets[0],
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        prepare_func = AsyncMock(return_value=(context, None))
        mock_backup_service = MagicMock()
        mock_post_processor = AsyncMock()
        mock_post_processor.progress_reporter = MagicMock()

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_class:
            mock_download_instance = AsyncMock()
            mock_download_instance.download_appimage.return_value = None
            mock_download_class.return_value = mock_download_instance

            success, error = await update_single_app(
                app_name="test-app",
                session=mock_session,
                force=False,
                update_info=update_info,
                global_config=global_config,
                prepare_context_func=prepare_func,
                backup_service=mock_backup_service,
                post_download_processor=mock_post_processor,
            )

        assert success is False
        assert error is not None
        assert "Download failed" in error

    @pytest.mark.asyncio
    async def test_update_single_app_verification_failure(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
        sample_release_data: Release,
    ) -> None:
        """Test update_single_app handles verification failure.

        Verifies that when VerificationError is raised during processing,
        error is caught and returned without propagation.
        """
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
            },
            "max_concurrent_downloads": 3,
        }

        update_info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="2.0.0",
            has_update=True,
            release_url="https://example.com/release",
            prerelease=False,
            original_tag_name="v2.0.0",
            release_data=sample_release_data,
            app_config=sample_app_config,
        )

        context = {
            "skip": False,
            "app_config": sample_app_config,
            "update_info": update_info,
            "appimage_asset": sample_release_data.assets[0],
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        prepare_func = AsyncMock(return_value=(context, None))
        mock_backup_service = MagicMock()
        mock_post_processor = AsyncMock()
        mock_post_processor.progress_reporter = MagicMock()
        mock_post_processor.process.side_effect = VerificationError(
            "Hash mismatch"
        )

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_class:
            mock_download_instance = AsyncMock()
            mock_download_instance.download_appimage.return_value = Path(
                "/test/download/app.AppImage"
            )
            mock_download_class.return_value = mock_download_instance

            success, error = await update_single_app(
                app_name="test-app",
                session=mock_session,
                force=False,
                update_info=update_info,
                global_config=global_config,
                prepare_context_func=prepare_func,
                backup_service=mock_backup_service,
                post_download_processor=mock_post_processor,
            )

        assert success is False
        assert error is not None
        assert "Hash mismatch" in str(error)

    @pytest.mark.asyncio
    async def test_update_single_app_unexpected_error(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
        sample_release_data: Release,
    ) -> None:
        """Test update_single_app raises UpdateError for unexpected exceptions.

        Verifies that when an unexpected exception occurs (not UpdateError
        or VerificationError), it's wrapped in UpdateError and propagated.
        """
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
            },
            "max_concurrent_downloads": 3,
        }

        update_info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="2.0.0",
            has_update=True,
            release_url="https://example.com/release",
            prerelease=False,
            original_tag_name="v2.0.0",
            release_data=sample_release_data,
            app_config=sample_app_config,
        )

        context = {
            "skip": False,
            "app_config": sample_app_config,
            "update_info": update_info,
            "appimage_asset": sample_release_data.assets[0],
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        prepare_func = AsyncMock(return_value=(context, None))
        mock_backup_service = MagicMock()
        mock_post_processor = AsyncMock()
        mock_post_processor.progress_reporter = MagicMock()
        mock_post_processor.process.side_effect = RuntimeError(
            "Unexpected error"
        )

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_class:
            mock_download_instance = AsyncMock()
            mock_download_instance.download_appimage.return_value = Path(
                "/test/download/app.AppImage"
            )
            mock_download_class.return_value = mock_download_instance

            with pytest.raises(UpdateError) as exc_info:
                await update_single_app(
                    app_name="test-app",
                    session=mock_session,
                    force=False,
                    update_info=update_info,
                    global_config=global_config,
                    prepare_context_func=prepare_func,
                    backup_service=mock_backup_service,
                    post_download_processor=mock_post_processor,
                )

            assert "Update failed" in str(exc_info.value)
            assert exc_info.value.context.get("app_name") == "test-app"
