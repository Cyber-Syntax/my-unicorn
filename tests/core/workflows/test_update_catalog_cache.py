"""Tests for catalog caching in UpdateManager."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.core.update.manager import UpdateManager


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager."""
    manager = MagicMock()
    manager.load_catalog = MagicMock()
    return manager


@pytest.fixture
def update_manager(mock_config_manager):
    """Create UpdateManager with mocked dependencies."""
    manager = UpdateManager(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        progress_reporter=MagicMock(),
    )
    # Mock global config
    manager.global_config = {
        "directory": {
            "download": "/tmp/test",
            "icon": "/tmp/icons",
        }
    }
    return manager


async def test_catalog_caching_first_load(update_manager, mock_config_manager):
    """Test catalog is loaded from file on first access."""
    catalog_data = {"github_owner": "test", "github_repo": "app"}
    mock_config_manager.load_catalog.return_value = catalog_data

    # First call - should load from file
    result = await update_manager._catalog_cache.load_catalog("qownnotes")

    assert result == catalog_data
    assert mock_config_manager.load_catalog.call_count == 1
    mock_config_manager.load_catalog.assert_called_with("qownnotes")


async def test_catalog_caching_cached_load(
    update_manager, mock_config_manager
):
    """Test catalog is only loaded once for multiple accesses."""
    catalog_data = {"github_owner": "test", "github_repo": "app"}
    mock_config_manager.load_catalog.return_value = catalog_data

    # First call - loads from file
    result1 = await update_manager._catalog_cache.load_catalog("qownnotes")
    assert mock_config_manager.load_catalog.call_count == 1

    # Second call - returns cached value
    result2 = await update_manager._catalog_cache.load_catalog("qownnotes")
    assert (
        mock_config_manager.load_catalog.call_count == 1
    )  # No additional call
    assert result1 is result2  # Same object


async def test_catalog_caching_different_catalogs(
    update_manager, mock_config_manager
):
    """Test different catalogs are cached independently."""
    catalog1 = {"github_owner": "test1", "github_repo": "app1"}
    catalog2 = {"github_owner": "test2", "github_repo": "app2"}

    def load_catalog_side_effect(ref):
        if ref == "qownnotes":
            return catalog1
        if ref == "zen-browser":
            return catalog2
        return None

    mock_config_manager.load_catalog.side_effect = load_catalog_side_effect

    # Load first catalog
    result1 = await update_manager._catalog_cache.load_catalog("qownnotes")
    assert result1 == catalog1
    assert mock_config_manager.load_catalog.call_count == 1

    # Load second catalog
    result2 = await update_manager._catalog_cache.load_catalog("zen-browser")
    assert result2 == catalog2
    assert mock_config_manager.load_catalog.call_count == 2

    # Access first catalog again - should be cached
    result3 = await update_manager._catalog_cache.load_catalog("qownnotes")
    assert result3 == catalog1
    assert mock_config_manager.load_catalog.call_count == 2  # No new call


async def test_catalog_caching_none_result(
    update_manager, mock_config_manager
):
    """Test None results are also cached to avoid repeated failures."""
    mock_config_manager.load_catalog.return_value = None

    # First call - returns None
    result1 = await update_manager._catalog_cache.load_catalog("nonexistent")
    assert result1 is None
    assert mock_config_manager.load_catalog.call_count == 1

    # Second call - should use cached None
    result2 = await update_manager._catalog_cache.load_catalog("nonexistent")
    assert result2 is None
    assert (
        mock_config_manager.load_catalog.call_count == 1
    )  # No additional call


async def test_catalog_cache_isolated_per_instance(mock_config_manager):
    """Test catalog cache is isolated per UpdateManager instance."""
    catalog_data = {"github_owner": "test", "github_repo": "app"}
    mock_config_manager.load_catalog.return_value = catalog_data

    # Create first instance
    manager1 = UpdateManager(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        progress_reporter=MagicMock(),
    )
    manager1.global_config = {
        "directory": {"download": "/tmp", "icon": "/tmp"}
    }

    # Load catalog in first instance
    await manager1._catalog_cache.load_catalog("qownnotes")
    assert mock_config_manager.load_catalog.call_count == 1

    # Create second instance
    manager2 = UpdateManager(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        progress_reporter=MagicMock(),
    )
    manager2.global_config = {
        "directory": {"download": "/tmp", "icon": "/tmp"}
    }

    # Load same catalog in second instance - should load again (different cache)
    await manager2._catalog_cache.load_catalog("qownnotes")
    assert mock_config_manager.load_catalog.call_count == 2
