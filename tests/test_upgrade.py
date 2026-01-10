"""Unit tests for self-update helpers and upgrade flow."""

from unittest.mock import AsyncMock, patch

import pytest

from my_unicorn.cli.upgrade import (
    check_for_self_update,
    perform_self_update,
    perform_self_update_async,
    should_perform_self_update,
)


def test_perform_self_update_success() -> None:
    """Test perform_self_update calls os.execvp with correct arguments."""
    with (
        patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
        patch("my_unicorn.cli.upgrade.os.execvp") as mock_execvp,
    ):
        mock_execvp.return_value = None  # execvp doesn't return on success
        perform_self_update()
        # Since execvp replaces the process, this shouldn't return True
        # But in test, it will return None, so we check it was called
        mock_execvp.assert_called_once_with(
            "uv",
            [
                "uv",
                "tool",
                "install",
                "--upgrade",
                "git+https://github.com/Cyber-Syntax/my-unicorn",
            ],
        )


def test_perform_self_update_failure() -> None:
    """Test perform_self_update handles execvp failure."""
    with (
        patch("my_unicorn.cli.upgrade.shutil.which", return_value="uv"),
        patch(
            "my_unicorn.cli.upgrade.os.execvp",
            side_effect=OSError("Command failed"),
        ),
        patch("my_unicorn.cli.upgrade.logger") as mock_logger,
    ):
        result = perform_self_update()
        assert result is False
        mock_logger.exception.assert_called_once()
        mock_logger.info.assert_called_once()
        # Check that info was called with the error message format
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "❌ Update failed: %s"
        assert isinstance(call_args[0][1], OSError)
        assert str(call_args[0][1]) == "Command failed"


@pytest.mark.asyncio
async def test_check_for_self_update_reports_newer_version() -> None:
    """Check_for_self_update returns True when a newer version exists."""

    with (
        patch(
            "my_unicorn.cli.upgrade._run_uv_tool_list",
            AsyncMock(return_value=False),
        ),
        patch(
            "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
            AsyncMock(return_value="2.0.1"),
        ),
        patch("my_unicorn.cli.upgrade.__version__", "2.0.0"),
    ):
        result = await check_for_self_update()
        assert result is True


@pytest.mark.asyncio
async def test_check_for_self_update_skips_when_latest() -> None:
    """Check_for_self_update returns False when already on latest."""

    with (
        patch(
            "my_unicorn.cli.upgrade._run_uv_tool_list",
            AsyncMock(return_value=False),
        ),
        patch(
            "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
            AsyncMock(return_value="2.0.0"),
        ),
        patch("my_unicorn.cli.upgrade.__version__", "2.0.0"),
    ):
        result = await check_for_self_update()
        assert result is False


@pytest.mark.asyncio
async def test_should_perform_self_update_when_version_unknown() -> None:
    """Proceed with upgrade when latest version cannot be determined."""

    with (
        patch(
            "my_unicorn.cli.upgrade._run_uv_tool_list",
            AsyncMock(return_value=False),
        ),
        patch(
            "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
            AsyncMock(return_value=None),
        ),
    ):
        should_upgrade, latest_version = await should_perform_self_update(
            "2.0.0"
        )
        assert should_upgrade is True
        assert latest_version is None


@pytest.mark.asyncio
async def test_perform_self_update_async() -> None:
    """Test perform_self_update_async calls perform_self_update."""
    with patch("my_unicorn.cli.upgrade.perform_self_update") as mock_perform:
        mock_perform.return_value = True
        result = await perform_self_update_async()
        assert result is True
        mock_perform.assert_called_once()


@pytest.mark.asyncio
async def test_should_upgrade_dev_installation() -> None:
    """Always upgrade when dev installation is detected."""

    with (
        patch(
            "my_unicorn.cli.upgrade._run_uv_tool_list",
            AsyncMock(return_value=True),
        ),
        patch(
            "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
            AsyncMock(return_value="2.0.1"),
        ),
        patch("my_unicorn.cli.upgrade.__version__", "2.0.0"),
    ):
        should_upgrade, latest_version = await should_perform_self_update(
            "2.0.0"
        )
        assert should_upgrade is True
        assert latest_version == "2.0.1"


@pytest.mark.asyncio
async def test_dev_installation_upgrade_same_version() -> None:
    """Upgrade dev installation even when version is the same."""

    with (
        patch(
            "my_unicorn.cli.upgrade._run_uv_tool_list",
            AsyncMock(return_value=True),
        ),
        patch(
            "my_unicorn.cli.upgrade._fetch_latest_prerelease_version",
            AsyncMock(return_value="2.0.0"),
        ),
        patch("my_unicorn.cli.upgrade.__version__", "2.0.0"),
    ):
        should_upgrade, latest_version = await should_perform_self_update(
            "2.0.0"
        )
        # Dev installation should always upgrade to production
        assert should_upgrade is True
        assert latest_version == "2.0.0"
