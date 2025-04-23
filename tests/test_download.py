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
import asyncio
import tempfile
from typing import Dict, Any, Set
from rich.console import Console
import responses

from src.download import DownloadManager, MultiAppProgress
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


class TestMultiAppProgress:
    """Tests for the MultiAppProgress class."""

    def test_get_renderables(self) -> None:
        """Test that get_renderables properly formats task renderings."""
        # Create a progress instance
        progress = MultiAppProgress()

        # Add a task
        task_id = progress.add_task("Test download", total=100, prefix="[1/2] ")

        # Get renderables
        renderables = progress.get_renderables()

        # Check we have exactly one renderable (for our one task)
        assert len(renderables) == 1

        # Add another task
        task_id2 = progress.add_task("Another download", total=200, prefix="[2/2] ")

        # Get renderables again
        renderables = progress.get_renderables()

        # Now we should have two renderables
        assert len(renderables) == 2

    def test_hidden_tasks_not_rendered(self) -> None:
        """Test that hidden tasks are not included in renderables."""
        # Create a progress instance
        progress = MultiAppProgress()

        # Add a visible task
        visible_task = progress.add_task("Visible task", total=100)

        # Add a hidden task
        hidden_task = progress.add_task("Hidden task", total=100, visible=False)

        # Get renderables
        renderables = progress.get_renderables()

        # We should only have one renderable for the visible task
        assert len(renderables) == 1


class TestDownloadManager:
    """Tests for the DownloadManager class."""

    @pytest.fixture
    def mock_github_api(self) -> MagicMock:
        """Create a mock GitHub API instance."""
        mock_api = MagicMock()
        mock_api.appimage_url = "https://example.com/app.AppImage"
        mock_api.appimage_name = "app.AppImage"
        mock_api.version = "1.0.0"
        return mock_api

    @pytest.fixture
    def download_manager(self, mock_github_api: MagicMock) -> DownloadManager:
        """Create a DownloadManager instance with a mock GitHub API."""
        return DownloadManager(mock_github_api, app_index=1, total_apps=2)

    def test_init(self, download_manager: DownloadManager, mock_github_api: MagicMock) -> None:
        """Test proper initialization of DownloadManager."""
        assert download_manager.github_api == mock_github_api
        assert download_manager.app_index == 1
        assert download_manager.total_apps == 2
        assert download_manager._progress_task_id is None

    def test_format_size(self, download_manager: DownloadManager) -> None:
        """Test size formatting function."""
        assert download_manager._format_size(0) == "0 B"
        assert download_manager._format_size(1024) == "1.0 KB"
        assert download_manager._format_size(1024 * 1024) == "1.0 MB"
        assert download_manager._format_size(1024 * 1024 * 1024) == "1.0 GB"
        assert download_manager._format_size(500) == "500 B"
        assert download_manager._format_size(1500) == "1.5 KB"

    def test_get_or_create_progress(self) -> None:
        """Test the get_or_create_progress class method."""
        # Ensure we start with no progress instance
        DownloadManager._global_progress = None
        DownloadManager._active_tasks = set()

        # Get a progress instance
        progress1 = DownloadManager.get_or_create_progress()

        # Verify it's a MultiAppProgress instance
        assert isinstance(progress1, MultiAppProgress)

        # Get another progress instance
        progress2 = DownloadManager.get_or_create_progress()

        # Verify it's the same instance
        assert progress1 is progress2

        # Clean up
        DownloadManager.stop_progress()
        assert DownloadManager._global_progress is None
        assert DownloadManager._active_tasks == set()

    @responses.activate
    def test_download_success(self, download_manager: DownloadManager, tmp_path: str) -> None:
        """Test successful download."""
        # Mock the directory
        download_dir = tmp_path / "downloads"
        os.makedirs(download_dir, exist_ok=True)

        # Set up mock responses
        test_url = "https://example.com/app.AppImage"
        test_content = b"test file content"

        # Mock the HEAD request to get content length
        responses.add(
            responses.HEAD, test_url, headers={"content-length": str(len(test_content))}, status=200
        )

        # Mock the GET request for the actual download
        responses.add(responses.GET, test_url, body=test_content, status=200, stream=True)

        # Apply patches for filesystem operations
        with patch("os.makedirs"), patch("os.chmod"), patch("builtins.open", mock_open()), patch(
            "os.stat"
        ), patch.object(download_manager, "_download_with_nested_progress") as mock_download:
            # Call the method
            download_manager.download()

            # Verify the method was called with correct parameters
            mock_download.assert_called_once_with(
                test_url,
                "app.AppImage",
                {"User-Agent": "AppImage-Updater/1.0", "Accept": "application/octet-stream"},
                isinstance(mock_download.call_args[0][3], Console),
                "[1/2] ",
            )

    def test_download_missing_url(self, download_manager: DownloadManager) -> None:
        """Test download with missing URL."""
        # Set missing URL
        download_manager.github_api.appimage_url = None

        # Verify it raises ValueError
        with pytest.raises(ValueError, match="AppImage URL or name not available"):
            download_manager.download()

    def test_download_missing_name(self, download_manager: DownloadManager) -> None:
        """Test download with missing filename."""
        # Set missing name
        download_manager.github_api.appimage_name = None

        # Verify it raises ValueError
        with pytest.raises(ValueError, match="AppImage URL or name not available"):
            download_manager.download()

    @responses.activate
    def test_download_with_nested_progress(
        self, download_manager: DownloadManager, tmp_path: str
    ) -> None:
        """Test the _download_with_nested_progress method with mocked responses."""
        # Mock data
        test_url = "https://example.com/app.AppImage"
        test_name = "app.AppImage"
        test_content = b"test file content" * 1000  # Make it large enough to test progress
        test_headers = {"User-Agent": "Test"}
        test_console = Console()
        test_prefix = "[1/2] "

        # Set up temporary directory
        downloads_dir = tmp_path / "downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        download_path = os.path.join(downloads_dir, test_name)

        # Mock responses
        responses.add(
            responses.HEAD, test_url, headers={"content-length": str(len(test_content))}, status=200
        )

        responses.add(responses.GET, test_url, body=test_content, status=200, stream=True)

        # Apply patches
        with patch("os.makedirs"), patch("os.chmod"), patch("os.stat"), patch(
            "builtins.open", mock_open()
        ) as mock_file, patch.object(
            DownloadManager, "get_or_create_progress"
        ) as mock_progress_getter:
            # Create mock progress
            mock_progress = MagicMock()
            mock_progress_getter.return_value = mock_progress

            # Set mock task ID
            mock_progress.add_task.return_value = 1

            # Call the method
            download_manager._download_with_nested_progress(
                test_url, test_name, test_headers, test_console, test_prefix
            )

            # Verify progress tracking was created
            mock_progress.add_task.assert_called_once()
            assert "Downloading app.AppImage" in mock_progress.add_task.call_args[0][0]

            # Verify the progress was updated
            mock_progress.update.assert_called()

            # Verify file was written
            mock_file().write.assert_called()

            # Verify task cleanup
            mock_progress.remove_task.assert_called_once_with(1)

    @responses.activate
    def test_download_network_error(self, download_manager: DownloadManager) -> None:
        """Test handling of network errors during download."""
        # Mock failing request
        test_url = "https://example.com/app.AppImage"
        test_name = "app.AppImage"
        responses.add(responses.HEAD, test_url, status=404)

        # Apply patches
        with patch("os.makedirs"), patch("builtins.open", mock_open()), patch.object(
            DownloadManager, "get_or_create_progress"
        ) as mock_progress_getter, patch.object(Console, "print") as mock_print:
            # Create mock progress
            mock_progress = MagicMock()
            mock_progress_getter.return_value = mock_progress

            # Call the method and check for expected exception
            with pytest.raises(RuntimeError, match="Network error while downloading"):
                download_manager._download_with_nested_progress(
                    test_url, test_name, {}, Console(), "[1/2] "
                )

            # Verify error message was printed
            mock_print.assert_called_once()
            assert "Download failed" in mock_print.call_args[0][0]

    @patch("threading.Thread")
    def test_concurrent_downloads(self, mock_thread: MagicMock, mock_github_api: MagicMock) -> None:
        """Test concurrent downloads don't interfere with each other."""
        # Create two download managers
        dm1 = DownloadManager(mock_github_api, app_index=1, total_apps=2)
        dm2 = DownloadManager(mock_github_api, app_index=2, total_apps=2)

        # Mock the _download_with_nested_progress method to avoid actual downloads
        with patch.object(dm1, "_download_with_nested_progress") as mock_download1, patch.object(
            dm2, "_download_with_nested_progress"
        ) as mock_download2, patch("os.makedirs"):
            # Run downloads from separate threads to simulate concurrency
            thread1 = threading.Thread(target=dm1.download)
            thread2 = threading.Thread(target=dm2.download)

            thread1.start()
            thread2.start()

            thread1.join()
            thread2.join()

            # Verify both download methods were called
            mock_download1.assert_called_once()
            mock_download2.assert_called_once()

        # Clean up
        DownloadManager.stop_progress()

    def test_stop_progress_handles_exceptions(self) -> None:
        """Test that stop_progress handles exceptions gracefully."""
        # Setup a mock progress that raises an exception when stopped
        mock_progress = MagicMock()
        mock_progress.stop.side_effect = Exception("Test exception")
        DownloadManager._global_progress = mock_progress
        DownloadManager._active_tasks = {1, 2, 3}

        # Call stop_progress
        with patch("logging.error") as mock_log_error:
            DownloadManager.stop_progress()

            # Verify the exception was logged
            mock_log_error.assert_called_once()
            assert "Error stopping progress display" in mock_log_error.call_args[0][0]

            # Verify the progress was still cleaned up
            assert DownloadManager._global_progress is None
            assert DownloadManager._active_tasks == set()


if __name__ == "__main__":
    unittest.main()
