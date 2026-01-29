"""Tests for consolidated config loading in UpdateManager."""

from unittest.mock import MagicMock

import pytest

from my_unicorn.core.workflows.update import UpdateManager
from my_unicorn.exceptions import ConfigurationError


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager."""
    manager = MagicMock()
    manager.load_app_config = MagicMock()
    return manager


@pytest.fixture
def update_manager(mock_config_manager):
    """Create UpdateManager with mocked dependencies."""
    manager = UpdateManager(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        progress_service=MagicMock(),
    )
    manager.global_config = {
        "directory": {
            "download": "/tmp/test",
            "icon": "/tmp/icons",
        }
    }
    return manager


def test_load_app_config_or_fail_success(update_manager, mock_config_manager):
    """Test successful config loading."""
    config_data = {
        "source": {"owner": "test", "repo": "app"},
        "state": {"version": "1.0.0"},
    }
    mock_config_manager.load_app_config.return_value = config_data

    result = update_manager._load_app_config_or_fail("qownnotes")

    assert result == config_data
    mock_config_manager.load_app_config.assert_called_once_with("qownnotes")


def test_load_app_config_or_fail_not_found(
    update_manager, mock_config_manager
):
    """Test error when config not found."""
    mock_config_manager.load_app_config.return_value = None

    with pytest.raises(
        ConfigurationError, match="No configuration found for app: nonexistent"
    ):
        update_manager._load_app_config_or_fail("nonexistent")


def test_load_app_config_or_fail_with_context(
    update_manager, mock_config_manager
):
    """Test error message includes context."""
    mock_config_manager.load_app_config.return_value = None

    with pytest.raises(
        ConfigurationError, match="check_update: No configuration found"
    ):
        update_manager._load_app_config_or_fail("nonexistent", "check_update")


def test_load_app_config_or_fail_different_contexts(
    update_manager, mock_config_manager
):
    """Test different contexts produce different error messages."""
    mock_config_manager.load_app_config.return_value = None

    # Context: check_update
    with pytest.raises(ConfigurationError) as exc_info:
        update_manager._load_app_config_or_fail("app1", "check_update")
    assert "check_update:" in str(exc_info.value)

    # Context: prepare_update
    with pytest.raises(ConfigurationError) as exc_info:
        update_manager._load_app_config_or_fail("app2", "prepare_update")
    assert "prepare_update:" in str(exc_info.value)

    # No context
    with pytest.raises(ConfigurationError) as exc_info:
        update_manager._load_app_config_or_fail("app3")
    assert "No configuration found for app: app3" in str(exc_info.value)
    # Should not contain a colon prefix
    assert not str(exc_info.value).startswith(":")


def test_load_app_config_or_fail_empty_context(
    update_manager, mock_config_manager
):
    """Test empty context is treated as no context."""
    mock_config_manager.load_app_config.return_value = None

    with pytest.raises(ConfigurationError) as exc_info:
        update_manager._load_app_config_or_fail("nonexistent", "")

    error_msg = str(exc_info.value)
    # Should not have prefix when context is empty string
    assert not error_msg.startswith(": ")
    assert "No configuration found for app: nonexistent" in error_msg
