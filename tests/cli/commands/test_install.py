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
            "my_unicorn.cli.commands.install.ServiceContainer"
        ) as mock_container_class,
        patch("my_unicorn.cli.commands.install.print_install_summary"),
    ):
        # Setup container mock
        mock_container = MagicMock()
        mock_container_class.return_value = mock_container

        # Setup install service via container
        mock_service = MagicMock()
        mock_service.install = AsyncMock(return_value=mock_results)
        mock_container.create_install_application_service.return_value = (
            mock_service
        )

        # Setup cleanup
        mock_container.cleanup = AsyncMock()

        await install_handler.execute(args)

        # Verify container was used correctly
        mock_container_class.assert_called_once()
        mock_container.create_install_application_service.assert_called_once()
        mock_service.install.assert_awaited_once()
        mock_container.cleanup.assert_awaited_once()
        call_args = mock_service.install.call_args
        assert call_args[0][0] == ["app1"]  # targets
