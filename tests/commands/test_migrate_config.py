#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the migrate_config command module.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os

from src.commands.migrate_config import MigrateConfigCommand
from src.config_migrator import ConfigMigrator


class TestMigrateConfigCommand(unittest.TestCase):
    """Test cases for the MigrateConfigCommand class."""

    def setUp(self):
        """set up test fixtures."""
        self.config_path = os.path.expanduser("~/.config/myunicorn/settings.json")

        # Mock config data
        self.global_config_data = {"existing_key": "existing_value"}

        # Mock migration results
        self.success_migration_results = {
            "global_config": {"migrated": True, "keys_added": ["new_key1", "new_key2"]},
            "app_configs": {
                "migrated_count": 2,
                "details": {"app1": ["app_key1", "app_key2"], "app2": ["app_key3"]},
            },
        }

        self.no_changes_migration_results = {
            "global_config": {"migrated": False, "keys_added": []},
            "app_configs": {"migrated_count": 0, "details": {}},
        }

    @patch("src.commands.migrate_config.ConfigMigrator")
    @patch("src.commands.migrate_config.os.path.isfile")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    @patch("builtins.print")
    def test_execute_with_existing_config_and_migrations(
        self, mock_print, mock_json_load, mock_file, mock_isfile, mock_config_migrator
    ):
        """Test execute method with existing config file and migrations needed."""
        # Setup mocks
        mock_isfile.return_value = True
        mock_json_load.return_value = self.global_config_data
        mock_config_migrator.run_full_migration.return_value = self.success_migration_results

        # Create and execute the command
        cmd = MigrateConfigCommand()
        cmd.execute()

        # Verify mocks were called correctly
        mock_isfile.assert_called_once_with(self.config_path)
        mock_file.assert_called_once_with(self.config_path, "r", encoding="utf-8")
        mock_json_load.assert_called_once()
        mock_config_migrator.run_full_migration.assert_called_once()

        # Verify print messages indicating successful migration
        # The print arguments should include messages about updated configurations
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(
            any(
                "Global configuration updated with 2 new settings" in call
                for call in print_calls
                if isinstance(call, str)
            )
        )
        self.assertTrue(
            any(
                "Updated 2 application configuration files" in call
                for call in print_calls
                if isinstance(call, str)
            )
        )

    @patch("src.commands.migrate_config.ConfigMigrator")
    @patch("src.commands.migrate_config.os.path.isfile")
    @patch("builtins.print")
    def test_execute_with_nonexistent_config(self, mock_print, mock_isfile, mock_config_migrator):
        """Test execute method when config file doesn't exist yet."""
        # Setup mocks
        mock_isfile.return_value = False
        mock_config_migrator.run_full_migration.return_value = self.success_migration_results

        # Create and execute the command
        cmd = MigrateConfigCommand()
        cmd.execute()

        # Verify mocks were called correctly
        mock_isfile.assert_called_once_with(self.config_path)
        mock_config_migrator.run_full_migration.assert_called_once()

        # Verify print message indicating config doesn't exist
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(
            any(
                "Global config file does not exist yet" in call
                for call in print_calls
                if isinstance(call, str)
            )
        )

    @patch("src.commands.migrate_config.ConfigMigrator")
    @patch("src.commands.migrate_config.os.path.isfile")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    @patch("builtins.print")
    def test_execute_with_no_migrations_needed(
        self, mock_print, mock_json_load, mock_file, mock_isfile, mock_config_migrator
    ):
        """Test execute method when no migrations are needed."""
        # Setup mocks
        mock_isfile.return_value = True
        mock_json_load.return_value = self.global_config_data
        mock_config_migrator.run_full_migration.return_value = self.no_changes_migration_results

        # Create and execute the command
        cmd = MigrateConfigCommand()
        cmd.execute()

        # Verify mocks were called correctly
        mock_config_migrator.run_full_migration.assert_called_once()

        # Verify print messages indicating no migrations needed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(
            any(
                "Global configuration is up-to-date" in call
                for call in print_calls
                if isinstance(call, str)
            )
        )
        self.assertTrue(
            any(
                "All application configurations are up-to-date" in call
                for call in print_calls
                if isinstance(call, str)
            )
        )

    @patch("src.commands.migrate_config.ConfigMigrator")
    @patch("src.commands.migrate_config.os.path.isfile")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    @patch("builtins.print")
    def test_execute_with_config_read_error(
        self, mock_print, mock_json_load, mock_file, mock_isfile, mock_config_migrator
    ):
        """Test execute method when there's an error reading the config file."""
        # Setup mocks
        mock_isfile.return_value = True
        mock_json_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_config_migrator.run_full_migration.return_value = self.success_migration_results

        # Create and execute the command
        cmd = MigrateConfigCommand()
        cmd.execute()

        # Verify migration still runs even with config read error
        mock_config_migrator.run_full_migration.assert_called_once()

        # Verify error message is printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(
            any(
                "Error reading config file" in call for call in print_calls if isinstance(call, str)
            )
        )


if __name__ == "__main__":
    unittest.main()
