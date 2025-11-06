from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from my_unicorn.download import DownloadService
from my_unicorn.github_client import Asset


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
    with patch("my_unicorn.download.get_logger") as mock_logger:
        yield mock_logger


@pytest_asyncio.fixture
def patch_progress_service():
    """Patch progress service to avoid real progress bars."""
    with patch(
        "my_unicorn.download.get_progress_service"
    ) as mock_progress_service:
        mock_service = MagicMock()
        mock_service.add_task = AsyncMock(return_value="task-id")
        mock_service.update_task = AsyncMock()
        mock_service.update_task_total = AsyncMock()
        mock_service.finish_task = AsyncMock()
        mock_progress_service.return_value = mock_service
        yield mock_service


async def async_chunk_gen(chunks: list[bytes]):
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
async def test_download_file_success(
    tmp_file, mock_session, patch_logger, patch_progress_service
):
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

    with patch(
        "my_unicorn.download.logger.progress_context",
        return_value=patch_logger,
    ):
        service = DownloadService(mock_session)
        await service.download_file(
            url="http://example.com/file.bin",
            dest=tmp_file,
            show_progress=True,
        )

    assert tmp_file.exists()
    assert tmp_file.read_bytes() == content


@pytest.mark.asyncio
async def test_download_file_error(
    tmp_file, mock_session, patch_logger, patch_progress_service
):
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

    with patch(
        "my_unicorn.download.logger.progress_context",
        return_value=patch_logger,
    ):
        service = DownloadService(mock_session)
        with pytest.raises(Exception):
            await service.download_file(
                url="http://example.com/file.bin",
                dest=tmp_file,
                show_progress=True,
            )


@pytest.mark.asyncio
async def test_download_appimage_success(
    tmp_file, mock_session, patch_logger, patch_progress_service
):
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

    with patch(
        "my_unicorn.download.logger.progress_context",
        return_value=patch_logger,
    ):
        service = DownloadService(mock_session)
        result = await service.download_appimage(asset, tmp_file)
    assert result == tmp_file
    assert tmp_file.read_bytes() == content


@pytest.mark.asyncio
async def test_download_icon_exists(tmp_file, mock_session, patch_logger):
    """Test DownloadService.download_icon returns early if icon exists."""
    tmp_file.write_bytes(b"icon")
    icon = {
        "icon_url": "http://example.com/icon",
        "icon_filename": tmp_file.name,
    }
    service = DownloadService(mock_session)
    with patch("my_unicorn.download.logger.info") as info_mock:
        result = await service.download_icon(icon, tmp_file)
    assert result == tmp_file
    info_mock.assert_called()


@pytest.mark.asyncio
async def test_download_icon_download(
    tmp_file, mock_session, patch_logger, patch_progress_service
):
    """Test DownloadService.download_icon downloads icon file."""
    icon = {
        "icon_url": "http://example.com/icon",
        "icon_filename": tmp_file.name,
    }
    # Patch download_file to simulate file writing
    with patch.object(
        DownloadService, "download_file", new_callable=AsyncMock
    ) as mock_download_file:
        mock_download_file.side_effect = (
            lambda url, dest, **kwargs: dest.write_bytes(b"icondata")
        )
        service = DownloadService(mock_session)
        result = await service.download_icon(icon, tmp_file)
    assert result == tmp_file
    assert tmp_file.read_bytes() == b"icondata"


def test_get_filename_from_url():
    """Test get_filename_from_url extracts filename."""
    from my_unicorn.download import DownloadService

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

    with patch(
        "my_unicorn.download.logger.progress_context",
        return_value=patch_logger,
    ):
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

    with patch(
        "my_unicorn.download.logger.progress_context",
        return_value=patch_logger,
    ):
        service = DownloadService(mock_session)
        with pytest.raises(Exception):
            await service.download_checksum_file(
                "http://example.com/checksum.txt"
            )


def test_download_error_exception():
    """Test DownloadError can be raised and caught."""
    from my_unicorn.download import DownloadError

    try:
        raise DownloadError("fail")
    except DownloadError as e:
        assert str(e) == "fail"
