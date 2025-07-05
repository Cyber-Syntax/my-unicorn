#!/usr/bin/env python3
"""Unit tests for the DeleteBackupsCommand class.

This module contains test cases for validating the functionality of backup
deletion operations including deleting all backups, app-specific backups,
old backups, and cleaning up according to maximum backup settings.
"""

import datetime
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.commands.delete_backups import DeleteBackupsCommand
from my_unicorn.global_config import GlobalConfigManager


@pytest.fixture
def mock_global_config() -> MagicMock:
    """Fixture providing a mocked GlobalConfigManager.

    Returns:
        MagicMock: A mock GlobalConfigManager with pre-configured test values.

    """
    mock_config = MagicMock(spec=GlobalConfigManager)
    mock_config.expanded_app_backup_storage_path = "/mock/backup/dir"
    mock_config.max_backups = 3
    return mock_config


@pytest.fixture
def delete_command() -> DeleteBackupsCommand:
    """Fixture providing a DeleteBackupsCommand instance for testing.

    Returns:
        DeleteBackupsCommand: An instance of the DeleteBackupsCommand class.

    """
    return DeleteBackupsCommand()


@pytest.fixture
def mock_file_operations() -> Generator[None, None, None]:
    """Fixture that mocks file operations to prevent actual file system changes.

    Yields:
        None: This fixture doesn't yield a value, it just sets up mocks.

    """
    with (
        patch("os.path.exists") as mock_exists,
        patch("os.listdir") as mock_listdir,
        patch("os.remove") as mock_remove,
        patch("os.path.isfile") as mock_isfile,
        patch("os.path.getmtime") as mock_getmtime,
        patch("logging.info") as mock_log_info,
        patch("logging.error") as mock_log_error,
        patch("logging.warning") as mock_log_warning,
    ):
        # set default return values
        mock_exists.return_value = True
        mock_isfile.return_value = True

        # Sample backup files
        mock_listdir.return_value = [
            "app1-1.0.0.appimage",
            "app1-2.0.0.appimage",
            "app1-3.0.0.appimage",
            "app1-4.0.0.appimage",
            "app2-1.0.0.appimage",
            "app2-2.0.0.appimage",
            "app3_20220101.appimage",
            "app3_20230101.appimage",
            "app4.appimage",
            "not_an_appimage.txt",
        ]

        yield


def test_execute_with_invalid_choice(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the execute method with an invalid choice input.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock GlobalConfigManager
    with patch("my_unicorn.commands.delete_backups.GlobalConfigManager", return_value=mock_global_config):
        # Mock user input
        monkeypatch.setattr("builtins.input", lambda _: "invalid")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the command
        delete_command.execute()

        # Assert the correct message was printed
        assert "Invalid choice. Returning to main menu..." in printed_messages


def test_execute_calls_correct_method(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that execute method calls the correct sub-method based on user input.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    with patch("my_unicorn.commands.delete_backups.GlobalConfigManager", return_value=mock_global_config):
        # Create mock methods
        delete_command._delete_all_backups = MagicMock()
        delete_command._delete_app_backups = MagicMock()
        delete_command._delete_old_backups = MagicMock()
        delete_command._cleanup_to_max_backups = MagicMock()

        # Test each choice
        for choice in ["1", "2", "3", "4", "5"]:
            # Reset mocks
            delete_command._delete_all_backups.reset_mock()
            delete_command._delete_app_backups.reset_mock()
            delete_command._delete_old_backups.reset_mock()
            delete_command._cleanup_to_max_backups.reset_mock()

            # Mock user input
            monkeypatch.setattr("builtins.input", lambda _: choice)

            # Mock print to avoid output
            monkeypatch.setattr("builtins.print", lambda *args: None)

            # Execute the command
            delete_command.execute()

            # Assert the correct method was called
            if choice == "1":
                assert delete_command._delete_all_backups.called
            elif choice == "2":
                assert delete_command._delete_app_backups.called
            elif choice == "3":
                assert delete_command._delete_old_backups.called
            elif choice == "4":
                assert delete_command._cleanup_to_max_backups.called
            # Choice 5 doesn't call any method, it just returns


def test_delete_all_backups_nonexistent_dir(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_all_backups with a non-existent backup directory.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path.exists to return False
    with patch("os.path.exists", return_value=False):
        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_all_backups(mock_global_config)

        # Assert the correct message was printed
        assert (
            f"Backup directory {mock_global_config.expanded_app_backup_storage_path} does not exist."
            in printed_messages
        )


def test_delete_all_backups_operation_cancelled(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mock_file_operations: None,
) -> None:
    """Test _delete_all_backups when user cancels the operation.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.
        mock_file_operations: Fixture that mocks file operations.

    """
    # Mock user input to cancel the operation
    monkeypatch.setattr("builtins.input", lambda _: "no")

    # Mock print to capture output
    printed_messages = []
    monkeypatch.setattr(
        "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
    )

    # Execute the method
    delete_command._delete_all_backups(mock_global_config)

    # Assert the correct message was printed
    assert "Operation cancelled." in printed_messages

    # Verify no files were deleted
    with patch("os.remove") as mock_remove:
        assert not mock_remove.called


def test_delete_all_backups_success(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful execution of _delete_all_backups.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path operations
    with (
        patch("os.path.exists", return_value=True),
        patch("os.listdir") as mock_listdir,
        patch("os.path.isfile", return_value=True),
        patch("os.remove") as mock_remove,
        patch("logging.info") as mock_log_info,
    ):
        # Sample backup files
        mock_files = ["app1-1.0.0.appimage", "app2-1.0.0.appimage", "not_an_appimage.txt"]
        mock_listdir.return_value = mock_files

        # Mock user input to confirm
        monkeypatch.setattr("builtins.input", lambda _: "yes")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_all_backups(mock_global_config)

        # Assert files were correctly removed
        assert mock_remove.call_count == 2  # Only .appimage files

        # Assert success message was printed
        assert any("Successfully deleted 2 backup files" in msg for msg in printed_messages)

        # Assert logging was called
        mock_log_info.assert_called_once()


def test_delete_all_backups_no_files(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_all_backups when no backup files are found.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path operations
    with (
        patch("os.path.exists", return_value=True),
        patch("os.listdir", return_value=["not_an_appimage.txt"]),
        patch("os.path.isfile", return_value=True),
        patch("os.remove") as mock_remove,
    ):
        # Mock user input to confirm
        monkeypatch.setattr("builtins.input", lambda _: "yes")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_all_backups(mock_global_config)

        # Assert no files were removed
        assert not mock_remove.called

        # Assert message was printed
        assert "No backup files found to delete." in printed_messages


def test_delete_app_backups_nonexistent_dir(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_app_backups with a non-existent backup directory.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path.exists to return False
    with patch("os.path.exists", return_value=False):
        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_app_backups(mock_global_config)

        # Assert the correct message was printed
        assert (
            f"Backup directory {mock_global_config.expanded_app_backup_storage_path} does not exist."
            in printed_messages
        )


def test_delete_app_backups_no_apps_found(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_app_backups when no app backups are found.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock _get_available_apps to return empty list
    with (
        patch.object(delete_command, "_get_available_apps", return_value=[]),
        patch("os.path.exists", return_value=True),
    ):
        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_app_backups(mock_global_config)

        # Assert the correct message was printed
        assert "No app backups found." in printed_messages


def test_delete_app_backups_invalid_selection(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_app_backups with an invalid app selection.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock _get_available_apps to return some apps
    with (
        patch.object(delete_command, "_get_available_apps", return_value=["app1", "app2"]),
        patch("os.path.exists", return_value=True),
    ):
        # Mock user input for invalid selection
        inputs = ["10"]  # Out of range
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0) if inputs else "")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_app_backups(mock_global_config)

        # Assert the correct message was printed
        assert "Invalid selection." in printed_messages


def test_delete_app_backups_cancelled(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_app_backups when user cancels the operation.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock _get_available_apps to return some apps
    with (
        patch.object(delete_command, "_get_available_apps", return_value=["app1", "app2"]),
        patch("os.path.exists", return_value=True),
        patch("os.remove") as mock_remove,
    ):
        # Mock user input to select app1 but cancel the operation
        inputs = ["1", "no"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0) if inputs else "")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_app_backups(mock_global_config)

        # Assert the correct message was printed
        assert "Operation cancelled." in printed_messages

        # Assert no files were removed
        assert not mock_remove.called


def test_delete_app_backups_success(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful execution of _delete_app_backups.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Sample backup files
    mock_files = [
        "app1-1.0.0.appimage",
        "app1-2.0.0.appimage",
        "app2-1.0.0.appimage",
        "not_an_appimage.txt",
    ]

    # Mock operations
    with (
        patch.object(delete_command, "_get_available_apps", return_value=["app1", "app2"]),
        patch("os.path.exists", return_value=True),
        patch("os.listdir", return_value=mock_files),
        patch("os.path.isfile", return_value=True),
        patch("os.remove") as mock_remove,
        patch("logging.info") as mock_log_info,
    ):
        # Mock user input to select app1 and confirm
        inputs = ["1", "yes"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0) if inputs else "")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_app_backups(mock_global_config)

        # Assert files were correctly removed
        assert mock_remove.call_count == 2  # Two app1 files

        # Assert success message was printed
        assert any(
            "Successfully deleted 2 backup files for app1" in msg for msg in printed_messages
        )

        # Assert logging was called
        mock_log_info.assert_called_once()


def test_delete_old_backups_nonexistent_dir(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_old_backups with a non-existent backup directory.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path.exists to return False
    with patch("os.path.exists", return_value=False):
        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_old_backups(mock_global_config)

        # Assert the correct message was printed
        assert (
            f"Backup directory {mock_global_config.expanded_app_backup_storage_path} does not exist."
            in printed_messages
        )


def test_delete_old_backups_invalid_choice(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_old_backups with an invalid choice.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path operations
    with patch("os.path.exists", return_value=True):
        # Mock user input for invalid selection
        monkeypatch.setattr("builtins.input", lambda _: "7")  # Invalid option

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_old_backups(mock_global_config)

        # Assert the correct message was printed
        assert "Invalid choice." in printed_messages


def test_delete_old_backups_predefined_date(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_old_backups with a predefined date option.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    today = datetime.datetime.now()
    week_ago = today - datetime.timedelta(days=7)

    # Mock datetime.now to return a fixed date for testing
    with (
        patch("datetime.datetime") as mock_datetime,
        patch("os.path.exists", return_value=True),
        patch("os.listdir") as mock_listdir,
        patch("os.path.isfile", return_value=True),
        patch("os.path.getmtime") as mock_getmtime,
        patch("os.remove") as mock_remove,
        patch("logging.info") as mock_log_info,
    ):
        # set up datetime mock
        mock_datetime.now.return_value = today
        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.strptime = datetime.datetime.strptime

        # Sample backup files
        mock_files = ["app1-1.0.0.appimage", "app1-2.0.0.appimage"]
        mock_listdir.return_value = mock_files

        # set up file modification times
        # First file is older than a week, second file is newer
        mock_getmtime.side_effect = [
            (week_ago - datetime.timedelta(days=1)).timestamp(),  # Older than a week
            (week_ago + datetime.timedelta(days=1)).timestamp(),  # Newer than a week
        ]

        # Mock user input to select 1 week and confirm
        inputs = ["1", "yes"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0) if inputs else "")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_old_backups(mock_global_config)

        # Assert only the older file was removed
        assert mock_remove.call_count == 1

        # Assert success message was printed
        assert any(
            "Successfully deleted 1 backup files older than 1 week" in msg
            for msg in printed_messages
        )

        # Assert logging was called
        mock_log_info.assert_called_once()


def test_delete_old_backups_custom_date(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _delete_old_backups with a custom date.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Create concrete timestamp values for testing
    old_timestamp = datetime.datetime(2022, 1, 1).timestamp()
    new_timestamp = datetime.datetime(2024, 1, 1).timestamp()
    cutoff_timestamp = datetime.datetime(2023, 1, 1).timestamp()

    # Mock datetime and file operations
    with (
        patch("datetime.datetime") as mock_datetime,
        patch("os.path.exists", return_value=True),
        patch("os.listdir") as mock_listdir,
        patch("os.path.isfile", return_value=True),
        patch("os.path.getmtime") as mock_getmtime,
        patch("os.remove") as mock_remove,
        patch("logging.info") as mock_log_info,
    ):
        # set up mock_datetime with real methods where needed
        mock_datetime.strptime.return_value = datetime.datetime(2023, 1, 1)
        mock_datetime.now.return_value = datetime.datetime(2023, 6, 1)

        # Important: set cutoff_timestamp explicitly rather than depending on MagicMock objects
        cutoff_date = mock_datetime.strptime.return_value
        # Make the cutoff_timestamp a concrete value
        mock_datetime.configure_mock(
            **{"strptime.return_value.timestamp.return_value": cutoff_timestamp}
        )

        # Sample backup files
        mock_files = ["app1-1.0.0.appimage", "app1-2.0.0.appimage"]
        mock_listdir.return_value = mock_files

        # set up file modification times with concrete values
        mock_getmtime.side_effect = [old_timestamp, new_timestamp]

        # Mock user input to select custom date and confirm
        inputs = ["6", "2023-01-01", "yes"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0) if inputs else "")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._delete_old_backups(mock_global_config)

        # Assert only the older file was removed
        assert mock_remove.call_count == 1

        # Assert success message was printed
        assert any(
            "Successfully deleted 1 backup files older than 2023-01-01" in msg
            for msg in printed_messages
        )


def test_cleanup_to_max_backups_nonexistent_dir(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _cleanup_to_max_backups with a non-existent backup directory.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path.exists to return False
    with patch("os.path.exists", return_value=False):
        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._cleanup_to_max_backups(mock_global_config)

        # Assert the correct message was printed
        assert (
            f"Backup directory {mock_global_config.expanded_app_backup_storage_path} does not exist."
            in printed_messages
        )


def test_cleanup_to_max_backups_cancelled(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _cleanup_to_max_backups when user cancels the operation.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path operations
    with patch("os.path.exists", return_value=True), patch("os.remove") as mock_remove:
        # Mock user input to cancel
        monkeypatch.setattr("builtins.input", lambda _: "no")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._cleanup_to_max_backups(mock_global_config)

        # Assert the correct message was printed
        assert "Operation cancelled." in printed_messages

        # Assert no files were removed
        assert not mock_remove.called


def test_cleanup_to_max_backups_no_apps(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _cleanup_to_max_backups when no app backups are found.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # Mock path operations and _get_available_apps
    with (
        patch("os.path.exists", return_value=True),
        patch.object(delete_command, "_get_available_apps", return_value=[]),
    ):
        # Mock user input to confirm
        monkeypatch.setattr("builtins.input", lambda _: "yes")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._cleanup_to_max_backups(mock_global_config)

        # Assert the correct message was printed
        assert "No app backups found." in printed_messages


def test_cleanup_to_max_backups_success(
    delete_command: DeleteBackupsCommand,
    mock_global_config: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful execution of _cleanup_to_max_backups.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.
        mock_global_config: Mocked configuration manager.
        monkeypatch: Pytest monkeypatch fixture for patching functions.

    """
    # set max_backups to 2 for this test
    mock_global_config.max_backups = 2

    # Sample file data
    app1_files = [
        ("app1-1.0.0.appimage", 1000),  # Oldest
        ("app1-2.0.0.appimage", 2000),
        ("app1-3.0.0.appimage", 3000),
        ("app1-4.0.0.appimage", 4000),  # Newest
    ]

    app2_files = [
        ("app2-1.0.0.appimage", 1500),  # Oldest
        ("app2-2.0.0.appimage", 2500),  # Newest
    ]

    all_files = [f[0] for f in app1_files + app2_files]

    # Mock operations
    with (
        patch("os.path.exists", return_value=True),
        patch.object(delete_command, "_get_available_apps", return_value=["app1", "app2"]),
        patch("os.listdir", return_value=all_files),
        patch("os.path.isfile", return_value=True),
        patch("os.path.getmtime") as mock_getmtime,
        patch("os.remove") as mock_remove,
        patch("logging.info") as mock_log_info,
    ):
        # Mock getmtime to return timestamps in order
        mock_getmtime.side_effect = lambda filepath: next(
            t for f, t in app1_files + app2_files if f in filepath
        )

        # Mock user input to confirm
        monkeypatch.setattr("builtins.input", lambda _: "yes")

        # Mock print to capture output
        printed_messages = []
        monkeypatch.setattr(
            "builtins.print", lambda *args: printed_messages.append(" ".join(map(str, args)))
        )

        # Execute the method
        delete_command._cleanup_to_max_backups(mock_global_config)

        # Assert files were correctly removed
        # app1 should have 2 older files removed, app2 should have none removed
        assert mock_remove.call_count == 2

        # Assert success message was printed
        assert any("Total: Removed 2 backup files" in msg for msg in printed_messages)


def test_get_available_apps(delete_command: DeleteBackupsCommand) -> None:
    """Test _get_available_apps method with various filename patterns.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.

    """
    # Test data with various filename patterns
    test_files = [
        "app1-1.0.0.appimage",  # Format: AppName-version
        "app1-2.0.0.appimage",
        "app2_20220101.appimage",  # Format: AppName_timestamp
        "app3.appimage",  # Format: AppName
        "something.txt",  # Not an AppImage
    ]

    # Mock operations
    with patch("os.listdir", return_value=test_files):
        apps = delete_command._get_available_apps("/mock/dir")

        # Assert apps were correctly extracted
        assert set(apps) == {"app1", "app2", "app3"}
        assert apps == sorted(apps)  # Should be sorted


def test_get_available_apps_error_handling(delete_command: DeleteBackupsCommand) -> None:
    """Test error handling in _get_available_apps method.

    Args:
        delete_command: The DeleteBackupsCommand instance to test.

    """
    # Mock operations to raise an error
    with (
        patch("os.listdir", side_effect=OSError("Test error")),
        patch("logging.error") as mock_log_error,
    ):
        apps = delete_command._get_available_apps("/mock/dir")

        # Assert empty list is returned and error is logged
        assert apps == []
        mock_log_error.assert_called_once()
