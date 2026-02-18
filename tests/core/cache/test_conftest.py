"""Verification tests for conftest fixtures in tests/core/cache/."""

from unittest.mock import MagicMock

from my_unicorn.core.cache import ReleaseCacheManager


def test_mock_config_manager_fixture(mock_config_manager: MagicMock) -> None:
    """Verify mock_config_manager is a MagicMock with ConfigManager spec."""
    assert isinstance(mock_config_manager, MagicMock)
    assert hasattr(mock_config_manager, "load_global_config")


def test_cache_manager_fixture(cache_manager: ReleaseCacheManager) -> None:
    """Verify cache_manager fixture creates ReleaseCacheManager instance."""
    assert isinstance(cache_manager, ReleaseCacheManager)
    assert cache_manager.ttl_hours == 24


def test_sample_release_data_fixture(sample_release_data: dict) -> None:
    """Verify sample_release_data has required keys."""
    assert "tag_name" in sample_release_data
    assert "name" in sample_release_data
    assert "published_at" in sample_release_data
    assert "assets" in sample_release_data

    assets = sample_release_data["assets"]
    assert len(assets) > 0
    assert any(asset["name"].endswith(".AppImage") for asset in assets)
