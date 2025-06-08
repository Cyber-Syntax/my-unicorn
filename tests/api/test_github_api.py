"""Tests for the GitHubAPI class, focusing on its direct responsibilities and orchestration."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests  # Keep for now, might be needed for some exception tests if not fully moved

from src.api.github_api import GitHubAPI
from src.api.assets import ReleaseInfo  # Added import for type hint
from src.utils import version_utils  # Added import
from src.utils import arch_extraction  # Added import for extract_arch_from_filename
# ReleaseManager might be needed for type hinting if we mock its instance
# from src.api.release_manager import ReleaseManager


@pytest.fixture
def github_api_instance() -> GitHubAPI:
    """Create a GitHubAPI instance with mocked dependencies for testing.

    Returns:
        GitHubAPI: A GitHubAPI instance with ReleaseManager mocked.
    """
    with patch(
        "src.api.github_api.GitHubAuthManager.get_auth_headers", return_value={"User-Agent": "test"}
    ):
        with patch("src.api.github_api.IconManager") as mock_icon_manager:
            # Mock the ReleaseManager that GitHubAPI instantiates
            with patch("src.api.github_api.ReleaseManager") as mock_release_manager_class:
                # Configure the instance that will be created
                mock_rm_instance = MagicMock()
                mock_release_manager_class.return_value = mock_rm_instance

                api = GitHubAPI(owner="test-owner", repo="test-repo")
                # Attach the mock instance to the api instance for later access in tests if needed
                api._release_fetcher = mock_rm_instance
                api._icon_manager = (
                    mock_icon_manager  # Ensure IconManager is also accessible if needed
                )
                return api


class TestGitHubAPIDirect:
    """Tests for the GitHubAPI class's direct logic and orchestration."""

    def test_initialization(self, github_api_instance: GitHubAPI) -> None:
        """Test GitHubAPI initialization.

        Args:
            github_api_instance: GitHubAPI fixture
        """
        assert github_api_instance.owner == "test-owner"
        assert github_api_instance.repo == "test-repo"
        # checksum_file_name and checksum_hash_type are initialized by ReleaseProcessor via _process_release
        # Let's check their state before _process_release is called.
        # These might be better tested after a successful _process_release call.
        # For now, let's assume they are None or default before processing.
        # The original test checked for "sha256", but this is set during _process_release.
        # Let's defer detailed checks of these to tests that involve _process_release.

        assert github_api_instance.version is None
        # checksum_file_download_url, app_download_url, appimage_name are also set by _process_release
        assert github_api_instance.checksum_file_download_url is None
        assert github_api_instance.app_download_url is None
        assert github_api_instance.appimage_name is None

        assert (
            github_api_instance._arch_keyword is None
        )  # This is set by AppImageSelector via _process_release
        # AppImageSelector is an internal detail, we trust it's initialized.
        # Specific tests for AppImageSelector will cover its arch_keywords.
        assert isinstance(github_api_instance._headers, dict)
        assert (
            github_api_instance._release_fetcher is not None
        )  # Check if ReleaseManager was instantiated (mocked)

    def test_arch_keyword_property(self, github_api_instance: GitHubAPI) -> None:
        """Test the arch_keyword property getter.

        Args:
            github_api_instance: GitHubAPI fixture
        """
        assert github_api_instance.arch_keyword is None  # Initially None
        github_api_instance._arch_keyword = "x86_64"  # Simulate it being set
        assert github_api_instance.arch_keyword == "x86_64"

    def test_get_latest_release_success(
        self,
        github_api_instance: GitHubAPI,
        mock_release_data: tuple[str, Any],  # mock_release_data from conftest
    ) -> None:
        """Test successful fetch and processing of the latest release."""
        # Configure the mock ReleaseManager's method
        github_api_instance._release_fetcher.get_latest_release_data.return_value = (
            True,
            mock_release_data,
        )

        # Mock _process_release as it's a complex internal method tested separately
        with patch.object(github_api_instance, "_process_release") as mock_process_release:
            success, data = github_api_instance.get_latest_release()

            assert success is True
            assert data == mock_release_data  # get_latest_release returns the raw data on success
            github_api_instance._release_fetcher.get_latest_release_data.assert_called_once_with(
                github_api_instance._headers
            )
            mock_process_release.assert_called_once_with(
                mock_release_data, version_check_only=False, is_batch=False
            )

    def test_get_latest_release_fetch_fails(self, github_api_instance: GitHubAPI) -> None:
        """Test when ReleaseManager fails to fetch data."""
        github_api_instance._release_fetcher.get_latest_release_data.return_value = (
            False,
            "Fetch error from RM",
        )

        with patch.object(github_api_instance, "_process_release") as mock_process_release:
            success, error_message = github_api_instance.get_latest_release()

            assert success is False
            assert error_message == "Fetch error from RM"
            github_api_instance._release_fetcher.get_latest_release_data.assert_called_once_with(
                github_api_instance._headers
            )
            mock_process_release.assert_not_called()

    def test_get_latest_release_rate_limit(self, github_api_instance: GitHubAPI) -> None:
        """Test rate limit handling during get_latest_release."""
        github_api_instance._release_fetcher.get_latest_release_data.return_value = (
            False,
            "GitHub API rate limit exceeded.",
        )

        with patch.object(github_api_instance, "refresh_auth") as mock_refresh_auth:
            with patch.object(github_api_instance, "_process_release") as mock_process_release:
                success, response_data = github_api_instance.get_latest_release()
                error_message_str = str(response_data)  # Ensure it's a string for .lower()

                assert success is False
                assert "rate limit exceeded" in error_message_str.lower()
                mock_refresh_auth.assert_called_once()
                mock_process_release.assert_not_called()

    def test_get_latest_release_processing_error(
        self, github_api_instance: GitHubAPI, mock_release_data: tuple[str, Any]
    ) -> None:
        """Test an error during the _process_release stage."""
        github_api_instance._release_fetcher.get_latest_release_data.return_value = (
            True,
            mock_release_data,
        )

        with patch.object(
            github_api_instance, "_process_release", side_effect=ValueError("Processing failed")
        ) as mock_process_release:
            success, response_data = github_api_instance.get_latest_release()
            error_message_str = str(response_data)  # Ensure it's a string

            assert success is False
            assert "failed to process release data" in error_message_str.lower()
            mock_process_release.assert_called_once_with(mock_release_data)

    def test_check_latest_version_success_update_available(
        self, github_api_instance: GitHubAPI, mock_release_data: tuple[str, Any]
    ) -> None:
        """Test successful version check with update available."""
        # Mock get_latest_release to simulate successful fetch and processing
        # _process_release would populate self.version, self._release_info etc.
        github_api_instance.version = "1.2.3"  # Simulate version set by _process_release
        github_api_instance._release_info = MagicMock()  # Simulate ReleaseInfo set
        github_api_instance._release_info.to_summary_dict.return_value = {
            "version": "1.2.3",
            "appimage_name": "app-x86_64.AppImage",
            # ... other fields needed by check_latest_version's response
        }

        with patch.object(
            github_api_instance, "get_latest_release", return_value=(True, mock_release_data)
        ):
            # Mock the ReleaseProcessor's compare_versions method
            with patch(
                "src.api.github_api.ReleaseProcessor.compare_versions",
                return_value=(True, "1.0.0", "1.2.3"),
            ) as mock_compare:
                # Simulate that _process_release has populated necessary attributes
                github_api_instance.version = "1.2.3"  # Latest version from mock_release_data

                # Mock what ReleaseProcessor.create_update_response would need/do
                # This part is tricky as check_latest_version directly calls ReleaseProcessor methods
                # For a true unit test of check_latest_version, we should mock ReleaseProcessor instance methods

                # Let's assume _process_release correctly populates _release_info
                # and version. The main logic in check_latest_version is the comparison.

                # To simplify, we'll mock the outcome of the comparison
                # and the data that would be returned.
                # A more detailed test would mock the ReleaseProcessor instance.

                # Simulate that _process_release (called by get_latest_release) populates these:
                github_api_instance.version = mock_release_data["tag_name"]
                github_api_instance._release_info = MagicMock()
                github_api_instance._release_info.version = mock_release_data["tag_name"]
                github_api_instance._release_info.prerelease = mock_release_data["prerelease"]
                # ... other attributes of _release_info if needed by ReleaseProcessor.compare_versions

                # Mock the ReleaseProcessor instance used within check_latest_version
                with patch("src.api.github_api.ReleaseProcessor") as mock_rp_class:
                    mock_rp_instance = MagicMock()
                    mock_rp_class.return_value = mock_rp_instance

                    # Mock compare_versions to indicate an update is available
                    # It should return: (bool, tuple[str, str])
                    mock_compare_versions_dict = {
                        "current_version": "v1.0.0",
                        "latest_version": mock_release_data["tag_name"],
                        "current_normalized": "1.0.0",
                        "latest_normalized": version_utils.normalize_version_for_comparison(
                            mock_release_data["tag_name"]
                        ),
                    }
                    mock_rp_instance.compare_versions.return_value = (
                        True,
                        mock_compare_versions_dict,
                    )

                    # The check_latest_version method in GitHubAPI constructs its own response dictionary.
                    # It does not directly use ReleaseProcessor.create_update_response.

                    update_available, info = github_api_instance.check_latest_version(
                        current_version="v1.0.0"
                    )

                    assert update_available is True
                    assert info["current_version"] == "v1.0.0"
                    assert info["latest_version"] == mock_release_data["tag_name"]
                    # Assert call to compare_versions with correct arguments
                    # The real compare_versions takes (current_version: str, latest_version: str)
                    mock_rp_instance.compare_versions.assert_called_once_with(
                        "v1.0.0", mock_release_data["tag_name"]
                    )

    def test_check_latest_version_success_no_update(
        self, github_api_instance: GitHubAPI, mock_release_data: tuple[str, Any]
    ) -> None:
        """Test successful version check with no update available."""
        with patch.object(
            github_api_instance, "get_latest_release", return_value=(True, mock_release_data)
        ):
            with patch("src.api.github_api.ReleaseProcessor") as mock_rp_class:
                mock_rp_instance = MagicMock()
                mock_rp_class.return_value = mock_rp_instance
                # Mock compare_versions to indicate no update
                # It should return: (bool, tuple[str, str])
                mock_compare_versions_dict_no_update = {
                    "current_version": mock_release_data["tag_name"],
                    "latest_version": mock_release_data["tag_name"],
                    "current_normalized": version_utils.normalize_version_for_comparison(
                        mock_release_data["tag_name"]
                    ),
                    "latest_normalized": version_utils.normalize_version_for_comparison(
                        mock_release_data["tag_name"]
                    ),
                }
                mock_rp_instance.compare_versions.return_value = (
                    False,
                    mock_compare_versions_dict_no_update,
                )

                # Simulate _process_release populating these
                github_api_instance.version = mock_release_data["tag_name"]
                github_api_instance._release_info = MagicMock()
                github_api_instance._release_info.version = mock_release_data["tag_name"]
                github_api_instance._release_info.prerelease = mock_release_data["prerelease"]

                update_available, info = github_api_instance.check_latest_version(
                    current_version=mock_release_data["tag_name"]
                )

                assert update_available is False
                assert info["current_version"] == mock_release_data["tag_name"]
                assert info["latest_version"] == mock_release_data["tag_name"]
                # Assert call to compare_versions with correct arguments
                mock_rp_instance.compare_versions.assert_called_once_with(
                    mock_release_data["tag_name"], mock_release_data["tag_name"]
                )

    def test_check_latest_version_fetch_failed(self, github_api_instance: GitHubAPI) -> None:
        """Test version check when get_latest_release fails."""
        with patch.object(
            github_api_instance, "get_latest_release", return_value=(False, "API fetch error")
        ):
            update_available, info = github_api_instance.check_latest_version(
                current_version="v1.0.0"
            )

            assert update_available is False
            assert "error" in info
            assert info["error"] == "API fetch error"

    def test_check_latest_version_processing_failed(
        self, github_api_instance: GitHubAPI, mock_release_data: tuple[str, Any]
    ) -> None:
        """Test version check when get_latest_release succeeds but subsequent processing (e.g. in ReleaseProcessor) fails."""
        # This simulates get_latest_release succeeding, but an issue occurring within check_latest_version's use of ReleaseProcessor
        with patch.object(
            github_api_instance, "get_latest_release", return_value=(True, mock_release_data)
        ):
            with patch("src.api.github_api.ReleaseProcessor") as mock_rp_class:
                mock_rp_instance = MagicMock()
                mock_rp_class.return_value = mock_rp_instance
                mock_rp_instance.compare_versions.side_effect = Exception("RP Error")

                # Simulate _process_release populating these
                github_api_instance.version = mock_release_data["tag_name"]
                github_api_instance._release_info = MagicMock()
                github_api_instance._release_info.version = mock_release_data["tag_name"]
                github_api_instance._release_info.prerelease = mock_release_data["prerelease"]

                update_available, info = github_api_instance.check_latest_version(
                    current_version="v1.0.0"
                )

                assert update_available is False
                assert "error" in info
                assert "error during version comparison" in info["error"].lower()

    def test_find_app_icon(self, github_api_instance: GitHubAPI) -> None:
        """Test finding application icon."""
        mock_icon_info = {"name": "app-icon.png", "url": "https://example.com/icon.png"}
        github_api_instance._icon_manager.find_icon.return_value = mock_icon_info

        icon_info = github_api_instance.find_app_icon()
        assert icon_info == mock_icon_info
        github_api_instance._icon_manager.find_icon.assert_called_once()

        # Test when icon is not found
        github_api_instance._icon_manager.find_icon.reset_mock()
        github_api_instance._icon_manager.find_icon.return_value = None
        icon_info = github_api_instance.find_app_icon()
        assert icon_info is None

        # Test when exception occurs
        github_api_instance._icon_manager.find_icon.reset_mock()
        github_api_instance._icon_manager.find_icon.side_effect = Exception("Icon error")
        icon_info = github_api_instance.find_app_icon()
        assert icon_info is None  # Should catch exception and return None

    def test_refresh_auth(self, github_api_instance: GitHubAPI) -> None:
        """Test refreshing authentication headers."""
        with patch("src.api.github_api.GitHubAuthManager.clear_cached_headers") as mock_clear:
            with patch(
                "src.api.github_api.GitHubAuthManager.get_auth_headers",
                return_value={"New": "Headers"},
            ) as mock_get:
                github_api_instance.refresh_auth()

                mock_clear.assert_called_once()
                mock_get.assert_called_once()
                assert github_api_instance._headers == {"New": "Headers"}

    def test_process_release_success(
        self,
        github_api_instance: GitHubAPI,
        mock_release_data: tuple[str, Any],
        mock_release_info_fixture: ReleaseInfo,  # mock_release_info_fixture is not used for comparison now
    ) -> None:
        """Test successful processing of release data by _process_release.
        This is a more focused test on _process_release itself.
        """
        # Mock dependencies of _process_release: AppImageSelector, SHAManager.
        with (
            patch("src.api.github_api.AppImageSelector") as mock_ais_class,
            patch("src.api.github_api.SHAManager") as mock_sham_class,
        ):  # mock_sham_class is the patcher object
            mock_ais_instance = MagicMock()
            mock_sham_instance = MagicMock()  # This will be the instance returned by SHAManager()

            mock_ais_class.return_value = mock_ais_instance
            mock_sham_class.return_value = (
                mock_sham_instance  # Configure the class mock to return our instance
            )

            # Configure AppImageSelector mock
            from src.api.selector import AssetSelectionResult

            appimage_filename_for_test = "app-x86_64.AppImage"
            asset_dict = {
                "name": appimage_filename_for_test,
                "browser_download_url": "url1",
                "size": 12345,  # AppImageAsset.from_github_asset uses .get("size")
            }
            mock_ais_instance.find_appimage_asset.return_value = AssetSelectionResult(
                asset=asset_dict, characteristic_suffix=""
            )

            # Configure SHAManager mock attributes that GitHubAPI will read
            checksum_file_name_for_test = "sha.txt"
            checksum_file_download_url_for_test = "url2"
            mock_sham_instance.checksum_file_name = checksum_file_name_for_test
            mock_sham_instance.checksum_file_download_url = checksum_file_download_url_for_test
            mock_sham_instance.checksum_hash_type = "sha256"

            # Call the method under test
            github_api_instance._process_release(mock_release_data)

            # Determine expected version as _process_release would
            current_tag = mock_release_data.get("tag_name", "")
            is_beta = mock_release_data.get("prerelease", False)
            expected_version = version_utils.extract_version(current_tag, is_beta)
            if not expected_version and appimage_filename_for_test:
                expected_version = version_utils.extract_version_from_filename(
                    appimage_filename_for_test
                )
            if not expected_version:  # Fallback if no version could be extracted
                # This case should ideally not be hit if mock_release_data and appimage_filename_for_test are well-defined
                expected_version = "0.0.0"

            # Determine expected arch_keyword as _process_release would
            expected_arch_keyword = (
                arch_extraction.extract_arch_from_filename(appimage_filename_for_test)
                if appimage_filename_for_test
                else None
            )

            # Assertions for attributes of github_api_instance
            assert github_api_instance.version == expected_version
            assert github_api_instance.appimage_name == appimage_filename_for_test
            assert github_api_instance.app_download_url == "url1"
            assert github_api_instance._arch_keyword == expected_arch_keyword
            assert github_api_instance.checksum_file_name == checksum_file_name_for_test
            assert github_api_instance.checksum_file_download_url == checksum_file_download_url_for_test
            assert github_api_instance.checksum_hash_type == "sha256"

            # Construct the expected ReleaseInfo object for comparison
            expected_release_info = ReleaseInfo(
                owner=github_api_instance.owner,
                repo=github_api_instance.repo,
                version=expected_version,
                appimage_name=appimage_filename_for_test,
                app_download_url="url1",
                checksum_file_name=checksum_file_name_for_test,
                checksum_file_download_url=checksum_file_download_url_for_test,
                checksum_hash_type="sha256",
                arch_keyword=expected_arch_keyword,
                release_notes=mock_release_data.get("body", ""),
                release_url=mock_release_data.get("html_url", ""),
                prerelease=is_beta,
                published_at=mock_release_data.get("published_at", ""),
                raw_assets=mock_release_data.get("assets", []),
            )
            assert github_api_instance._release_info == expected_release_info

    def test_process_release_missing_tag_name(self, github_api_instance: GitHubAPI) -> None:
        """Test _process_release with missing 'tag_name' in release data."""
        incomplete_data = {"name": "Release Name", "assets": []}  # Missing tag_name
        with pytest.raises(ValueError, match="Release data missing tag_name"):
            github_api_instance._process_release(incomplete_data)

    def test_process_release_no_appimage_found(
        self, github_api_instance: GitHubAPI, mock_release_data: tuple[str, Any]
    ) -> None:
        """Test _process_release when AppImageSelector finds no AppImage."""
        with (
            patch("src.api.github_api.AppImageSelector") as mock_ais_class,
            patch("src.api.github_api.SHAManager"),
            patch("src.api.github_api.ReleaseProcessor") as mock_rp_class_for_process_release,
        ):  # Patch class used by _process_release
            mock_ais_instance = MagicMock()
            mock_ais_class.return_value = mock_ais_instance
            mock_ais_instance.find_appimage_asset.return_value = None  # Simulate no AppImage found

            mock_internal_rp_instance = MagicMock()
            mock_rp_class_for_process_release.return_value = mock_internal_rp_instance
            mock_internal_rp_instance.extract_version_from_tag.return_value = (
                "1.2.3"  # Still need version for error message
            )

            with pytest.raises(ValueError, match="No compatible AppImage asset found"):
                github_api_instance._process_release(mock_release_data)
