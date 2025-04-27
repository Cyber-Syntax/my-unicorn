#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the GitHub API module.

This module contains pytest tests for the GitHubAPI class, which handles
GitHub API requests, version comparison, and AppImage selection.
"""

import json
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api import GitHubAPI
from src.auth_manager import GitHubAuthManager


@pytest.fixture
def github_api() -> GitHubAPI:
    """
    Create a basic GitHubAPI instance for testing.

    Returns:
        GitHubAPI: A basic GitHubAPI instance
    """
    with patch("src.api.GitHubAuthManager.get_auth_headers", return_value={"User-Agent": "test"}):
        with patch("src.api.IconManager"):
            api = GitHubAPI(owner="test-owner", repo="test-repo")
            return api


@pytest.fixture
def mock_release_data() -> Dict[str, Any]:
    """
    Create sample GitHub release data for testing.

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
    """
    Create sample GitHub beta release data for testing.

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
    """
    Create a list of all releases (stable and beta) for testing.

    Args:
        mock_release_data: Sample stable release data
        mock_beta_release_data: Sample beta release data

    Returns:
        List[Dict[str, Any]]: List of GitHub release data objects
    """
    return [mock_beta_release_data, mock_release_data]  # Beta is newer, so it comes first


@pytest.fixture
def mock_platform_info() -> Dict[str, str]:
    """
    Create mock platform information for testing.

    Returns:
        Dict[str, str]: Mock platform system and machine info
    """
    return {"system": "Linux", "machine": "x86_64"}


class TestGitHubAPI:
    """Tests for the GitHubAPI class."""

    def test_initialization(self, github_api: GitHubAPI) -> None:
        """
        Test GitHubAPI initialization with default parameters.

        Args:
            github_api: GitHubAPI fixture
        """
        assert github_api.owner == "test-owner"
        assert github_api.repo == "test-repo"
        assert github_api.sha_name == "sha256"
        assert github_api.hash_type == "sha256"
        assert github_api.version is None
        assert github_api.sha_url is None
        assert github_api.appimage_url is None
        assert github_api.appimage_name is None
        assert github_api._arch_keyword is None
        assert isinstance(github_api.arch_keywords, list)
        assert isinstance(github_api._headers, dict)

    def test_arch_keyword_property(self, github_api: GitHubAPI) -> None:
        """
        Test the arch_keyword property getter.

        Args:
            github_api: GitHubAPI fixture
        """
        assert github_api.arch_keyword is None
        github_api._arch_keyword = "x86_64"
        assert github_api.arch_keyword == "x86_64"

    def test_get_arch_keywords_with_provided_keyword(self) -> None:
        """
        Test getting architecture keywords when one is explicitly provided.
        """
        with patch(
            "src.api.GitHubAuthManager.get_auth_headers", return_value={"User-Agent": "test"}
        ):
            with patch("src.api.IconManager"):
                api = GitHubAPI(owner="test-owner", repo="test-repo", arch_keyword="custom-arch")
                assert api.arch_keywords == ["custom-arch"]

    def test_get_arch_keywords_for_current_platform(
        self, mock_platform_info: Dict[str, str]
    ) -> None:
        """
        Test getting architecture keywords for the current platform.

        Args:
            mock_platform_info: Mock platform info fixture
        """
        with patch("platform.system", return_value=mock_platform_info["system"]):
            with patch("platform.machine", return_value=mock_platform_info["machine"]):
                with patch(
                    "src.api.GitHubAuthManager.get_auth_headers",
                    return_value={"User-Agent": "test"},
                ):
                    with patch("src.api.IconManager"):
                        api = GitHubAPI(owner="test-owner", repo="test-repo")
                        assert "x86_64" in api.arch_keywords
                        assert "amd64" in api.arch_keywords
                        assert len(api.arch_keywords) > 0

    def test_get_latest_release_success(
        self, github_api: GitHubAPI, mock_release_data: Dict[str, Any], mock_requests_get: Any
    ) -> None:
        """
        Test successful fetch of the latest stable release.

        Args:
            github_api: GitHubAPI fixture
            mock_release_data: Mock release data fixture
            mock_requests_get: Requests mocker fixture
        """
        # Set up mock for the authenticated request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_release_data

        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ):
            with patch.object(github_api, "_process_release", return_value=True):
                success, data = github_api.get_latest_release()

                assert success is True
                assert data == mock_release_data

    def test_get_latest_release_not_found(self, github_api: GitHubAPI) -> None:
        """
        Test handling of 404 response when fetching the latest release.

        Args:
            github_api: GitHubAPI fixture
        """
        # Set up mock for the authenticated request
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ):
            with patch.object(
                github_api, "get_beta_releases", return_value=(True, {"tag_name": "v1.0.0-beta"})
            ):
                success, data = github_api.get_latest_release()

                # Should call get_beta_releases and return its result
                assert success is True
                assert isinstance(data, dict)
                assert data.get("tag_name") == "v1.0.0-beta"

    def test_get_latest_release_rate_limit_exceeded(self, github_api: GitHubAPI) -> None:
        """
        Test handling of rate limit exceeded response.

        Args:
            github_api: GitHubAPI fixture
        """
        # Set up mock for the authenticated request
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "API rate limit exceeded"

        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ):
            with patch.object(github_api, "refresh_auth") as mock_refresh:
                success, data = github_api.get_latest_release()

                assert success is False
                assert "rate limit exceeded" in data.lower()
                mock_refresh.assert_called_once()

    def test_get_latest_release_other_error(self, github_api: GitHubAPI) -> None:
        """
        Test handling of other errors when fetching the latest release.

        Args:
            github_api: GitHubAPI fixture
        """
        # Set up mock for the authenticated request
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ):
            success, data = github_api.get_latest_release()

            assert success is False
            assert "failed to fetch" in data.lower()
            assert "500" in data  # Status code should be included

    def test_get_latest_release_network_error(self, github_api: GitHubAPI) -> None:
        """
        Test handling of network errors when fetching the latest release.

        Args:
            github_api: GitHubAPI fixture
        """
        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            side_effect=requests.exceptions.RequestException("Connection error"),
        ):
            success, data = github_api.get_latest_release()

            assert success is False
            assert "network error" in data.lower()

    def test_get_latest_release_exception(self, github_api: GitHubAPI) -> None:
        """
        Test handling of unexpected exceptions when fetching the latest release.

        Args:
            github_api: GitHubAPI fixture
        """
        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            side_effect=Exception("Unexpected error"),
        ):
            success, data = github_api.get_latest_release()

            assert success is False
            assert "error" in data.lower()

    def test_get_beta_releases_success(
        self, github_api: GitHubAPI, mock_all_releases_data: List[Dict[str, Any]]
    ) -> None:
        """
        Test successful fetch of beta releases.

        Args:
            github_api: GitHubAPI fixture
            mock_all_releases_data: Mock releases data fixture
        """
        # Set up mock for the authenticated request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_all_releases_data

        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ):
            with patch.object(github_api, "_process_release", return_value=True):
                success, data = github_api.get_beta_releases()

                assert success is True
                assert data == mock_all_releases_data[0]  # Should return the first (latest) release

    def test_get_beta_releases_no_releases(self, github_api: GitHubAPI) -> None:
        """
        Test handling of empty releases list.

        Args:
            github_api: GitHubAPI fixture
        """
        # Set up mock for the authenticated request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ):
            success, data = github_api.get_beta_releases()

            assert success is False
            assert "no releases found" in data.lower()

    def test_get_beta_releases_error(self, github_api: GitHubAPI) -> None:
        """
        Test handling of errors when fetching beta releases.

        Args:
            github_api: GitHubAPI fixture
        """
        # Set up mock for the authenticated request
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ):
            success, data = github_api.get_beta_releases()

            assert success is False
            assert "failed to fetch releases" in data.lower()

    def test_get_beta_releases_exception(self, github_api: GitHubAPI) -> None:
        """
        Test handling of exceptions when fetching beta releases.

        Args:
            github_api: GitHubAPI fixture
        """
        with patch(
            "src.auth_manager.GitHubAuthManager.make_authenticated_request",
            side_effect=Exception("Unexpected error"),
        ):
            success, data = github_api.get_beta_releases()

            assert success is False
            assert "error checking beta releases" in data.lower()

    def test_get_response(self, github_api: GitHubAPI) -> None:
        """
        Test the get_response method which tries stable release then falls back to beta.

        Args:
            github_api: GitHubAPI fixture
        """
        with patch.object(
            github_api, "get_latest_release", return_value=(True, {"tag_name": "v1.0.0"})
        ):
            success, data = github_api.get_response()

            assert success is True
            assert data == {"tag_name": "v1.0.0"}

        # Test fallback to beta when stable fails
        with patch.object(
            github_api, "get_latest_release", return_value=(False, "No stable release")
        ):
            # We don't need to patch get_beta_releases because get_latest_release already calls it
            # and returns its result when no stable release is found
            success, data = github_api.get_response()

            assert success is False
            assert data == "No stable release"

    def test_check_latest_version_success(
        self, github_api: GitHubAPI, mock_release_data: Dict[str, Any]
    ) -> None:
        """
        Test successful version check with update available.

        Args:
            github_api: GitHubAPI fixture
            mock_release_data: Mock release data fixture
        """
        # We need to mock the behavior of _normalize_version_for_comparison and
        # _extract_base_version to ensure consistent version comparison

        with patch.object(github_api, "get_response", return_value=(True, mock_release_data)):
            with patch.object(github_api, "_get_arch_keywords", return_value=["x86_64"]):
                # Need to patch _normalize_version_for_comparison to ensure it behaves consistently
                with patch.object(
                    github_api, "_normalize_version_for_comparison"
                ) as mock_normalize:
                    # Set up the mock to return deterministic values for our test cases
                    mock_normalize.side_effect = (
                        lambda x: "1.0.0"
                        if x == "v1.0.0"
                        else "1.2.3"
                        if x == "v1.2.3" or x == mock_release_data["tag_name"]
                        else "2.0.0"
                    )

                    # Test when current version is older (update available)
                    update_available, info = github_api.check_latest_version(
                        current_version="v1.0.0"
                    )

                    assert update_available is True
                    assert info["current_version"] == "v1.0.0"
                    assert info["latest_version"] == mock_release_data["tag_name"]
                    assert "compatible_assets" in info

                    # Test when current version is same as latest (no update)
                    update_available, info = github_api.check_latest_version(
                        current_version="v1.2.3"
                    )

                    assert update_available is False
                    assert info["current_version"] == "v1.2.3"
                    assert info["latest_version"] == mock_release_data["tag_name"]

                    # Test when current version is newer (no update, unusual case)
                    update_available, info = github_api.check_latest_version(
                        current_version="v2.0.0"
                    )

                    assert update_available is False
                    assert info["current_version"] == "v2.0.0"
                    assert info["latest_version"] == mock_release_data["tag_name"]

    def test_check_latest_version_with_beta_repo(
        self, github_api: GitHubAPI, mock_beta_release_data: Dict[str, Any]
    ) -> None:
        """
        Test version check with a repo that uses beta versions.

        Args:
            github_api: GitHubAPI fixture
            mock_beta_release_data: Mock beta release data fixture
        """
        # Make the repo use beta versions
        github_api.repo = "FreeTube"  # This is in the beta_repos list

        with patch.object(github_api, "get_response", return_value=(True, mock_beta_release_data)):
            with patch.object(github_api, "_get_arch_keywords", return_value=["x86_64"]):
                # Test when base version is different (update available)
                update_available, info = github_api.check_latest_version(current_version="v1.2.0")

                assert update_available is True
                assert info["latest_version"] == mock_beta_release_data["tag_name"]

                # Test when base version is same (no update)
                # 1.3.0 base version equals 1.3.0-beta base version
                update_available, info = github_api.check_latest_version(current_version="v1.3.0")

                assert update_available is False
                assert info["latest_version"] == mock_beta_release_data["tag_name"]

    def test_check_latest_version_failed_response(self, github_api: GitHubAPI) -> None:
        """
        Test version check when getting response fails.

        Args:
            github_api: GitHubAPI fixture
        """
        with patch.object(github_api, "get_response", return_value=(False, "API error")):
            update_available, info = github_api.check_latest_version(current_version="v1.0.0")

            assert update_available is False
            assert "error" in info
            assert info["error"] == "API error"

    def test_check_latest_version_exception(self, github_api: GitHubAPI) -> None:
        """
        Test handling of exceptions during version check.

        Args:
            github_api: GitHubAPI fixture
        """
        with patch.object(github_api, "get_response", return_value=(True, {})):  # Empty response
            update_available, info = github_api.check_latest_version(current_version="v1.0.0")

            assert update_available is False
            assert "error" in info
            assert "error parsing" in info["error"].lower()

    def test_normalize_version_for_comparison(self, github_api: GitHubAPI) -> None:
        """
        Test version normalization for comparison.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with various version formats
        assert github_api._normalize_version_for_comparison("v1.2.3") == "1.2.3"
        assert github_api._normalize_version_for_comparison("V1.2.3") == "1.2.3"
        assert github_api._normalize_version_for_comparison("1.2.3") == "1.2.3"
        assert github_api._normalize_version_for_comparison("1.2.3-beta") == "1.2.3-beta"

        # Test with None
        assert github_api._normalize_version_for_comparison(None) == ""

        # Test with empty string
        assert github_api._normalize_version_for_comparison("") == ""

    def test_extract_base_version(self, github_api: GitHubAPI) -> None:
        """
        Test extracting base version from version string.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with various version formats
        assert github_api._extract_base_version("1.2.3") == "1.2.3"
        assert github_api._extract_base_version("1.2.3-beta") == "1.2.3"
        assert github_api._extract_base_version("1.2.3+build") == "1.2.3"
        assert github_api._extract_base_version("1.2.3_alpha") == "1.2.3"
        assert github_api._extract_base_version("1.2.3-beta.4") == "1.2.3"

    def test_repo_uses_beta(self, github_api: GitHubAPI) -> None:
        """
        Test detection of repos that use beta versions.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with non-beta repo
        assert github_api._repo_uses_beta() is False

        # Test with known beta repo
        github_api.repo = "FreeTube"
        assert github_api._repo_uses_beta() is True

    def test_find_app_icon(self, github_api: GitHubAPI) -> None:
        """
        Test finding application icon.

        Args:
            github_api: GitHubAPI fixture
        """
        mock_icon_info = {"name": "app-icon.png", "url": "https://example.com/icon.png"}

        with patch.object(github_api._icon_manager, "find_icon", return_value=mock_icon_info):
            icon_info = github_api.find_app_icon()

            assert icon_info == mock_icon_info

        # Test when icon is not found
        with patch.object(github_api._icon_manager, "find_icon", return_value=None):
            icon_info = github_api.find_app_icon()

            assert icon_info is None

        # Test when exception occurs
        with patch.object(
            github_api._icon_manager, "find_icon", side_effect=Exception("Icon error")
        ):
            icon_info = github_api.find_app_icon()

            assert icon_info is None

    def test_refresh_auth(self, github_api: GitHubAPI) -> None:
        """
        Test refreshing authentication headers.

        Args:
            github_api: GitHubAPI fixture
        """
        with patch("src.auth_manager.GitHubAuthManager.clear_cached_headers") as mock_clear:
            with patch(
                "src.auth_manager.GitHubAuthManager.get_auth_headers",
                return_value={"New": "Headers"},
            ) as mock_get:
                github_api.refresh_auth()

                mock_clear.assert_called_once()
                mock_get.assert_called_once()
                assert github_api._headers == {"New": "Headers"}

    def test_extract_version(self, github_api: GitHubAPI) -> None:
        """
        Test extracting version from tag string.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with various version formats
        assert github_api._extract_version("v1.2.3", False) == "1.2.3"
        assert github_api._extract_version("1.2.3", False) == "1.2.3"
        assert github_api._extract_version("v1.2.3-beta", True) == "1.2.3"
        assert github_api._extract_version("v1.2.3-stable", False) == "1.2.3"
        assert github_api._extract_version("release-1.2.3", False) == "1.2.3"

        # Test with non-standard version
        assert github_api._extract_version("version10", False) == "10"

        # Test with odd format
        odd_version = github_api._extract_version("odd-format", False)
        assert odd_version is None or isinstance(odd_version, str)

    def test_extract_version_from_filename(self, github_api: GitHubAPI) -> None:
        """
        Test extracting version from filename.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with various filename formats
        assert github_api._extract_version_from_filename("app-1.2.3-x86_64.AppImage") == "1.2.3"
        assert github_api._extract_version_from_filename("app-v1.2.3.AppImage") == "1.2.3"
        assert github_api._extract_version_from_filename("app-linux-1.2.3.AppImage") == "1.2.3"

        # Test with missing version
        assert github_api._extract_version_from_filename("app-latest.AppImage") is None

        # Test with None
        assert github_api._extract_version_from_filename(None) is None

    def test_process_release(
        self, github_api: GitHubAPI, mock_release_data: Dict[str, Any]
    ) -> None:
        """
        Test processing release data.

        Args:
            github_api: GitHubAPI fixture
            mock_release_data: Mock release data fixture
        """
        with patch.object(github_api, "_extract_version", return_value="1.2.3"):
            with patch.object(github_api, "_find_appimage_asset"):
                with patch.object(github_api, "_find_sha_asset"):
                    # Set up the appimage_name for the test
                    github_api.appimage_name = "app-1.2.3-x86_64.AppImage"

                    result = github_api._process_release(mock_release_data, False)

                    assert result is not None
                    assert result["version"] == "1.2.3"
                    assert result["owner"] == github_api.owner
                    assert result["repo"] == github_api.repo
                    assert github_api.version == "1.2.3"

    def test_process_release_missing_key(self, github_api: GitHubAPI) -> None:
        """
        Test handling of missing keys in release data.

        Args:
            github_api: GitHubAPI fixture
        """
        # Missing tag_name
        incomplete_data = {"assets": []}

        result = github_api._process_release(incomplete_data, False)

        assert result is None

    def test_is_sha_file(self, github_api: GitHubAPI) -> None:
        """
        Test detection of SHA files.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with various SHA file formats
        assert github_api._is_sha_file("app.sha256") is True
        assert github_api._is_sha_file("app.sha512") is True
        assert github_api._is_sha_file("app.yml") is True
        assert github_api._is_sha_file("app.yaml") is True
        assert github_api._is_sha_file("checksum.txt") is True
        assert github_api._is_sha_file("sha256sums") is True

        # Test with non-SHA files
        assert github_api._is_sha_file("app.AppImage") is False
        assert github_api._is_sha_file("app.png") is False
        assert github_api._is_sha_file("readme.md") is False

    def test_extract_arch_from_filename(self, github_api: GitHubAPI) -> None:
        """
        Test extracting architecture information from filename.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with various architecture patterns
        assert github_api._extract_arch_from_filename("app-x86_64.AppImage") == "x86_64"
        assert github_api._extract_arch_from_filename("app-amd64.AppImage") == "x86_64"
        assert github_api._extract_arch_from_filename("app-x64.AppImage") == "x86_64"
        assert github_api._extract_arch_from_filename("app-arm64.AppImage") == "arm64"
        assert github_api._extract_arch_from_filename("app-aarch64.AppImage") == "arm64"
        assert github_api._extract_arch_from_filename("app-armv7.AppImage") == "armv7"
        assert github_api._extract_arch_from_filename("app-i386.AppImage") == "i386"
        assert github_api._extract_arch_from_filename("app-mac.dmg") == "mac"
        assert github_api._extract_arch_from_filename("app-win.exe") == "win"

        # Test with no architecture
        assert github_api._extract_arch_from_filename("app.AppImage") == ""

        # Test with None
        assert github_api._extract_arch_from_filename(None) == ""

    def test_get_incompatible_archs(self, github_api: GitHubAPI) -> None:
        """
        Test getting incompatible architecture keywords.

        Args:
            github_api: GitHubAPI fixture
        """
        # Test with various architectures
        x86_64_incompatible = github_api._get_incompatible_archs("x86_64")
        assert "arm64" in x86_64_incompatible
        assert "aarch64" in x86_64_incompatible
        assert "i686" in x86_64_incompatible

        arm64_incompatible = github_api._get_incompatible_archs("arm64")
        assert "x86_64" in arm64_incompatible
        assert "amd64" in arm64_incompatible

        # Test with unsupported architecture
        assert github_api._get_incompatible_archs("unsupported") == []
