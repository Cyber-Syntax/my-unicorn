"""Tests for install command handler."""

from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.cli.commands.install import InstallCommandHandler


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Fixture for mock config manager."""
    mock = MagicMock()
    mock.load_global_config.return_value = {
        "directory": {
            "storage": "/tmp/storage",
            "download": "/tmp/download",
        },
        "max_concurrent_downloads": 3,
        "network": {
            "timeout_seconds": 10,
        },
    }
    return mock


@pytest.fixture
def install_handler(mock_config_manager: MagicMock) -> InstallCommandHandler:
    """Fixture to create InstallCommandHandler with mocked dependencies."""
    return InstallCommandHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_install_handler_no_targets(
    install_handler: InstallCommandHandler,
) -> None:
    """Test InstallCommandHandler with no targets."""
    args = Namespace(targets=[])

    with patch(
        "my_unicorn.cli.commands.install.display_no_targets_error"
    ) as mock_display:
        await install_handler.execute(args)

        mock_display.assert_called_once()


@pytest.mark.asyncio
async def test_install_handler_with_targets(
    install_handler: InstallCommandHandler,
) -> None:
    """Test InstallCommandHandler executes installation successfully."""
    args = Namespace(
        targets=["app1"],
        concurrency=3,
        no_verify=False,
    )

    mock_results = [{"success": True, "name": "app1", "version": "1.0.0"}]

    with (
        patch(
            "my_unicorn.cli.commands.install.create_http_session"
        ) as mock_session,
        patch(
            "my_unicorn.cli.commands.install.InstallApplicationService"
        ) as mock_service_class,
        patch("my_unicorn.cli.commands.install.print_install_summary"),
    ):
        # Setup async context manager for session
        mock_session_instance = MagicMock()
        mock_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session_instance
        )
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Setup install service
        mock_service = MagicMock()
        mock_service.install = AsyncMock(return_value=mock_results)
        mock_service_class.return_value = mock_service

        await install_handler.execute(args)

        # Verify service.install was called
        mock_service.install.assert_awaited_once()
        call_args = mock_service.install.call_args
        assert call_args[0][0] == ["app1"]  # targets


def test_expand_comma_separated_targets(
    install_handler: InstallCommandHandler,
) -> None:
    """Test _expand_comma_separated_targets method."""
    targets = ["app1,app2", "app3"]
    expanded = install_handler._expand_comma_separated_targets(  # noqa: SLF001
        targets
    )
    assert expanded == ["app1", "app2", "app3"]
