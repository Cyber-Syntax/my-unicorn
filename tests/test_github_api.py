import unittest
from unittest.mock import Mock, patch

from src.api import GitHubAPI

class TestGitHubAPI(unittest.TestCase):
    """Test cases for GitHubAPI class"""

    @patch("src.api.requests.get")
    def test_get_latest_release(self, mock_get):
        """Test fetching latest release with mock response and separate SHA asset"""
        # Arrange - Setup mock response with two assets: one AppImage and one SHA file.
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v1.2.3",
            "assets": [
                {"name": "app-arm64.AppImage", "browser_download_url": "http://example.com/app"},
                {
                    "name": "app-x86_64.sha256",
                    "browser_download_url": "http://example.com/app.sha256",
                },
                {
                    "name": "app-x86_64.sha512",
                    "browser_download_url": "http://example.com/app.sha512",
                },
                {"name": "app-x86_64.AppImage", "browser_download_url": "http://example.com/app"},
            ],
        }
        mock_get.return_value = mock_response

        # Act - Create API instance and call method
        api = GitHubAPI(owner="test", repo="app")
        result = api.get_response()

        # Assert - Verify expected outcomes
        self.assertEqual(result["version"], "1.2.3")
        self.assertEqual(result["appimage_url"], "http://example.com/app")
        # self.assertEqual(result["sha_name"], "app-x86_64.sha256")
        # self.assertEqual(result["sha_url"], "http://example.com/app.sha256")
        # Check that the selected appimage file contains ".AppImage"
        # self.assertTrue(result["appimage_name"].endswith(".AppImage"))
        mock_get.assert_called_once_with(
            "https://api.github.com/repos/test/app/releases/latest", timeout=10
        )

    @patch("platform.machine", return_value="x86_64")
    def test_arch_keyword_detection(self, mock_machine):
        """Test architecture keyword detection for x86_64"""
        api = GitHubAPI(owner="test", repo="app")
        # For x86_64 we expect keywords like "amd64" and "x86_64"
        self.assertIn("amd64", api.arch_keywords)
        self.assertIn("x86_64", api.arch_keywords)

    @patch("platform.machine", return_value="")
    def test_arch_keyword_detection_with_empty_machine(self, mock_machine):
        """Test that an empty machine string yields an empty keywords list"""
        api = GitHubAPI(owner="test", repo="app")
        self.assertEqual(api.arch_keywords, [])

    @patch("builtins.input", side_effect=["2"])
    @patch("src.api.requests.get")
    def test_get_response_missing_sha(self, mock_get, mock_input):
        """Test handling a release that lacks any SHA file asset.
        By choosing option '2' in the fallback, the API should set sha_name to 'no_sha_file'.
        """
        # Arrange: Create a fake release response that only includes an AppImage asset.
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v1.2.3",
            "assets": [
                {"name": "app-x86_64.AppImage", "browser_download_url": "http://example.com/app"}
            ],
        }
        mock_get.return_value = mock_response

        # Act: Create API instance without a pre-set sha_name, triggering the fallback.
        api = GitHubAPI(owner="test", repo="app", sha_name=None)
        result = api.get_response()

        # Assert: Ensure that after the fallback, sha_name is set to "no_sha_file"
        self.assertEqual(api.sha_name, "no_sha_file")
        # Also check that version and appimage details are correctly set.
        self.assertEqual(api.version, "1.2.3")
        self.assertTrue(api.appimage_name.endswith(".AppImage"))


if __name__ == "__main__":
    unittest.main()
