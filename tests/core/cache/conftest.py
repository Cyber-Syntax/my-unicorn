"""Fixtures for cache service tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.config import ConfigManager
from my_unicorn.core.cache import ReleaseCacheManager


@pytest.fixture
def mock_config_manager(tmp_path: Path) -> MagicMock:
    """Create a mock config manager with a temporary cache directory."""
    config_manager = MagicMock(spec=ConfigManager)
    tmp_path / "cache" / "releases"
    global_config = {"directory": {"cache": tmp_path / "cache"}}
    config_manager.load_global_config.return_value = global_config
    return config_manager


@pytest.fixture
def cache_manager(mock_config_manager: MagicMock) -> ReleaseCacheManager:
    """Create a ReleaseCacheManager instance for testing."""
    return ReleaseCacheManager(mock_config_manager, ttl_hours=24)


@pytest.fixture
def sample_release_data() -> dict:
    """Sample release data for testing."""
    return {
        "tag_name": "v1.0.0",
        "name": "Test Release",
        "published_at": "2025-08-30T12:00:00Z",
        "assets": [
            {
                "name": "test.AppImage",
                "browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
                "size": 12345678,
            },
            {
                "name": "test.AppImage.sha256",
                "browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/test.AppImage.sha256",
                "size": 64,
            },
            {
                "name": "source.tar.gz",
                "browser_download_url": "https://github.com/test/test/archive/v1.0.0.tar.gz",
                "size": 98765,
            },
        ],
    }
