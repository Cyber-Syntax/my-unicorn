#!/usr/bin/env python
"""Tests for InstallAppCommand functionality.

This module contains tests for the InstallAppCommand class, which handles
installing AppImages from the app catalog.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to sys.path using pathlib for better cross-platform compatibility
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import the modules directly to avoid import issues
from my_unicorn.catalog import AppInfo
from my_unicorn.commands.install_catalog import InstallAppCommand


@pytest.fixture
def app_info_fixture() -> AppInfo:
    """Provide a sample AppInfo object for testing.

    Returns:
        AppInfo: Sample application information

    """
    return AppInfo(
        owner="testowner",
        repo="testrepo",
        app_rename="Test App",
        description="A test application",
        category="Test",
        tags=["test", "sample"],
        checksum_hash_type="sha256",
        appimage_name_template="testapp-{arch}.AppImage",
        checksum_file_name="test.sha256",
        preferred_characteristic_suffixes=["x86_64", "amd64"],
        icon_info=None,
        icon_file_name=None,
        icon_repo_path=None,
    )


@pytest.fixture
def install_test_data() -> dict[str, str]:
    """Provide common test data for install app command tests.

    Returns:
        tuple[str, str]: Dictionary containing test values

    """
    return {
        "owner": "testowner",
        "repo": "testrepo",
        "appimage": "test.AppImage",
        "version": "1.0.0",
        "checksum_file_name": "test.sha256",
        "checksum_file_download_url": "http://example.com/test.sha256",
        "app_download_url": "http://example.com/test.AppImage",
        "checksum_hash_type": "sha256",
        "downloaded_file_path": "/tmp/test.AppImage",
    }


@pytest.fixture
def mocked_app_config(
    monkeypatch: pytest.MonkeyPatch, install_test_data: dict[str, str]
) -> MagicMock:
    """Mock the AppConfigManager class.

    Args:
        monkeypatch: Pytest fixture for patching
        install_test_data: Test data fixture

    Returns:
        MagicMock: Mocked AppConfigManager instance

    """
    mock = MagicMock()
    mock.owner = install_test_data["owner"]
    mock.repo = install_test_data["repo"]
    mock.version = install_test_data["version"]
    mock.appimage_name = install_test_data["appimage"]
    mock.checksum_file_name = install_test_data["checksum_file_name"]
    mock.checksum_hash_type = install_test_data["checksum_hash_type"]
    mock.config_folder = "/tmp/config"
    mock.config_file = "/tmp/config/testrepo.json"
    mock.config_file_name = "testrepo.json"

    app_config_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.AppConfigManager", app_config_class_mock)
    return mock


@pytest.fixture
def mocked_api(monkeypatch: pytest.MonkeyPatch, install_test_data: dict[str, str]) -> MagicMock:
    """Mock the GitHubAPI class.

    Args:
        monkeypatch: Pytest fixture for patching
        install_test_data: Test data fixture

    Returns:
        MagicMock: Mocked GitHubAPI instance

    """
    mock = MagicMock()
    mock.owner = install_test_data["owner"]
    mock.repo = install_test_data["repo"]
    mock.version = install_test_data["version"]
    mock.appimage_name = install_test_data["appimage"]
    mock.checksum_file_name = install_test_data["checksum_file_name"]
    mock.checksum_file_download_url = install_test_data["checksum_file_download_url"]
    mock.checksum_hash_type = install_test_data["checksum_hash_type"]
    mock.arch_keyword = None
    mock.app_download_url = install_test_data["app_download_url"]
    mock.get_response.return_value = (True, "Success")  # Success response
    mock.check_latest_version.return_value = (
        False,
        {
            "current_version": None,
            "latest_version": install_test_data["version"],
            "release_notes": "Test release notes",
            "release_url": "https://github.com/test/test/releases/tag/v1.0.0",
            "compatible_assets": [],
            "prerelease": False,
            "published_at": "2023-01-01T00:00:00Z",
        },
    )  # Proper response format

    api_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.GitHubAPI", api_class_mock)
    return mock


@pytest.fixture
def mocked_download_manager(
    monkeypatch: pytest.MonkeyPatch, install_test_data: dict[str, str]
) -> MagicMock:
    """Mock the DownloadManager class.

    Args:
        monkeypatch: Pytest fixture for patching
        install_test_data: Test data fixture

    Returns:
        MagicMock: Mocked DownloadManager instance

    """
    mock = MagicMock()
    mock.download.return_value = install_test_data["downloaded_file_path"]

    download_manager_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.DownloadManager", download_manager_class_mock)
    return mock


@pytest.fixture
def mocked_global_config(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the GlobalConfigManager class.

    Args:
        monkeypatch: Pytest fixture for patching

    Returns:
        MagicMock: Mocked GlobalConfigManager instance

    """
    mock = MagicMock()
    mock.expanded_app_storage_path = "/tmp"
    mock.expanded_app_backup_storage_path = "/tmp/backup"
    mock.batch_mode = True
    mock.keep_backup = True
    mock.config_file = "/tmp/global_config.json"
    mock.max_backups = 3

    global_config_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.GlobalConfigManager", global_config_class_mock)
    return mock


@pytest.fixture
def mocked_verifier(
    monkeypatch: pytest.MonkeyPatch, verification_success: bool = True
) -> MagicMock:
    """Mock the VerificationManager class.

    Args:
        monkeypatch: Pytest fixture for patching
        verification_success: Whether verification should succeed

    Returns:
        MagicMock: Mocked VerificationManager instance

    """
    mock = MagicMock()
    mock.verify_appimage.return_value = verification_success
    mock.set_appimage_path.return_value = None

    verifier_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.VerificationManager", verifier_class_mock)
    return mock


@pytest.fixture
def mocked_verifier_failure(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the VerificationManager class with verification failure.

    Args:
        monkeypatch: Pytest fixture for patching

    Returns:
        MagicMock: Mocked VerificationManager instance that fails verification

    """
    mock = MagicMock()
    mock.verify_appimage.return_value = False
    mock.set_appimage_path.return_value = None

    verifier_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.VerificationManager", verifier_class_mock)
    return mock


@pytest.fixture
def mocked_file_handler(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the FileHandler class.

    Args:
        monkeypatch: Pytest fixture for patching

    Returns:
        MagicMock: Mocked FileHandler instance

    """
    mock = MagicMock()
    mock.handle_appimage_operations.return_value = True

    file_handler_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.FileHandler", file_handler_class_mock)
    return mock


@pytest.fixture
def mocked_icon_manager(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the IconManager class.

    Args:
        monkeypatch: Pytest fixture for patching

    Returns:
        MagicMock: Mocked IconManager instance

    """
    mock = MagicMock()
    mock.ensure_app_icon.return_value = (True, "/tmp/icon.png")  # Success with icon path

    icon_manager_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.IconManager", icon_manager_class_mock)
    return mock


@pytest.fixture
def mocked_app_catalog_functions(
    monkeypatch: pytest.MonkeyPatch, app_info_fixture: AppInfo
) -> dict[str, MagicMock]:
    """Mock the app catalog functions.

    Args:
        monkeypatch: Pytest fixture for patching
        app_info_fixture: Sample app info

    Returns:
        tuple[str, MagicMock]: Dictionary of mocked functions

    """
    # Create mock functions for all app catalog functions
    mock_get_app_info = MagicMock(return_value=app_info_fixture)
    mock_get_all_apps = MagicMock(return_value=[app_info_fixture])
    mock_get_apps_by_category = MagicMock(return_value=[app_info_fixture])
    mock_search_apps = MagicMock(return_value=[app_info_fixture])
    mock_get_categories = MagicMock(return_value=["Test", "Productivity"])

    # Apply the mocks
    monkeypatch.setattr("my_unicorn.commands.install_catalog.get_app_info", mock_get_app_info)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.get_all_apps", mock_get_all_apps)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.get_apps_by_category", mock_get_apps_by_category)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.search_apps", mock_search_apps)
    monkeypatch.setattr("my_unicorn.commands.install_catalog.get_categories", mock_get_categories)

    # Return the mocks for inspection in tests
    return {
        "get_app_info": mock_get_app_info,
        "get_all_apps": mock_get_all_apps,
        "get_apps_by_category": mock_get_apps_by_category,
        "search_apps": mock_search_apps,
        "get_categories": mock_get_categories,
    }


@patch("builtins.input")
@patch("builtins.print")
def test_install_app_direct_install(
    mock_print: MagicMock,
    mock_input: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
    app_info_fixture: AppInfo,
) -> None:
    """Test direct app installation from catalog info.

    Args:
        mock_print: Mock for builtins.print
        mock_input: Mock for builtins.input
        mocked_app_config: Mocked AppConfigManager
        mocked_api: Mocked GitHubAPI
        mocked_download_manager: Mocked DownloadManager
        mocked_global_config: Mocked GlobalConfigManager
        mocked_verifier: Mocked VerificationManager
        mocked_file_handler: Mocked FileHandler
        mocked_icon_manager: Mocked IconManager
        app_info_fixture: Sample app info

    """
    # Setup mock inputs - installing directly bypassing menu
    mock_input.side_effect = ["y"]  # Confirm install

    # Create command and directly call the install method with app info
    cmd = InstallAppCommand()
    cmd._install_app(app_info_fixture)

    # Check correct flow - GitHub API initialized
    assert mocked_api.check_latest_version.called

    # App config updated correctly
    assert mocked_app_config.temp_save_config.called

    # File downloaded
    assert mocked_download_manager.download.called

    # Verification performed
    assert mocked_verifier.set_appimage_path.called
    assert mocked_verifier.verify_appimage.called

    # File operations completed
    assert mocked_file_handler.handle_appimage_operations.called

    # Config saved
    assert mocked_app_config.save_config.called

    # Icon downloaded
    assert mocked_icon_manager.ensure_app_icon.called


@patch("builtins.input")
@patch("builtins.print")
def test_install_app_skip_verification(
    mock_print: MagicMock,
    mock_input: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
    app_info_fixture: AppInfo,
) -> None:
    """Test app installation without SHA verification.

    Args:
        mock_print: Mock for builtins.print
        mock_input: Mock for builtins.input
        mocked_app_config: Mocked AppConfigManager
        mocked_api: Mocked GitHubAPI
        mocked_download_manager: Mocked DownloadManager
        mocked_global_config: Mocked GlobalConfigManager
        mocked_verifier: Mocked VerificationManager
        mocked_file_handler: Mocked FileHandler
        mocked_icon_manager: Mocked IconManager
        app_info_fixture: Sample app info

    """
    # Modify the app_info to skip verification
    app_info_fixture.skip_verification = True

    # set the API mock to skip verification as well
    mocked_api.skip_verification = True
    mocked_api.checksum_file_name = None
    mocked_api.checksum_hash_type = None

    # Setup mock inputs
    mock_input.side_effect = ["y"]  # Confirm install

    # Create command and directly call the install method with app info
    cmd = InstallAppCommand()
    cmd._install_app(app_info_fixture)

    # Verify that the verification was skipped
    mocked_verifier.verify_appimage.assert_not_called()

    # Other operations should still occur
    assert mocked_download_manager.download.called
    assert mocked_file_handler.handle_appimage_operations.called
    assert mocked_app_config.save_config.called


@patch("builtins.input")
@patch("builtins.print")
def test_install_app_verification_failure(
    mock_print: MagicMock,
    mock_input: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier_failure: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
    app_info_fixture: AppInfo,
) -> None:
    """Test behavior when verification fails during installation.

    Args:
        mock_print: Mock for builtins.print
        mock_input: Mock for builtins.input
        mocked_app_config: Mocked AppConfigManager
        mocked_api: Mocked GitHubAPI
        mocked_download_manager: Mocked DownloadManager
        mocked_global_config: Mocked GlobalConfigManager
        mocked_verifier_failure: Mocked VerificationManager that fails
        mocked_file_handler: Mocked FileHandler
        mocked_icon_manager: Mocked IconManager
        app_info_fixture: Sample app info

    """
    # Setup mock inputs
    mock_input.side_effect = ["y", "n"]  # Confirm install, don't retry

    # Create command and directly call the install method with app info
    cmd = InstallAppCommand()
    cmd._install_app(app_info_fixture)

    # Verification should be attempted but fail
    assert mocked_verifier_failure.verify_appimage.called

    # File operations and config saving should not occur after verification failure
    assert not mocked_file_handler.handle_appimage_operations.called
    assert not mocked_app_config.save_config.called


@patch("builtins.input")
@patch("builtins.print")
def test_install_app_api_failure(
    mock_print: MagicMock,
    mock_input: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
    app_info_fixture: AppInfo,
) -> None:
    """Test behavior when API call fails during installation.

    Args:
        mock_print: Mock for builtins.print
        mock_input: Mock for builtins.input
        mocked_app_config: Mocked AppConfigManager
        mocked_api: Mocked GitHubAPI
        mocked_download_manager: Mocked DownloadManager
        mocked_global_config: Mocked GlobalConfigManager
        mocked_verifier: Mocked VerificationManager
        mocked_file_handler: Mocked FileHandler
        mocked_icon_manager: Mocked IconManager
        app_info_fixture: Sample app info

    """
    # set API to fail with proper error response format
    mocked_api.check_latest_version.return_value = (False, {"error": "API Error"})

    # Setup mock inputs
    mock_input.side_effect = ["y"]  # Confirm install

    # Create command and directly call the install method with app info
    cmd = InstallAppCommand()
    cmd._install_app(app_info_fixture)

    # API call should occur but fail
    assert mocked_api.check_latest_version.called

    # Subsequent operations should not occur after API failure
    assert not mocked_download_manager.download.called
    assert not mocked_verifier.verify_appimage.called
    assert not mocked_file_handler.handle_appimage_operations.called
    assert not mocked_app_config.save_config.called
