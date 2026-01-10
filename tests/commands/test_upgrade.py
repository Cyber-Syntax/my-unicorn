"""Tests for UpgradeHandler (replacement for self-update command).

These tests mirror the previous self-update tests but use the new `upgrade`
command verb and the `UpgradeHandler` import.
"""

from argparse import Namespace
from unittest.mock import AsyncMock, patch

import pytest

from my_unicorn.cli.commands.upgrade import UpgradeHandler


@pytest.mark.asyncio
async def test_execute_perform_update_success() -> None:
    """Upgrade runs when a newer version is available."""
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
        mock_perform.return_value = True
        args = Namespace(check=False)
        await handler.execute(args)
        mock_check.assert_called_once()
        mock_perform.assert_called_once()


@pytest.mark.asyncio
async def test_execute_perform_update_failure() -> None:
    """Upgrade flow logs failure when exec does not start."""
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
        mock_perform.return_value = False
        args = Namespace(check=False)
        await handler.execute(args)
        mock_check.assert_called_once()
        mock_perform.assert_called_once()
        # Check that the failure message was logged
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
async def test_execute_check_version() -> None:
    """Check version displays current and latest versions."""
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
