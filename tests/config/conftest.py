"""Shared fixtures for config module tests.

This module provides common fixtures used across config tests:
- config_dir: Temporary configuration directory with dummy catalog
- config_manager: ConfigManager instance for testing
"""

from pathlib import Path

import orjson
import pytest

from my_unicorn.config import ConfigManager


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Provide a temporary config directory for ConfigManager."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Create temporary catalog directory with one app in the test environment
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    dummy_catalog = catalog_dir / "dummyapp.json"
    dummy_catalog.write_bytes(
        orjson.dumps(
            {
                "config_version": "2.0.0",
                "metadata": {
                    "name": "dummyapp",
                    "display_name": "Dummy App",
                    "description": "",
                },
                "source": {
                    "type": "github",
                    "owner": "dummy",
                    "repo": "dummyrepo",
                    "prerelease": False,
                },
                "appimage": {
                    "naming": {
                        "template": "",
                        "target_name": "dummy",
                        "architectures": ["amd64", "x86_64"],
                    }
                },
                "verification": {"method": "digest"},
                "icon": {"method": "extraction", "filename": "dummy.png"},
            }
        )
    )
    return config_dir


@pytest.fixture
def config_manager(config_dir: Path, tmp_path: Path) -> ConfigManager:
    """ConfigManager instance using temporary config_dir and catalog_dir."""
    # Use the temporary catalog directory for tests
    catalog_dir = tmp_path / "catalog"
    return ConfigManager(config_dir, catalog_dir)
