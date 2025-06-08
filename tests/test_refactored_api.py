#!/usr/bin/env python3
"""Tests for the refactored GitHub API and ReleaseProcessor modules."""

from unittest.mock import patch

import pytest

from api.assets import ReleaseInfo
from api.release_processor import ReleaseProcessor
from src.api.github_api import GitHubAPI


@pytest.fixture
def mock_release_info():
    """Create a mock ReleaseInfo dataclass instance for testing."""
    return ReleaseInfo(
        owner="test-owner",
        repo="test-repo",
        version="1.2.3",
        appimage_name="app-x86_64.AppImage",
        app_download_url="https://example.com/app-x86_64.AppImage",
        sha_name="sha256sums",
        sha_download_url="https://example.com/sha256sums",
        hash_type="sha256",
        arch_keyword="x86_64",
        release_notes="Release notes for version 1.2.3",
        release_url="https://github.com/test-owner/test-repo/releases/tag/v1.2.3",
        is_prerelease=False,
        published_at="2023-01-15T12:00:00Z",
    )


@pytest.fixture
def mock_release_data():
    """Create sample GitHub release data for testing."""
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
def release_processor():
    """Create a ReleaseProcessor instance for testing."""
    return ReleaseProcessor(owner="test-owner", repo="test-repo", arch_keyword="x86_64")


def test_release_info_creation(mock_release_data):
    """Test creating a ReleaseInfo object from release data."""
    asset_info = {
        "owner": "test-owner",
        "repo": "test-repo",
        "version": "1.2.3",
        "appimage_name": "app-x86_64.AppImage",
        "app_download_url": "https://example.com/app-x86_64.AppImage",
        "sha_name": "sha256sums",
        "sha_download_url": "https://example.com/sha256sums",
        "hash_type": "sha256",
        "arch_keyword": "x86_64",
    }

    from api.assets import ReleaseInfo

    release_info = ReleaseInfo.from_release_data(mock_release_data, asset_info)

    assert release_info.owner == "test-owner"
    assert release_info.repo == "test-repo"
    assert release_info.version == "1.2.3"
    assert release_info.appimage_name == "app-x86_64.AppImage"
    assert release_info.app_download_url == "https://example.com/app-x86_64.AppImage"
    assert release_info.sha_name == "sha256sums"
    assert release_info.sha_download_url == "https://example.com/sha256sums"
    assert release_info.hash_type == "sha256"
    assert release_info.arch_keyword == "x86_64"
    assert release_info.release_notes == "Release notes for version 1.2.3"
    assert release_info.release_url == "https://github.com/test-owner/test-repo/releases/tag/v1.2.3"
    assert release_info.is_prerelease is False
    assert release_info.published_at == "2023-01-15T12:00:00Z"


def test_release_processor_compare_versions(release_processor):
    """Test the version comparison logic in ReleaseProcessor."""
    # Version where update is available
    update_available, version_info = release_processor.compare_versions("1.0.0", "1.2.3")
    assert update_available is True
    assert version_info["current_version"] == "1.0.0"
    assert version_info["latest_version"] == "1.2.3"

    # Same version, no update
    update_available, version_info = release_processor.compare_versions("1.2.3", "1.2.3")
    assert update_available is False

    # Current version is newer, no update
    update_available, version_info = release_processor.compare_versions("2.0.0", "1.2.3")
    assert update_available is False


def test_release_processor_filter_assets(release_processor, mock_release_data):
    """Test filtering assets by architecture."""
    assets = mock_release_data["assets"]

    # Test filtering with x86_64 architecture
    arch_keywords = ["x86_64"]
    compatible_assets = release_processor.filter_compatible_assets(assets, arch_keywords)
    assert len(compatible_assets) == 1
    assert compatible_assets[0]["name"] == "app-x86_64.AppImage"

    # Test filtering with arm64 architecture
    arch_keywords = ["arm64"]
    compatible_assets = release_processor.filter_compatible_assets(assets, arch_keywords)
    assert len(compatible_assets) == 1
    assert compatible_assets[0]["name"] == "app-arm64.AppImage"

    # Test filtering with both architectures
    arch_keywords = ["x86_64", "arm64"]
    compatible_assets = release_processor.filter_compatible_assets(assets, arch_keywords)
    assert len(compatible_assets) == 2


def test_release_processor_create_update_response(release_processor, mock_release_info):
    """Test creating a standardized update response."""
    compatible_assets = [
        {
            "name": "app-x86_64.AppImage",
            "browser_download_url": "https://example.com/app-x86_64.AppImage",
            "size": 50000000,
        }
    ]

    response = release_processor.create_update_response(
        update_available=True,
        current_version="1.0.0",
        release_info=mock_release_info,
        compatible_assets=compatible_assets,
    )

    assert response["update_available"] is True
    assert response["current_version"] == "1.0.0"
    assert response["latest_version"] == "1.2.3"
    assert response["release_notes"] == "Release notes for version 1.2.3"
    assert response["release_url"] == "https://github.com/test-owner/test-repo/releases/tag/v1.2.3"
    assert len(response["compatible_assets"]) == 1
    assert response["compatible_assets"][0]["name"] == "app-x86_64.AppImage"
    assert response["is_prerelease"] is False
    assert response["app_download_url"] == "https://example.com/app-x86_64.AppImage"
    assert response["sha_download_url"] == "https://example.com/sha256sums"


def test_github_api_refactored(mock_release_data):
    """Test the refactored GitHubAPI class."""
    with patch(
        "src.api.github_api.GitHubAuthManager.get_auth_headers", return_value={"User-Agent": "test"}
    ):
        with patch("src.api.github_api.IconManager"):
            github_api = GitHubAPI(owner="test-owner", repo="test-repo")

            # Mock get_response to return our test data
            with patch.object(github_api, "get_response", return_value=(True, mock_release_data)):
                # Test check_latest_version with the refactored implementation
                with patch(
                    "src.release_processor.ReleaseProcessor.compare_versions"
                ) as mock_compare:
                    mock_compare.return_value = (
                        True,
                        {
                            "current_version": "1.0.0",
                            "latest_version": "1.2.3",
                            "current_normalized": "1.0.0",
                            "latest_normalized": "1.2.3",
                        },
                    )

                    # The API should use our release processor now
                    update_available, info = github_api.check_latest_version("1.0.0")

                    assert update_available is True
                    assert info["latest_version"] == "v1.2.3"
                    assert "release_notes" in info
                    assert "release_url" in info
                    assert "compatible_assets" in info
                    assert "is_prerelease" in info
                    assert "published_at" in info
