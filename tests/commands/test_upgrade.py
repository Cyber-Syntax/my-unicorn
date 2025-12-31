"""Tests for UpgradeHandler (replacement for self-update command).

These tests mirror the previous self-update tests but use the new `upgrade`
command verb and the `UpgradeHandler` import.
"""

from argparse import Namespace
from unittest.mock import AsyncMock

import pytest

from my_unicorn.auth import GitHubAuthManager
from my_unicorn.commands.upgrade import UpgradeHandler
from my_unicorn.config import ConfigManager
from my_unicorn.update import UpdateManager


@pytest.mark.asyncio
async def test_execute_check_only_update_available(mocker) -> None:
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = UpgradeHandler(config_manager, auth_manager, update_manager)
    mocker.patch(
        "my_unicorn.commands.upgrade.check_for_self_update",
        new=AsyncMock(return_value=True),
    )
    mock_logger = mocker.patch("my_unicorn.commands.upgrade.logger")
    args = Namespace(check_only=True)
    await handler.execute(args)
    mock_logger.info.assert_any_call("🔍 Checking for my-unicorn upgrade...")
    mock_logger.info.assert_any_call("")
    mock_logger.info.assert_any_call(
        "Run 'my-unicorn upgrade' to install the upgrade."
    )


@pytest.mark.asyncio
async def test_execute_check_only_no_update(mocker) -> None:
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = UpgradeHandler(config_manager, auth_manager, update_manager)
    mocker.patch(
        "my_unicorn.commands.upgrade.check_for_self_update",
        new=AsyncMock(return_value=False),
    )
    mock_logger = mocker.patch("my_unicorn.commands.upgrade.logger")
    args = Namespace(check_only=True)
    await handler.execute(args)
    mock_logger.info.assert_any_call("✅ my-unicorn is up to date")


@pytest.mark.asyncio
async def test_execute_perform_update_success(mocker) -> None:
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = UpgradeHandler(config_manager, auth_manager, update_manager)

    async def fake_check_for_self_update(refresh_cache: bool = False):
        return True

    async def fake_perform_self_update(refresh_cache: bool = False):
        return True

    mocker.patch(
        "my_unicorn.commands.upgrade.check_for_self_update",
        side_effect=fake_check_for_self_update,
    )
    mocker.patch(
        "my_unicorn.commands.upgrade.perform_self_update",
        side_effect=fake_perform_self_update,
    )
    mock_logger = mocker.patch("my_unicorn.commands.upgrade.logger")
    args = Namespace(check_only=False)
    await handler.execute(args)
    mock_logger.info.assert_any_call("")
    mock_logger.info.assert_any_call("🚀 Starting upgrade...")
    mock_logger.info.assert_any_call("✅ Upgrade completed successfully!")


@pytest.mark.asyncio
async def test_execute_perform_update_no_update(mocker) -> None:
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = UpgradeHandler(config_manager, auth_manager, update_manager)
    mocker.patch(
        "my_unicorn.commands.upgrade.check_for_self_update",
        new=AsyncMock(return_value=False),
    )
    mock_logger = mocker.patch("my_unicorn.commands.upgrade.logger")
    args = Namespace(check_only=False)
    await handler.execute(args)
    mock_logger.info.assert_any_call("✅ my-unicorn is already up to date")


@pytest.mark.asyncio
async def test_execute_perform_update_failure(mocker) -> None:
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = UpgradeHandler(config_manager, auth_manager, update_manager)

    async def fake_check_for_self_update(refresh_cache: bool = False):
        return True

    async def fake_perform_self_update(refresh_cache: bool = False):
        return False

    mocker.patch(
        "my_unicorn.commands.upgrade.check_for_self_update",
        side_effect=fake_check_for_self_update,
    )
    mocker.patch(
        "my_unicorn.commands.upgrade.perform_self_update",
        side_effect=fake_perform_self_update,
    )
    mock_logger = mocker.patch("my_unicorn.commands.upgrade.logger")
    args = Namespace(check_only=False)
    await handler.execute(args)
    mock_logger.info.assert_any_call(
        "❌ Upgrade failed. Please try again or update manually."
    )
