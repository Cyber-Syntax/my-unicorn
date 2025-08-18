"""Tests for SelfUpdateHandler self-update command.

These tests verify the behavior of the self-update command handler,
including checking for updates and performing updates.
"""

from argparse import Namespace

import pytest

from my_unicorn.auth import GitHubAuthManager
from my_unicorn.commands.self_update import SelfUpdateHandler
from my_unicorn.config import ConfigManager
from my_unicorn.update import UpdateManager


@pytest.mark.asyncio
async def test_execute_check_only_update_available(mocker) -> None:
    """Test check_only mode when an update is available."""
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = SelfUpdateHandler(config_manager, auth_manager, update_manager)
    # Patch the underlying SelfUpdater.check_for_update to simulate update available
    mocker.patch("my_unicorn.repo.SelfUpdater.check_for_update", return_value=True)
    args = Namespace(check_only=True)
    print_mock = mocker.patch("builtins.print")
    await handler.execute(args)
    print_mock.assert_any_call("🔍 Checking for my-unicorn updates...")
    print_mock.assert_any_call("\nRun 'my-unicorn self-update' to install the update.")


@pytest.mark.asyncio
async def test_execute_check_only_no_update(mocker) -> None:
    """Test check_only mode when no update is available."""
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = SelfUpdateHandler(config_manager, auth_manager, update_manager)
    mocker.patch("my_unicorn.repo.SelfUpdater.check_for_update", return_value=False)
    args = Namespace(check_only=True)
    print_mock = mocker.patch("builtins.print")
    await handler.execute(args)
    print_mock.assert_any_call("✅ my-unicorn is up to date")


@pytest.mark.asyncio
async def test_execute_perform_update_success(mocker) -> None:
    """Test performing self-update when update is available and succeeds."""
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = SelfUpdateHandler(config_manager, auth_manager, update_manager)

    # Patch check_for_self_update and perform_self_update as async mocks
    async def fake_check_for_self_update():
        return True

    async def fake_perform_self_update():
        return True

    mocker.patch(
        "my_unicorn.commands.self_update.check_for_self_update",
        side_effect=fake_check_for_self_update,
    )
    mocker.patch(
        "my_unicorn.commands.self_update.perform_self_update",
        side_effect=fake_perform_self_update,
    )
    args = Namespace(check_only=False)
    print_mock = mocker.patch("builtins.print")
    await handler.execute(args)
    print_mock.assert_any_call("\n🚀 Starting self-update...")
    print_mock.assert_any_call("✅ Self-update completed successfully!")
    print_mock.assert_any_call(
        "Please restart your terminal or run 'hash -r' to refresh the command cache."
    )


@pytest.mark.asyncio
async def test_execute_perform_update_no_update(mocker) -> None:
    """Test performing self-update when no update is available."""
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = SelfUpdateHandler(config_manager, auth_manager, update_manager)
    mocker.patch("my_unicorn.repo.SelfUpdater.check_for_update", return_value=False)
    args = Namespace(check_only=False)
    print_mock = mocker.patch("builtins.print")
    await handler.execute(args)
    print_mock.assert_any_call("✅ my-unicorn is already up to date")


@pytest.mark.asyncio
async def test_execute_perform_update_failure(mocker) -> None:
    """Test performing self-update when update fails."""
    config_manager = ConfigManager()
    auth_manager = GitHubAuthManager()
    update_manager = UpdateManager(config_manager)
    handler = SelfUpdateHandler(config_manager, auth_manager, update_manager)

    # Patch check_for_self_update and perform_self_update as async mocks
    async def fake_check_for_self_update():
        return True

    async def fake_perform_self_update():
        return False

    mocker.patch(
        "my_unicorn.commands.self_update.check_for_self_update",
        side_effect=fake_check_for_self_update,
    )
    mocker.patch(
        "my_unicorn.commands.self_update.perform_self_update",
        side_effect=fake_perform_self_update,
    )
    args = Namespace(check_only=False)
    print_mock = mocker.patch("builtins.print")
    await handler.execute(args)
    print_mock.assert_any_call("❌ Self-update failed. Please try again or update manually.")
