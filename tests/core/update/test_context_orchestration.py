"""Tests for context.py orchestration function.

This module tests the main prepare_update_context orchestration function
which coordinates all helper functions to prepare the complete update context.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.update.context import prepare_update_context
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.exceptions import ConfigurationError, UpdateError


@pytest.fixture
def app_config_with_source() -> dict[str, Any]:
    """Provide app config with proper source dict structure.

    Returns:
        Application configuration with GitHub source dictionary
        for testing orchestration functions.

    """
    return {
        "owner": "test-owner",
        "repo": "test-repo",
        "source": {
            "owner": "test-owner",
            "repo": "test-repo",
            "prerelease": False,
        },
        "appimage": {
            "name": "test-app.AppImage",
            "version": "1.0.0",
            "characteristic_suffix": ["-x86_64", "-linux"],
        },
        "icon": {
            "installed": True,
            "url": "https://example.com/icon.png",
        },
    }


class TestPrepareUpdateContext:
    """Tests for prepare_update_context orchestration function."""

    @pytest.mark.asyncio
    async def test_prepare_update_context_happy_path(
        self,
        mock_session: AsyncMock,
        update_info_factory: Callable[..., UpdateInfo],
        app_config_with_source: dict[str, Any],
        sample_asset: Asset,
    ) -> None:
        """Test prepare_update_context with successful update flow.

        Verifies the happy path where all functions succeed and return
        complete context with app_config, update_info, GitHub config,
        catalog_entry, and appimage_asset, ready for update execution.
        """
        release_data = MagicMock()
        release_data.assets = [sample_asset]
        update_info = update_info_factory(
            release_data=release_data,
            has_update=True,
        )

        check_func = AsyncMock(return_value=update_info)
        load_config_func = MagicMock(return_value=app_config_with_source)
        load_catalog_func = AsyncMock(return_value=None)

        with patch(
            "my_unicorn.core.update.context.select_best_appimage_asset",
            return_value=sample_asset,
        ):
            context, error = await prepare_update_context(
                app_name="test-app",
                session=mock_session,
                force=False,
                update_info=None,
                check_single_update_func=check_func,
                load_app_config_func=load_config_func,
                load_catalog_cached_func=load_catalog_func,
            )

        assert error is None
        assert context is not None
        assert context["app_config"] == app_config_with_source
        assert context["update_info"] == update_info
        assert context["owner"] == "test-owner"
        assert context["repo"] == "test-repo"
        assert context["catalog_entry"] is None
        assert context["appimage_asset"] == sample_asset

    @pytest.mark.asyncio
    async def test_prepare_update_context_skip_path(
        self,
        mock_session: AsyncMock,
        skip_update_info: UpdateInfo,
    ) -> None:
        """Test prepare_update_context returns skip context when up to date.

        Verifies that when update_info indicates no update available and
        force is False, the function returns skip context with success=True
        and skip=True, allowing caller to handle skip case.
        """
        check_func = AsyncMock(return_value=skip_update_info)
        load_config_func = MagicMock()
        load_catalog_func = AsyncMock()

        context, error = await prepare_update_context(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=None,
            check_single_update_func=check_func,
            load_app_config_func=load_config_func,
            load_catalog_cached_func=load_catalog_func,
        )

        assert error is None
        assert context is not None
        assert context.get("skip") is True
        assert context.get("success") is True
        # These should not be called in skip case
        load_config_func.assert_not_called()
        load_catalog_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_prepare_update_context_resolve_info_error(
        self,
        mock_session: AsyncMock,
        error_update_info: UpdateInfo,
    ) -> None:
        """Test prepare_update_context returns error from resolve_update_info.

        Verifies that when resolve_update_info returns an error (update check
        failed), prepare_update_context propagates the error and does not
        proceed with config loading.
        """
        check_func = AsyncMock(return_value=error_update_info)
        load_config_func = MagicMock()
        load_catalog_func = AsyncMock()

        context, error = await prepare_update_context(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=None,
            check_single_update_func=check_func,
            load_app_config_func=load_config_func,
            load_catalog_cached_func=load_catalog_func,
        )

        assert context is None
        assert error is not None
        assert error == error_update_info.error_reason
        load_config_func.assert_not_called()
        load_catalog_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_prepare_update_context_load_config_error(
        self,
        mock_session: AsyncMock,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test prepare_update_context returns error from load_update_config.

        Verifies that when load_update_config fails (config doesn't exist),
        prepare_update_context propagates the error and does not proceed
        with catalog loading or asset selection.
        """
        update_info = update_info_factory(has_update=True)
        check_func = AsyncMock(return_value=update_info)
        load_config_func = MagicMock(
            side_effect=ConfigurationError("Config not found")
        )
        load_catalog_func = AsyncMock()

        context, error = await prepare_update_context(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=None,
            check_single_update_func=check_func,
            load_app_config_func=load_config_func,
            load_catalog_cached_func=load_catalog_func,
        )

        assert context is None
        assert error is not None
        assert "Config not found" in error
        load_catalog_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_prepare_update_context_load_catalog_error(
        self,
        mock_session: AsyncMock,
        update_info_factory: Callable[..., UpdateInfo],
        app_config_with_source: dict[str, Any],
    ) -> None:
        """Test prepare_update_context raises load_catalog_for_update error.

        Verifies that when load_catalog_for_update raises UpdateError
        (catalog referenced but not found), the error propagates up from
        prepare_update_context, indicating catalog loading failure.
        """
        catalog_config = app_config_with_source.copy()
        catalog_config["catalog_ref"] = "missing-catalog"

        update_info = update_info_factory(has_update=True)
        check_func = AsyncMock(return_value=update_info)
        load_config_func = MagicMock(return_value=catalog_config)
        load_catalog_func = AsyncMock(
            side_effect=UpdateError("Catalog not found")
        )

        with pytest.raises(UpdateError) as exc_info:
            await prepare_update_context(
                app_name="test-app",
                session=mock_session,
                force=False,
                update_info=None,
                check_single_update_func=check_func,
                load_app_config_func=load_config_func,
                load_catalog_cached_func=load_catalog_func,
            )

        assert "Catalog not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_prepare_update_context_select_asset_error(
        self,
        mock_session: AsyncMock,
        update_info_factory: Callable[..., UpdateInfo],
        app_config_with_source: dict[str, Any],
    ) -> None:
        """Test prepare_update_context returns select_asset_for_update error.

        Verifies that when select_asset_for_update fails (no AppImage found),
        prepare_update_context propagates the error and returns error context.
        """
        release_data = MagicMock()
        release_data.assets = []
        update_info = update_info_factory(
            release_data=release_data,
            has_update=True,
        )

        check_func = AsyncMock(return_value=update_info)
        load_config_func = MagicMock(return_value=app_config_with_source)
        load_catalog_func = AsyncMock(return_value=None)

        with patch(
            "my_unicorn.core.update.context.select_best_appimage_asset",
            return_value=None,
        ):
            context, error = await prepare_update_context(
                app_name="test-app",
                session=mock_session,
                force=False,
                update_info=None,
                check_single_update_func=check_func,
                load_app_config_func=load_config_func,
                load_catalog_cached_func=load_catalog_func,
            )

        assert context is None
        assert error is not None
        assert "AppImage not found" in error
