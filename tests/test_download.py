from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from my_unicorn.infrastructure.download import DownloadService
from my_unicorn.infrastructure.github import Asset


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
    with patch("my_unicorn.infrastructure.download.get_logger") as mock_logger:
        yield mock_logger


async def async_chunk_gen(chunks: list[bytes]):
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
        side_effect=Exception("Network error")
    )
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    with pytest.raises(Exception):
        await service.download_file(
            url="http://example.com/file.bin",
            dest=tmp_file,
        )


@pytest.mark.asyncio
async def test_download_appimage_success(tmp_file, mock_session, patch_logger):
    """Test DownloadService.download_appimage downloads AppImage successfully."""
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
    from my_unicorn.infrastructure.download import DownloadService

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
        side_effect=Exception("Checksum error")
    )
    mock_session.get.return_value = mock_response

    service = DownloadService(mock_session)
    with pytest.raises(Exception):
        await service.download_checksum_file("http://example.com/checksum.txt")


def test_download_error_exception():
    """Test DownloadError can be raised and caught."""
    from my_unicorn.infrastructure.download import DownloadError

    try:
        raise DownloadError("fail")
    except DownloadError as e:
        assert str(e) == "fail"
