#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for DownloadCommand functionality.

This module contains tests for the DownloadCommand class, which handles
downloading AppImages from GitHub releases.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

import pytest
from unittest.mock import MagicMock

# Add the project root to sys.path using pathlib for better cross-platform compatibility
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import the modules directly to avoid import issues
import src.commands.download
from src.commands.download import DownloadCommand
from src.api import GitHubAPI
from src.app_config import AppConfigManager
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.verify import VerificationManager
from src.parser import ParseURL
from src.global_config import GlobalConfigManager
from src.icon_manager import IconManager


@pytest.fixture
def download_test_data() -> Dict[str, str]:
    """Provide common test data for download command tests.

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
    }


@pytest.fixture
def mocked_parser(monkeypatch: pytest.MonkeyPatch, download_test_data: Dict[str, str]) -> MagicMock:
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

    parser_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("commands.download.ParseURL", parser_class_mock)
    return mock


@pytest.fixture
def mocked_app_config(
    monkeypatch: pytest.MonkeyPatch, download_test_data: Dict[str, str]
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
        download_test_data["sha_name"],
        download_test_data["hash_type"],
    )
    mock.config_folder = "/tmp/config"
    mock.config_file_name = "test_config.json"

    app_config_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("commands.download.AppConfigManager", app_config_class_mock)
    return mock


@pytest.fixture
def mocked_api(monkeypatch: pytest.MonkeyPatch, download_test_data: Dict[str, str]) -> MagicMock:
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
    mock.sha_name = download_test_data["sha_name"]
    mock.sha_url = download_test_data["sha_url"]
    mock.hash_type = download_test_data["hash_type"]
    mock.arch_keyword = None
    mock.appimage_url = download_test_data["appimage_url"]

    api_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("commands.download.GitHubAPI", api_class_mock)
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
    monkeypatch.setattr("commands.download.DownloadManager", download_manager_class_mock)
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

    global_config_class_mock = MagicMock(return_value=mock)
    monkeypatch.setattr("commands.download.GlobalConfigManager", global_config_class_mock)
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
    monkeypatch.setattr("commands.download.VerificationManager", verifier_class_mock)
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
    monkeypatch.setattr("commands.download.VerificationManager", verifier_class_mock)
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
    monkeypatch.setattr("commands.download.FileHandler", file_handler_class_mock)
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
    monkeypatch.setattr("commands.download.IconManager", icon_manager_class_mock)
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


def test_download_command_no_sha_file(
    mocked_parser: MagicMock,
    mocked_app_config: MagicMock,
    mocked_api: MagicMock,
    mocked_download_manager: MagicMock,
    mocked_global_config: MagicMock,
    mocked_verifier: MagicMock,
    mocked_file_handler: MagicMock,
    mocked_icon_manager: MagicMock,
    download_test_data: Dict[str, str],
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
    # Set sha_name to "no_sha_file" to trigger the skip verification path
    mocked_api.sha_name = "no_sha_file"

    # Create and execute the command
    cmd = DownloadCommand()
    cmd.execute()

    # Verify that verification was not attempted
    mocked_verifier.verify_appimage.assert_not_called()

    # Verify that file operations and config saving still occur
    mocked_file_handler.handle_appimage_operations.assert_called_once()
    mocked_app_config.save_config.assert_called_once()
