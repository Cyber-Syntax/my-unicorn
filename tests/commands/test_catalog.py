"""Tests for the catalog command handler."""

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

from my_unicorn.commands.catalog import CatalogHandler


@pytest.fixture
def mock_config_manager():
    """Fixture to mock the configuration manager."""
    config_manager = MagicMock()
    config_manager.list_catalog_apps.return_value = ["app1", "app2", "app3"]
    config_manager.list_installed_apps.return_value = [
        "installed_app1",
        "installed_app2",
    ]

    def load_catalog(app):
        return {
            "metadata": {
                "display_name": app,
                "description": "Test app description",
            },
            "source": {"type": "github", "owner": "test", "repo": app},
            "verification": {"method": "digest"},
            "icon": {"method": "extraction"},
        }

    def load_config(app):
        if app.startswith("installed"):
            raise ValueError(
                f"Config for '{app}' is version 1.0.0, expected 2.0.0. Run 'my-unicorn migrate' to upgrade."
            )

    config_manager.load_catalog_entry.side_effect = load_catalog
    config_manager.load_app_config.side_effect = load_config
    return config_manager


@pytest.fixture
def catalog_handler(mock_config_manager):
    """Fixture to create a CatalogHandler instance with mocked dependencies."""
    return CatalogHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_catalog_available_apps(catalog_handler, mocker):
    """Test CatalogHandler._list_available_apps."""
    mock_logger = mocker.patch("my_unicorn.commands.catalog.logger")
    args = Namespace(available=True, installed=False, info=None)

    await catalog_handler.execute(args)

    mock_logger.info.assert_any_call("📋 Available AppImages (%d apps):", 3)
    # Check for apps displayed with descriptions
    assert any("app1" in str(call) for call in mock_logger.info.call_args_list)
    assert any("app2" in str(call) for call in mock_logger.info.call_args_list)
    assert any("app3" in str(call) for call in mock_logger.info.call_args_list)
    assert any(
        "Test app description" in str(call)
        for call in mock_logger.info.call_args_list
    )


@pytest.mark.asyncio
async def test_catalog_installed_apps(catalog_handler, mocker):
    """Test CatalogHandler._list_installed_apps."""
    mock_logger = mocker.patch("my_unicorn.commands.catalog.logger")
    args = Namespace(available=False, installed=True, info=None)

    await catalog_handler.execute(args)

    mock_logger.info.assert_any_call("📦 Installed AppImages:")
    # Check for migration prompt
    assert any(
        "my-unicorn migrate" in str(call)
        for call in mock_logger.info.call_args_list
    )


@pytest.mark.asyncio
async def test_catalog_info(catalog_handler, mocker):
    """Test CatalogHandler._show_app_info."""
    mock_logger = mocker.patch("my_unicorn.commands.catalog.logger")
    args = Namespace(available=False, installed=False, info="app1")

    await catalog_handler.execute(args)

    mock_logger.info.assert_any_call("📦 %s", "app1")
    mock_logger.info.assert_any_call("  %s", "Test app description")
    mock_logger.info.assert_any_call("  Repository:     %s", "test/app1")
