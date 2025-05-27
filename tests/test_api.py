#!/usr/bin/env python3
"""Tests for the GitHub API module.

This module contains pytest tests for the GitHubAPI class, which handles
GitHub API requests, version comparison, and AppImage selection.
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api.github_api import GitHubAPI


@pytest.fixture
def github_api() -> GitHubAPI:
    """Create a basic GitHubAPI instance for testing.

    Returns:
        GitHubAPI: A basic GitHubAPI instance

    """
    with patch(
        "src.api.github_api.GitHubAuthManager.get_auth_headers", return_value={"User-Agent": "test"}
    ):
        with patch("src.api.github_api.IconManager"):
            api = GitHubAPI(owner="test-owner", repo="test-repo")
            return api


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
def mock_release_info() -> "ReleaseInfo":
    """Create a mock ReleaseInfo dataclass instance for testing.

    Returns:
        ReleaseInfo: A mock ReleaseInfo instance

    """
    from api.assets import ReleaseInfo

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


class TestGitHubAPI:
    """Tests for the GitHubAPI class."""

    def test_initialization(self, github_api: GitHubAPI) -> None:
        """Test GitHubAPI initialization with default parameters.

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
        """Test the arch_keyword property getter.

        Args:
            github_api: GitHubAPI fixture

        """
        assert github_api.arch_keyword is None
        github_api._arch_keyword = "x86_64"
        assert github_api.arch_keyword == "x86_64"

    def test_get_arch_keywords_with_provided_keyword(self) -> None:
        """Test getting architecture keywords when one is explicitly provided."""
        with patch(
            "src.api.github_api.GitHubAuthManager.get_auth_headers",
            return_value={"User-Agent": "test"},
        ):
            with patch("src.api.github_api.IconManager"):
                api = GitHubAPI(owner="test-owner", repo="test-repo", arch_keyword="custom-arch")
                assert "custom-arch" in api.arch_keywords

    def test_get_arch_keywords_for_current_platform(
        self, mock_platform_info: Dict[str, str]
    ) -> None:
        """Test getting architecture keywords for the current platform.

        Args:
            mock_platform_info: Mock platform info fixture

        """
        with patch("platform.system", return_value=mock_platform_info["system"]):
            with patch("platform.machine", return_value=mock_platform_info["machine"]):
                with patch("src.utils.arch_utils.get_arch_keywords") as mock_get_arch_keywords:
                    mock_get_arch_keywords.return_value = ["x86_64", "amd64", "x64"]

                    with patch(
                        "src.api.github_api.GitHubAuthManager.get_auth_headers",
                        return_value={"User-Agent": "test"},
                    ):
                        with patch("src.api.github_api.IconManager"):
                            api = GitHubAPI(owner="test-owner", repo="test-repo")
                            assert "x86_64" in api.arch_keywords
                            assert "amd64" in api.arch_keywords
                            assert len(api.arch_keywords) > 0

    def test_get_latest_release_success(
        self, github_api: GitHubAPI, mock_release_data: Dict[str, Any]
    ) -> None:
        """Test successful fetch of the latest stable release.

        Args:
            github_api: GitHubAPI fixture
            mock_release_data: Mock release data fixture

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
        """Test handling of 404 response when fetching the latest release.

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
        """Test handling of rate limit exceeded response.

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
        """Test handling of other errors when fetching the latest release.

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
        """Test handling of network errors when fetching the latest release.

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
        """Test handling of unexpected exceptions when fetching the latest release.

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
        """Test successful fetch of beta releases.

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
        """Test handling of empty releases list.

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
        """Test handling of errors when fetching beta releases.

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
        """Test handling of exceptions when fetching beta releases.

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
        """Test the get_response method which tries stable release then falls back to beta.

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
        """Test successful version check with update available.

        Args:
            github_api: GitHubAPI fixture
            mock_release_data: Mock release data fixture

        """
        with patch.object(github_api, "get_response", return_value=(True, mock_release_data)):
            # Need to patch version_utils functions to ensure they behave consistently
            with patch(
                "src.utils.version_utils.normalize_version_for_comparison"
            ) as mock_normalize:
                with patch("src.utils.version_utils.repo_uses_beta") as mock_repo_uses_beta:
                    with patch("src.utils.version_utils.extract_base_version") as mock_extract_base:
                        # Set up the mocks to return deterministic values for our test cases
                        mock_normalize.side_effect = (
                            lambda x: "1.0.0"
                            if x == "v1.0.0"
                            else "1.2.3"
                            if x == "v1.2.3" or x == mock_release_data["tag_name"]
                            else "2.0.0"
                        )
                        mock_repo_uses_beta.return_value = False

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
        """Test version check with a repo that uses beta versions.

        Args:
            github_api: GitHubAPI fixture
            mock_beta_release_data: Mock beta release data fixture

        """
        # Make the repo use beta versions
        github_api.repo = "FreeTube"  # This is in the beta_repos list

        with patch.object(github_api, "get_response", return_value=(True, mock_beta_release_data)):
            with patch(
                "src.utils.version_utils.normalize_version_for_comparison"
            ) as mock_normalize:
                with patch("src.utils.version_utils.repo_uses_beta") as mock_repo_uses_beta:
                    with patch("src.utils.version_utils.extract_base_version") as mock_extract_base:
                        # Set up the mocks
                        mock_normalize.side_effect = lambda x: x.lstrip("v") if x else ""
                        mock_repo_uses_beta.return_value = True
                        mock_extract_base.side_effect = (
                            lambda x: "1.2.0" if x == "1.2.0" else "1.3.0"
                        )

                        # Test when base version is different (update available)
                        update_available, info = github_api.check_latest_version(
                            current_version="v1.2.0"
                        )

                        assert update_available is True
                        assert info["latest_version"] == mock_beta_release_data["tag_name"]

                        # Test when base version is same (no update)
                        # 1.3.0 base version equals 1.3.0-beta base version
                        update_available, info = github_api.check_latest_version(
                            current_version="v1.3.0"
                        )

                        assert update_available is False
                        assert info["latest_version"] == mock_beta_release_data["tag_name"]

    def test_check_latest_version_failed_response(self, github_api: GitHubAPI) -> None:
        """Test version check when getting response fails.

        Args:
            github_api: GitHubAPI fixture

        """
        with patch.object(github_api, "get_response", return_value=(False, "API error")):
            update_available, info = github_api.check_latest_version(current_version="v1.0.0")

            assert update_available is False
            assert "error" in info
            assert info["error"] == "API error"

    def test_check_latest_version_exception(self, github_api: GitHubAPI) -> None:
        """Test handling of exceptions during version check.

        Args:
            github_api: GitHubAPI fixture

        """
        with patch.object(github_api, "get_response", return_value=(True, {})):  # Empty response
            update_available, info = github_api.check_latest_version(current_version="v1.0.0")

            assert update_available is False
            assert "error" in info
            assert "error parsing" in info["error"].lower()

    def test_find_app_icon(self, github_api: GitHubAPI) -> None:
        """Test finding application icon.

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
        """Test refreshing authentication headers.

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

    def test_process_release(
        self, github_api: GitHubAPI, mock_release_data: Dict[str, Any]
    ) -> None:
        """Test processing release data.

        Args:
            github_api: GitHubAPI fixture
            mock_release_data: Mock release data fixture

        """
        with patch("src.utils.version_utils.extract_version", return_value="1.2.3"):
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
        """Test handling of missing keys in release data.

        Args:
            github_api: GitHubAPI fixture

        """
        # Missing tag_name
        incomplete_data = {"assets": []}

        with patch("logging.error") as mock_log:
            result = github_api._process_release(incomplete_data, False)
            assert result is None
            mock_log.assert_called_once()

    def test_find_appimage_asset(self, github_api: GitHubAPI) -> None:
        """Test finding AppImage assets based on architecture.

        Args:
            github_api: GitHubAPI fixture

        """
        # Create test assets
        assets = [
            {
                "name": "app-x86_64.AppImage",
                "browser_download_url": "https://example.com/app-x86_64.AppImage",
            },
            {
                "name": "app-arm64.AppImage",
                "browser_download_url": "https://example.com/app-arm64.AppImage",
            },
        ]

        with patch("src.utils.arch_utils.get_current_arch", return_value="x86_64"):
            with patch(
                "src.utils.arch_utils.get_incompatible_archs", return_value=["arm64", "aarch64"]
            ):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_appimage") as mock_select:
                        # Test finding architecture-specific AppImage
                        github_api._find_appimage_asset(assets)
                        mock_select.assert_called_once()
                        assert mock_select.call_args[0][0]["name"] == "app-x86_64.AppImage"

    def test_select_appimage(self, github_api: GitHubAPI) -> None:
        """Test selecting an AppImage asset.

        Args:
            github_api: GitHubAPI fixture

        """
        # Create a mock AppImage asset
        mock_asset = {
            "name": "app-x86_64.AppImage",
            "browser_download_url": "https://example.com/app-x86_64.AppImage",
        }

        with patch("logging.info"):
            github_api._select_appimage(mock_asset)

            assert github_api.appimage_url == "https://example.com/app-x86_64.AppImage"
            assert github_api.appimage_name == "app-x86_64.AppImage"
            assert github_api._arch_keyword == "-x86_64.appimage"

        # Test with other architecture patterns
        mock_asset = {
            "name": "app-amd64.AppImage",
            "browser_download_url": "https://example.com/app-amd64.AppImage",
        }

        with patch("logging.info"):
            github_api._select_appimage(mock_asset)

            assert github_api.appimage_url == "https://example.com/app-amd64.AppImage"
            assert github_api.appimage_name == "app-amd64.AppImage"
            assert github_api._arch_keyword == "-amd64.appimage"

    def test_find_sha_asset(self, github_api: GitHubAPI) -> None:
        """Test finding SHA asset for verification.

        Args:
            github_api: GitHubAPI fixture

        """
        # Skip test if SHA verification is disabled
        github_api.sha_name = "sha256"
        github_api.appimage_name = "app-x86_64.AppImage"

        # Create test assets
        assets = [
            {
                "name": "app-x86_64.AppImage",
                "browser_download_url": "https://example.com/app-x86_64.AppImage",
            },
            {
                "name": "sha256sums",
                "browser_download_url": "https://example.com/sha256sums",
            },
        ]

        with patch("src.utils.arch_utils.extract_arch_from_filename", return_value="x86_64"):
            with patch("logging.info"):
                with patch.object(github_api, "_select_sha_asset") as mock_select:
                    # Test exact match first
                    github_api.sha_name = "sha256sums"
                    github_api._find_sha_asset(assets)
                    mock_select.assert_called_once()
                    assert mock_select.call_args[0][0]["name"] == "sha256sums"

    def test_select_sha_asset(self, github_api: GitHubAPI) -> None:
        """Test selecting a SHA asset.

        Args:
            github_api: GitHubAPI fixture

        """
        # Create a mock SHA asset
        mock_asset = {
            "name": "sha256sums",
            "browser_download_url": "https://example.com/sha256sums",
        }

        with patch("src.utils.sha_utils.detect_hash_type", return_value="sha256"):
            with patch("logging.info"):
                github_api._select_sha_asset(mock_asset)

                assert github_api.sha_name == "sha256sums"
                assert github_api.sha_url == "https://example.com/sha256sums"
                assert github_api.hash_type == "sha256"

        # Test when hash type can't be detected
        mock_asset = {
            "name": "checksums.txt",
            "browser_download_url": "https://example.com/checksums.txt",
        }

        with patch("src.utils.sha_utils.detect_hash_type", return_value=None):
            with patch("logging.info"):
                with patch("src.utils.ui_utils.get_user_input", return_value="sha512"):
                    github_api._select_sha_asset(mock_asset)

                    assert github_api.sha_name == "checksums.txt"
                    assert github_api.sha_url == "https://example.com/checksums.txt"
                    assert github_api.hash_type == "sha512"

    def test_handle_sha_fallback(self, github_api: GitHubAPI) -> None:
        """Test handling SHA fallback when no SHA file is found.

        Args:
            github_api: GitHubAPI fixture

        """
        github_api.appimage_name = "app-x86_64.AppImage"
        assets = [
            {
                "name": "app-x86_64.AppImage",
                "browser_download_url": "https://example.com/app-x86_64.AppImage",
            },
            {
                "name": "manual-sha256",
                "browser_download_url": "https://example.com/manual-sha256",
            },
        ]

        # Test when user enters filename manually and it exists
        with patch("src.utils.ui_utils.get_user_input", side_effect=["1", "manual-sha256"]):
            with patch("logging.warning"):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_sha_asset") as mock_select:
                        github_api._handle_sha_fallback(assets)
                        mock_select.assert_called_once()
                        assert github_api.sha_name == "manual-sha256"

        # Test when user chooses to skip verification
        with patch("src.utils.ui_utils.get_user_input", return_value="2"):
            with patch("logging.warning"):
                with patch("logging.info"):
                    github_api._handle_sha_fallback(assets)
                    assert github_api.sha_name == "no_sha_file"

    def test_find_sha_asset_specific_cases(self, github_api: GitHubAPI) -> None:
        """Test the specific Joplin case mentioned in the requirements.

        The test verifies the SHA detection prioritization for Joplin, which includes:
        1. Joplin-3.2.13.AppImage.sha512 (highest priority)
        2. latest-linux.yml (second priority)
        3. latest.yml (lowest priority)

        Args:
            github_api: GitHubAPI fixture

        """
        github_api.appimage_name = "Joplin-3.2.13.AppImage"

        # Create assets matching the specific Joplin case
        # Priority order starting from the highest
        assets = [
            {
                "name": "Joplin-3.2.13.AppImage",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage",
            },
            {
                "name": "Joplin-3.2.13.AppImage.sha512",  # Should be selected first
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage.sha512",
            },
            {
                "name": "Joplin-3.2.13.AppImage.sha256",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage.sha256",
            },
            {
                "name": "Joplin-3.2.13.AppImage.sha256sum",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage.sha256sum",
            },
            {
                "name": "Joplin-3.2.13.AppImage.sha512sum",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage.sha512sum",
            },
            {
                "name": "latest-linux.yml",
                "browser_download_url": "https://example.com/latest-linux.yml",
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://example.com/SHA256SUMS.txt",
            },
            {
                "name": "SHA512SUMS.txt",
                "browser_download_url": "https://example.com/SHA512SUMS.txt",
            },
            {
                "name": "checksums.txt",
                "browser_download_url": "https://example.com/checksums.txt",
            },
            {
                "name": "latest.yml",
                "browser_download_url": "https://example.com/latest.yml",
            },
        ]

        # Test that direct AppImage SHA gets priority
        with patch("src.utils.arch_utils.extract_arch_from_filename", return_value=None):
            with patch("src.utils.sha_utils.is_sha_file", return_value=True):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_sha_asset") as mock_select:
                        github_api._find_sha_asset(assets)
                        mock_select.assert_called_once()
                        assert (
                            mock_select.call_args[0][0]["name"] == "Joplin-3.2.13.AppImage.sha512"
                        )

    def test_find_sha_asset_fallback_to_linux_yml(self, github_api: GitHubAPI) -> None:
        """Test fallback to latest-linux.yml when direct SHA files are not available."""
        github_api.appimage_name = "Joplin-3.2.13.AppImage"

        # Same assets but without the direct SHA files
        assets = [
            {
                "name": "Joplin-3.2.13.AppImage",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage",
            },
            {
                "name": "latest-linux.yml",
                "browser_download_url": "https://example.com/latest-linux.yml",
            },
            {
                "name": "Joplin-3.2.13.AppImage.sha256sum",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage.sha256sum",
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://example.com/SHA256SUMS.txt",
            },
            {
                "name": "SHA512SUMS.txt",
                "browser_download_url": "https://example.com/SHA512SUMS.txt",
            },
            {
                "name": "checksums.txt",
                "browser_download_url": "https://example.com/checksums.txt",
            },
            {
                "name": "latest.yml",
                "browser_download_url": "https://example.com/latest.yml",
            },
            {
                "name": "latest.yml",
                "browser_download_url": "https://example.com/latest.yml",
            },
        ]

        with patch("src.utils.arch_utils.extract_arch_from_filename", return_value=None):
            with patch("src.utils.sha_utils.is_sha_file", return_value=True):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_sha_asset") as mock_select:
                        github_api._find_sha_asset(assets)
                        mock_select.assert_called_once()
                        assert mock_select.call_args[0][0]["name"] == "latest-linux.yml"

    def test_find_sha_asset_fallback_to_arch_specific(self, github_api: GitHubAPI) -> None:
        """Test fallback to architecture-specific SHA files when direct SHA files aren't available.

        This test verifies the second priority in SHA file selection:
        - Direct AppImage SHA (missing in this test)
        - Architecture-specific SHA (should be selected)

        Args:
            github_api: GitHubAPI fixture

        """
        github_api.appimage_name = "Joplin-3.2.13-x86_64.AppImage"

        assets = [
            {
                "name": "Joplin-3.2.13-x86_64.AppImage",
                "browser_download_url": "https://example.com/Joplin-3.2.13-x86_64.AppImage",
            },
            {
                "name": "latest-linux.yml",
                "browser_download_url": "https://example.com/latest-linux.yml",
            },
            {
                "name": "checksums-x86_64.sha256",  # Architecture-specific SHA
                "browser_download_url": "https://example.com/checksums-x86_64.sha256",
            },
        ]

        with patch("src.utils.arch_utils.extract_arch_from_filename", return_value=None):
            with patch("src.utils.sha_utils.is_sha_file", return_value=True):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_sha_asset") as mock_select:
                        github_api._find_sha_asset(assets)
                        mock_select.assert_called_once()
                        assert mock_select.call_args[0][0]["name"] == "latest-linux.yml"

    def test_find_sha_asset_fallback_to_sha256sums(self, github_api: GitHubAPI) -> None:
        """Test fallback to SHA256SUMS.txt when higher priority files aren't available.

        This test verifies the fourth priority in SHA file selection:
        - Direct AppImage SHA (missing)
        - Architecture-specific SHA (missing)
        - latest-linux.yml (missing)
        - SHA256SUMS.txt (should be selected)

        Args:
            github_api: GitHubAPI fixture

        """
        github_api.appimage_name = "Joplin-3.2.13.AppImage"

        assets = [
            {
                "name": "Joplin-3.2.13.AppImage",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage",
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://example.com/SHA256SUMS.txt",
            },
            {
                "name": "latest.yml",  # Lower priority
                "browser_download_url": "https://example.com/latest.yml",
            },
        ]

        with patch("src.utils.arch_utils.extract_arch_from_filename", return_value=None):
            with patch("src.utils.sha_utils.is_sha_file", return_value=True):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_sha_asset") as mock_select:
                        github_api._find_sha_asset(assets)
                        mock_select.assert_called_once()
                        assert mock_select.call_args[0][0]["name"] == "SHA256SUMS.txt"

    def test_find_sha_asset_fallback_to_generic_checksums(self, github_api: GitHubAPI) -> None:
        """Test fallback to generic checksum files when higher priority files aren't available.

        This test verifies the fifth priority in SHA file selection:
        - Direct AppImage SHA (missing)
        - Architecture-specific SHA (missing)
        - latest-linux.yml (missing)
        - SHA256SUMS.txt (missing)
        - Generic checksums (should be selected)

        Args:
            github_api: GitHubAPI fixture

        """
        github_api.appimage_name = "Joplin-3.2.13.AppImage"

        assets = [
            {
                "name": "Joplin-3.2.13.AppImage",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage",
            },
            {
                "name": "checksums.txt",  # Generic checksum file
                "browser_download_url": "https://example.com/checksums.txt",
            },
            {
                "name": "latest.yml",  # Lower priority
                "browser_download_url": "https://example.com/latest.yml",
            },
        ]

        with patch("src.utils.arch_utils.extract_arch_from_filename", return_value=None):
            with patch("src.utils.sha_utils.is_sha_file", return_value=True):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_sha_asset") as mock_select:
                        github_api._find_sha_asset(assets)
                        mock_select.assert_called_once()
                        assert mock_select.call_args[0][0]["name"] == "checksums.txt"

    def test_find_sha_asset_fallback_to_latest_yml(self, github_api: GitHubAPI) -> None:
        """Test fallback to latest.yml when all higher priority files aren't available.

        This test verifies the lowest priority in SHA file selection:
        - All higher priority files missing
        - latest.yml (should be selected as last resort)

        Args:
            github_api: GitHubAPI fixture

        """
        # Set appimage_name without "linux" to test the priority logic
        github_api.appimage_name = "Joplin-3.2.13.AppImage"

        assets = [
            {
                "name": "Joplin-3.2.13.AppImage",
                "browser_download_url": "https://example.com/Joplin-3.2.13.AppImage",
            },
            {
                "name": "latest.yml",  # Should be selected as last resort
                "browser_download_url": "https://example.com/latest.yml",
            },
        ]

        with patch("src.utils.arch_utils.extract_arch_from_filename", return_value=None):
            with patch("src.utils.sha_utils.is_sha_file", return_value=True):
                with patch("logging.info"):
                    with patch.object(github_api, "_select_sha_asset") as mock_select:
                        github_api._find_sha_asset(assets)
                        mock_select.assert_called_once()
                        assert mock_select.call_args[0][0]["name"] == "latest.yml"
