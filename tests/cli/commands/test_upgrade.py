"""Tests for UpgradeHandler (replacement for self-update command).

These tests mirror the previous self-update tests but use the new `upgrade`
command verb and the `UpgradeHandler` import.
"""

from argparse import Namespace
from unittest.mock import AsyncMock, patch

import pytest

from my_unicorn.cli.commands.upgrade import UpgradeHandler


@pytest.mark.asyncio
async def test_execute_perform_update_calls_with_version() -> None:
    """Upgrade calls perform_self_update with the resolved version tag."""
    handler = UpgradeHandler()
    with (
        patch(
            "my_unicorn.cli.commands.upgrade.perform_self_update"
        ) as mock_perform,
        patch(
            "my_unicorn.cli.commands.upgrade.should_perform_self_update",
            AsyncMock(return_value=(True, "2.0.1")),
        ) as mock_check,
    ):
        mock_perform.return_value = (
            None  # execvp replaces process; never returns on success
        )
        args = Namespace(check=False)
        await handler.execute(args)
        mock_check.assert_called_once()
        mock_perform.assert_called_once_with("2.0.1")


@pytest.mark.asyncio
async def test_execute_perform_update_failure() -> None:
    """Upgrade flow logs failure when execvp returns (i.e. did not replace process)."""
    handler = UpgradeHandler()
    with (
        patch(
            "my_unicorn.cli.commands.upgrade.perform_self_update"
        ) as mock_perform,
        patch(
            "my_unicorn.cli.commands.upgrade.should_perform_self_update",
            AsyncMock(return_value=(True, "2.0.1")),
        ) as mock_check,
        patch("my_unicorn.cli.commands.upgrade.logger") as mock_logger,
    ):
        mock_perform.return_value = False  # execvp failed, returned instead
        args = Namespace(check=False)
        await handler.execute(args)
        mock_check.assert_called_once()
        mock_perform.assert_called_once_with("2.0.1")
        mock_logger.info.assert_any_call(
            "❌ Upgrade failed. Please try again or update manually."
        )


@pytest.mark.asyncio
async def test_execute_skips_when_latest() -> None:
    """Upgrade is skipped when already on the latest release."""
    handler = UpgradeHandler()
    with (
        patch(
            "my_unicorn.cli.commands.upgrade.should_perform_self_update",
            AsyncMock(return_value=(False, "2.0.0")),
        ) as mock_check,
        patch(
            "my_unicorn.cli.commands.upgrade.perform_self_update"
        ) as mock_perform,
        patch("my_unicorn.cli.commands.upgrade.logger") as mock_logger,
    ):
        args = Namespace(check=False)
        await handler.execute(args)
        mock_check.assert_called_once()
        mock_perform.assert_not_called()
        mock_logger.info.assert_any_call(
            "✨ You are already running the latest my-unicorn (%s).",
            "2.0.0",
        )


@pytest.mark.asyncio
async def test_execute_skips_when_version_unavailable() -> None:
    """Upgrade is skipped when latest version cannot be determined."""
    handler = UpgradeHandler()
    with (
        patch(
            "my_unicorn.cli.commands.upgrade.should_perform_self_update",
            AsyncMock(return_value=(False, None)),
        ),
        patch(
            "my_unicorn.cli.commands.upgrade.perform_self_update"
        ) as mock_perform,
        patch("my_unicorn.cli.commands.upgrade.__version__", "2.0.0"),
    ):
        args = Namespace(check=False)
        await handler.execute(args)
        mock_perform.assert_not_called()


@pytest.mark.asyncio
async def test_execute_check_version_newer_available() -> None:
    """Check version displays current and latest versions when update is available."""
    handler = UpgradeHandler()
    with (
        patch(
            "my_unicorn.cli.commands.upgrade.should_perform_self_update",
            AsyncMock(return_value=(True, "2.0.1")),
        ) as mock_check,
        patch("my_unicorn.cli.commands.upgrade.logger") as mock_logger,
        patch("my_unicorn.cli.commands.upgrade.__version__", "2.0.0"),
    ):
        args = Namespace(check=True)
        await handler.execute(args)
        mock_check.assert_called_once()
        mock_logger.info.assert_any_call(
            "Current: %s, Latest: %s",
            "2.0.0",
            "2.0.1",
        )
        mock_logger.info.assert_any_call("✅ A newer version is available!")


@pytest.mark.asyncio
async def test_execute_check_version_already_latest() -> None:
    """Check version reports up to date when on the latest release."""
    handler = UpgradeHandler()
    with (
        patch(
            "my_unicorn.cli.commands.upgrade.should_perform_self_update",
            AsyncMock(return_value=(False, "2.0.0")),
        ) as mock_check,
        patch("my_unicorn.cli.commands.upgrade.logger") as mock_logger,
        patch("my_unicorn.cli.commands.upgrade.__version__", "2.0.0"),
    ):
        args = Namespace(check=True)
        await handler.execute(args)
        mock_check.assert_called_once()
        mock_logger.info.assert_any_call(
            "Current: %s, Latest: %s",
            "2.0.0",
            "2.0.0",
        )
        mock_logger.info.assert_any_call(
            "✨ You are running the latest version."
        )


@pytest.mark.asyncio
async def test_execute_check_version_unavailable() -> None:
    """Check version warns when GitHub is unreachable."""
    handler = UpgradeHandler()
    with (
        patch(
            "my_unicorn.cli.commands.upgrade.should_perform_self_update",
            AsyncMock(return_value=(False, None)),
        ),
        patch("my_unicorn.cli.commands.upgrade.logger") as mock_logger,
        patch("my_unicorn.cli.commands.upgrade.__version__", "2.0.0"),
    ):
        args = Namespace(check=True)
        await handler.execute(args)
        mock_logger.warning.assert_any_call(
            "Could not determine the latest version. Current: %s",
            "2.0.0",
        )
