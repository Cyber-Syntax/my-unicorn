"""Tests for context.py helper functions.

This module tests helper functions used in update context preparation:
resolve_update_info, load_update_config, load_catalog_for_update, and
select_asset_for_update.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.update.context import (
    load_catalog_for_update,
    load_update_config,
    resolve_update_info,
    select_asset_for_update,
)
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.exceptions import ConfigurationError, UpdateError


class TestResolveUpdateInfo:
    """Tests for resolve_update_info function."""

    @pytest.mark.asyncio
    async def test_resolve_update_info_from_cache(
        self,
        mock_session: AsyncMock,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test resolve_update_info uses cached update info.

        Verifies that when update_info parameter is provided, the
        function returns it directly without calling check_single_update_func,
        enabling efficient use of cached data.
        """
        cached_info = update_info_factory(
            app_name="test-app",
            has_update=True,
        )
        check_func = AsyncMock()

        result_info, error = await resolve_update_info(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=cached_info,
            check_single_update_func=check_func,
        )

        assert result_info == cached_info
        assert error is None
        check_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_update_info_check_new_update(
        self,
        mock_session: AsyncMock,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test resolve_update_info checks for updates when not cached.

        Verifies that when no cached update_info is provided, the function
        calls check_single_update_func to fetch fresh update information.
        """
        fresh_info = update_info_factory(
            app_name="test-app",
            has_update=True,
            latest_version="2.0.0",
        )
        check_func = AsyncMock(return_value=fresh_info)

        result_info, error = await resolve_update_info(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=None,
            check_single_update_func=check_func,
        )

        assert result_info == fresh_info
        assert error is None
        check_func.assert_called_once_with("test-app", mock_session)

    @pytest.mark.asyncio
    async def test_resolve_update_info_check_failed_returns_error(
        self,
        mock_session: AsyncMock,
        error_update_info: UpdateInfo,
    ) -> None:
        """Test resolve_update_info returns error when check fails.

        Verifies that when check_single_update_func returns an UpdateInfo
        with error_reason set, resolve_update_info returns None for info
        and error message, indicating update check failure.
        """
        check_func = AsyncMock(return_value=error_update_info)

        result_info, error = await resolve_update_info(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=None,
            check_single_update_func=check_func,
        )

        assert result_info is None
        assert error is not None
        assert error == error_update_info.error_reason

    @pytest.mark.asyncio
    async def test_resolve_update_info_skip_when_no_update_and_not_forced(
        self,
        mock_session: AsyncMock,
        skip_update_info: UpdateInfo,
    ) -> None:
        """Test resolve_update_info returns skip condition correctly.

        Verifies that when has_update is False and force is False,
        the function returns the UpdateInfo unchanged to allow caller
        to handle the skip case (already up to date).
        """
        check_func = AsyncMock(return_value=skip_update_info)

        result_info, error = await resolve_update_info(
            app_name="test-app",
            session=mock_session,
            force=False,
            update_info=None,
            check_single_update_func=check_func,
        )

        assert result_info == skip_update_info
        assert error is None
        assert result_info.has_update is False


class TestLoadUpdateConfig:
    """Tests for load_update_config function."""

    def test_load_update_config_from_update_info_cache(
        self,
        update_info_factory: Callable[..., UpdateInfo],
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test load_update_config uses cached config from UpdateInfo.

        Verifies that when UpdateInfo contains cached app_config,
        the function returns it immediately without calling
        load_app_config_func, enabling efficient use of cached data.
        """
        update_info = update_info_factory(app_config=sample_app_config)
        load_func = MagicMock()

        config, error = load_update_config(
            app_name="test-app",
            update_info=update_info,
            load_app_config_func=load_func,
        )

        assert config == sample_app_config
        assert error is None
        load_func.assert_not_called()

    def test_load_update_config_from_filesystem(
        self,
        update_info_factory: Callable[..., UpdateInfo],
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test load_update_config loads from filesystem when not cached.

        Verifies that when UpdateInfo has no cached config, the function
        calls load_app_config_func with proper context to load config
        from filesystem.
        """
        update_info = update_info_factory(app_config=None)
        load_func = MagicMock(return_value=sample_app_config)

        config, error = load_update_config(
            app_name="test-app",
            update_info=update_info,
            load_app_config_func=load_func,
        )

        assert config == sample_app_config
        assert error is None
        load_func.assert_called_once_with("test-app", "prepare_update")

    def test_load_update_config_error(
        self,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test load_update_config returns error when load fails.

        Verifies that when load_app_config_func raises ConfigurationError,
        the function catches it, logs the error, and returns None with
        error message, enabling graceful error handling.
        """
        update_info = update_info_factory(app_config=None)
        load_func = MagicMock(
            side_effect=ConfigurationError("Invalid app config")
        )

        config, error = load_update_config(
            app_name="test-app",
            update_info=update_info,
            load_app_config_func=load_func,
        )

        assert config is None
        assert error is not None
        assert "Invalid app config" in error


class TestLoadCatalogForUpdate:
    """Tests for load_catalog_for_update function."""

    @pytest.mark.asyncio
    async def test_load_catalog_for_update_none_catalog(
        self,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test load_catalog_for_update returns None when no catalog_ref.

        Verifies that when app_config has no catalog_ref, the function
        returns None immediately without calling load_catalog_cached_func,
        allowing apps without catalog entries to proceed.
        """
        app_config = sample_app_config.copy()
        # Ensure no catalog_ref
        app_config.pop("catalog_ref", None)
        load_func = AsyncMock()

        result = await load_catalog_for_update(
            app_name="test-app",
            app_config=app_config,
            load_catalog_cached_func=load_func,
        )

        assert result is None
        load_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_catalog_for_update_success(
        self,
        sample_app_config: dict[str, Any],
        sample_catalog: dict[str, Any],
    ) -> None:
        """Test load_catalog_for_update loads catalog successfully.

        Verifies that when app_config has catalog_ref, the function
        calls load_catalog_cached_func and returns the loaded catalog data.
        """
        app_config = sample_app_config.copy()
        app_config["catalog_ref"] = "test-catalog"
        load_func = AsyncMock(return_value=sample_catalog)

        result = await load_catalog_for_update(
            app_name="test-app",
            app_config=app_config,
            load_catalog_cached_func=load_func,
        )

        assert result == sample_catalog
        load_func.assert_called_once_with("test-catalog")

    @pytest.mark.asyncio
    async def test_load_catalog_for_update_error(
        self,
        sample_app_config: dict[str, Any],
    ) -> None:
        """Test load_catalog_for_update raises UpdateError on file not found.

        Verifies that when load_catalog_cached_func raises FileNotFoundError,
        the function converts it to UpdateError with proper context,
        enabling consistent error handling.
        """
        app_config = sample_app_config.copy()
        app_config["catalog_ref"] = "missing-catalog"
        load_func = AsyncMock(side_effect=FileNotFoundError())

        with pytest.raises(UpdateError) as exc_info:
            await load_catalog_for_update(
                app_name="test-app",
                app_config=app_config,
                load_catalog_cached_func=load_func,
            )

        error = exc_info.value
        assert error.context["app_name"] == "test-app"
        assert error.context["catalog_ref"] == "missing-catalog"


class TestSelectAssetForUpdate:
    """Tests for select_asset_for_update function."""

    def test_select_asset_for_update_success(
        self,
        sample_asset: Asset,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test select_asset_for_update returns asset when found.

        Verifies that when update_info contains release_data with assets,
        the function successfully selects an AppImage asset and returns it
        with no error.
        """
        release_data = MagicMock()
        release_data.assets = [sample_asset]
        update_info = update_info_factory(release_data=release_data)

        # Mock select_best_appimage_asset to return our asset
        with patch(
            "my_unicorn.core.update.context.select_best_appimage_asset",
            return_value=sample_asset,
        ):
            asset, error = select_asset_for_update(
                app_name="test-app",
                update_info=update_info,
                catalog_entry=None,
            )

        assert asset == sample_asset
        assert error is None

    def test_select_asset_for_update_no_release_data(
        self,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test select_asset_for_update returns error when no release data.

        Verifies that when update_info has no release_data, the function
        returns None for asset and appropriate error message, enabling
        graceful handling of missing release information.
        """
        update_info = update_info_factory(release_data=None)

        asset, error = select_asset_for_update(
            app_name="test-app",
            update_info=update_info,
            catalog_entry=None,
        )

        assert asset is None
        assert error is not None
        assert "No release data" in error

    def test_select_asset_for_update_appimage_not_found(
        self,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test select_asset_for_update returns error when AppImage not found.

        Verifies that when no suitable AppImage asset is found in release data,
        the function returns None for asset and informative error message.
        """
        release_data = MagicMock()
        release_data.assets = []
        update_info = update_info_factory(release_data=release_data)

        # Mock select_best_appimage_asset to return None
        with patch(
            "my_unicorn.core.update.context.select_best_appimage_asset",
            return_value=None,
        ):
            asset, error = select_asset_for_update(
                app_name="test-app",
                update_info=update_info,
                catalog_entry=None,
            )

        assert asset is None
        assert error is not None
        assert "AppImage not found" in error
