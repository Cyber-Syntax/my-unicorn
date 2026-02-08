"""Tests for workflows.py - Multiple Apps Update Function.

This module tests concurrent update workflow functions for multiple apps
including semaphore limits, partial failures, and exception handling.
"""

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.core.update.workflows import update_multiple_apps
from my_unicorn.exceptions import UpdateError


class TestUpdateMultipleApps:
    """Tests for update_multiple_apps function."""

    @pytest.mark.asyncio
    async def test_update_multiple_apps_success(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_multiple_apps succeeds with multiple apps.

        Verifies that all apps are updated successfully and results
        are properly aggregated.
        """
        global_config = {"max_concurrent_downloads": 3}

        app_names = ["app1", "app2", "app3"]

        update_single_mock = AsyncMock(
            side_effect=[(True, None), (True, None), (True, None)]
        )
        update_cached_progress_mock = AsyncMock()

        results, _errors = await update_multiple_apps(
            app_names=app_names,
            force=False,
            update_infos=None,
            api_task_id=None,
            global_config=global_config,
            update_single_app_func=update_single_mock,
            update_cached_progress_func=update_cached_progress_mock,
            progress_reporter=mock_progress_reporter,
        )

        assert results == {"app1": True, "app2": True, "app3": True}
        assert _errors == {}
        assert update_single_mock.call_count == 3

    @pytest.mark.asyncio
    async def test_update_multiple_apps_semaphore_limit(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_multiple_apps respects semaphore concurrency limit.

        Verifies that concurrent updates are limited by the semaphore
        based on max_concurrent_downloads configuration.
        """
        global_config = {"max_concurrent_downloads": 2}

        app_names = ["app1", "app2", "app3", "app4"]

        async def track_concurrency(
            *args: Any, **kwargs: Any
        ) -> tuple[bool, None]:
            await asyncio.sleep(0.01)
            return True, None

        update_single_mock = AsyncMock(side_effect=track_concurrency)
        update_cached_progress_mock = AsyncMock()

        results, _errors = await update_multiple_apps(
            app_names=app_names,
            force=False,
            update_infos=None,
            api_task_id=None,
            global_config=global_config,
            update_single_app_func=update_single_mock,
            update_cached_progress_func=update_cached_progress_mock,
            progress_reporter=mock_progress_reporter,
        )

        assert len(results) == 4
        assert all(v is True for v in results.values())

    @pytest.mark.asyncio
    async def test_update_multiple_apps_partial_failures(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_multiple_apps handles partial failures gracefully.

        Verifies that when some apps fail and others succeed, both
        are captured in respective result and error dictionaries.
        """
        global_config = {"max_concurrent_downloads": 3}

        app_names = ["app1", "app2", "app3"]

        update_single_mock = AsyncMock(
            side_effect=[
                (True, None),
                (False, "Download failed"),
                (True, None),
            ]
        )
        update_cached_progress_mock = AsyncMock()

        results, errors = await update_multiple_apps(
            app_names=app_names,
            force=False,
            update_infos=None,
            api_task_id=None,
            global_config=global_config,
            update_single_app_func=update_single_mock,
            update_cached_progress_func=update_cached_progress_mock,
            progress_reporter=mock_progress_reporter,
        )

        assert results["app1"] is True
        assert results["app2"] is False
        assert results["app3"] is True
        assert "app2" in errors
        assert errors["app2"] == "Download failed"

    @pytest.mark.asyncio
    async def test_update_multiple_apps_exception_handling(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_multiple_apps handles exceptions per-app gracefully.

        Verifies that when an exception occurs for one app, other apps
        continue to be processed and exception is logged appropriately.
        """
        global_config = {"max_concurrent_downloads": 3}

        app_names = ["app1", "app2", "app3"]

        async def side_effect_with_exception(
            *args: Any, **kwargs: Any
        ) -> tuple[bool, None]:
            if args[0] == "app2":
                raise UpdateError(message="Process failed", context={})
            return True, None

        update_single_mock = AsyncMock(side_effect=side_effect_with_exception)
        update_cached_progress_mock = AsyncMock()

        results, _errors = await update_multiple_apps(
            app_names=app_names,
            force=False,
            update_infos=None,
            api_task_id=None,
            global_config=global_config,
            update_single_app_func=update_single_mock,
            update_cached_progress_func=update_cached_progress_mock,
            progress_reporter=mock_progress_reporter,
        )

        assert results["app1"] is True
        assert results["app3"] is True

    @pytest.mark.asyncio
    async def test_update_multiple_apps_with_cached_info(
        self,
        mock_progress_reporter: MagicMock,
        update_info_factory: Callable[..., UpdateInfo],
    ) -> None:
        """Test update_multiple_apps uses cached update info efficiently.

        Verifies that when update_infos are provided, they are passed to
        update_single_app_func and update_cached_progress_func is called.
        """
        global_config = {"max_concurrent_downloads": 3}

        app_names = ["app1", "app2"]
        update_infos = [
            update_info_factory(app_name="app1"),
            update_info_factory(app_name="app2"),
        ]

        update_single_mock = AsyncMock(
            side_effect=[(True, None), (True, None)]
        )
        update_cached_progress_mock = AsyncMock()

        results, _errors = await update_multiple_apps(
            app_names=app_names,
            force=False,
            update_infos=update_infos,
            api_task_id="task-123",
            global_config=global_config,
            update_single_app_func=update_single_mock,
            update_cached_progress_func=update_cached_progress_mock,
            progress_reporter=mock_progress_reporter,
        )

        assert results == {"app1": True, "app2": True}
        assert update_cached_progress_mock.call_count == 2
