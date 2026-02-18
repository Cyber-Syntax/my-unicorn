"""Tests for remove command handler."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.cli.commands.remove import RemoveHandler


@pytest.fixture
def mock_config_manager():
    """Fixture to mock the configuration manager with v2 config format."""
    config_manager = MagicMock()
    config_manager.load_global_config.return_value = {
        "directory": {
            "storage": Path("/mock/storage"),
            "icon": Path("/mock/icons"),
        }
    }

    def load_app_config_side_effect(app_name):
        if app_name == "missing_app":
            return None
        # v2 format
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": app_name,
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": f"/mock/storage/{app_name}.AppImage",
                "verification": {"passed": True, "methods": []},
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": f"/mock/icons/{app_name}.png",
                },
            },
        }

    def get_effective_config_side_effect(app_name):
        if app_name == "missing_app":
            msg = f"No config found for {app_name}"
            raise ValueError(msg)
        return {
            "config_version": "2.0.0",
            "metadata": {"name": app_name, "display_name": app_name.title()},
            "source": {
                "type": "github",
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {
                "version": "1.0.0",
                "installed_date": "2024-01-01T00:00:00",
                "installed_path": f"/mock/storage/{app_name}.AppImage",
                "verification": {"passed": True, "methods": []},
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": f"/mock/icons/{app_name}.png",
                },
            },
        }

    config_manager.load_app_config.side_effect = load_app_config_side_effect
    config_manager.app_config_manager.get_effective_config.side_effect = (
        get_effective_config_side_effect
    )
    config_manager.remove_app_config = MagicMock()
    return config_manager


@pytest.fixture
def global_config():
    """Fixture to mock the global configuration."""
    return {
        "directory": {
            "storage": Path("/mock/storage"),
            "icon": Path("/mock/icons"),
        }
    }


@pytest.fixture
def remove_handler(mock_config_manager, global_config):
    """Fixture to create a RemoveHandler instance with mocked dependencies."""
    return RemoveHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )


def _create_mock_remove_service(
    success: bool = True, error: str | None = None
):
    """Helper to create a mock RemoveService with proper result."""
    mock_result = MagicMock()
    mock_result.success = success
    mock_result.error = error

    mock_service = MagicMock()
    mock_service.remove_app = AsyncMock(return_value=mock_result)
    return mock_service


@pytest.mark.asyncio
async def test_remove_single_app_success(
    remove_handler, mock_config_manager, global_config
):
    """Test successful removal of a single app."""
    mock_service = _create_mock_remove_service(success=True)

    mock_container = MagicMock()
    mock_container.create_remove_service.return_value = mock_service
    mock_container.cleanup = AsyncMock()

    with patch(
        "my_unicorn.cli.commands.remove.ServiceContainer",
        return_value=mock_container,
    ) as mock_container_class:
        args = Namespace(apps=["test_app"], keep_config=False)
        await remove_handler.execute(args)

        # Verify container was created with correct dependencies
        mock_container_class.assert_called_once()
        call_kwargs = mock_container_class.call_args.kwargs
        assert call_kwargs["config_manager"] == mock_config_manager

        # Verify service was obtained from container
        mock_container.create_remove_service.assert_called_once()

        # Verify remove_app was called with correct arguments
        mock_service.remove_app.assert_awaited_once_with("test_app", False)

        # Verify cleanup was called
        mock_container.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_single_app_keep_config(
    remove_handler, mock_config_manager, global_config
):
    """Test removal of a single app while keeping its config."""
    mock_service = _create_mock_remove_service(success=True)

    mock_container = MagicMock()
    mock_container.create_remove_service.return_value = mock_service
    mock_container.cleanup = AsyncMock()

    with patch(
        "my_unicorn.cli.commands.remove.ServiceContainer",
        return_value=mock_container,
    ):
        args = Namespace(apps=["test_app"], keep_config=True)
        await remove_handler.execute(args)

        # Verify remove_app was called with keep_config=True
        mock_service.remove_app.assert_awaited_once_with("test_app", True)

        # Verify cleanup was called
        mock_container.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_multiple_apps(remove_handler, mock_config_manager):
    """Test removal of multiple apps."""
    mock_service = _create_mock_remove_service(success=True)

    mock_container = MagicMock()
    mock_container.create_remove_service.return_value = mock_service
    mock_container.cleanup = AsyncMock()

    with patch(
        "my_unicorn.cli.commands.remove.ServiceContainer",
        return_value=mock_container,
    ):
        args = Namespace(apps=["app1", "app2"], keep_config=False)
        await remove_handler.execute(args)

        # Verify remove_app was called for each app
        assert mock_service.remove_app.await_count == 2

        # Verify cleanup was called
        mock_container.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_missing_app_no_raise(
    remove_handler, mock_config_manager, caplog
):
    """Test removal of a missing app returns error result without raising."""
    mock_service = _create_mock_remove_service(
        success=False, error="App 'missing_app' not found"
    )

    mock_container = MagicMock()
    mock_container.create_remove_service.return_value = mock_service
    mock_container.cleanup = AsyncMock()

    with patch(
        "my_unicorn.cli.commands.remove.ServiceContainer",
        return_value=mock_container,
    ):
        args = Namespace(apps=["missing_app"], keep_config=False)
        # Should not raise since "not found" is in error message
        await remove_handler.execute(args)

        # Verify cleanup was still called
        mock_container.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_failure_raises_runtime_error(
    remove_handler, mock_config_manager
):
    """Test removal failure raises RuntimeError for non-'not found' errors."""
    mock_service = _create_mock_remove_service(
        success=False, error="Permission denied"
    )

    mock_container = MagicMock()
    mock_container.create_remove_service.return_value = mock_service
    mock_container.cleanup = AsyncMock()

    with patch(
        "my_unicorn.cli.commands.remove.ServiceContainer",
        return_value=mock_container,
    ):
        args = Namespace(apps=["test_app"], keep_config=False)

        with pytest.raises(RuntimeError, match="Permission denied"):
            await remove_handler.execute(args)

        # Verify cleanup was still called despite the error
        mock_container.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_cleanup_called_on_exception(
    remove_handler, mock_config_manager
):
    """Test cleanup is called even when service raises an exception."""
    mock_service = MagicMock()
    mock_service.remove_app = AsyncMock(side_effect=Exception("Boom"))

    mock_container = MagicMock()
    mock_container.create_remove_service.return_value = mock_service
    mock_container.cleanup = AsyncMock()

    with patch(
        "my_unicorn.cli.commands.remove.ServiceContainer",
        return_value=mock_container,
    ):
        args = Namespace(apps=["test_app"], keep_config=False)

        with pytest.raises(Exception, match="Boom"):
            await remove_handler.execute(args)

        # Verify cleanup was still called despite the exception
        mock_container.cleanup.assert_awaited_once()
