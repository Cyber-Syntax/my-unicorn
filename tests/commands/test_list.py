"""Tests for the list command handler."""

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

from my_unicorn.commands.list import ListHandler


@pytest.fixture
def mock_config_manager():
    """Fixture to mock the configuration manager."""
    config_manager = MagicMock()
    config_manager.list_catalog_apps.return_value = ["app1", "app2", "app3"]
    config_manager.list_installed_apps.return_value = [
        "installed_app1",
        "installed_app2",
    ]

    def load_config(app):
        if app.startswith("installed"):
            raise ValueError(
                f"Config for '{app}' is version 1.0.0, expected 2.0.0. Run 'my-unicorn migrate' to upgrade."
            )

    config_manager.load_app_config.side_effect = load_config
    return config_manager


@pytest.fixture
def list_handler(mock_config_manager):
    """Fixture to create a ListHandler instance with mocked dependencies."""
    return ListHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_list_available_apps(list_handler, capsys):
    """Test ListHandler._list_available_apps."""
    args = Namespace(available=True)

    await list_handler.execute(args)

    captured = capsys.readouterr()
    assert "📋 Available AppImages:" in captured.out
    assert "app1" in captured.out
    assert "app2" in captured.out
    assert "app3" in captured.out


@pytest.mark.asyncio
async def test_list_installed_apps(list_handler, capsys):
    """Test ListHandler._list_installed_apps."""
    args = Namespace(available=False)

    await list_handler.execute(args)

    captured = capsys.readouterr()
    assert "📦 Installed AppImages:" in captured.out
    assert "installed_app1" in captured.out
    assert "installed_app2" in captured.out
    assert "run 'my-unicorn migrate'" in captured.out


@pytest.mark.asyncio
async def test_list_installed_apps_with_config_error(
    list_handler, mock_config_manager, capsys
):
    """Test ListHandler._list_installed_apps with a config error."""
    mock_config_manager.list_installed_apps.return_value.append("broken_app")
    mock_config_manager.load_app_config.side_effect = (
        lambda app: None
        if app == "broken_app"
        else {
            "appimage": {
                "version": "1.0.0",
                "installed_date": "2023-01-01T12:00:00Z",
            }
        }
    )

    args = Namespace(available=False)

    await list_handler.execute(args)

    captured = capsys.readouterr()
    assert "📦 Installed AppImages:" in captured.out
    assert "broken_app" in captured.out
    assert "(config error)" in captured.out
