#!/usr/bin/env python3
"""Tests for the update_all_async module.

This module contains tests for the SelectiveUpdateCommand class that handles
updating multiple AppImages concurrently using async I/O operations.
"""

import pytest

from my_unicorn.auth_manager import GitHubAuthManager

# Import the classes to test
from my_unicorn.commands.update_all_async import SelectiveUpdateCommand


class DummyApp:
    def __init__(self, name):
        self.name = name
        self.current = "1.0.0"
        self.latest = "1.1.0"


@pytest.fixture(autouse=True)
def no_github_actual_calls(monkeypatch):
    # Stub out real GitHub API rate limit
    monkeypatch.setattr(GitHubAuthManager, "get_rate_limit_info", lambda: (100, 5000, None, True))
    yield


@pytest.fixture
def cmd():
    return SelectiveUpdateCommand()


@pytest.mark.parametrize(
    "remaining,limit,apps,expected",
    [
        # enough remaining for all
        (9, 10, [DummyApp(i) for i in range(3)], True),
        # exact boundary: 3 apps *3 =9 remaining
        (9, 10, [DummyApp(i) for i in range(3)], True),
    ],
)
def test_check_rate_limits_sufficient(monkeypatch, cmd, remaining, limit, apps, expected):
    # stub rate limit
    monkeypatch.setattr(
        GitHubAuthManager, "get_rate_limit_info", lambda: (remaining, limit, None, True)
    )
    can_proceed, filtered, msg = cmd._check_rate_limits(
        [{"name": f"app{i}"} for i in range(len(apps))]
    )
    assert can_proceed is expected
    assert len(filtered) == len(apps)
    assert "Sufficient API rate limits" in msg


@pytest.mark.parametrize(
    "remaining,limit,apps,expected_count",
    [
        # insufficient for all: 5 remaining can process 1 app (5//3 =1)
        (5, 100, [DummyApp(i) for i in range(3)], 1),
        # zero remaining
        (0, 100, [DummyApp(i) for i in range(2)], 0),
    ],
)
def test_check_rate_limits_insufficient(monkeypatch, cmd, remaining, limit, apps, expected_count):
    monkeypatch.setattr(
        GitHubAuthManager, "get_rate_limit_info", lambda: (remaining, limit, None, False)
    )
    can_proceed, filtered, msg = cmd._check_rate_limits(
        [{"name": f"app{i}"} for i in range(len(apps))]
    )
    assert can_proceed is False
    assert len(filtered) == expected_count
    assert ("Insufficient API rate limits" in msg) or ("Cannot process any apps" in msg)


@pytest.mark.parametrize(
    "batch_mode,user_input,expected",
    [
        (True, None, True),
        (False, "y", True),
        (False, "n", False),
    ],
)
def test_confirm_updates(monkeypatch, cmd, batch_mode, user_input, expected):
    # configure batch mode
    cmd.global_config.batch_mode = batch_mode
    apps = [{"name": "app1", "current": "0.1", "latest": "0.2"}]
    if not batch_mode:
        # stub input
        monkeypatch.setattr("builtins.input", lambda prompt="": user_input)
    result = cmd._confirm_updates(apps)
    assert result is expected


@pytest.mark.asyncio
async def test_update_single_app_async_success(monkeypatch, cmd):
    # Stub core update to return success
    monkeypatch.setattr(cmd, "_perform_app_update_core", lambda **kwargs: (True, {}))
    app_data = {"name": "app1", "latest": "2.0"}
    success, result = await cmd._update_single_app_async(app_data, app_index=1, total_apps=1)
    assert success is True


@pytest.mark.asyncio
async def test_update_single_app_async_failure(monkeypatch, cmd):
    # Stub core update to return failure
    monkeypatch.setattr(cmd, "_perform_app_update_core", lambda **kwargs: (False, {}))
    app_data = {"name": "app1", "latest": "2.0"}
    success, result = await cmd._update_single_app_async(app_data, app_index=1, total_apps=1)
    assert success is False
