import unittest
from unittest.mock import MagicMock, mock_open, patch

from src.download import DownloadManager


# A fake API object to simulate the attributes that DownloadManager expects.
class FakeAPI:
    def __init__(self, appimage_name, appimage_url):
        self.appimage_name = appimage_name
        self.appimage_url = appimage_url


class TestDownloadManager(unittest.TestCase):
    @patch("os.path.exists")
    def test_is_app_exist_not_set(self, mock_exists):
        # When appimage_name is not set, is_app_exist() should print a message and return False.
        fake_api = FakeAPI(None, None)
        dm = DownloadManager(fake_api)
        with patch("builtins.print") as mock_print:
            self.assertFalse(dm.is_app_exist())
            mock_print.assert_called_with("AppImage name is not set.")

    @patch("os.path.exists")
    def test_is_app_exist_true(self, mock_exists):
        # If the file exists (os.path.exists returns True), is_app_exist() should return True.
        fake_api = FakeAPI("test.AppImage", "http://example.com/test.AppImage")
        dm = DownloadManager(fake_api)
        mock_exists.return_value = True
        with patch("builtins.print") as mock_print:
            self.assertTrue(dm.is_app_exist())
            mock_print.assert_called_with("test.AppImage already exists in the current directory")

    @patch("src.download.requests.get")
    @patch("os.path.exists")
    def test_download_success(self, mock_exists, mock_get):
        # If the file does not exist, download() should call requests.get, write file chunks, and close the response.
        fake_api = FakeAPI("test.AppImage", "http://example.com/test.AppImage")
        dm = DownloadManager(fake_api)
        mock_exists.return_value = False

        # Create a fake response object with necessary attributes.
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"content-length": "16"}
        # Simulate iter_content yielding several chunks.
        fake_response.iter_content = lambda chunk_size: [b"1234", b"5678", b"abcd", b"efgh"]
        fake_response.close = MagicMock()
        mock_get.return_value = fake_response

        # Patch open to simulate file writing and patch tqdm to avoid lengthy progress bar output.
        m = mock_open()
        with patch("builtins.open", m), patch("tqdm.tqdm") as mock_tqdm:
            dm.download()

        # Verify that write was called at least once and that the response was closed.
        handle = m()
        handle.write.assert_any_call(b"1234")
        fake_response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
