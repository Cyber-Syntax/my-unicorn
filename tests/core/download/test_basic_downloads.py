"""Tests for basic DownloadService functionality.

Tests basic download operations including file downloads, appimage downloads,
and checksum file downloads.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.download import DownloadError, DownloadService
from my_unicorn.core.github import Asset
from tests.core.conftest import async_chunk_gen


@pytest.mark.asyncio
async def test_download_file_success(
    tmp_file: Any, mock_session: Any, patch_logger: Any
) -> None:
    """Test DownloadService.download_file downloads file successfully."""
    content = b"hello world"
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None
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
async def test_download_file_error(
    tmp_file: Any, mock_session: Any, patch_logger: Any
) -> None:
    """Test DownloadService.download_file handles error during download."""
    content = b"data"
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None
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
async def test_download_appimage_success(
    tmp_file: Any, mock_session: Any, patch_logger: Any
) -> None:
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
    mock_response.__aexit__.return_value = None
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


def test_get_filename_from_url() -> None:
    """Test get_filename_from_url extracts filename."""
    service = DownloadService(MagicMock())
    url = "https://github.com/owner/repo/releases/download/v1.0.0/app.AppImage"
    assert service.get_filename_from_url(url) == "app.AppImage"


@pytest.mark.asyncio
async def test_download_checksum_file_success(
    mock_session: Any, patch_logger: Any
) -> None:
    """Test download_checksum_file returns content."""
    content = "abc123"
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None
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
async def test_download_checksum_file_error(
    mock_session: Any, patch_logger: Any
) -> None:
    """Test download_checksum_file raises on error."""
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None
    mock_response.raise_for_status = MagicMock(
        side_effect=DownloadError("Checksum error")
    )
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    with pytest.raises(DownloadError, match="Failed to download"):
        await service.download_checksum_file("http://example.com/checksum.txt")


def test_download_error_exception() -> None:
    """Test DownloadError can be raised and caught."""
    with pytest.raises(DownloadError, match="fail"):
        raise DownloadError("fail")
