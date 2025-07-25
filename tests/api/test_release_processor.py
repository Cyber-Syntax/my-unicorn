"""Tests for the ReleaseProcessor class."""

from typing import Any
from unittest.mock import patch

import pytest

from my_unicorn.api.assets import (
    ReleaseInfo,
)  # AppImageAsset, SHAAsset not directly used in tests after refactor
from my_unicorn.api.release_processor import ReleaseProcessor

# Fixtures from conftest.py are available:
# mock_release_data, mock_beta_release_data, mock_all_releases_data,
# mock_platform_info, mock_release_info_fixture


@pytest.fixture
def release_processor_instance(mock_platform_info: tuple[str, str]) -> ReleaseProcessor:
    """Provides a ReleaseProcessor instance for testing."""
    # ReleaseProcessor __init__ takes owner, repo, arch_keyword
    # arch_keyword can be derived from mock_platform_info for consistency
    return ReleaseProcessor(
        owner="test-owner",
        repo="test-repo",
        arch_keyword=mock_platform_info["machine"],  # e.g., "x86_64"
    )


class TestReleaseProcessorLogic:
    """Tests for the core logic of ReleaseProcessor."""

    # test_extract_version_from_tag removed as ReleaseProcessor does not have this public method.
    # Version extraction is handled by version_utils, which should be tested separately.

    @pytest.mark.parametrize(
        "current_version, latest_version, repo_name, expected_update",
        [
            ("1.0.0", "1.2.3", "test-repo", True),
            ("1.2.3", "1.2.3", "test-repo", False),
            ("1.3.0", "1.2.3", "test-repo", False),  # Current is newer
            # Test with 'v' prefix, normalization should handle it
            ("v1.0.0", "v1.2.3", "test-repo", True),
            (
                "1.0.0",
                "v1.2.3-beta",
                "test-repo",
                True,
            ),  # Update to newer beta version (1.2.3-beta > 1.0.0)
            (
                "1.2.3",
                "v1.2.3-beta",
                "test-repo",
                False,
            ),  # Stable 1.2.3 is newer than prerelease 1.2.3-beta
            # Standard version comparison for all repos (no special beta logic except zen-browser)
            ("0.17.0", "0.17.1-beta", "FreeTube", True),
            ("0.17.1-beta", "0.17.1-beta", "FreeTube", False),  # Exact same beta
            ("0.17.1", "0.17.1-beta", "FreeTube", False),  # Stable 0.17.1 > 0.17.1-beta
            ("0.18.0", "0.17.1-beta", "FreeTube", False),
        ],
    )
    def test_compare_versions(
        self,
        release_processor_instance: ReleaseProcessor,
        current_version: str,  # Renamed from current_version_str for clarity
        latest_version: str,  # Renamed from latest_version_tag
        repo_name: str,
        expected_update: bool,
        # latest_prerelease is not used by ReleaseProcessor.compare_versions directly
    ):
        """Test version comparison logic."""
        original_repo = release_processor_instance.repo
        release_processor_instance.repo = repo_name  # set repo for zen-browser specific logic

        # Call compare_versions with positional arguments as per its signature
        update_available, versions_dict = release_processor_instance.compare_versions(
            current_version, latest_version
        )

        assert update_available == expected_update
        assert versions_dict["current_version"] == current_version
        assert versions_dict["latest_version"] == latest_version
        # Can add more assertions for normalized versions if needed

        release_processor_instance.repo = original_repo  # Reset repo

    def test_process_release_data(  # Was test_populate_release_info
        self, release_processor_instance: ReleaseProcessor, mock_release_data: tuple[str, Any]
    ):
        """Test processing of raw release data into ReleaseInfo."""
        processed_asset_info = {
            "owner": release_processor_instance.owner,
            "repo": release_processor_instance.repo,
            "version": "1.2.3",
            "appimage_name": "app-x86_64.AppImage",
            "app_download_url": "https://example.com/app-x86_64.AppImage",
            "checksum_file_name": "app-x86_64.AppImage.sha256",
            "checksum_file_download_url": "https://example.com/app-x86_64.AppImage.sha256",
            "checksum_hash_type": "sha256",
            "arch_keyword": "x86_64",
        }
        # is_beta argument for process_release_data defaults to False, can be tested explicitly if needed
        release_info = release_processor_instance.process_release_data(
            release_data=mock_release_data, asset_info=processed_asset_info
        )

        assert isinstance(release_info, ReleaseInfo)
        assert release_info.owner == processed_asset_info["owner"]
        assert release_info.repo == processed_asset_info["repo"]
        assert release_info.version == processed_asset_info["version"]
        # ... (other assertions remain the same)
        assert release_info.appimage_name == processed_asset_info["appimage_name"]
        assert release_info.app_download_url == processed_asset_info["app_download_url"]
        assert release_info.checksum_file_name == processed_asset_info["checksum_file_name"]
        assert (
            release_info.checksum_file_download_url
            == processed_asset_info["checksum_file_download_url"]
        )
        assert release_info.checksum_hash_type == processed_asset_info["checksum_hash_type"]
        assert release_info.arch_keyword == processed_asset_info["arch_keyword"]
        assert release_info.release_notes == mock_release_data["body"]
        assert release_info.release_url == mock_release_data["html_url"]
        assert release_info.prerelease == mock_release_data["prerelease"]
        assert release_info.published_at == mock_release_data["published_at"]
        assert release_info.raw_assets == mock_release_data["assets"]

    def test_process_release_data_key_error(  # Was test_populate_release_info_no_sha (conceptually different now)
        self, release_processor_instance: ReleaseProcessor
    ):
        """Test process_release_data with missing key in asset_info causing KeyError."""
        incomplete_asset_info = {
            "owner": "test"
        }  # Missing repo, version etc. which ReleaseInfo.from_release_data expects
        # process_release_data catches KeyError and returns None
        release_info = release_processor_instance.process_release_data(
            release_data={"body": "notes", "assets": []},  # Provide assets for raw_assets
            asset_info=incomplete_asset_info,
        )
        assert release_info is None

    def test_create_update_response(
        self, release_processor_instance: ReleaseProcessor, mock_release_info_fixture: ReleaseInfo
    ):
        """Test creation of the update response dictionary."""
        current_v = "1.0.0"
        update_available_flag = True
        # compatible_assets is a required argument for create_update_response
        compatible_assets_list_mock = [
            {
                "name": "app-x86_64.AppImage",
                "url": "url1",
                "size": 123,
                "browser_download_url": "url1",
            }
        ]

        # No need to mock filter_compatible_assets if we are testing create_update_response's direct logic
        # and providing the compatible_assets it needs.
        response = release_processor_instance.create_update_response(
            update_available=update_available_flag,
            current_version=current_v,
            release_info=mock_release_info_fixture,  # This fixture should have raw_assets
            compatible_assets=compatible_assets_list_mock,
        )

        assert response["update_available"] == update_available_flag
        assert response["current_version"] == current_v
        assert response["latest_version"] == mock_release_info_fixture.version
        assert response["release_notes"] == mock_release_info_fixture.release_notes
        assert response["release_url"] == mock_release_info_fixture.release_url
        assert response["compatible_assets"] == compatible_assets_list_mock
        # ... assert other fields from mock_release_info_fixture like appimage_name, url etc.
        assert response["appimage_name"] == mock_release_info_fixture.appimage_name
        assert response["app_download_url"] == mock_release_info_fixture.app_download_url

    def test_filter_compatible_assets(
        self,
        release_processor_instance: ReleaseProcessor,
        mock_release_data: tuple[str, Any],
        mock_platform_info: tuple[str, str],
    ):
        """Test filtering of compatible assets."""
        raw_assets_list = mock_release_data["assets"]

        # Case 1: ReleaseProcessor uses its self.arch_keyword internally via arch.get_arch_keywords
        # The arch_keyword for release_processor_instance is set from mock_platform_info["machine"]
        # We mock arch.get_arch_keywords to control its output based on this.
        expected_arch_keyword_for_call = release_processor_instance.arch_keyword  # e.g. "x86_64"
        assert expected_arch_keyword_for_call is not None, (
            "arch_keyword from fixture should not be None for this test"
        )

        with patch(
            "my_unicorn.api.release_processor.arch.get_arch_keywords"
        ) as mock_get_arch_keywords:
            # If arch.get_arch_keywords is called with a non-None arch_keyword (like "x86_64"),
            # it returns a list containing that keyword: `[arch_keyword]`.
            # So, the mock should replicate this behavior for the specific input it will receive.
            # We can use side_effect for more complex input-dependent mocking if needed,
            # but for a fixed input, setting return_value based on that input is fine.
            mock_get_arch_keywords.return_value = [expected_arch_keyword_for_call]

            compatible = release_processor_instance.filter_compatible_assets(raw_assets_list)

            assert len(compatible) == 1
            # Assuming mock_platform_info["machine"] is "x86_64" for this to pass with mock_release_data
            assert compatible[0]["name"] == f"app-{expected_arch_keyword_for_call}.AppImage"
            mock_get_arch_keywords.assert_called_once_with(expected_arch_keyword_for_call)

        # Case 2: Provide explicit arch_keywords argument to filter_compatible_assets
        # This call should NOT use the mocked arch.get_arch_keywords
        # because arch_keywords is provided directly.
        specific_arch_keywords_for_test = ["arm64", "aarch64"]
        # Reset mock or use a new one if concerned about call counts across cases
        with patch(
            "my_unicorn.api.release_processor.arch.get_arch_keywords"
        ) as mock_get_arch_keywords_case2:
            compatible_arm = release_processor_instance.filter_compatible_assets(
                raw_assets_list, arch_keywords=specific_arch_keywords_for_test
            )
            assert len(compatible_arm) == 1
            assert compatible_arm[0]["name"] == "app-arm64.AppImage"
            mock_get_arch_keywords_case2.assert_not_called()  # Crucial: ensure it uses the provided list
