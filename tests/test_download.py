"""Test module for download manager functionality.

This module tests the download manager and progress display functionality,
with a focus on concurrent download handling.
"""

import os
import threading
import time
from typing import List, TYPE_CHECKING
from unittest.mock import MagicMock, patch, mock_open
import sys
import pytest
import requests
import unittest

from src.download import DownloadManager 
from src.progress_manager import DynamicProgressManager
from src.api import GitHubAPI

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def mock_github_api() -> MagicMock:
    """Create a mock GitHub API for testing.

    Returns:
        MagicMock: A mocked GitHubAPI instance
    """
    mock_api = MagicMock(spec=GitHubAPI)
    mock_api.appimage_url = "https://example.com/test.AppImage"
    mock_api.appimage_name = "test.AppImage"
    mock_api.version = "1.0.0"
    return mock_api


@pytest.fixture
def mock_requests_responses(monkeypatch: "MonkeyPatch") -> None:
    """Mock requests responses for testing downloads.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    # Mock head response
    mock_head = MagicMock()
    mock_head.raise_for_status = MagicMock()
    mock_head.headers = {"content-length": "1024000"}  # 1MB file

    # Mock get response
    mock_get = MagicMock()
    mock_get.raise_for_status = MagicMock()
    # Generate some fake content chunks for the download
    chunks = [b"x" * 102400] * 10  # 10 chunks of 100KB each
    mock_get.iter_content = MagicMock(return_value=chunks)

    # Patch the requests methods
    monkeypatch.setattr(requests, "head", lambda *args, **kwargs: mock_head)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: mock_get)


@pytest.fixture(autouse=True)
def cleanup_progress_manager() -> None:
    """Reset the ProgressManager singleton between tests."""
    # Reset before test
    ProgressManager._instance = None

    # Run the test
    yield

    # Reset after test
    ProgressManager._instance = None


@pytest.fixture
def setup_download_dir() -> None:
    """Set up and clean up the downloads directory."""
    # Create directory if it doesn't exist
    os.makedirs("downloads", exist_ok=True)

    # Run the test
    yield

    # Clean up test files
    if os.path.exists("downloads/test.AppImage"):
        os.remove("downloads/test.AppImage")
    if os.path.exists("downloads/test2.AppImage"):
        os.remove("downloads/test2.AppImage")


def test_progress_manager_singleton() -> None:
    """Test that ProgressManager maintains a single instance."""
    # Create two instances
    manager1 = ProgressManager()
    manager2 = ProgressManager()

    # Verify they're the same object
    assert manager1 is manager2
    assert id(manager1) == id(manager2)


def test_progress_manager_reference_counting() -> None:
    """Test that ProgressManager tracks references correctly."""
    manager = ProgressManager()

    # Initially no progress display
    assert manager._progress is None
    assert manager._user_count == 0

    # First use creates progress
    with manager.get_progress() as progress1:
        assert manager._progress is not None
        assert manager._user_count == 1

        # Second use increments counter
        with manager.get_progress() as progress2:
            assert manager._user_count == 2
            # Both references point to the same progress
            assert progress1 is progress2

        # Back to one user
        assert manager._user_count == 1
        assert manager._progress is not None

    # No more users, progress cleaned up
    assert manager._user_count == 0
    assert manager._progress is None


def test_download_manager_basic(
    mock_github_api: MagicMock, mock_requests_responses: None, setup_download_dir: None
) -> None:
    """Test basic download functionality with progress display.

    Args:
        mock_github_api: Mock GitHub API fixture
        mock_requests_responses: Mock requests responses fixture
        setup_download_dir: Fixture to set up and clean download directory
    """
    # Create download manager
    download_manager = DownloadManager(mock_github_api)

    # Perform download
    download_manager.download()

    # Verify file was created
    assert os.path.exists("downloads/test.AppImage")


def test_concurrent_downloads(
    mock_github_api: MagicMock, mock_requests_responses: None, setup_download_dir: None
) -> None:
    """Test that concurrent downloads share the same progress display.

    Args:
        mock_github_api: Mock GitHub API fixture
        mock_requests_responses: Mock requests responses fixture
        setup_download_dir: Fixture to set up and clean download directory
    """
    # Create two API objects with different filenames
    api1 = MagicMock(spec=GitHubAPI)
    api1.appimage_url = "https://example.com/test.AppImage"
    api1.appimage_name = "test.AppImage"

    api2 = MagicMock(spec=GitHubAPI)
    api2.appimage_url = "https://example.com/test2.AppImage"
    api2.appimage_name = "test2.AppImage"

    # Create download managers
    dm1 = DownloadManager(api1)
    dm2 = DownloadManager(api2)

    # Create a function to run in a thread
    def download_thread(download_manager: DownloadManager) -> None:
        download_manager.download()

    # Launch two download threads
    threads: List[threading.Thread] = []

    # Start first thread
    t1 = threading.Thread(target=download_thread, args=(dm1,))
    t1.start()
    threads.append(t1)

    # Small delay to ensure first thread has started
    time.sleep(0.1)

    # Start second thread
    t2 = threading.Thread(target=download_thread, args=(dm2,))
    t2.start()
    threads.append(t2)

    # Wait for both threads to complete
    for thread in threads:
        thread.join()

    # Verify both files were created
    assert os.path.exists("downloads/test.AppImage")
    assert os.path.exists("downloads/test2.AppImage")

    # Verify progress manager was properly cleaned up
    progress_manager = ProgressManager()
    assert progress_manager._progress is None
    assert progress_manager._user_count == 0


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
