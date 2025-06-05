#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the update_all_auto command module.

This module contains tests for the UpdateAllAutoCommand class,
which handles automatic checking and updating of all AppImages.
"""

import os
import sys
import io
import asyncio
from typing import Any
from unittest.mock import patch, MagicMock, call, PropertyMock

import pytest
import pytest_asyncio

from src.commands.update_all_auto import UpdateAllAutoCommand
from src.auth_manager import GitHubAuthManager
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager


class TestUpdateAllAutoCommand:
    """Test suite for the UpdateAllAutoCommand class."""

    @pytest.fixture
    def command(self) -> UpdateAllAutoCommand:
        """Create an instance of UpdateAllAutoCommand for testing.

        Returns:
            UpdateAllAutoCommand: An instance of the command class
        """
        cmd = UpdateAllAutoCommand()
        # Setup basic mocks for command dependencies
        cmd.app_config = MagicMock(spec=AppConfigManager)
        cmd.global_config = MagicMock(spec=GlobalConfigManager)
        cmd.global_config.batch_mode = False
        return cmd

    @pytest_asyncio.fixture
    async def event_loop(self) -> asyncio.AbstractEventLoop:
        """Create and yield an event loop for asyncio tests.

        Returns:
            asyncio.AbstractEventLoop: An event loop for testing async functions
        """
        loop = asyncio.get_event_loop_policy().new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture
    def mock_app_config(self) -> MagicMock:
        """Create a mock AppConfigManager.

        Returns:
            MagicMock: Mock object for AppConfigManager
        """
        mock = MagicMock(spec=AppConfigManager)
        mock.list_json_files.return_value = ["app1.json", "app2.json", "app3.json"]
        return mock

    @pytest.fixture
    def mock_global_config(self) -> MagicMock:
        """Create a mock GlobalConfigManager.

        Returns:
            MagicMock: Mock object for GlobalConfigManager
        """
        mock = MagicMock(spec=GlobalConfigManager)
        mock.batch_mode = False
        return mock

    @pytest.fixture
    def updatable_apps(self) -> list[tuple[str, Any]]:
        """Create sample data for updatable apps.

        Returns:
            list[tuple[str, Any]]: list of updatable app information dictionaries
        """
        return [
            {
                "config_file": "app1.json",
                "name": "app1",
                "current": "1.0.0",
                "latest": "2.0.0",
                "repository": "owner/app1",  # Add repository information
                "repo_owner": "owner",  # Add owner information
                "repo_name": "app1",  # Add repo name information
            },
            {
                "config_file": "app2.json",
                "name": "app2",
                "current": "3.1.2",
                "latest": "3.2.0",
                "repository": "owner/app2",  # Add repository information
                "repo_owner": "owner",  # Add owner information
                "repo_name": "app2",  # Add repo name information
            },
        ]

    @pytest.fixture
    def mock_rate_limit_info(self) -> tuple:
        """Mock data for GitHub API rate limit information.

        Returns:
            tuple: (remaining, limit, reset_time, is_authenticated)
        """
        return (100, 5000, "2025-04-27 10:00:00", True)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_execute_no_config_files(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
    ) -> None:
        """Test execute method when no AppImage configuration files exist.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        mock_auth_manager.get_rate_limit_info.return_value = (
            100,
            5000,
            "2025-04-27 10:00:00",
            True,
        )
        command._list_all_config_files = MagicMock(return_value=[])

        # Execute
        command.execute()

        # Verify
        output = mock_stdout.getvalue()
        assert "No AppImage configuration files found" in output
        assert "Use the Download option first" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_execute_insufficient_rate_limits(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
    ) -> None:
        """Test execute method when there are insufficient GitHub API rate limits.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        command._list_all_config_files = MagicMock(
            return_value=["app1.json", "app2.json", "app3.json"]
        )
        # set rate limit to be lower than needed
        mock_auth_manager.get_rate_limit_info.return_value = (2, 5000, "2025-04-27 10:00:00", True)

        # Execute
        command.execute()

        # Verify
        output = mock_stdout.getvalue()
        assert "Not enough API requests available" in output
        assert "GitHub API Rate Limit Warning" in output
        assert "Minimum requests required: 3" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_execute_all_up_to_date(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
    ) -> None:
        """Test execute method when all apps are up to date.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        mock_auth_manager.get_rate_limit_info.return_value = (
            100,
            5000,
            "2025-04-27 10:00:00",
            True,
        )
        command._list_all_config_files = MagicMock(return_value=["app1.json", "app2.json"])
        command._find_all_updatable_apps = MagicMock(return_value=[])

        # Execute
        command.execute()

        # Verify
        output = mock_stdout.getvalue()
        assert "All AppImages are up to date" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_execute_batch_mode_updates(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test execute method in batch mode with updates available.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Setup
        mock_auth_manager.get_rate_limit_info.return_value = (
            100,
            5000,
            "2025-04-27 10:00:00",
            True,
        )
        command._list_all_config_files = MagicMock(return_value=["app1.json", "app2.json"])
        command._find_all_updatable_apps = MagicMock(return_value=updatable_apps)
        command._display_update_list = MagicMock()
        command._update_apps_async_wrapper = MagicMock()
        # set batch mode to True
        command.global_config.batch_mode = True

        # Execute
        command.execute()

        # Verify
        command._update_apps_async_wrapper.assert_called_once_with(updatable_apps)
        output = mock_stdout.getvalue()
        assert "Batch mode enabled" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_execute_interactive_mode(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test execute method in interactive mode with updates available.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Setup
        mock_auth_manager.get_rate_limit_info.return_value = (
            100,
            5000,
            "2025-04-27 10:00:00",
            True,
        )
        command._list_all_config_files = MagicMock(return_value=["app1.json", "app2.json"])
        command._find_all_updatable_apps = MagicMock(return_value=updatable_apps)
        command._display_update_list = MagicMock()
        command._handle_interactive_update = MagicMock()
        # set batch mode to False
        command.global_config.batch_mode = False

        # Execute
        command.execute()

        # Verify
        command._handle_interactive_update.assert_called_once_with(updatable_apps, True)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_execute_keyboard_interrupt(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
    ) -> None:
        """Test execute method when interrupted by KeyboardInterrupt.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        mock_auth_manager.get_rate_limit_info.return_value = (
            100,
            5000,
            "2025-04-27 10:00:00",
            True,
        )
        command._list_all_config_files = MagicMock(return_value=["app1.json", "app2.json"])
        command._find_all_updatable_apps = MagicMock(side_effect=KeyboardInterrupt)

        # Execute
        command.execute()

        # Verify
        output = mock_stdout.getvalue()
        assert "Operation cancelled by user (Ctrl+C)" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_find_all_updatable_apps(
        self, mock_stdout: io.StringIO, command: UpdateAllAutoCommand
    ) -> None:
        """Test _find_all_updatable_apps method to find apps with updates available.

        Args:
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        app_data = {"name": "app1", "current": "1.0.0", "latest": "2.0.0"}

        command._list_all_config_files = MagicMock(return_value=["app1.json"])
        command._check_single_app_version = MagicMock(return_value=app_data)

        # Execute
        result = command._find_all_updatable_apps()

        # Verify
        assert len(result) == 1
        assert result[0]["name"] == "app1"
        assert result[0]["current"] == "1.0.0"
        assert result[0]["latest"] == "2.0.0"
        output = mock_stdout.getvalue()
        assert "app1: update available: 1.0.0 → 2.0.0" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_find_all_updatable_apps_no_configs(
        self, mock_stdout: io.StringIO, command: UpdateAllAutoCommand
    ) -> None:
        """Test _find_all_updatable_apps when no config files exist.

        Args:
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        command._list_all_config_files = MagicMock(return_value=[])

        # Execute
        result = command._find_all_updatable_apps()

        # Verify
        assert len(result) == 0
        output = mock_stdout.getvalue()
        assert "No AppImage configuration files found" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_find_all_updatable_apps_error(
        self, mock_stdout: io.StringIO, command: UpdateAllAutoCommand
    ) -> None:
        """Test _find_all_updatable_apps handling errors during check.

        Args:
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        command._list_all_config_files = MagicMock(return_value=["app1.json"])
        command._check_single_app_version = MagicMock(side_effect=Exception("API error"))

        # Execute
        result = command._find_all_updatable_apps()

        # Verify
        assert len(result) == 0
        output = mock_stdout.getvalue()
        assert "error: API error" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("builtins.input", return_value="cancel")
    def test_handle_interactive_update_cancel(
        self,
        mock_input: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test _handle_interactive_update when user cancels.

        Args:
            mock_input: Mocked input function
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Execute
        command._handle_interactive_update(updatable_apps)

        # Verify
        mock_input.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Update cancelled" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("builtins.input", return_value="all")
    def test_handle_interactive_update_all(
        self,
        mock_input: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test _handle_interactive_update when user selects all apps.

        Args:
            mock_input: Mocked input function
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Setup
        # Create a mock for update_apps_async_wrapper
        command._update_apps_async_wrapper = MagicMock()
        command._update_apps = MagicMock()

        # Execute
        command._handle_interactive_update(updatable_apps)

        # Verify
        mock_input.assert_called_once()
        if command._update_apps_async_wrapper.call_count > 0:
            command._update_apps_async_wrapper.assert_called_once_with(updatable_apps)
        else:
            command._update_apps.assert_called_once_with(updatable_apps)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("builtins.input", return_value="1")
    def test_handle_interactive_update_specific(
        self,
        mock_input: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test _handle_interactive_update when user selects specific apps.

        Args:
            mock_input: Mocked input function
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Setup
        command._update_apps_async_wrapper = MagicMock()
        command._update_apps = MagicMock()

        # Execute
        command._handle_interactive_update(updatable_apps)

        # Verify
        mock_input.assert_called_once()
        # Check that one of the update methods was called
        if command._update_apps_async_wrapper.call_count > 0:
            command._update_apps_async_wrapper.assert_called_once()
            # Verify that only the first app was passed
            selected_apps = command._update_apps_async_wrapper.call_args[0][0]
            assert len(selected_apps) == 1
            assert selected_apps[0] == updatable_apps[0]
        else:
            command._update_apps.assert_called_once()
            # Verify that only the first app was passed
            selected_apps = command._update_apps.call_args[0][0]
            assert len(selected_apps) == 1
            assert selected_apps[0] == updatable_apps[0]

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("builtins.input", return_value="invalid")
    def test_handle_interactive_update_invalid_input(
        self,
        mock_input: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test _handle_interactive_update with invalid user input.

        Args:
            mock_input: Mocked input function
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Execute
        command._handle_interactive_update(updatable_apps)

        # Verify
        mock_input.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Invalid input" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("builtins.input", return_value="99")
    def test_handle_interactive_update_invalid_indices(
        self,
        mock_input: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test _handle_interactive_update with out-of-range indices.

        Args:
            mock_input: Mocked input function
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Execute
        command._handle_interactive_update(updatable_apps)

        # Verify
        mock_input.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Invalid selection" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_update_apps_async_wrapper(
        self,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test _update_apps_async_wrapper for async updates.

        Args:
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Setup
        mock_loop = MagicMock()

        success_count = 1
        failure_count = 1
        # Results should be a dictionary keyed by app names, not a list
        results = {
            "app1": {"status": "success", "message": "Updated", "elapsed": 1.5},
            "app2": {"status": "failed", "message": "Failed", "elapsed": 0.5},
        }

        # Mock the asyncio event loop and run_until_complete
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            mock_loop.run_until_complete.return_value = (success_count, failure_count, results)
            command._display_rate_limit_info = MagicMock()

            # Execute the method under test
            command._update_apps_async_wrapper(updatable_apps)

        # Verify
        mock_loop.run_until_complete.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Starting asynchronous update" in output or "asynchronous update" in output
        assert "Update Summary" in output
        assert "Successfully updated: 1" in output
        assert "Failed updates: 1" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_display_update_list(
        self,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        updatable_apps: list[tuple[str, Any]],
    ) -> None:
        """Test _display_update_list method shows apps correctly.

        Args:
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            updatable_apps: Sample updatable apps data
        """
        # Execute
        command._display_update_list(updatable_apps)

        # Verify
        output = mock_stdout.getvalue()
        assert f"Found {len(updatable_apps)} apps to update" in output
        assert "app1" in output
        assert "1.0.0" in output
        assert "2.0.0" in output
        assert "app2" in output
        assert "3.1.2" in output
        assert "3.2.0" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_display_rate_limit_info(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
        mock_rate_limit_info: tuple,
    ) -> None:
        """Test _display_rate_limit_info shows rate limit info.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
            mock_rate_limit_info: Mock rate limit data
        """
        # Setup
        mock_auth_manager.get_rate_limit_info.return_value = mock_rate_limit_info

        # Execute
        command._display_rate_limit_info()

        # Verify
        output = mock_stdout.getvalue()
        assert "GitHub API Rate Limits" in output
        assert "Remaining requests: 100/5000" in output
        assert "Resets at: 2025-04-27 10:00:00" in output

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("src.commands.update_all_auto.GitHubAuthManager")
    def test_display_rate_limit_info_low_requests(
        self,
        mock_auth_manager: MagicMock,
        mock_stdout: io.StringIO,
        command: UpdateAllAutoCommand,
    ) -> None:
        """Test _display_rate_limit_info shows warning when low on requests.

        Args:
            mock_auth_manager: Mocked GitHubAuthManager
            mock_stdout: Captured stdout
            command: Instance of UpdateAllAutoCommand
        """
        # Setup
        mock_auth_manager.get_rate_limit_info.return_value = (50, 5000, "2025-04-27 10:00:00", True)

        # Execute
        command._display_rate_limit_info()

        # Verify
        output = mock_stdout.getvalue()
        assert "GitHub API Rate Limits" in output
        assert "Remaining requests: 50/5000" in output
        assert "Running low on API requests!" in output
