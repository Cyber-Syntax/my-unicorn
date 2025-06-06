# FIX: not work
import os
import sys
import unittest
from unittest.mock import patch

# Add the project root to sys.path so that the 'src' package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.api.github_api import GitHubAPI
from src.commands.install_url import DownloadCommand


class TestIntegrationDownloadFlow(unittest.TestCase):
    @patch("builtins.input")
    @patch("src.download.DownloadManager.download")
    @patch("src.verify.VerificationManager.verify_appimage", return_value=True)
    @patch("src.file_handler.FileHandler.handle_appimage_operations", return_value=True)
    @patch("src.app_config.AppConfigManager.ask_sha_hash", return_value=("test.sha256", "sha256"))
    @patch("src.api.github_api.GitHubAPI.get_response")
    @patch("src.app_config.AppConfigManager.temp_save_config")
    @patch("src.app_config.AppConfigManager.save_config")
    @patch("src.global_config.GlobalConfigManager.load_config")
    def test_full_flow(
        self,
        mock_gc_load,
        mock_app_save,
        mock_temp_save,
        mock_api_get,
        mock_ask_sha,
        mock_file_handle,
        mock_verify,
        mock_download,
        mock_input,
    ):
        """Integration test for the complete download command flow:
        1. Parse the URL and extract owner/repo.
        2. Ask for SHA file info.
        3. Fetch release data from GitHub (simulated).
        4. Save a temporary configuration.
        5. "Download" the AppImage.
        6. Verify the AppImage.
        7. Run file operations (backup, move, rename, etc.).
        8. Save final configuration.
        """
        # Simulate user entering the GitHub URL.
        mock_input.return_value = "https://github.com/testowner/testrepo"

        # Create a fake API response for GitHubAPI.get_response().
        # In the actual get_response, the API attributes (version, appimage_name, etc.)
        # would be set from the GitHub API JSON response.
        def fake_get_response():
            # We create a fake GitHubAPI instance state.
            api = GitHubAPI(
                owner="testowner",
                repo="testrepo",
                sha_name="test.sha256",
                hash_type="sha256",
                arch_keyword=None,
            )
            api.version = "1.0.0"
            api.appimage_name = "test.AppImage"
            api.appimage_url = "http://example.com/test.AppImage"
            api.sha_url = "http://example.com/test.sha256"
            api.arch_keyword = None
            # To simulate the flow, we also update attributes on the AppConfig later.
            return {
                "owner": api.owner,
                "repo": api.repo,
                "version": api.version,
                "sha_name": api.sha_name,
                "hash_type": api.hash_type,
                "appimage_name": api.appimage_name,
                "arch_keyword": api.arch_keyword,
                "appimage_url": api.appimage_url,
                "sha_url": api.sha_url,
            }

        mock_api_get.side_effect = fake_get_response

        # Now run the full download command execution.
        # All interactive prompts and external calls are mocked so that the flow
        # resembles the real run without doing actual network or file I/O.
        cmd = DownloadCommand()
        cmd.execute()

        # Assert that each key step in the flow was called.
        mock_api_get.assert_called_once()  # GitHubAPI.get_response() was called.
        mock_ask_sha.assert_called_once()  # AppConfigManager.ask_sha_hash() was called.
        mock_temp_save.assert_called_once()  # Temporary configuration was saved.
        mock_download.assert_called_once()  # DownloadManager.download() was invoked.
        mock_verify.assert_called_once()  # VerificationManager.verify_appimage() was run.
        mock_file_handle.assert_called_once()  # FileHandler.handle_appimage_operations() was executed.
        mock_app_save.assert_called_once()  # Final configuration saving took place.
        mock_gc_load.assert_called_once()  # Global configuration was loaded.


if __name__ == "__main__":
    unittest.main()
