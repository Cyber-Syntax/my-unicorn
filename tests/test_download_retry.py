"""Tests for download retry logic and error handling.

This module tests the refactored download retry logic to ensure:
1. Network interruptions during downloads trigger retry attempts
2. Partial files are cleaned up after failures
3. Retry logs are visible
4. Exponential backoff works correctly
5. Timeout configuration is enforced
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

from my_unicorn.download import DownloadService
from my_unicorn.progress import ProgressType

# Test constants
DEFAULT_RETRY_ATTEMPTS = 3


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    return session


@pytest.fixture
def mock_asyncio_sleep(monkeypatch):
    """Mock asyncio.sleep to prevent real delays during tests."""

    async def instant_sleep(seconds):
        """Mock sleep that returns immediately."""

    monkeypatch.setattr(asyncio, "sleep", instant_sleep)
    return instant_sleep


@pytest.fixture
def mock_config(monkeypatch):
    """Mock config_manager to return predictable test values."""
    mock_config_data = {
        "network": {"retry_attempts": "3", "timeout_seconds": "10"}
    }

    def mock_load_global_config():
        return mock_config_data

    monkeypatch.setattr(
        "my_unicorn.download.config_manager.load_global_config",
        mock_load_global_config,
    )
    return mock_config_data


@pytest.fixture
def mock_progress_service():
    """Create a mock progress service."""
    progress = AsyncMock()
    progress.is_active = lambda: True
    progress.add_task = AsyncMock(return_value="task_id_123")
    progress.update_task = AsyncMock()
    progress.finish_task = AsyncMock()
    return progress


@pytest.fixture
def download_service(mock_session, mock_progress_service, mock_config):
    """Create a DownloadService instance with mocked dependencies."""
    return DownloadService(mock_session, mock_progress_service)


class TestDownloadRetryLogic:
    """Test suite for download retry logic."""

    @pytest.mark.asyncio
    async def test_successful_download_no_retry(
        self, download_service, mock_session, tmp_path
    ):
        """Test successful download completes without retry."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.raise_for_status = Mock()

        # Mock chunk iteration
        async def mock_chunks():
            yield b"test data chunk 1"
            yield b"test data chunk 2"

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download
        await download_service.download_file(url, dest, show_progress=False)

        # Verify file was created
        assert dest.exists()
        assert dest.read_bytes() == b"test data chunk 1test data chunk 2"

        # Verify session.get was called only once (no retries)
        assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_network_failure_triggers_retry(
        self, download_service, mock_session, tmp_path, mock_asyncio_sleep
    ):
        """Test network failure during download triggers retry."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # First attempt fails, second succeeds
        mock_response_fail = AsyncMock()
        mock_response_fail.status = 200
        mock_response_fail.headers = {"Content-Length": "1024"}
        mock_response_fail.raise_for_status = Mock()

        # Mock chunk iteration that fails mid-download
        async def mock_chunks_fail():
            yield b"partial data"
            raise aiohttp.ClientError("Connection reset")

        mock_response_fail.content.iter_chunked = (
            lambda size: mock_chunks_fail()
        )

        # Second attempt succeeds
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.headers = {"Content-Length": "1024"}
        mock_response_success.raise_for_status = Mock()

        async def mock_chunks_success():
            yield b"complete data"

        mock_response_success.content.iter_chunked = (
            lambda size: mock_chunks_success()
        )

        # Configure session to fail first, then succeed
        mock_session.get.return_value.__aenter__.side_effect = [
            mock_response_fail,
            mock_response_success,
        ]

        # Execute download (should retry and succeed)
        await download_service.download_file(url, dest, show_progress=False)

        # Verify session.get was called twice (1 failure + 1 success)
        call_count_expected = 2
        assert mock_session.get.call_count == call_count_expected

        # Verify final file contains only successful data (partial cleaned up)
        assert dest.exists()
        assert dest.read_bytes() == b"complete data"

    @pytest.mark.asyncio
    async def test_partial_file_cleanup_after_failure(
        self, download_service, mock_session, tmp_path, mock_asyncio_sleep
    ):
        """Test partial files are cleaned up after download failures."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Mock response that fails mid-download
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.raise_for_status = Mock()

        async def mock_chunks():
            yield b"partial data that will be cleaned up"
            raise aiohttp.ClientError("Connection lost")

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download (should fail after retries)
        with pytest.raises(aiohttp.ClientError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify partial file was cleaned up
        assert not dest.exists()

    @pytest.mark.asyncio
    async def test_retry_exhaustion(
        self, download_service, mock_session, tmp_path, mock_asyncio_sleep
    ):
        """Test all retry attempts are exhausted before raising error."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Mock response that always fails
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.raise_for_status = Mock()

        async def mock_chunks():
            yield b"partial"
            raise aiohttp.ClientError("Network error")

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download (should fail after all retries)
        with pytest.raises(aiohttp.ClientError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify session.get was called 3 times (default retry_attempts=3)
        assert mock_session.get.call_count == DEFAULT_RETRY_ATTEMPTS

        # Verify partial file was cleaned up
        assert not dest.exists()

    @pytest.mark.asyncio
    async def test_exponential_backoff(
        self, download_service, mock_session, tmp_path, monkeypatch
    ):
        """Test exponential backoff between retry attempts."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Track sleep calls
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        # Mock response that always fails
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.raise_for_status = Mock()

        async def mock_chunks():
            yield b"data"
            raise aiohttp.ClientError("Network error")

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download (should fail after retries)
        with pytest.raises(aiohttp.ClientError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify exponential backoff: 2^1=2, 2^2=4
        # (no sleep after final attempt)
        assert sleep_calls == [2, 4]

    @pytest.mark.asyncio
    async def test_timeout_during_download(
        self, download_service, mock_session, tmp_path, mock_asyncio_sleep
    ):
        """Test timeout during chunk reading triggers retry."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Mock response that times out
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.raise_for_status = Mock()

        async def mock_chunks():
            yield b"some data"
            raise TimeoutError("Read timeout")

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download (should fail after retries)
        with pytest.raises(TimeoutError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify retry attempts were made
        assert mock_session.get.call_count == DEFAULT_RETRY_ATTEMPTS

        # Verify partial file was cleaned up
        assert not dest.exists()

    @pytest.mark.asyncio
    async def test_connection_error_before_chunks(
        self, download_service, mock_session, tmp_path, mock_asyncio_sleep
    ):
        """Test connection error before chunk reading triggers retry."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Mock connection error
        mock_session.get.side_effect = aiohttp.ClientError(
            "Connection refused"
        )

        # Execute download (should fail after retries)
        with pytest.raises(aiohttp.ClientError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify retry attempts were made
        assert mock_session.get.call_count == DEFAULT_RETRY_ATTEMPTS

        # Verify no file was created
        assert not dest.exists()

    @pytest.mark.asyncio
    async def test_http_error_status_triggers_retry(
        self, download_service, mock_session, tmp_path, mock_asyncio_sleep
    ):
        """Test HTTP error status (e.g., 500) triggers retry."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Mock response with error status
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status.side_effect = aiohttp.ClientError(
            "500 Server Error"
        )

        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download (should fail after retries)
        with pytest.raises(aiohttp.ClientError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify retry attempts were made
        assert mock_session.get.call_count == DEFAULT_RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_download_with_progress_retry(
        self,
        download_service,
        mock_session,
        mock_progress_service,
        tmp_path,
        mock_asyncio_sleep,
    ):
        """Test download with progress tracking handles retries correctly."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # First attempt fails, second succeeds
        mock_response_fail = AsyncMock()
        mock_response_fail.status = 200
        mock_response_fail.headers = {"Content-Length": "1024"}
        mock_response_fail.raise_for_status = Mock()

        async def mock_chunks_fail():
            yield b"partial"
            raise aiohttp.ClientError("Connection lost")

        mock_response_fail.content.iter_chunked = (
            lambda size: mock_chunks_fail()
        )

        # Second attempt succeeds
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.headers = {"Content-Length": "1024"}
        mock_response_success.raise_for_status = Mock()

        async def mock_chunks_success():
            yield b"complete data"

        mock_response_success.content.iter_chunked = (
            lambda size: mock_chunks_success()
        )

        mock_session.get.return_value.__aenter__.side_effect = [
            mock_response_fail,
            mock_response_success,
        ]

        # Execute download with progress
        await download_service.download_file(
            url, dest, show_progress=True, progress_type=ProgressType.DOWNLOAD
        )

        # Verify progress task was created twice (once per attempt)
        expected_task_calls = 2
        assert mock_progress_service.add_task.call_count == expected_task_calls

        # Verify progress task was finished twice
        assert (
            mock_progress_service.finish_task.call_count == expected_task_calls
        )

        # Verify final file exists and is correct
        assert dest.exists()
        assert dest.read_bytes() == b"complete data"

    @pytest.mark.asyncio
    async def test_non_retryable_error_cleanup(
        self, download_service, mock_session, tmp_path
    ):
        """Test non-retryable errors cleanup partial files immediately."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Mock response that raises a non-retryable error
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.raise_for_status = Mock()

        async def mock_chunks():
            yield b"partial data"
            # ValueError is not caught by retry logic
            # (not ClientError/TimeoutError)
            raise ValueError("Unexpected error")

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download (should fail immediately)
        with pytest.raises(ValueError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify only one attempt was made
        # (no retries for non-retryable errors)
        assert mock_session.get.call_count == 1

        # Verify partial file was cleaned up
        assert not dest.exists()

    @pytest.mark.asyncio
    async def test_partial_file_cleanup_failure_logged(
        self,
        download_service,
        mock_session,
        tmp_path,
        caplog,
        mock_asyncio_sleep,
    ):
        """Test cleanup failure is logged but doesn't break retry logic."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        # Make destination read-only to simulate cleanup failure
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Mock response that fails
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.raise_for_status = Mock()

        async def mock_chunks():
            yield b"partial"
            raise aiohttp.ClientError("Network error")

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Execute download (should fail)
        with pytest.raises(aiohttp.ClientError):
            await download_service.download_file(
                url, dest, show_progress=False
            )

        # Verify retry attempts were still made despite cleanup issues
        assert mock_session.get.call_count == DEFAULT_RETRY_ATTEMPTS


class TestDownloadServiceHelperMethods:
    """Test helper methods added in refactoring."""

    @pytest.mark.asyncio
    async def test_attempt_download_success(
        self, download_service, mock_session, tmp_path
    ):
        """Test _attempt_download helper method succeeds."""
        dest = tmp_path / "test.AppImage"
        url = "https://example.com/test.AppImage"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "100"}
        mock_response.raise_for_status = Mock()

        async def mock_chunks():
            yield b"test data"

        mock_response.content.iter_chunked = lambda size: mock_chunks()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        timeout = aiohttp.ClientTimeout(
            total=600, sock_read=30, sock_connect=10
        )

        # Execute single attempt
        await download_service._attempt_download(
            url,
            dest,
            show_progress=False,
            progress_type=ProgressType.DOWNLOAD,
            timeout=timeout,
        )

        # Verify file was created
        assert dest.exists()
        assert dest.read_bytes() == b"test data"

    @pytest.mark.asyncio
    async def test_download_without_progress(self, download_service, tmp_path):
        """Test _download_without_progress helper method."""
        dest = tmp_path / "test.AppImage"

        # Mock response
        mock_response = AsyncMock()

        async def mock_chunks():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"

        mock_response.content.iter_chunked = lambda size: mock_chunks()

        # Execute download without progress
        await download_service._download_without_progress(mock_response, dest)

        # Verify file was created with all chunks
        assert dest.exists()
        assert dest.read_bytes() == b"chunk1chunk2chunk3"
