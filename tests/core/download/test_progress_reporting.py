"""Tests for progress reporting during downloads.

Tests progress tracking, task creation, updates, and completion for downloads.
Also includes tests for sync fallback behavior with progress and HAS_AIOFILES
flag.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.download import DownloadService
from my_unicorn.core.protocols import ProgressType
from tests.core.conftest import MockProgressReporter, async_chunk_gen


class TestDownloadServiceProgressReporting:
    """Test progress reporting during downloads."""

    @pytest.mark.asyncio
    async def test_download_with_progress_creates_task(
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Download should create a progress task for large files."""
        # 2MB file (above MIN_SIZE_FOR_PROGRESS threshold)
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Download should update progress task with bytes downloaded."""
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Download should finish progress task on completion."""
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Small files should skip progress tracking."""
        content = b"small file"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Progress should be skipped when reporter is inactive."""
        content = b"x" * (2 * 1024 * 1024)
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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


class TestSyncFallbackWithProgress:
    """Test sync fallback behavior with progress tracking."""

    @pytest.mark.asyncio
    async def test_sync_fallback_with_progress_updates(
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Sync fallback should update progress during download."""
        # 1MB of content to ensure progress updates
        content = b"x" * (1024 * 1024)
        mock_response = MagicMock()
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Sync fallback should return total bytes downloaded."""
        content = b"test data for counting"
        mock_response = MagicMock()
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


class TestHasAiofilesFlag:
    """Test HAS_AIOFILES flag behavior."""

    def test_has_aiofiles_flag_exists(self) -> None:
        """HAS_AIOFILES flag is defined in download module."""
        from my_unicorn.core import download  # noqa: PLC0415

        assert hasattr(download, "HAS_AIOFILES")
        assert isinstance(download.HAS_AIOFILES, bool)

    def test_aiofiles_is_available(self) -> None:
        """Aiofiles is available in test environment."""
        from my_unicorn.core.download import HAS_AIOFILES  # noqa: PLC0415

        assert HAS_AIOFILES is True

    @pytest.mark.asyncio
    async def test_download_branches_on_has_aiofiles(
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
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
