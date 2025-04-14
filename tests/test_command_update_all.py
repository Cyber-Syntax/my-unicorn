import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the project root to sys.path so that the 'src' package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from commands.update_all import AppImageUpdater, UpdateCommand, VersionChecker
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager


class TestUpdateCommand(unittest.TestCase):
    """Test cases for the UpdateCommand class."""

    @patch("builtins.input", return_value="y")  # Mock user input to always return 'y'
    @patch("builtins.print")  # Mock print to avoid console output during tests
    def test_execute_flow_with_updates(self, mock_print, mock_input):
        """Test the full execution flow when updates are available."""
        # Set up test instance
        cmd = UpdateCommand()

        # Mock global_config
        cmd.global_config = MagicMock()
        cmd.global_config.batch_mode = False  # Test user confirmation flow

        # Mock version_checker
        cmd.version_checker = MagicMock()
        mock_updatable = [
            {
                "config_file": "/tmp/testrepo.json",
                "name": "test.AppImage",
                "current": "1.0.0",
                "latest": "1.1.0",
            }
        ]
        cmd.version_checker.find_updatable_apps.return_value = mock_updatable

        # Mock appimage_updater
        cmd.appimage_updater = MagicMock()

        # Execute update command
        cmd.execute()

        # Assert expected method calls
        cmd.global_config.load_config.assert_called_once()
        cmd.version_checker.find_updatable_apps.assert_called_once_with(cmd.app_config)
        cmd.appimage_updater.execute_batch.assert_called_once_with(
            mock_updatable, cmd.global_config
        )

    @patch("builtins.print")  # Mock print to avoid console output during tests
    def test_execute_flow_no_updates(self, mock_print):
        """Test execution flow when no updates are available."""
        # Set up test instance
        cmd = UpdateCommand()

        # Mock global_config
        cmd.global_config = MagicMock()

        # Mock version_checker to return empty list (no updates)
        cmd.version_checker = MagicMock()
        cmd.version_checker.find_updatable_apps.return_value = []

        # Mock appimage_updater
        cmd.appimage_updater = MagicMock()

        # Execute update command
        cmd.execute()

        # Assert expected method calls
        cmd.global_config.load_config.assert_called_once()
        cmd.version_checker.find_updatable_apps.assert_called_once_with(cmd.app_config)
        # Should not call execute_batch when no updates are available
        cmd.appimage_updater.execute_batch.assert_not_called()

    @patch("builtins.input", return_value="n")  # Mock user input to return 'n' (no)
    @patch("builtins.print")  # Mock print to avoid console output during tests
    def test_execute_flow_user_cancels(self, mock_print, mock_input):
        """Test execution flow when user cancels the update."""
        # Set up test instance
        cmd = UpdateCommand()

        # Mock global_config
        cmd.global_config = MagicMock()
        cmd.global_config.batch_mode = False  # Test user confirmation flow

        # Mock version_checker
        cmd.version_checker = MagicMock()
        mock_updatable = [
            {
                "config_file": "/tmp/testrepo.json",
                "name": "test.AppImage",
                "current": "1.0.0",
                "latest": "1.1.0",
            }
        ]
        cmd.version_checker.find_updatable_apps.return_value = mock_updatable

        # Mock appimage_updater
        cmd.appimage_updater = MagicMock()

        # Execute update command
        cmd.execute()

        # Assert expected method calls
        cmd.global_config.load_config.assert_called_once()
        cmd.version_checker.find_updatable_apps.assert_called_once_with(cmd.app_config)
        # Should not call execute_batch when user cancels
        cmd.appimage_updater.execute_batch.assert_not_called()

    @patch("builtins.print")  # Mock print to avoid console output during tests
    def test_batch_mode_auto_confirms(self, mock_print):
        """Test that batch mode automatically confirms updates."""
        # Set up test instance
        cmd = UpdateCommand()

        # Mock global_config with batch mode enabled
        cmd.global_config = MagicMock()
        cmd.global_config.batch_mode = True

        # Mock version_checker
        cmd.version_checker = MagicMock()
        mock_updatable = [
            {
                "config_file": "/tmp/testrepo.json",
                "name": "test.AppImage",
                "current": "1.0.0",
                "latest": "1.1.0",
            }
        ]
        cmd.version_checker.find_updatable_apps.return_value = mock_updatable

        # Mock appimage_updater
        cmd.appimage_updater = MagicMock()

        # Execute update command
        cmd.execute()

        # Assert expected method calls - should proceed without user input in batch mode
        cmd.global_config.load_config.assert_called_once()
        cmd.appimage_updater.execute_batch.assert_called_once_with(
            mock_updatable, cmd.global_config
        )


class TestVersionChecker(unittest.TestCase):
    """Test cases for the VersionChecker class."""

    def test_find_updatable_apps(self):
        """Test finding updatable apps."""
        # This would be expanded in a real test suite
        pass


class TestAppImageUpdater(unittest.TestCase):
    """Test cases for the AppImageUpdater class."""

    def test_execute_batch(self):
        """Test batch execution of app updates."""
        # This would be expanded in a real test suite
        pass


if __name__ == "__main__":
    unittest.main()
