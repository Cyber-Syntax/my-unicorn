"""Tests for async I/O and protocol usage in DownloadService.

Tests the ProgressReporter protocol implementation and async file I/O behavior
using aiofiles with fallback to sync I/O.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.download import DownloadService
from my_unicorn.core.protocols import NullProgressReporter
from tests.core.conftest import MockProgressReporter, async_chunk_gen


class TestDownloadServiceProtocolUsage:
    """Test that DownloadService uses ProgressReporter protocol correctly."""

    def test_accepts_progress_reporter_protocol(
        self, mock_session: Any
    ) -> None:
        """DownloadService accepts any ProgressReporter implementation."""
        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)
        assert service.progress_reporter is reporter

    def test_uses_null_reporter_when_none_provided(
        self, mock_session: Any
    ) -> None:
        """DownloadService uses NullProgressReporter when none provided."""
        service = DownloadService(mock_session, progress_reporter=None)
        assert isinstance(service.progress_reporter, NullProgressReporter)

    def test_uses_null_reporter_by_default(self, mock_session: Any) -> None:
        """DownloadService should default to NullProgressReporter."""
        service = DownloadService(mock_session)
        assert isinstance(service.progress_reporter, NullProgressReporter)

    def test_null_reporter_is_not_active(self, mock_session: Any) -> None:
        """NullProgressReporter should report as inactive."""
        service = DownloadService(mock_session)
        assert service.progress_reporter.is_active() is False

    def test_mock_reporter_is_active(self, mock_session: Any) -> None:
        """MockProgressReporter should report as active."""
        reporter = MockProgressReporter()
        service = DownloadService(mock_session, progress_reporter=reporter)
        assert service.progress_reporter.is_active() is True


class TestDownloadServiceAsyncFileIO:
    """Test async file I/O behavior using aiofiles."""

    @pytest.mark.asyncio
    async def test_download_uses_aiofiles_when_available(
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Download should use aiofiles for async file I/O."""
        content = b"test content for aiofiles"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Download should fallback to sync I/O when aiofiles unavailable."""
        content = b"sync fallback content"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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
        self, tmp_file: Any, mock_session: Any, patch_logger: Any
    ) -> None:
        """Sync fallback should use run_in_executor for non-blocking I/O."""
        content = b"executor test"
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
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
