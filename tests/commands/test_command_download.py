#!/usr/bin/env python
"""Tests for DownloadCommand functionality.

This module contains tests for the DownloadCommand class, which handles
downloading AppImages from GitHub releases.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add the project root to sys.path using pathlib for better cross-platform compatibility
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import the modules directly to avoid import issues
from src.commands.install_url import DownloadCommand


@pytest.fixture
def download_test_data() -> tuple[str, str]:
    """Provide common test data for download command tests.

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
    }


@pytest.fixture
def mocked_parser(monkeypatch: pytest.MonkeyPatch, download_test_data: tuple[str, str]) -> MagicMock:
    """Mock the ParseURL class.

    Args:
        monkeypatch: Pytest fixture for patching
        download_test_data: Test data fixture

    Returns:
        MagicMock: Mocked ParseURL instance

    """
    mock = MagicMock()
    mock.owner = download_test_data["owner"]
    mock.repo = download_test_data["repo"]
    # Mock the ask_url method to avoid input() calls during tests
    mock.ask_url.return_value = None

    parser_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_url.ParseURL", parser_class_mock)
    return mock


@pytest.fixture
def mocked_app_config(
    monkeypatch: pytest.MonkeyPatch, download_test_data: tuple[str, str]
) -> MagicMock:
    """Mock the AppConfigManager class.

    Args:
        monkeypatch: Pytest fixture for patching
        download_test_data: Test data fixture

    Returns:
        MagicMock: Mocked AppConfigManager instance

    """
    mock = MagicMock()
    mock.ask_sha_hash.return_value = (
        download_test_data["checksum_file_name"],
        download_test_data["checksum_hash_type"],
    )
    mock.config_folder = "/tmp/config"
    mock.config_file_name = "test_config.json"

    app_config_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_url.AppConfigManager", app_config_class_mock)
    return mock


@pytest.fixture
def mocked_api(monkeypatch: pytest.MonkeyPatch, download_test_data: tuple[str, str]) -> MagicMock:
    """Mock the GitHubAPI class.

    Args:
        monkeypatch: Pytest fixture for patching
        download_test_data: Test data fixture

    Returns:
        MagicMock: Mocked GitHubAPI instance

    """
    mock = MagicMock()
    mock.owner = download_test_data["owner"]
    mock.repo = download_test_data["repo"]
    mock.version = download_test_data["version"]
    mock.appimage_name = download_test_data["appimage"]
    mock.checksum_file_name = download_test_data["checksum_file_name"]
    mock.checksum_file_download_url = download_test_data["checksum_file_download_url"]
    mock.checksum_hash_type = download_test_data["checksum_hash_type"]
    mock.arch_keyword = None
    mock.app_download_url = download_test_data["app_download_url"]

    api_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_url.GitHubAPI", api_class_mock)
    return mock


@pytest.fixture
def mocked_download_manager(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the DownloadManager class.

    Args:
        monkeypatch: Pytest fixture for patching

    Returns:
        MagicMock: Mocked DownloadManager instance

    """
    mock = MagicMock()
    mock.download.return_value = True

    download_manager_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_url.DownloadManager", download_manager_class_mock)
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
    monkeypatch.setattr("src.global_config.GlobalConfigManager", global_config_class_mock)
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

    verifier_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_url.VerificationManager", verifier_class_mock)
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

    verifier_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_url.VerificationManager", verifier_class_mock)
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
    monkeypatch.setattr("src.commands.install_url.FileHandler", file_handler_class_mock)
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

    icon_manager_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("src.commands.install_url.IconManager", icon_manager_class_mock)
    return mock


def test_download_command_success_flow(
    mocked_parser: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
) -> None:
    """Test successful execution flow of the download command.

    This test verifies that all expected components are called in the correct order
    when the download and verification succeed.

    Args:
        mocked_parser: Mocked ParseURL instance
        mocked_app_config: Mocked AppConfigManager instance
        mocked_api: Mocked GitHubAPI instance
        mocked_download_manager: Mocked DownloadManager instance
        mocked_global_config: Mocked GlobalConfigManager instance
        mocked_verifier: Mocked VerificationManager instance
        mocked_file_handler: Mocked FileHandler instance
        mocked_icon_manager: Mocked IconManager instance

    """
    # Create and execute the command
    cmd = DownloadCommand()
    cmd.execute()

    # Verify the expected flow of operations
    mocked_parser.ask_url.assert_called_once()
    mocked_api.get_response.assert_called_once()
    mocked_app_config.temp_save_config.assert_called_once()
    mocked_download_manager.download.assert_called_once()
    mocked_verifier.verify_appimage.assert_called_once()
    mocked_file_handler.handle_appimage_operations.assert_called_once()
    mocked_app_config.save_config.assert_called_once()


def test_download_command_verification_failure(
    mocked_parser: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier_failure: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test download command behavior when verification fails.

    This test verifies that the download process stops properly after
    verification failure, and file operations and config saving are not performed.

    Args:
        mocked_parser: Mocked ParseURL instance
        mocked_app_config: Mocked AppConfigManager instance
        mocked_api: Mocked GitHubAPI instance
        mocked_download_manager: Mocked DownloadManager instance
        mocked_global_config: Mocked GlobalConfigManager instance
        mocked_verifier_failure: Mocked VerificationManager instance that fails verification
        mocked_file_handler: Mocked FileHandler instance
        mocked_icon_manager: Mocked IconManager instance
        monkeypatch: Pytest fixture for patching functions

    """
    # Mock the input function to return 'n' (no retry)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    # Create and execute the command
    cmd = DownloadCommand()
    cmd.execute()

    # Verify that verification was attempted
    mocked_verifier_failure.verify_appimage.assert_called_once()

    # Verify that the flow stops after verification failure
    mocked_file_handler.handle_appimage_operations.assert_not_called()
    mocked_app_config.save_config.assert_not_called()


def test_download_command_skip_verification(
    mocked_parser: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
    download_test_data: tuple[str, str],
) -> None:
    """Test download command behavior when no SHA file is available.

    This test verifies that when no SHA file is available, verification is skipped
    and the flow continues to file operations.

    Args:
        mocked_parser: Mocked ParseURL instance
        mocked_app_config: Mocked AppConfigManager instance
        mocked_api: Mocked GitHubAPI instance
        mocked_download_manager: Mocked DownloadManager instance
        mocked_global_config: Mocked GlobalConfigManager instance
        mocked_verifier: Mocked VerificationManager instance
        mocked_file_handler: Mocked FileHandler instance
        mocked_icon_manager: Mocked IconManager instance
        download_test_data: Test data dictionary

    """
    # set skip_verification to trigger the skip verification path
    mocked_api.skip_verification = True
    mocked_api.checksum_file_name = None

    # Create and execute the command
    cmd = DownloadCommand()
    cmd.execute()

    # Verify that verification was not attempted
    mocked_verifier.verify_appimage.assert_not_called()

    # Verify that file operations and config saving still occur
    mocked_file_handler.handle_appimage_operations.assert_called_once()
    mocked_app_config.save_config.assert_called_once()
