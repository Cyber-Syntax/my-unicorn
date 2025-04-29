#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for InstallAppCommand functionality.

This module contains tests for the InstallAppCommand class, which handles
installing AppImages from the app catalog.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List

import pytest
from unittest.mock import MagicMock, patch

# Add the project root to sys.path using pathlib for better cross-platform compatibility
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import the modules directly to avoid import issues
from src.commands.install_app import InstallAppCommand
from src.app_catalog import AppInfo
from src.api import GitHubAPI
from src.app_config import AppConfigManager
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.verify import VerificationManager
from src.global_config import GlobalConfigManager
from src.icon_manager import IconManager


@pytest.fixture
def app_info_fixture() -> AppInfo:
    """Provide a sample AppInfo object for testing.

    Returns:
        AppInfo: Sample application information
    """
    return AppInfo(
        name="Test App",
        description="A test application",
        owner="testowner",
        repo="testrepo",
        sha_name="test.sha256",
        hash_type="sha256",
        category="Test",
        tags=["test", "sample"],
    )


@pytest.fixture
def install_test_data() -> Dict[str, str]:
    """Provide common test data for install app command tests.

    Returns:
        Dict[str, str]: Dictionary containing test values
    """
    return {
        "owner": "testowner",
        "repo": "testrepo",
        "appimage": "test.AppImage",
        "version": "1.0.0",
        "sha_name": "test.sha256",
        "sha_url": "http://example.com/test.sha256",
        "appimage_url": "http://example.com/test.AppImage",
        "hash_type": "sha256",
        "downloaded_file_path": "/tmp/test.AppImage",
    }


@pytest.fixture
def mocked_app_config(
    monkeypatch: pytest.MonkeyPatch, install_test_data: Dict[str, str]
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
    mock.sha_name = install_test_data["sha_name"]
    mock.hash_type = install_test_data["hash_type"]
    mock.config_folder = "/tmp/config"
    mock.config_file = "/tmp/config/testrepo.json"
    mock.config_file_name = "testrepo.json"

    app_config_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_app.AppConfigManager", app_config_class_mock)
    return mock


@pytest.fixture
def mocked_api(monkeypatch: pytest.MonkeyPatch, install_test_data: Dict[str, str]) -> MagicMock:
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
    mock.sha_name = install_test_data["sha_name"]
    mock.sha_url = install_test_data["sha_url"]
    mock.hash_type = install_test_data["hash_type"]
    mock.arch_keyword = None
    mock.appimage_url = install_test_data["appimage_url"]
    mock.get_response.return_value = (True, "Success")  # Success response

    api_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_app.GitHubAPI", api_class_mock)
    return mock


@pytest.fixture
def mocked_download_manager(
    monkeypatch: pytest.MonkeyPatch, install_test_data: Dict[str, str]
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
    monkeypatch.setattr("src.commands.install_app.DownloadManager", download_manager_class_mock)
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
    mock.expanded_appimage_download_folder_path = "/tmp"
    mock.expanded_appimage_download_backup_folder_path = "/tmp/backup"
    mock.batch_mode = True
    mock.keep_backup = True
    mock.config_file = "/tmp/global_config.json"
    mock.max_backups = 3

    global_config_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_app.GlobalConfigManager", global_config_class_mock)
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
    monkeypatch.setattr("src.commands.install_app.VerificationManager", verifier_class_mock)
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
    monkeypatch.setattr("src.commands.install_app.VerificationManager", verifier_class_mock)
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
    monkeypatch.setattr("src.commands.install_app.FileHandler", file_handler_class_mock)
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
    mock.ensure_app_icon.return_value = None

    icon_manager_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_app.IconManager", icon_manager_class_mock)
    return mock


@pytest.fixture
def mocked_app_catalog_functions(
    monkeypatch: pytest.MonkeyPatch, app_info_fixture: AppInfo
) -> Dict[str, MagicMock]:
    """Mock the app catalog functions.

    Args:
        monkeypatch: Pytest fixture for patching
        app_info_fixture: Sample app info

    Returns:
        Dict[str, MagicMock]: Dictionary of mocked functions
    """
    # Create mock functions for all app catalog functions
    mock_get_app_info = MagicMock(return_value=app_info_fixture)
    mock_get_all_apps = MagicMock(return_value=[app_info_fixture])
    mock_get_apps_by_category = MagicMock(return_value=[app_info_fixture])
    mock_search_apps = MagicMock(return_value=[app_info_fixture])
    mock_get_categories = MagicMock(return_value=["Test", "Productivity"])

    # Apply the mocks
    monkeypatch.setattr("src.commands.install_app.get_app_info", mock_get_app_info)
    monkeypatch.setattr("src.commands.install_app.get_all_apps", mock_get_all_apps)
    monkeypatch.setattr("src.commands.install_app.get_apps_by_category", mock_get_apps_by_category)
    monkeypatch.setattr("src.commands.install_app.search_apps", mock_search_apps)
    monkeypatch.setattr("src.commands.install_app.get_categories", mock_get_categories)

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
    assert mocked_api.get_response.called

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
def test_install_app_no_sha_file(
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
    # Modify the app_info to have no SHA file
    app_info_fixture.sha_name = "no_sha_file"

    # Set the API mock to return no SHA file as well
    mocked_api.sha_name = "no_sha_file"

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
    # Set API to fail
    mocked_api.get_response.return_value = (False, "API Error")

    # Setup mock inputs
    mock_input.side_effect = ["y"]  # Confirm install

    # Create command and directly call the install method with app info
    cmd = InstallAppCommand()
    cmd._install_app(app_info_fixture)

    # API call should occur but fail
    assert mocked_api.get_response.called

    # Subsequent operations should not occur after API failure
    assert not mocked_download_manager.download.called
    assert not mocked_verifier.verify_appimage.called
    assert not mocked_file_handler.handle_appimage_operations.called
    assert not mocked_app_config.save_config.called


@patch("builtins.input")
@patch("builtins.print")
def test_install_app_menu_navigation(
    mock_print: MagicMock,
    mock_input: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_global_config: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_app_catalog_functions: Dict[str, MagicMock],
    app_info_fixture: AppInfo,
) -> None:
    """Test app catalog menu navigation in InstallAppCommand.

    Args:
        mock_print: Mock for builtins.print
        mock_input: Mock for builtins.input
        mocked_app_config: Mocked AppConfigManager
        mocked_api: Mocked GitHubAPI
        mocked_global_config: Mocked GlobalConfigManager
        mocked_file_handler: Mocked FileHandler
        mocked_app_catalog_functions: Mocked app catalog functions
        app_info_fixture: Sample app info
    """
    # Mock for _install_app method to avoid going through actual installation
    with patch.object(InstallAppCommand, "_install_app", return_value=None) as mock_install_app:
        # Test viewing all apps
        mock_input.side_effect = [
            "1",
            "1",
            "y",
            "4",
        ]  # View all, select first app, confirm, return to main

        cmd = InstallAppCommand()
        cmd.execute()

        # Check that get_all_apps was called
        assert mocked_app_catalog_functions["get_all_apps"].called

        # Check that _install_app was called with the correct app info
        mock_install_app.assert_called_once_with(app_info_fixture)

        # Reset mocks
        mock_install_app.reset_mock()
        mocked_app_catalog_functions["get_all_apps"].reset_mock()

        # Test category browsing
        mock_input.side_effect = [
            "2",
            "1",
            "1",
            "y",
            "4",
        ]  # Browse by category, select first category, select first app, confirm, return to main

        cmd = InstallAppCommand()
        cmd.execute()

        # Check that get_categories was called
        assert mocked_app_catalog_functions["get_categories"].called

        # Check that get_apps_by_category was called
        assert mocked_app_catalog_functions["get_apps_by_category"].called

        # Check that _install_app was called with the correct app info
        mock_install_app.assert_called_once_with(app_info_fixture)

        # Reset mocks
        mock_install_app.reset_mock()
        mocked_app_catalog_functions["get_categories"].reset_mock()
        mocked_app_catalog_functions["get_apps_by_category"].reset_mock()

        # Test search
        mock_input.side_effect = [
            "3",
            "test",
            "1",
            "y",
            "4",
        ]  # Search, query "test", select first result, confirm, return to main

        cmd = InstallAppCommand()
        cmd.execute()

        # Check that search_apps was called with the correct query
        mocked_app_catalog_functions["search_apps"].assert_called_once_with("test")

        # Check that _install_app was called with the correct app info
        mock_install_app.assert_called_once_with(app_info_fixture)

        # Test direct exit
        mock_input.side_effect = ["4"]  # Return to main menu

        cmd = InstallAppCommand()
        cmd.execute()

        # Check that no installation was attempted
        assert not mock_install_app.called
