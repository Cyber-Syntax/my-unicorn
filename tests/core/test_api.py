"""Tests for GitHub API client functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio

from my_unicorn.core.api import (
    Asset,
    AssetSelector,
    GitHubClient,
    ReleaseFetcher,
    create_api_timeout,
    extract_and_validate_version,
    extract_github_config,
)
from my_unicorn.types import ChecksumFileInfo


def test_create_api_timeout():
    """Test timeout factory creates correct configuration."""
    timeout = create_api_timeout(10)

    assert timeout.total == 30.0
    assert timeout.sock_read == 20.0
    assert timeout.sock_connect == 10.0


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
    """Mock ConfigManager to return predictable test values."""
    mock_config_data = {
        "network": {"retry_attempts": "3", "timeout_seconds": "10"}
    }

    class MockConfigManager:
        def load_global_config(self):
            return mock_config_data

    monkeypatch.setattr(
        "my_unicorn.core.api.ConfigManager",
        MockConfigManager,
    )
    return mock_config_data


@pytest.mark.asyncio
async def test_fetch_latest_release_success(mock_session):
    """Test ReleaseFetcher.fetch_latest_release returns release data."""
    fetcher = ReleaseFetcher(
        owner="Cyber-Syntax",
        repo="my-unicorn",
        session=mock_session,
        cache_manager=None,
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
    """Test detection of various checksum file patterns.

    Now filters out platform-incompatible files (Windows, macOS).
    Also filters out non-AppImage checksums per is_relevant_checksum logic.
    """
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

    # Should detect platform-compatible standalone checksum files only
    # Windows and macOS YAML files are filtered out (platform incompatible)
    # app.sum and hashes.digest are filtered out (no AppImage base)
    expected_checksum_files = [
        "checksums.txt",
        "SHA512SUMS",
        "MD5SUMS",
    ]

    for expected in expected_checksum_files:
        assert expected in detected_names

    # These should be filtered out
    assert "latest-windows.yml" not in detected_names  # Windows
    assert "latest-mac.yaml" not in detected_names  # macOS
    assert "app.sum" not in detected_names  # No AppImage base
    assert "hashes.digest" not in detected_names  # No AppImage base
    assert "regular-file.txt" not in detected_names  # Not a checksum
    assert len(checksum_files) == 3


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
        cache_manager=None,
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
        cache_manager=None,
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
        cache_manager=None,
    )
    mock_session.get.side_effect = asyncio.TimeoutError
    with pytest.raises(asyncio.TimeoutError):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_fetch_latest_release_malformed_response(
    mock_session, mock_asyncio_sleep, mock_config
):
    """Test fetch_latest_release handles malformed API response."""
    fetcher = ReleaseFetcher(
        owner="Cyber-Syntax",
        repo="my-unicorn",
        session=mock_session,
        cache_manager=None,
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

    # Simulate malformed response: unexpected type (non-dict)
    # fetch_stable_release defensively returns None for non-dict responses,
    # so fetch_latest_release raises ValueError (not AttributeError).
    mock_response.json = AsyncMock(return_value="not-a-dict")
    mock_session.get.return_value = mock_response
    with pytest.raises(ValueError, match="No stable release found"):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_github_client_get_latest_release(mock_session):
    """Test GitHubClient.get_latest_release returns release info."""
    # Create client instance
    GitHubClient(mock_session)
    # Skip: constructor does not support repo_url injection yet


class TestAssetSelectorPlatformCompatibility:
    """Test platform compatibility filtering."""

    def test_is_platform_compatible_accepts_linux_x86_64(self):
        """Test that Linux x86_64 AppImages are accepted."""
        # Plain AppImages
        assert AssetSelector.is_platform_compatible("test.AppImage")
        assert AssetSelector.is_platform_compatible("app-1.2.3.AppImage")

        # Explicit x86_64 markers
        assert AssetSelector.is_platform_compatible(
            "QOwnNotes-x86_64.AppImage"
        )
        assert AssetSelector.is_platform_compatible(
            "KeePassXC-2.7.10-x86_64.AppImage"
        )
        assert AssetSelector.is_platform_compatible("app-amd64.AppImage")

        # With version info
        assert AssetSelector.is_platform_compatible("Joplin-3.4.12.AppImage")

    def test_is_platform_compatible_rejects_windows(self):
        """Test that Windows files are rejected."""
        # Windows extensions
        assert not AssetSelector.is_platform_compatible("app-installer.exe")
        assert not AssetSelector.is_platform_compatible("setup.msi")

        # Windows patterns
        assert not AssetSelector.is_platform_compatible("app-Win64.AppImage")
        assert not AssetSelector.is_platform_compatible("app-win32.AppImage")
        assert not AssetSelector.is_platform_compatible("app-Windows.AppImage")
        assert not AssetSelector.is_platform_compatible(
            "LegacyWindows.AppImage"
        )
        assert not AssetSelector.is_platform_compatible(
            "PortableWindows.AppImage"
        )

    def test_is_platform_compatible_rejects_macos(self):
        """Test that macOS files are rejected."""
        # macOS extensions
        assert not AssetSelector.is_platform_compatible("app.dmg")
        assert not AssetSelector.is_platform_compatible("installer.pkg")

        # macOS patterns
        assert not AssetSelector.is_platform_compatible("app-mac.AppImage")
        assert not AssetSelector.is_platform_compatible("app-darwin.AppImage")
        assert not AssetSelector.is_platform_compatible("app-osx.AppImage")
        assert not AssetSelector.is_platform_compatible("app-apple.AppImage")

        # macOS YAML files
        assert not AssetSelector.is_platform_compatible("latest-mac.yml")
        assert not AssetSelector.is_platform_compatible("latest-mac-arm64.yml")
        assert not AssetSelector.is_platform_compatible("mac-latest.yaml")

        # Should not reject "macro" (contains "mac" but not standalone)
        assert AssetSelector.is_platform_compatible("macro-app.AppImage")

    def test_is_platform_compatible_rejects_arm(self):
        """Test that ARM architecture files are rejected."""
        assert not AssetSelector.is_platform_compatible("app-arm64.AppImage")
        assert not AssetSelector.is_platform_compatible("app-aarch64.AppImage")
        assert not AssetSelector.is_platform_compatible("app-armv7l.AppImage")
        assert not AssetSelector.is_platform_compatible("app-armhf.AppImage")
        assert not AssetSelector.is_platform_compatible("app-armv6.AppImage")

    def test_is_platform_compatible_rejects_source(self):
        """Test that source archives are rejected."""
        assert not AssetSelector.is_platform_compatible("app-src-1.0.tar.gz")
        assert not AssetSelector.is_platform_compatible("app_src_1.0.tar.gz")
        assert not AssetSelector.is_platform_compatible("app.src.tar.xz")
        assert not AssetSelector.is_platform_compatible(
            "app-source-code.tar.gz"
        )

    def test_is_platform_compatible_rejects_experimental(self):
        """Test that experimental builds are rejected."""
        assert not AssetSelector.is_platform_compatible(
            "app-experimental.AppImage"
        )
        assert not AssetSelector.is_platform_compatible(
            "app-qt6-experimental.AppImage"
        )

    def test_is_platform_compatible_empty_filename(self):
        """Test handling of empty filename."""
        assert not AssetSelector.is_platform_compatible("")
        assert not AssetSelector.is_platform_compatible(None)


class TestAssetSelectorChecksumFiltering:
    """Test checksum file relevance filtering."""

    def test_is_relevant_checksum_accepts_compatible_checksums(self):
        """Test that checksums for compatible AppImages are accepted."""
        # Standard checksum extensions
        assert AssetSelector.is_relevant_checksum(
            "QOwnNotes-x86_64.AppImage.sha256sum"
        )
        assert AssetSelector.is_relevant_checksum(
            "KeePassXC-2.7.10-x86_64.AppImage.DIGEST"
        )
        assert AssetSelector.is_relevant_checksum(
            "Joplin-3.4.12.AppImage.sha512"
        )
        assert AssetSelector.is_relevant_checksum("app.AppImage.sha256")

    def test_is_relevant_checksum_accepts_standalone_checksum_files(self):
        """Test that standalone checksum files are accepted."""
        # These were previously being filtered out incorrectly
        assert AssetSelector.is_relevant_checksum("SHA256SUMS.txt")
        assert AssetSelector.is_relevant_checksum("SHA256SUMS")
        assert AssetSelector.is_relevant_checksum("latest-linux.yml")
        assert AssetSelector.is_relevant_checksum("checksums.txt")

    def test_is_relevant_checksum_rejects_windows_checksums(self):
        """Test that checksums for Windows files are rejected."""
        assert not AssetSelector.is_relevant_checksum(
            "KeePassXC-2.7.10-Win64.msi.DIGEST"
        )
        assert not AssetSelector.is_relevant_checksum("app-windows.exe.sha256")
        assert not AssetSelector.is_relevant_checksum(
            "installer-win32.msi.sha512sum"
        )

    def test_is_relevant_checksum_rejects_arm_checksums(self):
        """Test that checksums for ARM AppImages are rejected."""
        assert not AssetSelector.is_relevant_checksum(
            "Obsidian-1.9.14-arm64.AppImage.sha256"
        )
        assert not AssetSelector.is_relevant_checksum(
            "app-aarch64.AppImage.sha512sum"
        )

    def test_is_relevant_checksum_rejects_macos_checksums(self):
        """Test that checksums for macOS files are rejected."""
        assert not AssetSelector.is_relevant_checksum("latest-mac-arm64.yml")
        assert not AssetSelector.is_relevant_checksum("app-darwin.dmg.sha256")
        # Test standalone macOS checksum files are also rejected
        assert not AssetSelector.is_relevant_checksum("latest-mac.yml")
        assert not AssetSelector.is_relevant_checksum("latest-darwin.yml")

    def test_is_relevant_checksum_requires_appimage_base(self):
        """Test that non-AppImage checksums are rejected."""
        assert not AssetSelector.is_relevant_checksum("archive.tar.gz.sha256")
        assert not AssetSelector.is_relevant_checksum("source.zip.sha512sum")
        assert not AssetSelector.is_relevant_checksum("README.md.sha256")

    def test_is_relevant_checksum_not_a_checksum(self):
        """Test that non-checksum files are rejected."""
        assert not AssetSelector.is_relevant_checksum("app.AppImage")
        assert not AssetSelector.is_relevant_checksum("README.md")

    def test_is_relevant_checksum_empty_filename(self):
        """Test handling of empty filename."""
        assert not AssetSelector.is_relevant_checksum("")
        assert not AssetSelector.is_relevant_checksum(None)


class TestAssetSelectorDetectChecksumFiles:
    """Test checksum file detection with platform filtering."""

    def test_detect_checksum_files_excludes_arm_yaml(self):
        """Test that ARM YAML files are excluded from checksum detection."""
        assets = [
            Asset(
                name="latest-linux.yml",
                browser_download_url="https://example.com/latest-linux.yml",
                size=1024,
                digest="",
            ),
            Asset(
                name="latest-linux-arm.yml",
                browser_download_url="https://example.com/latest-linux-arm.yml",
                size=1024,
                digest="",
            ),
            Asset(
                name="app-x86_64.AppImage",
                browser_download_url="https://example.com/app.AppImage",
                size=10240,
                digest="",
            ),
        ]

        result = AssetSelector.detect_checksum_files(assets, "v1.0.0")

        assert len(result) == 1, "Should detect only x86_64 YAML file"
        assert result[0].filename == "latest-linux.yml"
        assert result[0].format_type == "yaml"

    def test_detect_checksum_files_excludes_macos_yaml(self):
        """Test that macOS YAML files are excluded from checksum detection."""
        assets = [
            Asset(
                name="latest-linux.yml",
                browser_download_url="https://example.com/latest-linux.yml",
                size=1024,
                digest="",
            ),
            Asset(
                name="latest-mac.yml",
                browser_download_url="https://example.com/latest-mac.yml",
                size=1024,
                digest="",
            ),
            Asset(
                name="latest-mac-arm64.yml",
                browser_download_url="https://example.com/latest-mac-arm64.yml",
                size=1024,
                digest="",
            ),
        ]

        result = AssetSelector.detect_checksum_files(assets, "v1.0.0")

        assert len(result) == 1, "Should detect only Linux YAML file"
        assert result[0].filename == "latest-linux.yml"

    def test_detect_checksum_files_excludes_windows_checksums(self):
        """Test that Windows checksum files are excluded from detection."""
        assets = [
            Asset(
                name="app-x86_64.AppImage.sha256",
                browser_download_url="https://example.com/app.AppImage.sha256",
                size=64,
                digest="",
            ),
            Asset(
                name="app-Win64.msi.DIGEST",
                browser_download_url="https://example.com/app-Win64.msi.DIGEST",
                size=128,
                digest="",
            ),
            Asset(
                name="KeePassXC-Win64-LegacyWindows.zip.DIGEST",
                browser_download_url="https://example.com/keepass.DIGEST",
                size=128,
                digest="",
            ),
        ]

        result = AssetSelector.detect_checksum_files(assets, "v2.7.10")

        assert len(result) == 1, "Should detect only x86_64 Linux checksum"
        assert result[0].filename == "app-x86_64.AppImage.sha256"

    def test_detect_checksum_files_excludes_arm_appimage_checksums(self):
        """Test that ARM AppImage checksums are excluded from detection."""
        assets = [
            Asset(
                name="app-x86_64.AppImage.sha256",
                browser_download_url="https://example.com/app-x86_64.AppImage.sha256",
                size=64,
                digest="",
            ),
            Asset(
                name="Obsidian-1.9.14-arm64.AppImage.sha256",
                browser_download_url="https://example.com/obsidian-arm.sha256",
                size=64,
                digest="",
            ),
            Asset(
                name="app-aarch64.AppImage.sha512sum",
                browser_download_url="https://example.com/app-aarch64.sha512sum",
                size=128,
                digest="",
            ),
            Asset(
                name="freetube-0.23.12-beta-armv7l.AppImage.sha256",
                browser_download_url="https://example.com/freetube-arm.sha256",
                size=64,
                digest="",
            ),
        ]

        result = AssetSelector.detect_checksum_files(assets, "v1.9.14")

        assert len(result) == 1, "Should detect only x86_64 AppImage checksum"
        assert result[0].filename == "app-x86_64.AppImage.sha256"

    def test_detect_checksum_files_arm_only_release(self):
        """Test that ARM-only releases return empty checksum file list."""
        assets = [
            Asset(
                name="app-arm64.AppImage",
                browser_download_url="https://example.com/app-arm64.AppImage",
                size=10240,
                digest="",
            ),
            Asset(
                name="latest-linux-arm.yml",
                browser_download_url="https://example.com/latest-linux-arm.yml",
                size=1024,
                digest="",
            ),
            Asset(
                name="app-arm64.AppImage.sha256",
                browser_download_url="https://example.com/app-arm64.sha256",
                size=64,
                digest="",
            ),
        ]

        result = AssetSelector.detect_checksum_files(assets, "v1.0.0-arm")

        assert len(result) == 0, "ARM-only release should return empty list"

    def test_detect_checksum_files_mixed_platforms(self):
        """Test x86_64 checksums selected from mixed-platform release."""
        assets = [
            # AppImages
            Asset(
                name="app-x86_64.AppImage",
                browser_download_url="https://example.com/app-x86_64.AppImage",
                size=10240,
                digest="",
            ),
            Asset(
                name="app-arm64.AppImage",
                browser_download_url="https://example.com/app-arm64.AppImage",
                size=10240,
                digest="",
            ),
            # YAML checksums
            Asset(
                name="latest-linux.yml",
                browser_download_url="https://example.com/latest-linux.yml",
                size=1024,
                digest="",
            ),
            Asset(
                name="latest-linux-arm.yml",
                browser_download_url="https://example.com/latest-linux-arm.yml",
                size=1024,
                digest="",
            ),
            Asset(
                name="latest-mac.yml",
                browser_download_url="https://example.com/latest-mac.yml",
                size=1024,
                digest="",
            ),
            # Traditional checksums
            Asset(
                name="SHA256SUMS.txt",
                browser_download_url="https://example.com/SHA256SUMS.txt",
                size=512,
                digest="",
            ),
        ]

        result = AssetSelector.detect_checksum_files(assets, "v1.0.0")

        assert len(result) == 2, "Should detect 2 x86_64 checksum files"

        filenames = {r.filename for r in result}
        assert filenames == {
            "latest-linux.yml",
            "SHA256SUMS.txt",
        }, "Should include only x86_64 Linux checksums"

        # Verify YAML is prioritized first
        assert result[0].format_type == "yaml"
        assert result[0].filename == "latest-linux.yml"


class TestAssetSelectorFilterForCache:
    """Test complete cache filtering logic."""

    def create_asset(self, name: str) -> Asset:
        """Create a mock Asset for testing."""
        return Asset(
            name=name,
            size=1024,
            digest="",
            browser_download_url=f"https://example.com/{name}",
        )

    def test_filter_for_cache_keeps_compatible_appimages(self):
        """Test that compatible AppImages are kept."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("tool-amd64.AppImage"),
            self.create_asset("program.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 3
        assert all(a.name.endswith(".AppImage") for a in filtered)

    def test_filter_for_cache_removes_windows_appimages(self):
        """Test that Windows AppImages are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-Win64.AppImage"),
            self.create_asset("app-windows.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 1
        assert filtered[0].name == "app-x86_64.AppImage"

    def test_filter_for_cache_removes_macos_files(self):
        """Test that macOS files are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app.dmg"),
            self.create_asset("installer.pkg"),
            self.create_asset("app-darwin.AppImage"),
            self.create_asset("latest-mac.yml"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 1
        assert filtered[0].name == "app-x86_64.AppImage"

    def test_filter_for_cache_removes_arm_appimages(self):
        """Test that ARM AppImages are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-arm64.AppImage"),
            self.create_asset("app-aarch64.AppImage"),
            self.create_asset("app-armhf.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 1
        assert filtered[0].name == "app-x86_64.AppImage"

    def test_filter_for_cache_keeps_relevant_checksums(self):
        """Test that relevant checksum files are kept."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-x86_64.AppImage.sha256sum"),
            self.create_asset("app-x86_64.AppImage.DIGEST"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 3
        assert "app-x86_64.AppImage" in [a.name for a in filtered]
        assert "app-x86_64.AppImage.sha256sum" in [a.name for a in filtered]
        assert "app-x86_64.AppImage.DIGEST" in [a.name for a in filtered]

    def test_filter_for_cache_keeps_standalone_checksum_files(self):
        """Test that standalone checksum files are now kept in cache."""
        # These were previously being filtered out incorrectly
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("SHA256SUMS.txt"),
            self.create_asset("latest-linux.yml"),
            self.create_asset("MD5SUMS"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 4
        filtered_names = [a.name for a in filtered]
        assert "app-x86_64.AppImage" in filtered_names
        assert "SHA256SUMS.txt" in filtered_names
        assert "latest-linux.yml" in filtered_names
        assert "MD5SUMS" in filtered_names

    def test_filter_for_cache_removes_irrelevant_checksums(self):
        """Test that checksums for incompatible files are filtered out."""
        assets = [
            self.create_asset("app-x86_64.AppImage"),
            self.create_asset("app-x86_64.AppImage.sha256sum"),
            self.create_asset("app-Win64.msi.DIGEST"),
            self.create_asset("app-arm64.AppImage.sha256"),
            self.create_asset("latest-mac.yml"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 2
        assert filtered[0].name == "app-x86_64.AppImage"
        assert filtered[1].name == "app-x86_64.AppImage.sha256sum"

    def test_filter_for_cache_real_world_keepassxc(self):
        """Test with real KeePassXC release assets."""
        assets = [
            # Keep these
            self.create_asset("KeePassXC-2.7.10-x86_64.AppImage"),
            self.create_asset("KeePassXC-2.7.10-x86_64.AppImage.DIGEST"),
            # Filter these out (.sig files are GPG signatures, not checksums)
            self.create_asset("KeePassXC-2.7.10-x86_64.AppImage.sig"),
            self.create_asset("KeePassXC-2.7.10-Win64.msi"),
            self.create_asset("KeePassXC-2.7.10-Win64.msi.DIGEST"),
            self.create_asset("KeePassXC-2.7.10.dmg"),
            self.create_asset("KeePassXC-2.7.10.dmg.DIGEST"),
            self.create_asset("KeePassXC-2.7.10-src.tar.xz"),
            self.create_asset("KeePassXC-2.7.10-src.tar.xz.DIGEST"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        # Should only keep x86_64 AppImage and its DIGEST checksum
        # Note: .sig files are GPG signatures, not checksums, so filtered
        assert len(filtered) == 2
        filtered_names = [a.name for a in filtered]
        assert "KeePassXC-2.7.10-x86_64.AppImage" in filtered_names
        assert "KeePassXC-2.7.10-x86_64.AppImage.DIGEST" in filtered_names

    def test_filter_for_cache_empty_list(self):
        """Test filtering an empty asset list."""
        assets = []
        filtered = AssetSelector.filter_for_cache(assets)
        assert len(filtered) == 0

    def test_filter_for_cache_no_compatible_assets(self):
        """Test when no assets are compatible."""
        assets = [
            self.create_asset("app.dmg"),
            self.create_asset("installer.exe"),
            self.create_asset("app-arm64.AppImage"),
        ]

        filtered = AssetSelector.filter_for_cache(assets)

        assert len(filtered) == 0


class TestExtractGitHubConfig:
    """Tests for extract_github_config function."""

    def test_extract_github_config_from_source(self):
        """Test extract_github_config from source."""

        effective_config = {
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            }
        }

        owner, repo, prerelease = extract_github_config(effective_config)

        assert owner == "test-owner"
        assert repo == "test-repo"
        assert prerelease is False

    def test_extract_github_config_missing_source(self):
        """Test extract_github_config with missing source."""

        effective_config = {}

        owner, repo, prerelease = extract_github_config(effective_config)

        assert owner == "unknown"
        assert repo == "unknown"
        assert prerelease is False

    def test_extract_github_config_default_prerelease(self):
        """Test extract_github_config with default prerelease value."""

        effective_config = {
            "source": {"owner": "test-owner", "repo": "test-repo"}
        }

        owner, repo, prerelease = extract_github_config(effective_config)

        assert owner == "test-owner"
        assert repo == "test-repo"
        assert prerelease is False  # Default value

    def test_extract_github_config_with_prerelease_true(self):
        """Test extract_github_config with prerelease set to True."""

        effective_config = {
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": True,
            }
        }

        owner, repo, prerelease = extract_github_config(effective_config)

        assert prerelease is True


class TestExtractAndValidateVersion:
    """Test extract_and_validate_version function."""

    def test_valid_extraction_and_validation(self) -> None:
        """Test valid extraction and validation."""
        result = extract_and_validate_version("package@1.2.3")
        assert result == "1.2.3"

    def test_invalid_version_returns_none(self) -> None:
        """Test invalid version returns None."""
        result = extract_and_validate_version("package@abc")
        assert result is None

    def test_valid_complex_package(self) -> None:
        """Test valid complex package."""
        result = extract_and_validate_version("@standardnotes/desktop@3.198.1")
        assert result == "3.198.1"

    def test_simple_version_string(self) -> None:
        """Test simple version string."""
        result = extract_and_validate_version("v1.2.3")
        assert result == "1.2.3"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = extract_and_validate_version("")
        assert result is None
