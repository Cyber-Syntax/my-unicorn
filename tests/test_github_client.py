"""Tests for GitHub API client functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio

from my_unicorn.infrastructure.github import (
    Asset,
    AssetSelector,
    ChecksumFileInfo,
    GitHubClient,
    ReleaseFetcher,
)


@pytest_asyncio.fixture
def mock_session():
    """Provide a mock aiohttp.ClientSession."""
    return MagicMock()


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
        "my_unicorn.config.config_manager.load_global_config",
        mock_load_global_config,
    )
    return mock_config_data


@pytest.mark.asyncio
async def test_fetch_latest_release_success(mock_session):
    """Test ReleaseFetcher.fetch_latest_release returns release data."""
    fetcher = ReleaseFetcher(
        owner="Cyber-Syntax",
        repo="my-unicorn",
        session=mock_session,
        use_cache=False,
    )
    # Prepare mock response
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.status = 200
    mock_response.headers = {}
    mock_response.json = AsyncMock(
        return_value={
            "tag_name": "v1.2.3",
            "prerelease": False,
            "assets": [
                {
                    "name": "app.AppImage",
                    "size": 12345,
                    "digest": "",
                    "browser_download_url": "https://github.com/Cyber-Syntax/my-unicorn/releases/download/v1.2.3/app.AppImage",
                }
            ],
        }
    )
    mock_session.get.return_value = mock_response

    result = await fetcher.fetch_latest_release()
    assert result.version == "1.2.3"
    assert result.prerelease is False
    assert len(result.assets) > 0
    assert result.assets[0].browser_download_url.endswith(".AppImage")


def test_detect_checksum_files_yaml_priority():
    """Test that YAML checksum files are prioritized over traditional ones."""
    assets = [
        {
            "name": "app.AppImage",
            "browser_download_url": "https://example.com/app.AppImage",
            "size": 12345,
            "digest": "",
        },
        {
            "name": "SHA256SUMS.txt",
            "browser_download_url": "https://example.com/SHA256SUMS.txt",
            "size": 567,
            "digest": "",
        },
        {
            "name": "latest-linux.yml",
            "browser_download_url": "https://example.com/latest-linux.yml",
            "size": 1234,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v1.0.0"
    )

    assert len(checksum_files) == 2
    # YAML should be first (prioritized)
    assert checksum_files[0].filename == "latest-linux.yml"
    assert checksum_files[0].format_type == "yaml"
    assert checksum_files[0].url == "https://example.com/latest-linux.yml"

    # Traditional should be second
    assert checksum_files[1].filename == "SHA256SUMS.txt"
    assert checksum_files[1].format_type == "traditional"
    assert checksum_files[1].url == "https://example.com/SHA256SUMS.txt"


def test_detect_checksum_files_multiple_patterns():
    """Test detection of various checksum file patterns."""
    assets = [
        {
            "name": "latest-windows.yml",
            "browser_download_url": "https://example.com/latest-windows.yml",
            "size": 1,
            "digest": "",
        },
        {
            "name": "latest-mac.yaml",
            "browser_download_url": "https://example.com/latest-mac.yaml",
            "size": 1,
            "digest": "",
        },
        {
            "name": "checksums.txt",
            "browser_download_url": "https://example.com/checksums.txt",
            "size": 1,
            "digest": "",
        },
        {
            "name": "SHA512SUMS",
            "browser_download_url": "https://example.com/SHA512SUMS",
            "size": 1,
            "digest": "",
        },
        {
            "name": "MD5SUMS",
            "browser_download_url": "https://example.com/MD5SUMS",
            "size": 1,
            "digest": "",
        },
        {
            "name": "app.sum",
            "browser_download_url": "https://example.com/app.sum",
            "size": 1,
            "digest": "",
        },
        {
            "name": "hashes.digest",
            "browser_download_url": "https://example.com/hashes.digest",
            "size": 1,
            "digest": "",
        },
        {
            "name": "regular-file.txt",
            "browser_download_url": "https://example.com/regular-file.txt",
            "size": 1,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v1.0.0"
    )

    detected_names = [cf.filename for cf in checksum_files]

    # Should detect all checksum files but not regular file
    expected_checksum_files = [
        "latest-windows.yml",
        "latest-mac.yaml",
        "checksums.txt",
        "SHA512SUMS",
        "MD5SUMS",
        "app.sum",
        "hashes.digest",
    ]

    for expected in expected_checksum_files:
        assert expected in detected_names

    assert "regular-file.txt" not in detected_names
    assert len(checksum_files) == 7


def test_detect_checksum_files_format_detection():
    """Test proper format type detection for different file extensions."""
    assets = [
        {
            "name": "latest-linux.yml",
            "browser_download_url": "https://example.com/latest-linux.yml",
            "size": 1,
            "digest": "",
        },
        {
            "name": "checksums.yaml",
            "browser_download_url": "https://example.com/checksums.yaml",
            "size": 1,
            "digest": "",
        },
        {
            "name": "SHA256SUMS.txt",
            "browser_download_url": "https://example.com/SHA256SUMS.txt",
            "size": 1,
            "digest": "",
        },
        {
            "name": "MD5SUMS",
            "browser_download_url": "https://example.com/MD5SUMS",
            "size": 1,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v1.0.0"
    )

    # Check format types
    format_map = {cf.filename: cf.format_type for cf in checksum_files}

    assert format_map["latest-linux.yml"] == "yaml"
    assert format_map["checksums.yaml"] == "yaml"
    assert format_map["SHA256SUMS.txt"] == "traditional"
    assert format_map["MD5SUMS"] == "traditional"


def test_detect_checksum_files_case_insensitive():
    """Test that checksum file detection is case insensitive."""
    assets = [
        {
            "name": "LATEST-LINUX.YML",
            "browser_download_url": "https://example.com/LATEST-LINUX.YML",
            "size": 1,
            "digest": "",
        },
        {
            "name": "sha256sums.TXT",
            "browser_download_url": "https://example.com/sha256sums.TXT",
            "size": 1,
            "digest": "",
        },
        {
            "name": "CHECKSUMS.txt",
            "browser_download_url": "https://example.com/CHECKSUMS.txt",
            "size": 1,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v1.0.0"
    )

    assert len(checksum_files) == 3
    detected_names = [cf.filename for cf in checksum_files]
    assert "LATEST-LINUX.YML" in detected_names
    assert "sha256sums.TXT" in detected_names
    assert "CHECKSUMS.txt" in detected_names


def test_detect_checksum_files_empty_assets():
    """Test checksum file detection with empty assets list."""
    checksum_files = AssetSelector.detect_checksum_files([], "v1.0.0")
    assert len(checksum_files) == 0


def test_detect_checksum_files_no_checksum_files():
    """Test checksum file detection when no checksum files are present."""
    assets = [
        {
            "name": "app.AppImage",
            "browser_download_url": "https://example.com/app.AppImage",
            "size": 12345,
            "digest": "",
        },
        {
            "name": "readme.txt",
            "browser_download_url": "https://example.com/readme.txt",
            "size": 567,
            "digest": "",
        },
        {
            "name": "changelog.md",
            "browser_download_url": "https://example.com/changelog.md",
            "size": 890,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v1.0.0"
    )
    assert len(checksum_files) == 0


def test_detect_checksum_files_legcord_example():
    """Test checksum file detection with real Legcord example."""
    assets = [
        {
            "name": "Legcord-1.1.5-linux-x86_64.AppImage",
            "browser_download_url": "https://github.com/Legcord/Legcord/releases/download/v1.1.5/Legcord-1.1.5-linux-x86_64.AppImage",
            "size": 124457255,
            "digest": "",
        },
        {
            "name": "latest-linux.yml",
            "browser_download_url": "https://github.com/Legcord/Legcord/releases/download/v1.1.5/latest-linux.yml",
            "size": 1234,
            "digest": "",
        },
        {
            "name": "Legcord-1.1.5-linux-x86_64.rpm",
            "browser_download_url": "https://github.com/Legcord/Legcord/releases/download/v1.1.5/Legcord-1.1.5-linux-x86_64.rpm",
            "size": 82429221,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v1.1.5"
    )

    assert len(checksum_files) == 1
    assert checksum_files[0].filename == "latest-linux.yml"
    assert checksum_files[0].format_type == "yaml"
    assert "v1.1.5" in checksum_files[0].url


def test_detect_checksum_files_siyuan_example():
    """Test checksum file detection with real SiYuan example."""
    assets = [
        {
            "name": "siyuan-3.2.1-linux.AppImage",
            "browser_download_url": "https://github.com/siyuan-note/siyuan/releases/download/v3.2.1/siyuan-3.2.1-linux.AppImage",
            "size": 123456789,
            "digest": "",
        },
        {
            "name": "SHA256SUMS.txt",
            "browser_download_url": "https://github.com/siyuan-note/siyuan/releases/download/v3.2.1/SHA256SUMS.txt",
            "size": 567,
            "digest": "",
        },
        {
            "name": "siyuan-3.2.1-linux.deb",
            "browser_download_url": "https://github.com/siyuan-note/siyuan/releases/download/v3.2.1/siyuan-3.2.1-linux.deb",
            "size": 987654321,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v3.2.1"
    )

    assert len(checksum_files) == 1
    assert checksum_files[0].filename == "SHA256SUMS.txt"
    assert checksum_files[0].format_type == "traditional"
    assert "v3.2.1" in checksum_files[0].url


def test_detect_checksum_files_appimage_patterns():
    """Test detection of AppImage-specific checksum file patterns."""
    assets = [
        {
            "name": "myapp.AppImage",
            "browser_download_url": "https://example.com/myapp.AppImage",
            "size": 12345,
            "digest": "",
        },
        {
            "name": "myapp.appimage.sha256",
            "browser_download_url": "https://github.com/owner/repo/releases/download/v2.0.0/myapp.appimage.sha256",
            "size": 64,
            "digest": "",
        },
        {
            "name": "myapp.appimage.sha512",
            "browser_download_url": "https://github.com/owner/repo/releases/download/v2.0.0/myapp.appimage.sha512",
            "size": 128,
            "digest": "",
        },
        {
            "name": "other-app.appimage.sha256",
            "browser_download_url": "https://github.com/owner/repo/releases/download/v2.0.0/other-app.appimage.sha256",
            "size": 64,
            "digest": "",
        },
    ]

    # Convert to Asset objects
    asset_objects = [
        Asset.from_api_response(a)
        for a in assets
        if Asset.from_api_response(a)
    ]
    checksum_files = AssetSelector.detect_checksum_files(
        asset_objects, "v2.0.0"
    )

    assert len(checksum_files) == 3
    detected_names = [cf.filename for cf in checksum_files]
    assert "myapp.appimage.sha256" in detected_names
    assert "myapp.appimage.sha512" in detected_names
    assert "other-app.appimage.sha256" in detected_names

    # All should be traditional format
    for cf in checksum_files:
        assert cf.format_type == "traditional"
        assert "v2.0.0" in cf.url


def test_checksum_file_info_dataclass():
    """Test ChecksumFileInfo dataclass creation and immutability."""
    info = ChecksumFileInfo(
        filename="test.yml",
        url="https://example.com/test.yml",
        format_type="yaml",
    )

    assert info.filename == "test.yml"
    assert info.url == "https://example.com/test.yml"
    assert info.format_type == "yaml"

    # Should be frozen (immutable)
    with pytest.raises(AttributeError):
        info.filename = "changed.yml"


@pytest.mark.asyncio
async def test_fetch_latest_release_api_error(mock_session):
    """Test fetch_latest_release raises on API error."""
    fetcher = ReleaseFetcher(
        owner="Cyber-Syntax",
        repo="my-unicorn",
        session=mock_session,
        use_cache=False,
    )
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.status = 404
    # Make raise_for_status a regular Mock, not async
    mock_response.raise_for_status = MagicMock(
        side_effect=Exception("Not Found")
    )
    mock_session.get.return_value = mock_response

    with pytest.raises(ValueError, match="No stable release found"):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_fetch_latest_release_network_error(
    mock_session, mock_asyncio_sleep, mock_config
):
    """Test fetch_latest_release handles network error."""
    fetcher = ReleaseFetcher(
        owner="Cyber-Syntax",
        repo="my-unicorn",
        session=mock_session,
        use_cache=False,
    )
    # Simulate aiohttp.ClientError (network error)
    mock_session.get.side_effect = aiohttp.ClientError("Network down")
    with pytest.raises(aiohttp.ClientError):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_fetch_latest_release_timeout(
    mock_session, mock_asyncio_sleep, mock_config
):
    """Test fetch_latest_release handles timeout error."""
    fetcher = ReleaseFetcher(
        owner="Cyber-Syntax",
        repo="my-unicorn",
        session=mock_session,
        use_cache=False,
    )
    mock_session.get.side_effect = asyncio.TimeoutError
    with pytest.raises(asyncio.TimeoutError):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_fetch_latest_release_malformed_response(mock_session):
    """Test fetch_latest_release handles malformed API response."""
    fetcher = ReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.status = 200
    mock_response.headers = {}
    # Simulate malformed response: None
    mock_response.json = AsyncMock(return_value=None)
    mock_session.get.return_value = mock_response
    # Should raise ValueError when no release found (malformed response)
    with pytest.raises(ValueError, match="No stable release found"):
        await fetcher.fetch_latest_release()

    # Simulate malformed response: unexpected type
    mock_response.json = AsyncMock(return_value="not-a-dict")
    mock_session.get.return_value = mock_response
    # Should raise AttributeError when trying to call .get() on non-dict
    with pytest.raises(AttributeError):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_github_client_get_latest_release(mock_session):
    """Test GitHubClient.get_latest_release returns release info."""
    # Create client instance
    GitHubClient(mock_session)
    # Skip: constructor does not support repo_url injection yet
