"""Tests for workflows.py - Single App Update Advanced Scenarios.

This module tests advanced scenarios for single app updates including
backup creation, context errors, and data validation edge cases.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.core.update.workflows import update_single_app


class TestUpdateSingleAppAdvanced:
    """Tests for advanced update_single_app scenarios."""

    @pytest.mark.asyncio
    async def test_update_single_app_with_backup(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
        sample_release_data: Release,
    ) -> None:
        """Test update_single_app creates backup before download.

        Verifies that when current app exists, backup is created with
        correct app name and version parameters.
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

        call_args = mock_backup_service.create_backup.call_args
        assert call_args[0][1] == "test-app"
        assert call_args[0][2] == "1.0.0"

    @pytest.mark.asyncio
    async def test_update_single_app_context_error(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test update_single_app when context preparation returns error.

        Verifies that when prepare_context_func returns an error, the
        function returns failure with that error message.
        """
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
            },
            "max_concurrent_downloads": 3,
        }

        prepare_func = AsyncMock(
            return_value=(None, "Failed to load app configuration")
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

        assert success is False
        assert error == "Failed to load app configuration"

    @pytest.mark.asyncio
    async def test_update_single_app_invalid_update_info_type(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test update_single_app when context has invalid UpdateInfo type.

        Verifies that when context.update_info is not an UpdateInfo instance,
        the function returns failure with a descriptive error message.
        """
        global_config = {
            "directory": {
                "storage": Path("/test/storage"),
                "download": Path("/test/download"),
            },
            "max_concurrent_downloads": 3,
        }

        context = {
            "skip": False,
            "app_config": sample_app_config,
            "update_info": {"invalid": "dict not UpdateInfo"},
            "appimage_asset": MagicMock(),
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        prepare_func = AsyncMock(return_value=(context, None))
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

        assert success is False
        assert "Invalid update context" in error

    @pytest.mark.asyncio
    async def test_update_single_app_post_download_failure(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
        sample_release_data: Release,
    ) -> None:
        """Test update_single_app when post-download processing fails.

        Verifies that when post_download_processor.process returns
        success=False, error is returned appropriately.
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
        mock_post_processor.process.return_value = MagicMock(
            success=False, error="Icon extraction failed"
        )
        mock_post_processor.progress_reporter = MagicMock()

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
        assert error == "Icon extraction failed"

    @pytest.mark.asyncio
    async def test_update_single_app_missing_release_data(
        self,
        mock_session: AsyncMock,
        sample_app_config: dict[str, Any],
        sample_asset: Asset,
    ) -> None:
        """Test update_single_app when release_data is missing from UpdateInfo.

        Verifies that when UpdateInfo has release_data set to None,
        an UpdateError is raised appropriately.
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
            release_data=None,
            app_config=sample_app_config,
        )

        context = {
            "skip": False,
            "app_config": sample_app_config,
            "update_info": update_info,
            "appimage_asset": sample_asset,
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        prepare_func = AsyncMock(return_value=(context, None))
        mock_backup_service = MagicMock()
        mock_post_processor = MagicMock()
        mock_post_processor.progress_reporter = MagicMock()

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
        assert "release_data must be available" in error
