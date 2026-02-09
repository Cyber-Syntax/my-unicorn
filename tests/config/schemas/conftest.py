"""Shared fixtures for schema validation tests."""

from pathlib import Path

import pytest


@pytest.fixture
def test_data_root() -> Path:
    """Return path to test data root directory.

    Returns:
        Path to docs/dev/data/ directory.
    """
    return Path(__file__).parent.parent.parent.parent / "docs" / "dev" / "data"


@pytest.fixture
def cache_examples_dir(test_data_root: Path) -> Path:
    """Return path to cache examples directory.

    Returns:
        Path to docs/dev/data/example_cache_configs/ directory.
    """
    return test_data_root / "example_cache_configs"


@pytest.fixture
def app_state_dir(test_data_root: Path) -> Path:
    """Return path to app state examples directory.

    Returns:
        Path to docs/dev/data/example_app_state_configs/ directory.
    """
    return test_data_root / "example_app_state_configs"


@pytest.fixture
def global_config_path(test_data_root: Path) -> Path:
    """Return path to global settings.conf file.

    Returns:
        Path to docs/dev/data/settings.conf file.
    """
    return test_data_root / "settings.conf"
