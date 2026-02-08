"""Test global config validation against real production settings.conf."""

import configparser
from pathlib import Path

import pytest


@pytest.fixture
def global_config_path():
    """Return path to global settings.conf file."""
    return (
        Path(__file__).parent.parent.parent.parent
        / "docs"
        / "dev"
        / "data"
        / "settings.conf"
    )


def test_global_config_structure(global_config_path):
    """Test that global settings.conf has correct structure.

    Validates:
    - config_version exists and equals "1.1.0"
    - Required sections exist: [DEFAULT], [network], [directory]
    - Numeric fields are parseable as integers:
        - max_concurrent_downloads
        - max_backup
        - retry_attempts
        - timeout_seconds
    - Directory path fields are non-empty strings
    """
    if not global_config_path.exists():
        pytest.skip(f"Global config file not found: {global_config_path}")

    config = configparser.ConfigParser()
    config.read(global_config_path)

    # Verify config_version exists and is correct
    # Note: configparser includes inline comments, so we split them
    config_version_raw = config.get("DEFAULT", "config_version", fallback=None)
    config_version = (
        config_version_raw.split("#")[0].strip()
        if config_version_raw
        else None
    )
    assert config_version == "1.1.0", (
        f"config_version should be '1.1.0', got {config_version}"
    )

    # Verify required sections exist
    required_sections = ["DEFAULT", "network", "directory"]
    for section in required_sections:
        assert config.has_section(section) or section == "DEFAULT", (
            f"Missing required section: [{section}]"
        )

    # Verify numeric fields in [DEFAULT]
    default_numeric_fields = {
        "max_concurrent_downloads": int,
        "max_backup": int,
    }
    for field, expected_type in default_numeric_fields.items():
        value = config.get("DEFAULT", field, fallback=None)
        assert value is not None, f"Missing field in [DEFAULT]: {field}"
        try:
            parsed_value = expected_type(value)
            assert parsed_value >= 0, (
                f"{field} should be non-negative, got {parsed_value}"
            )
        except ValueError as e:
            msg = (
                f"Field '{field}' is not a valid "
                f"{expected_type.__name__}: {value}"
            )
            raise AssertionError(msg) from e

    # Verify numeric fields in [network]
    network_numeric_fields = {
        "retry_attempts": int,
        "timeout_seconds": int,
    }
    for field, expected_type in network_numeric_fields.items():
        value = config.get("network", field, fallback=None)
        assert value is not None, f"Missing field in [network]: {field}"
        try:
            parsed_value = expected_type(value)
            assert parsed_value > 0, (
                f"{field} should be positive, got {parsed_value}"
            )
        except ValueError as e:
            msg = (
                f"Field '{field}' is not a valid "
                f"{expected_type.__name__}: {value}"
            )
            raise AssertionError(msg) from e

    # Verify directory path fields are non-empty strings
    directory_path_fields = [
        "download",
        "storage",
        "backup",
        "icon",
        "settings",
        "logs",
        "cache",
    ]
    for field in directory_path_fields:
        value = config.get("directory", field, fallback=None)
        assert value is not None, f"Missing directory path field: [{field}]"
        assert isinstance(value, str), (
            f"Directory path '{field}' should be string, got {type(value)}"
        )
        assert len(value) > 0, f"Directory path '{field}' should not be empty"
