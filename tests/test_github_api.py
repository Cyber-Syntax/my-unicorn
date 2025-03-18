import unittest
from unittest.mock import patch, MagicMock
from src.api import GitHubAPI

class TestGitHubAPI(unittest.TestCase):

    @patch('requests.get')
    def test_get_response_success(self, mock_get):
        # Mock the response to simulate a successful API call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v1.0.0",
            "assets": [
                {"name": "test.AppImage", "browser_download_url": "http://example.com/test.AppImage"}
            ]
        }
        mock_get.return_value = mock_response

        api = GitHubAPI(owner='test_owner', repo='test_repo')
        response = api.get_response()

        self.assertIsNotNone(response)
        self.assertEqual(response['version'], '1.0.0')
        self.assertEqual(response['appimage_name'], 'test.AppImage')

    @patch('requests.get')
    def test_get_response_failure(self, mock_get):
        # Mock the response to simulate a failed API call
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        api = GitHubAPI(owner='test_owner', repo='test_repo')
        response = api.get_response()

        self.assertIsNone(response)

    @patch('requests.get')
    def test_get_response_beta_fallback(self, mock_get):
        # Mock the response to simulate a beta fallback scenario
        mock_response_latest = MagicMock()
        mock_response_latest.status_code = 404

        mock_response_beta = MagicMock()
        mock_response_beta.status_code = 200
        mock_response_beta.json.return_value = [
            {
                "tag_name": "v1.0.0-beta",
                "assets": [
                    {"name": "test-beta.AppImage", "browser_download_url": "http://example.com/test-beta.AppImage"}
                ]
            }
        ]

        mock_get.side_effect = [mock_response_latest, mock_response_beta]

        api = GitHubAPI(owner='test_owner', repo='test_repo')
        response = api.get_response()

        self.assertIsNotNone(response)
        self.assertEqual(response['version'], '1.0.0-beta')
        self.assertEqual(response['appimage_name'], 'test-beta.AppImage')

if __name__ == '__main__':
    unittest.main()
