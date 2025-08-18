"""Tests for CatalogInstallStrategy: validation and install logic."""

from unittest.mock import MagicMock

import aiohttp
import pytest

from my_unicorn.strategies.install import ValidationError
from my_unicorn.strategies.install_catalog import CatalogInstallStrategy


@pytest.fixture
async def catalog_strategy():
    """Async fixture for CatalogInstallStrategy with mocked dependencies."""
    # Mocks for dependencies
    catalog_manager = MagicMock()
    config_manager = MagicMock()
    global_config = {"max_concurrent_downloads": 2}
    config_manager.load_global_config.return_value = global_config
    github_client = MagicMock()
    download_service = MagicMock()
    storage_service = MagicMock()
    # Use a real aiohttp session for interface compatibility
    async with aiohttp.ClientSession() as session:
        # Patch get_available_apps to return a controlled catalog
        catalog_manager.get_available_apps.return_value = {
            "app1": {"name": "app1"},
            "app2": {"name": "app2"},
        }
        # Patch get_app_config for install logic
        catalog_manager.get_app_config.side_effect = (
            lambda name: {"name": name} if name in ["app1", "app2"] else None
        )

        strategy = CatalogInstallStrategy(
            catalog_manager=catalog_manager,
            config_manager=config_manager,
            github_client=github_client,
            download_service=download_service,
            storage_service=storage_service,
            session=session,
        )
        yield strategy


def test_validate_targets_valid(catalog_strategy):
    """Test validate_targets with valid app names."""
    catalog_strategy.validate_targets(["app1"])
    catalog_strategy.validate_targets(["app1", "app2"])


def test_validate_targets_invalid(catalog_strategy):
    """Test validate_targets raises ValidationError for invalid app name."""
    with pytest.raises(ValidationError):
        catalog_strategy.validate_targets(["not_in_catalog"])


def test_validate_targets_partial_invalid(catalog_strategy):
    """Test validate_targets raises ValidationError if any target is invalid."""
    with pytest.raises(ValidationError):
        catalog_strategy.validate_targets(["app1", "not_in_catalog"])


@pytest.mark.asyncio
async def test_install_success(mocker, catalog_strategy):
    """Test install returns success for valid targets."""
    # Patch _install_single_app to simulate success
    mocker.patch.object(
        catalog_strategy,
        "_install_single_app",
        side_effect=lambda sem, app_name, **kwargs: {
            "target": app_name,
            "success": True,
            "path": f"/fake/path/{app_name}.AppImage",
            "name": f"{app_name}.AppImage",
            "source": "catalog",
        },
    )
    result = await catalog_strategy.install(["app1", "app2"])
    assert all(r["success"] for r in result)
    assert result[0]["target"] == "app1"
    assert result[1]["target"] == "app2"


@pytest.mark.asyncio
async def test_install_failure(mocker, catalog_strategy):
    """Test install returns error for failed install."""

    # Patch _install_single_app to simulate failure
    def fail_install(sem, app_name, **kwargs):
        raise Exception("Install failed")

    mocker.patch.object(catalog_strategy, "_install_single_app", side_effect=fail_install)
    result = await catalog_strategy.install(["app1"])
    assert not result[0]["success"]
    assert "Install failed" in result[0]["error"]


@pytest.mark.asyncio
async def test_install_mixed_results(mocker, catalog_strategy):
    """Test install returns mixed success/error for multiple targets."""

    def mixed_install(sem, app_name, **kwargs):
        if app_name == "app1":
            return {
                "target": app_name,
                "success": True,
                "path": f"/fake/path/{app_name}.AppImage",
                "name": f"{app_name}.AppImage",
                "source": "catalog",
            }
        else:
            raise Exception("Install failed")

    mocker.patch.object(catalog_strategy, "_install_single_app", side_effect=mixed_install)
    result = await catalog_strategy.install(["app1", "app2"])
    assert result[0]["success"]
    assert not result[1]["success"]
    assert "Install failed" in result[1]["error"]
