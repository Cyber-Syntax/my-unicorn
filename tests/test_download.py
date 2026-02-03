"""Tests for DownloadService including protocol usage and async file I/O."""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from my_unicorn.core.download import DownloadError, DownloadService
from my_unicorn.core.github import Asset
from my_unicorn.core.protocols import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)

# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
def tmp_file(tmp_path: Path) -> Path:
    """Create a temporary file path for downloads."""
    return tmp_path / "testfile.bin"


@pytest_asyncio.fixture
def mock_session():
    """Provide a mock aiohttp.ClientSession."""
    return MagicMock()


@pytest_asyncio.fixture
def patch_logger():
    """Patch get_logger to avoid real logging output."""
    with patch("my_unicorn.core.download.get_logger") as mock_logger:
        yield mock_logger


async def async_chunk_gen(
    chunks: list[bytes],
) -> AsyncGenerator[bytes, None]:
    """Async generator yielding chunks for simulating HTTP responses."""
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
async def test_download_file_success(tmp_file, mock_session, patch_logger):
    """Test DownloadService.download_file downloads file successfully."""
    content = b"hello world"
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.headers = {"Content-Length": str(len(content))}
    mock_response.content.iter_chunked = lambda size: async_chunk_gen(
        [content]
    )
    mock_response.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    await service.download_file(
        url="http://example.com/file.bin",
        dest=tmp_file,
    )

    assert tmp_file.exists()
    assert tmp_file.read_bytes() == content


@pytest.mark.asyncio
async def test_download_file_error(tmp_file, mock_session, patch_logger):
    """Test DownloadService.download_file handles error during download."""
    content = b"data"
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.headers = {"Content-Length": str(len(content))}
    mock_response.content.iter_chunked = lambda size: async_chunk_gen(
        [content]
    )
    mock_response.raise_for_status = MagicMock(
        side_effect=DownloadError("Network error")
    )
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    with pytest.raises(DownloadError, match="Failed to download"):
        await service.download_file(
            url="http://example.com/file.bin",
            dest=tmp_file,
        )


@pytest.mark.asyncio
async def test_download_appimage_success(tmp_file, mock_session, patch_logger):
    """Test DownloadService.download_appimage downloads AppImage."""
    asset = Asset(
        name="test.AppImage",
        size=100,
        browser_download_url="http://example.com/appimage",
        digest=None,
    )
    content = b"appimage"
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.headers = {"Content-Length": str(len(content))}
    mock_response.content.iter_chunked = lambda size: async_chunk_gen(
        [content]
    )
    mock_response.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    result = await service.download_appimage(asset, tmp_file)
    assert result == tmp_file
    assert tmp_file.read_bytes() == content


def test_get_filename_from_url():
    """Test get_filename_from_url extracts filename."""
    service = DownloadService(MagicMock())
    url = "https://github.com/owner/repo/releases/download/v1.0.0/app.AppImage"
    assert service.get_filename_from_url(url) == "app.AppImage"


@pytest.mark.asyncio
async def test_download_checksum_file_success(mock_session, patch_logger):
    """Test download_checksum_file returns content."""
    content = "abc123"
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.headers = {"Content-Length": str(len(content))}
    mock_response.text = AsyncMock(return_value=content)
    mock_response.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    result = await service.download_checksum_file(
        "http://example.com/checksum.txt"
    )
    assert result == content


@pytest.mark.asyncio
async def test_download_checksum_file_error(mock_session, patch_logger):
    """Test download_checksum_file raises on error."""
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.raise_for_status = MagicMock(
        side_effect=DownloadError("Checksum error")
    )
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    with pytest.raises(DownloadError, match="Failed to download"):
        await service.download_checksum_file("http://example.com/checksum.txt")


def test_download_error_exception():
    """Test DownloadError can be raised and caught."""
    with pytest.raises(DownloadError, match="fail"):
        raise DownloadError("fail")


# ---------------------------------------------------------------------------
# MockProgressReporter for tracking progress calls
# ---------------------------------------------------------------------------


class MockProgressReporter(ProgressReporter):
    """Mock implementation of ProgressReporter for testing.

    Tracks all method calls for verification in tests.
    Methods are async to match the download service's await usage.
    """

    def __init__(self) -> None:
        """Initialize mock reporter with empty tracking collections."""
        self.tasks: dict[str, dict] = {}
        self.updates: list[tuple[str, float | None, str | None]] = []
        self.finished: list[tuple[str, bool, str | None]] = []
        self._active = True
        self._task_counter = 0

    def is_active(self) -> bool:
        """Return whether the reporter is active."""
        return self._active

    async def add_task(
        self,
        name: str,
        progress_type: ProgressType,
        total: float | None = None,
    ) -> str:
        """Add a task and return its ID."""
        self._task_counter += 1
        task_id = f"mock-task-{self._task_counter}"
        self.tasks[task_id] = {
            "name": name,
            "progress_type": progress_type,
            "total": total,
            "completed": 0,
            "description": "",
        }
        return task_id

    async def update_task(
        self,
        task_id: str,
        completed: float | None = None,
        description: str | None = None,
    ) -> None:
        """Record a task update."""
        self.updates.append((task_id, completed, description))
        if task_id in self.tasks:
            if completed is not None:
                self.tasks[task_id]["completed"] = completed
            if description is not None:
                self.tasks[task_id]["description"] = description

    async def finish_task(
        self,
        task_id: str,
        *,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Record a task finish."""
        self.finished.append((task_id, success, description))

    def get_task_info(self, task_id: str) -> dict[str, object]:
        """Get task info by ID."""
        if task_id in self.tasks:
            return self.tasks[task_id]
        return {"completed": 0.0, "total": None, "description": ""}


# ---------------------------------------------------------------------------
# Protocol Usage Tests (Task 2.1)
# ---------------------------------------------------------------------------


class TestDownloadServiceProtocolUsage:
    """Test that DownloadService uses ProgressReporter protocol correctly."""

    def test_accepts_progress_reporter_protocol(self, mock_session):
        """DownloadService accepts any ProgressReporter implementation."""
        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)
        assert service.progress_reporter is reporter

    def test_uses_null_reporter_when_none_provided(self, mock_session):
        """DownloadService uses NullProgressReporter when none provided."""
        service = DownloadService(mock_session, progress_reporter=None)
        assert isinstance(service.progress_reporter, NullProgressReporter)

    def test_uses_null_reporter_by_default(self, mock_session):
        """DownloadService should default to NullProgressReporter."""
        service = DownloadService(mock_session)
        assert isinstance(service.progress_reporter, NullProgressReporter)

    def test_null_reporter_is_not_active(self, mock_session):
        """NullProgressReporter should report as inactive."""
        service = DownloadService(mock_session)
        assert service.progress_reporter.is_active() is False

    def test_mock_reporter_is_active(self, mock_session):
        """MockProgressReporter should report as active."""
        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)
        assert service.progress_reporter.is_active() is True


# ---------------------------------------------------------------------------
# Async File I/O Tests (Task 2.2)
# ---------------------------------------------------------------------------


class TestDownloadServiceAsyncFileIO:
    """Test async file I/O behavior using aiofiles."""

    @pytest.mark.asyncio
    async def test_download_uses_aiofiles_when_available(
        self, tmp_file, mock_session, patch_logger
    ):
        """Download should use aiofiles for async file I/O."""
        content = b"test content for aiofiles"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(len(content))}
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content]
        )
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        with (
            patch("my_unicorn.core.download.HAS_AIOFILES", True),
            patch("my_unicorn.core.download.aiofiles") as mock_aiofiles,
        ):
            mock_file = AsyncMock()
            mock_aiofiles.open.return_value.__aenter__.return_value = mock_file
            mock_aiofiles.open.return_value.__aexit__.return_value = None

            service = DownloadService(mock_session)
            await service._download_without_progress(mock_response, tmp_file)

            mock_aiofiles.open.assert_called_once_with(tmp_file, mode="wb")
            mock_file.write.assert_called_once_with(content)

    @pytest.mark.asyncio
    async def test_download_fallback_to_sync_io(
        self, tmp_file, mock_session, patch_logger
    ):
        """Download should fallback to sync I/O when aiofiles unavailable."""
        content = b"sync fallback content"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(len(content))}
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content]
        )
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        with patch("my_unicorn.core.download.HAS_AIOFILES", False):
            service = DownloadService(mock_session)
            await service._download_without_progress(mock_response, tmp_file)

            assert tmp_file.exists()
            assert tmp_file.read_bytes() == content

    @pytest.mark.asyncio
    async def test_sync_fallback_uses_executor(
        self, tmp_file, mock_session, patch_logger
    ):
        """Sync fallback should use run_in_executor for non-blocking I/O."""
        content = b"executor test"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content]
        )

        service = DownloadService(mock_session)

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor = AsyncMock()

            await service._download_sync_fallback(mock_response, tmp_file)

            mock_loop.run_in_executor.assert_called()
            assert mock_loop.run_in_executor.call_count >= 1


# ---------------------------------------------------------------------------
# Progress Reporting Tests
# ---------------------------------------------------------------------------


class TestDownloadServiceProgressReporting:
    """Test progress reporting during downloads."""

    @pytest.mark.asyncio
    async def test_download_with_progress_creates_task(
        self, tmp_file, mock_session, patch_logger
    ):
        """Download should create a progress task for large files."""
        # 2MB file (above MIN_SIZE_FOR_PROGRESS threshold)
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(len(content))}
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content[i : i + 8192] for i in range(0, len(content), 8192)]
        )
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)

        await service.download_file(
            url="http://example.com/large.bin",
            dest=tmp_file,
            progress_type=ProgressType.DOWNLOAD,
        )

        assert len(reporter.tasks) == 1
        task_id = next(iter(reporter.tasks.keys()))
        assert reporter.tasks[task_id]["name"] == tmp_file.name
        task_progress_type = reporter.tasks[task_id]["progress_type"]
        assert task_progress_type == ProgressType.DOWNLOAD

    @pytest.mark.asyncio
    async def test_download_with_progress_updates_task(
        self, tmp_file, mock_session, patch_logger
    ):
        """Download should update progress task with bytes downloaded."""
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(len(content))}
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content[i : i + 8192] for i in range(0, len(content), 8192)]
        )
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)

        await service.download_file(
            url="http://example.com/large.bin",
            dest=tmp_file,
        )

        assert len(reporter.updates) > 0
        # Final update should show complete download
        final_completed = reporter.updates[-1][1]
        assert final_completed == len(content)

    @pytest.mark.asyncio
    async def test_download_with_progress_finishes_task(
        self, tmp_file, mock_session, patch_logger
    ):
        """Download should finish progress task on completion."""
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(len(content))}
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content[i : i + 8192] for i in range(0, len(content), 8192)]
        )
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)

        await service.download_file(
            url="http://example.com/large.bin",
            dest=tmp_file,
        )

        assert len(reporter.finished) == 1
        _task_id, success, description = reporter.finished[0]
        assert success is True
        assert description is None

    @pytest.mark.asyncio
    async def test_no_progress_for_small_files(
        self, tmp_file, mock_session, patch_logger
    ):
        """Small files should skip progress tracking."""
        content = b"small file"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(len(content))}
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content]
        )
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)

        await service.download_file(
            url="http://example.com/small.bin",
            dest=tmp_file,
        )

        # No progress tasks created for small files
        assert len(reporter.tasks) == 0

    @pytest.mark.asyncio
    async def test_no_progress_when_reporter_inactive(
        self, tmp_file, mock_session, patch_logger
    ):
        """Progress should be skipped when reporter is inactive."""
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.headers = {"Content-Length": str(len(content))}
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content[i : i + 8192] for i in range(0, len(content), 8192)]
        )
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        # NullProgressReporter is inactive
        service = DownloadService(mock_session)

        await service.download_file(
            url="http://example.com/large.bin",
            dest=tmp_file,
        )

        # File still downloaded successfully
        assert tmp_file.exists()


# ---------------------------------------------------------------------------
# Sync Fallback with Progress Tests
# ---------------------------------------------------------------------------


class TestSyncFallbackWithProgress:
    """Test sync fallback behavior with progress tracking."""

    @pytest.mark.asyncio
    async def test_sync_fallback_with_progress_updates(
        self, tmp_file, mock_session, patch_logger
    ):
        """Sync fallback should update progress during download."""
        # 1MB of content to ensure progress updates
        content = b"x" * (1024 * 1024)
        mock_response = AsyncMock()
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content[i : i + 8192] for i in range(0, len(content), 8192)]
        )

        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)

        task_id = await reporter.add_task(
            "test", ProgressType.DOWNLOAD, total=len(content)
        )

        downloaded = await service._download_sync_fallback_with_progress(
            mock_response, tmp_file, task_id
        )

        assert downloaded == len(content)
        assert len(reporter.updates) > 0
        assert tmp_file.exists()

    @pytest.mark.asyncio
    async def test_sync_fallback_returns_bytes_downloaded(
        self, tmp_file, mock_session, patch_logger
    ):
        """Sync fallback should return total bytes downloaded."""
        content = b"test data for counting"
        mock_response = AsyncMock()
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content]
        )

        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)

        task_id = await reporter.add_task(
            "test", ProgressType.DOWNLOAD, total=len(content)
        )

        downloaded = await service._download_sync_fallback_with_progress(
            mock_response, tmp_file, task_id
        )

        assert downloaded == len(content)


# ---------------------------------------------------------------------------
# HAS_AIOFILES Flag Tests
# ---------------------------------------------------------------------------


class TestHasAiofilesFlag:
    """Test HAS_AIOFILES flag behavior."""

    def test_has_aiofiles_flag_exists(self):
        """HAS_AIOFILES flag is defined in download module."""
        from my_unicorn.core import download  # noqa: PLC0415

        assert hasattr(download, "HAS_AIOFILES")
        assert isinstance(download.HAS_AIOFILES, bool)

    def test_aiofiles_is_available(self):
        """Aiofiles is available in test environment."""
        from my_unicorn.core.download import HAS_AIOFILES  # noqa: PLC0415

        assert HAS_AIOFILES is True

    @pytest.mark.asyncio
    async def test_download_branches_on_has_aiofiles(
        self, tmp_file, mock_session, patch_logger
    ):
        """Download method branches based on HAS_AIOFILES flag."""
        content = b"branching test"
        mock_response = AsyncMock()
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content]
        )

        service = DownloadService(mock_session)

        # Test with HAS_AIOFILES = False
        with (
            patch("my_unicorn.core.download.HAS_AIOFILES", False),
            patch.object(
                service, "_download_sync_fallback", new_callable=AsyncMock
            ) as mock_fallback,
        ):
            await service._download_without_progress(mock_response, tmp_file)
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_with_progress_branches_on_has_aiofiles(
        self, tmp_file, mock_session, patch_logger
    ):
        """Download with progress branches based on HAS_AIOFILES flag."""
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.content.iter_chunked = lambda size: async_chunk_gen(
            [content[i : i + 8192] for i in range(0, len(content), 8192)]
        )

        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)

        with (
            patch("my_unicorn.core.download.HAS_AIOFILES", False),
            patch.object(
                service,
                "_download_sync_fallback_with_progress",
                new_callable=AsyncMock,
            ) as mock_fallback,
        ):
            mock_fallback.return_value = len(content)
            await service._download_with_progress(
                mock_response,
                tmp_file,
                len(content),
                ProgressType.DOWNLOAD,
            )
            mock_fallback.assert_called_once()


# ---------------------------------------------------------------------------
# Original Tests (preserved from before refactoring)
# ---------------------------------------------------------------------------
