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
async def test_catalog_available_apps(catalog_handler, capsys):
    """Test CatalogHandler._list_available_apps."""
    args = Namespace(available=True, installed=False, info=None)

    await catalog_handler.execute(args)

    captured = capsys.readouterr()
    assert "📋 Available AppImages" in captured.out
    assert "app1" in captured.out
    assert "app2" in captured.out
    assert "app3" in captured.out
    assert "Test app description" in captured.out


@pytest.mark.asyncio
async def test_catalog_installed_apps(catalog_handler, capsys):
    """Test CatalogHandler._list_installed_apps."""
    args = Namespace(available=False, installed=True, info=None)

    await catalog_handler.execute(args)

    captured = capsys.readouterr()
    assert "📦 Installed AppImages:" in captured.out
    assert "installed_app1" in captured.out
    assert "installed_app2" in captured.out
    assert "run 'my-unicorn migrate'" in captured.out


@pytest.mark.asyncio
async def test_catalog_info(catalog_handler, capsys):
    """Test CatalogHandler._show_app_info."""
    args = Namespace(available=False, installed=False, info="app1")

    await catalog_handler.execute(args)

    captured = capsys.readouterr()
    assert "📦 app1" in captured.out
    assert "Test app description" in captured.out
    assert "Repository:" in captured.out
    assert "test/app1" in captured.out
