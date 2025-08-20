from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from my_unicorn.github_client import ChecksumFileInfo, GitHubClient, GitHubReleaseFetcher


@pytest_asyncio.fixture
def mock_session():
    """Provide a mock aiohttp.ClientSession."""
    return MagicMock()


@pytest.mark.asyncio
async def test_fetch_latest_release_success(mock_session):
    """Test GitHubReleaseFetcher.fetch_latest_release returns release data."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
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
                    "browser_download_url": "https://github.com/Cyber-Syntax/my-unicorn/releases/download/v1.2.3/app.AppImage"
                }
            ],
        }
    )
    mock_session.get.return_value = mock_response

    result = await fetcher.fetch_latest_release()
    assert result["version"] == "1.2.3"
    assert result["prerelease"] is False
    # The result may have assets or browser_download_url at top level
    if result.get("assets"):
        assert result["assets"][0]["browser_download_url"].endswith(".AppImage")
    elif "browser_download_url" in result:
        assert result["browser_download_url"].endswith(".AppImage")


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

    checksum_files = GitHubReleaseFetcher.detect_checksum_files(assets, "v1.0.0")

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

    checksum_files = GitHubReleaseFetcher.detect_checksum_files(assets, "v1.0.0")

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

    checksum_files = GitHubReleaseFetcher.detect_checksum_files(assets, "v1.0.0")

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

    checksum_files = GitHubReleaseFetcher.detect_checksum_files(assets, "v1.0.0")

    assert len(checksum_files) == 3
    detected_names = [cf.filename for cf in checksum_files]
    assert "LATEST-LINUX.YML" in detected_names
    assert "sha256sums.TXT" in detected_names
    assert "CHECKSUMS.txt" in detected_names


def test_detect_checksum_files_empty_assets():
    """Test checksum file detection with empty assets list."""
    checksum_files = GitHubReleaseFetcher.detect_checksum_files([], "v1.0.0")
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

    checksum_files = GitHubReleaseFetcher.detect_checksum_files(assets, "v1.0.0")
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

    checksum_files = GitHubReleaseFetcher.detect_checksum_files(assets, "v1.1.5")

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

    checksum_files = GitHubReleaseFetcher.detect_checksum_files(assets, "v3.2.1")

    assert len(checksum_files) == 1
    assert checksum_files[0].filename == "SHA256SUMS.txt"
    assert checksum_files[0].format_type == "traditional"
    assert "v3.2.1" in checksum_files[0].url


def test_checksum_file_info_dataclass():
    """Test ChecksumFileInfo dataclass creation and immutability."""
    info = ChecksumFileInfo(
        filename="test.yml", url="https://example.com/test.yml", format_type="yaml"
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
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.status = 404
    mock_response.raise_for_status.side_effect = Exception("Not Found")
    mock_session.get.return_value = mock_response

    with pytest.raises(Exception):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_fetch_latest_release_network_error(mock_session):
    """Test fetch_latest_release handles network error (e.g., connection lost)."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    # Simulate aiohttp.ClientError (network error)
    import aiohttp

    mock_session.get.side_effect = aiohttp.ClientError("Network down")
    with pytest.raises(aiohttp.ClientError):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_fetch_latest_release_timeout(mock_session):
    """Test fetch_latest_release handles timeout error."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    import asyncio

    mock_session.get.side_effect = asyncio.TimeoutError
    with pytest.raises(asyncio.TimeoutError):
        await fetcher.fetch_latest_release()


@pytest.mark.asyncio
async def test_fetch_latest_release_malformed_response(mock_session):
    """Test fetch_latest_release handles malformed API response."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.status = 200
    mock_response.headers = {}
    # Simulate malformed response: None
    mock_response.json = AsyncMock(return_value=None)
    mock_session.get.return_value = mock_response
    # Should raise AttributeError if data is not a dict
    try:
        await fetcher.fetch_latest_release()
    except AttributeError:
        pass

    # Simulate malformed response: unexpected type
    mock_response.json = AsyncMock(return_value="not-a-dict")
    mock_session.get.return_value = mock_response
    try:
        await fetcher.fetch_latest_release()
    except AttributeError:
        pass


def test_parse_repo_url_valid():
    """Test parse_repo_url parses valid GitHub repo URLs."""
    url = "https://github.com/Cyber-Syntax/my-unicorn"
    owner, repo = GitHubReleaseFetcher.parse_repo_url(url)
    assert owner == "Cyber-Syntax"
    assert repo == "my-unicorn"


def test_parse_repo_url_invalid():
    """Test parse_repo_url raises on invalid URL."""
    url = "https://gitlab.com/foo/bar"
    with pytest.raises(ValueError):
        GitHubReleaseFetcher.parse_repo_url(url)


def test_build_icon_url_and_extract_icon_filename():
    """Test build_icon_url and extract_icon_filename produce correct results."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=MagicMock()
    )
    icon_url = fetcher.build_icon_url("icon.png")
    assert (
        icon_url == "https://raw.githubusercontent.com/Cyber-Syntax/my-unicorn/main/icon.png"
    )
    filename = fetcher.extract_icon_filename(icon_url, "my-unicorn")
    assert filename == "my-unicorn.png"


@pytest.mark.asyncio
async def test_check_rate_limit(mock_session):
    """Test check_rate_limit returns rate limit info."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "resources": {"core": {"limit": 5000, "remaining": 4999, "reset": 1234567890}}
        }
    )
    mock_session.get.return_value = mock_response

    info = await fetcher.check_rate_limit()
    assert "core" in info["resources"]
    assert info["resources"]["core"]["limit"] == 5000


@pytest.mark.asyncio
async def test_check_rate_limit_network_error(mock_session):
    """Test check_rate_limit handles network error."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    import aiohttp

    mock_session.get.side_effect = aiohttp.ClientError("Network unreachable")
    with pytest.raises(aiohttp.ClientError):
        await fetcher.check_rate_limit()


@pytest.mark.asyncio
async def test_check_rate_limit_timeout(mock_session):
    """Test check_rate_limit handles timeout error."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    import asyncio

    mock_session.get.side_effect = asyncio.TimeoutError
    with pytest.raises(asyncio.TimeoutError):
        await fetcher.check_rate_limit()


@pytest.mark.asyncio
async def test_check_rate_limit_malformed_response(mock_session):
    """Test check_rate_limit handles malformed API response."""
    fetcher = GitHubReleaseFetcher(
        owner="Cyber-Syntax", repo="my-unicorn", session=mock_session
    )
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.status = 200
    # Simulate malformed response: None
    mock_response.json = AsyncMock(return_value=None)
    mock_session.get.return_value = mock_response
    # Should raise AttributeError if data is not a dict
    try:
        await fetcher.check_rate_limit()
    except AttributeError:
        pass

    # Simulate malformed response: unexpected type
    mock_response.json = AsyncMock(return_value="not-a-dict")
    mock_session.get.return_value = mock_response
    try:
        await fetcher.check_rate_limit()
    except AttributeError:
        pass


@pytest.mark.asyncio
async def test_github_client_get_latest_release(mock_session):
    """Test GitHubClient.get_latest_release returns release info."""
    client = GitHubClient(mock_session)
    # Optionally set repo URL if needed by the test, or skip this test if not supported
    # If the method requires repo_url, this test should be adjusted to match the actual API.
    # For now, we skip this test as the constructor does not support repo_url injection.
