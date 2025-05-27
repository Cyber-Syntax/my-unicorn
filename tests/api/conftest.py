"""Configuration and shared fixtures for API tests."""

import pytest
from typing import Any, Dict, List

# It's good practice to keep imports specific to where they are used,
# but for conftest, direct imports for types used in fixtures are common.
# If ReleaseInfo is only used in one fixture, it could be imported there.
from src.api.assets import ReleaseInfo


@pytest.fixture
def mock_release_data() -> Dict[str, Any]:
    """Create sample GitHub release data for testing.

    Returns:
        Dict[str, Any]: Sample GitHub release data

    """
    return {
        "tag_name": "v1.2.3",
        "name": "Release 1.2.3",
        "prerelease": False,
        "draft": False,
        "published_at": "2023-01-15T12:00:00Z",
        "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.2.3",
        "body": "Release notes for version 1.2.3",
        "assets": [
            {
                "name": "app-x86_64.AppImage",
                "browser_download_url": "https://example.com/app-x86_64.AppImage",
                "size": 50000000,
            },
            {
                "name": "app-arm64.AppImage",
                "browser_download_url": "https://example.com/app-arm64.AppImage",
                "size": 48000000,
            },
            {
                "name": "sha256sums",
                "browser_download_url": "https://example.com/sha256sums",
                "size": 1024,
            },
        ],
    }


@pytest.fixture
def mock_beta_release_data() -> Dict[str, Any]:
    """Create sample GitHub beta release data for testing.

    Returns:
        Dict[str, Any]: Sample GitHub beta release data

    """
    return {
        "tag_name": "v1.3.0-beta",
        "name": "Beta Release 1.3.0",
        "prerelease": True,
        "draft": False,
        "published_at": "2023-02-01T12:00:00Z",
        "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.3.0-beta",
        "body": "Beta release notes for version 1.3.0",
        "assets": [
            {
                "name": "app-x86_64.AppImage",
                "browser_download_url": "https://example.com/beta/app-x86_64.AppImage",
                "size": 51000000,
            },
            {
                "name": "app-arm64.AppImage",
                "browser_download_url": "https://example.com/beta/app-arm64.AppImage",
                "size": 49000000,
            },
            {
                "name": "sha256sums",
                "browser_download_url": "https://example.com/beta/sha256sums",
                "size": 1024,
            },
        ],
    }


@pytest.fixture
def mock_all_releases_data(
    mock_release_data: Dict[str, Any], mock_beta_release_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Create a list of all releases (stable and beta) for testing.

    Args:
        mock_release_data: Sample stable release data
        mock_beta_release_data: Sample beta release data

    Returns:
        List[Dict[str, Any]]: List of GitHub release data objects

    """
    return [mock_beta_release_data, mock_release_data]  # Beta is newer, so it comes first


@pytest.fixture
def mock_platform_info() -> Dict[str, str]:
    """Create mock platform information for testing.

    Returns:
        Dict[str, str]: Mock platform system and machine info

    """
    return {"system": "Linux", "machine": "x86_64"}


@pytest.fixture
def mock_release_info_fixture() -> "ReleaseInfo": # Renamed to avoid conflict if used directly
    """Create a mock ReleaseInfo dataclass instance for testing.

    Returns:
        ReleaseInfo: A mock ReleaseInfo instance

    """
    # Import locally if preferred, or keep at top if used by multiple fixtures
    # from src.api.assets import ReleaseInfo

    return ReleaseInfo(
        owner="test-owner",
        repo="test-repo",
        version="1.2.3",
        appimage_name="app-x86_64.AppImage",
        appimage_url="https://example.com/app-x86_64.AppImage",
        sha_name="sha256sums",
        sha_url="https://example.com/sha256sums",
        hash_type="sha256",
        arch_keyword="x86_64",
        release_notes="Release notes for version 1.2.3",
        release_url="https://github.com/test-owner/test-repo/releases/tag/v1.2.3",
        is_prerelease=False,
        published_at="2023-01-15T12:00:00Z",
    )