#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the UpdateAsyncCommand class.

This module contains tests for the UpdateAsyncCommand class that handles
updating multiple AppImages concurrently using async I/O operations.
"""

import asyncio
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
from typing import Dict, Any, List, Set, Tuple, Optional, Union

from src.commands.update_all_async import UpdateAsyncCommand
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.auth_manager import GitHubAuthManager


class DummyApp:
    """Simple dummy app class for testing."""

    def __init__(self, name: str):
        """Initialize a dummy app with test version data.

        Args:
            name: App name for identification
        """
        self.name = name
        self.current = "1.0.0"
        self.latest = "1.1.0"


@pytest.fixture(autouse=True)
def no_github_actual_calls(monkeypatch):
    """Prevent actual GitHub API calls during tests.

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    # Stub out real GitHub API rate limit
    monkeypatch.setattr(GitHubAuthManager, "get_rate_limit_info", lambda: (100, 5000, None, True))
    yield


@pytest.fixture
def update_command():
    """Create an UpdateAsyncCommand instance for testing.

    Returns:
        UpdateAsyncCommand: A command instance
    """
    cmd = UpdateAsyncCommand()
    cmd.console = MagicMock()
    cmd.max_concurrent_updates = 2
    return cmd


@pytest.fixture
def mock_app_configs() -> List[Dict[str, Any]]:
    """Create mock app configurations for testing.

    Returns:
        List[Dict[str, Any]]: List of app config dictionaries
    """
    return [
        {
            "name": "app1",
            "config_file": "app1.json",
            "current": "1.0.0",
            "latest": "1.1.0",
        },
        {
            "name": "app2",
            "config_file": "app2.json",
            "current": "2.0.0",
            "latest": "2.1.0",
        },
        {
            "name": "app3",
            "config_file": "app3.json",
            "current": "3.0.0",
            "latest": "3.1.0",
        },
        {
            "name": "app4",
            "config_file": "app4.json",
            "current": "4.0.0",
            "latest": "4.1.0",
        },
    ]


def test_init(update_command: UpdateAsyncCommand) -> None:
    """Test initialization of the command."""
    assert update_command.max_concurrent_updates == 2
    assert update_command.semaphore is None


@pytest.mark.parametrize(
    "remaining,limit,expected_proceed,expected_count",
    [
        # Sufficient rate limits
        (100, 100, True, 4),
        # Exact boundary based on app count and requests per app
        (12, 100, True, 4),  # 4 apps × 3 requests = 12
        # Insufficient for all, but enough for some
        (6, 100, False, 2),  # 6 ÷ 3 = 2 apps
        # Not enough for any app
        (2, 100, False, 0),
    ],
)
def test_check_rate_limits(
    monkeypatch,
    update_command,
    mock_app_configs,
    remaining,
    limit,
    expected_proceed,
    expected_count,
):
    """Test rate limit checking with various scenarios."""
    # Configure the rate limit response
    monkeypatch.setattr(
        GitHubAuthManager, "get_rate_limit_info", lambda: (remaining, limit, "reset_time", True)
    )

    # Call the method
    can_proceed, filtered_apps, message = update_command._check_rate_limits(mock_app_configs)

    # Verify results
    assert can_proceed is expected_proceed
    assert len(filtered_apps) == expected_count

    # Check appropriate message
    if expected_proceed:
        assert "Sufficient" in message
    else:
        assert "Insufficient" in message
        if expected_count == 0:
            assert "Cannot process any apps" in message


@pytest.mark.asyncio
async def test_update_single_app_async_success(monkeypatch, update_command):
    """Test successful async update of a single app."""
    # Stub the core update method to return success
    monkeypatch.setattr(update_command, "_perform_app_update_core", lambda **kwargs: (True, {}))

    # Test data
    app_data = {
        "name": "test_app",
        "config_file": "test_app.json",
        "current": "1.0.0",
        "latest": "1.1.0",
    }

    # Call the method
    result = await update_command._update_single_app_async(
        app_data, is_batch=True, app_index=1, total_apps=1
    )

    # Verify success
    assert result is True


@pytest.mark.asyncio
async def test_update_single_app_async_failure(monkeypatch, update_command):
    """Test failed async update of a single app."""
    # Stub the core update method to return failure
    monkeypatch.setattr(update_command, "_perform_app_update_core", lambda **kwargs: (False, {}))

    # Test data
    app_data = {
        "name": "test_app",
        "config_file": "test_app.json",
        "current": "1.0.0",
        "latest": "1.1.0",
    }

    # Call the method
    result = await update_command._update_single_app_async(
        app_data, is_batch=True, app_index=1, total_apps=4
    )

    # Verify failure
    assert result is False


@pytest.mark.asyncio
async def test_update_single_app_async_exception(monkeypatch, update_command):
    """Test exception handling in async update of a single app."""
    # Stub the core update method to raise an exception
    monkeypatch.setattr(
        update_command,
        "_perform_app_update_core",
        lambda **kwargs: exec('raise Exception("Test error")'),
    )

    # Test data
    app_data = {
        "name": "test_app",
        "config_file": "test_app.json",
        "current": "1.0.0",
        "latest": "1.1.0",
    }

    # Call the method and expect it to handle the exception
    result = await update_command._update_single_app_async(
        app_data, is_batch=True, app_index=1, total_apps=4
    )

    # Verify failure due to exception
    assert result is False


@pytest.mark.asyncio
async def test_update_apps_async(monkeypatch, update_command, mock_app_configs):
    """Test the async update of multiple apps."""
    # Setup mocks for async operations
    mock_semaphore = AsyncMock()
    update_command.semaphore = mock_semaphore

    # Mock the single app update to return success/failure based on app index
    async def mock_update_single(app_data, is_batch, app_index, total_apps):
        # Make app1 and app3 succeed, app2 and app4 fail
        return app_index % 2 == 1  # Odd indices succeed

    # Apply mocks
    monkeypatch.setattr(update_command, "_update_single_app_async", mock_update_single)
    monkeypatch.setattr(update_command, "_display_rate_limit_info", MagicMock())

    # Create a mock for asyncio.gather to return predetermined results
    mock_results = [
        (True, {"status": "success", "message": "Updated app1", "elapsed": 1.0}),
        (False, {"status": "failed", "message": "Failed to update app2", "elapsed": 1.0}),
        (True, {"status": "success", "message": "Updated app3", "elapsed": 1.0}),
        (False, {"status": "failed", "message": "Failed to update app4", "elapsed": 1.0}),
    ]

    # Setup mock gather
    async def mock_gather(*args):
        return mock_results

    # Setup mock event loop
    mock_loop = MagicMock()
    mock_loop.run_until_complete = lambda x: asyncio.run(mock_gather())

    # Apply mocks
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: mock_loop)

    # Call the method
    update_command._update_apps_async(mock_app_configs)

    # Verify rate limits were displayed
    update_command._display_rate_limit_info.assert_called_once()
