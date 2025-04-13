import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the project root to sys.path so that the 'src' package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from commands.download import DownloadCommand
from src.api import GitHubAPI
from src.app_config import AppConfigManager
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.verify import VerificationManager
from src.parser import ParseURL
from src.global_config import GlobalConfigManager


class TestDownloadCommand(unittest.TestCase):
    def setUp(self):
        # Set up test data
        self.test_owner = "testowner"
        self.test_repo = "testrepo"
        self.test_appimage = "test.AppImage"
        self.test_version = "1.0.0"
        self.test_sha_name = "test.sha256"
        self.test_sha_url = "http://example.com/test.sha256"
        self.test_appimage_url = "http://example.com/test.AppImage"

    @patch("commands.download.ParseURL")
    @patch("commands.download.AppConfigManager")
    @patch("commands.download.GitHubAPI")
    @patch("commands.download.DownloadManager")
    @patch("commands.download.GlobalConfigManager")
    @patch("commands.download.VerificationManager")
    @patch("commands.download.FileHandler")
    def test_execute_success_flow(
        self,
        mock_file_handler,
        mock_verifier,
        mock_global_config,
        mock_download_manager,
        mock_api,
        mock_app_config,
        mock_parser,
    ):
        # Setup ParseURL mock
        parser_instance = mock_parser.return_value
        parser_instance.owner = self.test_owner
        parser_instance.repo = self.test_repo

        # Setup AppConfigManager mock
        app_config_instance = mock_app_config.return_value
        app_config_instance.ask_sha_hash.return_value = (self.test_sha_name, "sha256")
        app_config_instance.config_folder = "/tmp/config"
        app_config_instance.config_file_name = "test_config.json"

        # Setup GitHubAPI mock
        api_instance = mock_api.return_value
        api_instance.owner = self.test_owner
        api_instance.repo = self.test_repo
        api_instance.version = self.test_version
        api_instance.appimage_name = self.test_appimage
        api_instance.sha_name = self.test_sha_name
        api_instance.sha_url = self.test_sha_url
        api_instance.hash_type = "sha256"
        api_instance.arch_keyword = None
        api_instance.appimage_url = self.test_appimage_url

        # Setup GlobalConfigManager mock
        global_config_instance = mock_global_config.return_value
        global_config_instance.expanded_appimage_download_folder_path = "/tmp"
        global_config_instance.expanded_appimage_download_backup_folder_path = "/tmp/backup"
        global_config_instance.batch_mode = True
        global_config_instance.keep_backup = True
        global_config_instance.config_file = "/tmp/global_config.json"

        # Setup DownloadManager mock
        download_manager_instance = mock_download_manager.return_value
        download_manager_instance.download.return_value = True

        # Setup VerificationManager mock
        verifier_instance = mock_verifier.return_value
        verifier_instance.verify_appimage.return_value = True

        # Setup FileHandler mock
        file_handler_instance = mock_file_handler.return_value
        file_handler_instance.handle_appimage_operations.return_value = True

        # Create and execute the command
        cmd = DownloadCommand()
        cmd.execute()

        # Verify the expected flow of operations
        parser_instance.ask_url.assert_called_once()
        api_instance.get_response.assert_called_once()
        app_config_instance.temp_save_config.assert_called_once()
        mock_download_manager.return_value.download.assert_called_once()
        verifier_instance.verify_appimage.assert_called_once()
        file_handler_instance.handle_appimage_operations.assert_called_once()
        app_config_instance.save_config.assert_called_once()

    @patch("commands.download.ParseURL")
    @patch("commands.download.AppConfigManager")
    @patch("commands.download.GitHubAPI")
    @patch("commands.download.DownloadManager")
    @patch("commands.download.GlobalConfigManager")
    @patch("commands.download.VerificationManager")
    @patch("commands.download.FileHandler")
    def test_execute_verification_failure(
        self,
        mock_file_handler,
        mock_verifier,
        mock_global_config,
        mock_download_manager,
        mock_api,
        mock_app_config,
        mock_parser,
    ):
        # Similar setup as success flow...
        parser_instance = mock_parser.return_value
        parser_instance.owner = self.test_owner
        parser_instance.repo = self.test_repo

        app_config_instance = mock_app_config.return_value
        app_config_instance.ask_sha_hash.return_value = (self.test_sha_name, "sha256")

        api_instance = mock_api.return_value
        api_instance.owner = self.test_owner
        api_instance.repo = self.test_repo
        api_instance.version = self.test_version
        api_instance.appimage_name = self.test_appimage
        api_instance.sha_name = self.test_sha_name
        api_instance.sha_url = self.test_sha_url
        api_instance.hash_type = "sha256"
        api_instance.arch_keyword = None

        # Set verification to fail
        verifier_instance = mock_verifier.return_value
        verifier_instance.verify_appimage.return_value = False

        # Create and execute the command
        cmd = DownloadCommand()
        cmd.execute()

        try:
            # Verify that the flow stops after verification failure
            verifier_instance.verify_appimage.assert_called_once()
            file_handler_instance = mock_file_handler.return_value
            file_handler_instance.handle_appimage_operations.assert_not_called()
            app_config_instance.save_config.assert_not_called()
        except Exception as e:
            self.fail(f"Test failed with exception: {str(e)}")


if __name__ == "__main__":
    unittest.main()
