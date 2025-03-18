import unittest
from unittest.mock import patch, MagicMock
from src.download import DownloadManager
from src.api import GitHubAPI

class TestDownloadManager(unittest.TestCase):

    @patch('requests.get')
    def test_download_success(self, mock_get):
        # Mock the response to simulate a successful download
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content = lambda chunk_size: [b'a' * chunk_size] * 128
        mock_get.return_value = mock_response

        api = GitHubAPI(owner='test_owner', repo='test_repo')
        api.appimage_name = 'test.AppImage'
        api.appimage_url = 'http://example.com/test.AppImage'
        download_manager = DownloadManager(api)

        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            with patch('os.path.exists', return_value=False):
                with patch('tqdm.tqdm') as mock_tqdm:
                    download_manager.download()
                    mock_file.assert_called_once_with('test.AppImage', 'wb')
                    mock_tqdm.assert_called_once()

    @patch('requests.get')
    def test_download_file_exists(self, mock_get):
        api = GitHubAPI(owner='test_owner', repo='test_repo')
        api.appimage_name = 'test.AppImage'
        api.appimage_url = 'http://example.com/test.AppImage'
        download_manager = DownloadManager(api)

        with patch('os.path.exists', return_value=True):
            download_manager.download()
            mock_get.assert_not_called()

    @patch('requests.get')
    def test_download_failure(self, mock_get):
        # Mock the response to simulate a failed download
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        api = GitHubAPI(owner='test_owner', repo='test_repo')
        api.appimage_name = 'test.AppImage'
        api.appimage_url = 'http://example.com/test.AppImage'
        download_manager = DownloadManager(api)

        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            with patch('os.path.exists', return_value=False):
                with self.assertRaises(SystemExit):
                    download_manager.download()
                    mock_file.assert_not_called()

if __name__ == '__main__':
    unittest.main()
