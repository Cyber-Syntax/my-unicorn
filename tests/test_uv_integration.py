"""Tests for UV integration in my-unicorn.

This module tests the UV detection and integration functionality
in the upgrade module and setup script.
"""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from my_unicorn.workflows.upgrade import SelfUpdater


class TestUVDetection:
    """Test UV availability detection."""

    @patch("my_unicorn.workflows.upgrade.subprocess.run")
    def test_uv_available(self, mock_run):
        """Test UV detection when UV is installed."""
        # Mock successful UV version check
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "uv 0.1.0"
        mock_run.return_value = mock_result

        # Create mock dependencies
        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {"repo": "/tmp/test"}
        }
        session = MagicMock()

        # Create updater instance
        updater = SelfUpdater(config_manager, session)

        # Verify UV was detected
        assert updater._uv_available is True
        mock_run.assert_called_once_with(
            ["uv", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )

    @patch("my_unicorn.workflows.upgrade.subprocess.run")
    def test_uv_not_available_file_not_found(self, mock_run):
        """Test UV detection when UV is not installed."""
        # Mock FileNotFoundError when UV is not found
        mock_run.side_effect = FileNotFoundError()

        # Create mock dependencies
        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {"repo": "/tmp/test"}
        }
        session = MagicMock()

        # Create updater instance
        updater = SelfUpdater(config_manager, session)

        # Verify UV was not detected
        assert updater._uv_available is False

    @patch("my_unicorn.workflows.upgrade.subprocess.run")
    def test_uv_not_available_timeout(self, mock_run):
        """Test UV detection when command times out."""
        # Mock timeout error
        mock_run.side_effect = subprocess.TimeoutExpired("uv", 5)

        # Create mock dependencies
        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {"repo": "/tmp/test"}
        }
        session = MagicMock()

        # Create updater instance
        updater = SelfUpdater(config_manager, session)

        # Verify UV was not detected
        assert updater._uv_available is False

    @patch("my_unicorn.workflows.upgrade.subprocess.run")
    def test_uv_not_available_non_zero_exit(self, mock_run):
        """Test UV detection when command fails."""
        # Mock failed UV version check
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        # Create mock dependencies
        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {"repo": "/tmp/test"}
        }
        session = MagicMock()

        # Create updater instance
        updater = SelfUpdater(config_manager, session)

        # Verify UV was not detected
        assert updater._uv_available is False


class TestUVIntegration:
    """Test UV integration in upgrade workflow."""

    @patch("my_unicorn.workflows.upgrade.subprocess.run")
    def test_updater_logs_uv_status(self, mock_run, caplog):
        """Test that updater logs UV availability status."""
        # Mock UV available
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "uv 0.1.0"
        mock_run.return_value = mock_result

        # Create mock dependencies
        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {"repo": "/tmp/test"}
        }
        session = MagicMock()

        # Create updater instance
        with caplog.at_level("DEBUG"):
            updater = SelfUpdater(
                config_manager,
                session,
            )

        # Verify UV status is logged
        assert updater._uv_available is True
        assert any(
            "UV is available" in record.message for record in caplog.records
        )

    @patch("my_unicorn.workflows.upgrade.subprocess.run")
    def test_updater_logs_uv_not_available(self, mock_run, caplog):
        """Test that updater logs when UV is not available."""
        # Mock UV not available
        mock_run.side_effect = FileNotFoundError()

        # Create mock dependencies
        config_manager = MagicMock()
        config_manager.load_global_config.return_value = {
            "directory": {"repo": "/tmp/test"}
        }
        session = MagicMock()

        # Create updater instance
        with caplog.at_level("DEBUG"):
            updater = SelfUpdater(
                config_manager,
                session,
            )

        # Verify UV status is logged
        assert updater._uv_available is False
        assert any(
            "UV is not available" in record.message
            for record in caplog.records
        )


@pytest.mark.integration
class TestUVSetupScript:
    """Integration tests for setup.sh UV support."""

    def test_setup_script_has_uv_function(self):
        """Test that setup.sh contains has_uv function."""
        with open("setup.sh") as f:
            content = f.read()

        assert "has_uv()" in content
        assert "command -v uv" in content

    def test_setup_script_uses_uv_conditionally(self):
        """Test that setup.sh conditionally uses UV."""
        with open("setup.sh") as f:
            content = f.read()

        assert "if has_uv; then" in content
        assert "uv venv" in content
        assert "uv pip install" in content

    def test_setup_script_has_pip_fallback(self):
        """Test that setup.sh has pip fallback."""
        with open("setup.sh") as f:
            content = f.read()

        assert "python3 -m venv" in content
        assert "python3 -m pip install" in content
