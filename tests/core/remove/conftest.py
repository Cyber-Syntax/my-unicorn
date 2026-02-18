"""Shared fixtures for RemoveService tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.remove import RemoveService
from my_unicorn.types import AppStateConfig, GlobalConfig


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Return a mock ConfigManager for testing."""
    manager = MagicMock()
    manager.load_app_config = MagicMock()
    manager.remove_app_config = MagicMock(return_value=True)
    return manager


@pytest.fixture
def mock_cache_manager() -> MagicMock:
    """Return a mock ReleaseCacheManager for testing."""
    manager = MagicMock()
    manager.clear_cache = AsyncMock()
    return manager


@pytest.fixture
def global_config() -> GlobalConfig:
    """Return a test global configuration."""
    return {
        "directory": {
            "storage": Path("/test/storage"),
            "icon": Path("/test/icons"),
            "backup": Path("/test/backups"),
        }
    }


@pytest.fixture
def sample_app_config() -> AppStateConfig:
    """Return a sample app configuration for testing."""
    return {
        "config_version": "2.0.0",
        "metadata": {
            "name": "test-app",
            "display_name": "Test App",
        },
        "source": {
            "type": "github",
            "owner": "test-owner",
            "repo": "test-repo",
            "prerelease": False,
        },
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T00:00:00Z",
            "installed_path": "/test/storage/test-app.AppImage",
            "verification": {
                "passed": True,
                "methods": [],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/test/icons/test-app.png",
            },
        },
    }


@pytest.fixture
def remove_service(
    mock_config_manager: MagicMock,
    global_config: GlobalConfig,
    mock_cache_manager: MagicMock,
) -> RemoveService:
    """Return a configured RemoveService instance for testing."""
    return RemoveService(
        config_manager=mock_config_manager,
        global_config=global_config,
        cache_manager=mock_cache_manager,
    )
