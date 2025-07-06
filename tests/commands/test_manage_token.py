#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the manage_token command module.

This module contains tests for the ManageTokenCommand class that handles
GitHub token management through a command-line interface.
"""

import os
import builtins
import pytest
from unittest.mock import patch, MagicMock, call, mock_open
from datetime import datetime, timedelta
import json
import logging

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture

# Import the module to test
from my_unicorn.commands.manage_token import ManageTokenCommand
from my_unicorn.secure_token import SecureTokenManager
from my_unicorn.auth_manager import GitHubAuthManager

# Disable logging during tests to prevent token exposure
logging.getLogger("my_unicorn.commands.manage_token").setLevel(logging.CRITICAL)
logging.getLogger("my_unicorn.secure_token").setLevel(logging.CRITICAL)
logging.getLogger("my_unicorn.auth_manager").setLevel(logging.CRITICAL)

# Safe mock token value used throughout tests
SAFE_MOCK_TOKEN = "ghp_mocktokenfortesting123456789abcdefghijklmnopq"


class TestManageTokenCommand:
    """Tests for the ManageTokenCommand class."""

    @pytest.fixture(autouse=True)
    def prevent_real_token_access(self, monkeypatch):
        """
        Prevent any potential access to real tokens during tests.

        This fixture runs automatically for all tests in this class.
        """
        # Ensure environment variables can't leak tokens
        monkeypatch.setenv("GITHUB_TOKEN", "")
        # Prevent any system keyring access
        monkeypatch.setattr("keyring.get_password", lambda *args: None)
        # Prevent any real file access for token files
        monkeypatch.setattr("os.path.expanduser", lambda path: "/tmp/fake_home" + path[1:])
        return None

    @pytest.fixture
    def command(self):
        """Create a command instance for testing."""
        return ManageTokenCommand()

    @pytest.fixture
    def mock_secure_token_manager(self, monkeypatch):
        """Mock SecureTokenManager for testing."""
        mock_manager = MagicMock()
        # Default returns for common methods
        mock_manager.token_exists.return_value = True
        mock_manager.get_token.return_value = SAFE_MOCK_TOKEN
        mock_manager.get_token_metadata.return_value = {
            "created_at": datetime.now().timestamp(),
            "expires_at": (datetime.now() + timedelta(days=30)).timestamp(),
            "last_used_at": datetime.now().timestamp(),
            "storage_method": "Encrypted file",
        }
        mock_manager.is_token_expired.return_value = False
        mock_manager.get_token_expiration_info.return_value = (False, "2099-12-31 23:59:59")
        mock_manager.prompt_for_token.return_value = SAFE_MOCK_TOKEN
        mock_manager.save_token.return_value = True
        mock_manager.remove_token.return_value = True
        mock_manager.get_keyring_status.return_value = {
            "keyring_module_installed": True,
            "any_keyring_available": True,
            "gnome_keyring_available": True,
            "kde_wallet_available": False,
            "crypto_available": True,
        }
        mock_manager.get_audit_logs.return_value = [
            {
                "timestamp": datetime.now().isoformat(),
                "action": "test_action",
                "source_ip": "127.0.0.1",
            }
        ]

        monkeypatch.setattr("my_unicorn.commands.manage_token.SecureTokenManager", mock_manager)
        return mock_manager

    @pytest.fixture
    def mock_auth_manager(self, monkeypatch):
        """Mock GitHubAuthManager for testing."""
        mock_manager = MagicMock()
        # Default returns for common methods
        mock_manager.get_token_info.return_value = {
            "token_exists": True,
            "token_valid": True,
            "is_expired": False,
            "expiration_date": "2099-12-31 23:59:59",
            "days_until_rotation": 60,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_used_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        mock_manager.get_live_rate_limit_info.return_value = {
            "remaining": 4990,
            "limit": 5000,
            "reset": int(datetime.now().timestamp()) + 3600,
            "reset_formatted": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "is_authenticated": True,
            "resources": {
                "core": {
                    "limit": 5000,
                    "remaining": 4990,
                    "reset": int(datetime.now().timestamp()) + 3600,
                },
                "search": {
                    "limit": 30,
                    "remaining": 28,
                    "reset": int(datetime.now().timestamp()) + 3600,
                },
            },
        }
        mock_manager.validate_token.return_value = (
            True,
            {
                "is_valid": True,
                "scopes": ["repo", "user"],
                "rate_limit": 5000,
                "token_type": "Fine-Grained Token",
                "is_fine_grained": True,
            },
        )

        monkeypatch.setattr("my_unicorn.commands.manage_token.GitHubAuthManager", mock_manager)
        return mock_manager

    @patch("builtins.print")
    @patch(
        "builtins.input", side_effect=["1", "8"]
    )  # First choose option 1, then exit with option 8
    def test_execute_menu_and_exit(
        self, mock_input, mock_print, command, mock_secure_token_manager
    ):
        """Test executing the command and navigating the menu."""
        # Setup
        with patch.object(command, "_save_to_keyring") as mock_save_to_keyring:
            # Execute
            command.execute()

            # Verify
            mock_save_to_keyring.assert_called_once()
            # Check that menu was printed
            mock_print.assert_any_call("\nGitHub Token Management:")

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["1"])  # Token expiration choice
    def test_get_token_expiration_days(self, mock_input, mock_print, command):
        """Test getting token expiration days."""
        # Execute
        result = command._get_token_expiration_days()

        # Verify
        assert result == 30  # Should return 30 days for choice 1
        mock_input.assert_called_once()

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["5", "45"])  # Custom period
    def test_get_token_expiration_days_custom(self, mock_input, mock_print, command):
        """Test getting custom token expiration days."""
        # Execute
        result = command._get_token_expiration_days()

        # Verify
        assert result == 45  # Should return custom 45 days
        assert mock_input.call_count == 2

    @patch("builtins.print")
    @patch("builtins.input", return_value=SAFE_MOCK_TOKEN)
    def test_validate_token_valid(self, mock_input, mock_print, command, mock_auth_manager):
        """Test validating a valid token."""
        # Execute
        result = command._validate_token(SAFE_MOCK_TOKEN)

        # Verify
        assert result is True
        mock_auth_manager.validate_token.assert_called_once()
        # Should print success message
        mock_print.assert_any_call(" ✅ Valid!")

    @patch("builtins.print")
    @patch("builtins.input", return_value="bad_token")
    def test_validate_token_invalid(self, mock_input, mock_print, command, mock_auth_manager):
        """Test validating an invalid token."""
        # Setup
        mock_auth_manager.validate_token.return_value = (
            False,
            {"is_valid": False, "error": "Invalid token"},
        )

        # Execute
        result = command._validate_token("bad_token")

        # Verify
        assert result is False
        mock_auth_manager.validate_token.assert_called_once()
        # Should print failure message
        mock_print.assert_any_call(" ❌ Invalid!")

    @patch("builtins.print")
    def test_view_token_expiration(self, mock_print, command, mock_secure_token_manager):
        """Test viewing token expiration information."""
        # Execute
        command._view_token_expiration()

        # Verify
        mock_secure_token_manager.get_token_metadata.assert_called_once()
        # Should print expiration information
        mock_print.assert_any_call("\n--- Token Expiration Information ---")

    @patch("builtins.print")
    def test_view_token_expiration_no_token(self, mock_print, command, mock_secure_token_manager):
        """Test viewing token expiration when no token exists."""
        # Setup
        mock_secure_token_manager.token_exists.return_value = False

        # Execute
        command._view_token_expiration()

        # Verify
        mock_secure_token_manager.get_token_metadata.assert_not_called()
        # Should print no token message
        mock_print.assert_any_call("\n❌ No token configured")

    @patch("builtins.print")
    def test_view_audit_logs(self, mock_print, command, mock_secure_token_manager):
        """Test viewing audit logs."""
        # Execute
        command._view_audit_logs()

        # Verify
        mock_secure_token_manager.get_audit_logs.assert_called_once()
        # Should print audit log header
        mock_print.assert_any_call("\n--- Token Usage Audit Logs ---")

    @patch("builtins.print")
    def test_view_audit_logs_no_logs(self, mock_print, command, mock_secure_token_manager):
        """Test viewing audit logs when no logs exist."""
        # Setup
        mock_secure_token_manager.get_audit_logs.return_value = []

        # Execute
        command._view_audit_logs()

        # Verify
        mock_secure_token_manager.get_audit_logs.assert_called_once()
        # Should print no logs message
        mock_print.assert_any_call("\n❓ No audit logs available")

    @patch("builtins.print")
    @patch("builtins.input", return_value="y")  # Confirm removal
    def test_remove_token(
        self, mock_input, mock_print, command, mock_secure_token_manager, mock_auth_manager
    ):
        """Test removing a token."""
        # Execute
        command._remove_token()

        # Verify
        mock_secure_token_manager.remove_token.assert_called_once()
        mock_auth_manager.clear_cached_headers.assert_called_once()
        # Should print success message
        mock_print.assert_any_call("\n✅ GitHub token removed successfully")

    @patch("builtins.print")
    @patch("builtins.input", return_value="n")  # Cancel removal
    def test_remove_token_cancelled(
        self, mock_input, mock_print, command, mock_secure_token_manager
    ):
        """Test cancelling token removal."""
        # Execute
        command._remove_token()

        # Verify
        mock_secure_token_manager.remove_token.assert_not_called()
        # Should print cancellation message
        mock_print.assert_any_call("Token removal cancelled.")

    @patch("builtins.print")
    def test_check_rate_limits(self, mock_print, command, mock_auth_manager):
        """Test checking rate limits."""
        # Execute
        command._check_rate_limits()

        # Verify
        mock_auth_manager.get_live_rate_limit_info.assert_called_once()
        # Should print rate limit header
        mock_print.assert_any_call("\n--- GitHub API Rate Limits ---")

    @patch("builtins.print")
    def test_check_rate_limits_with_token(self, mock_print, command, mock_auth_manager):
        """Test checking rate limits with a specific token."""
        # Execute
        command._check_rate_limits(SAFE_MOCK_TOKEN)

        # Verify
        # Should create custom headers with the token
        mock_auth_manager.get_live_rate_limit_info.assert_called_once()
        headers = mock_auth_manager.get_live_rate_limit_info.call_args[1]["custom_headers"]
        assert headers["Authorization"] == f"Bearer {SAFE_MOCK_TOKEN}"

        # Ensure no real tokens are accidentally used even in test failures
        with pytest.raises(AssertionError):
            real_looking_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
            assert headers["Authorization"] == f"Bearer {real_looking_token}"

    @patch("builtins.print")
    @patch(
        "builtins.input", side_effect=["y", "n"]
    )  # Yes to update token, No to additional prompts
    def test_add_update_token(
        self, mock_input, mock_print, command, mock_secure_token_manager, mock_auth_manager
    ):
        """Test adding/updating a token."""
        # The test is for updating an existing token
        with patch.object(command, "_get_token_expiration_days", return_value=30) as mock_get_days:
            # Execute
            command._save_to_keyring()

            # Verify
            mock_secure_token_manager.get_token.assert_called_once()
            mock_get_days.assert_called_once()

            # Verify save_token was called with the right parameters
            mock_secure_token_manager.save_token.assert_called_once()
            call_args = mock_secure_token_manager.save_token.call_args
            assert call_args[0][0] == SAFE_MOCK_TOKEN  # First positional arg is the token
            assert call_args[1]["expires_in_days"] == 30  # Check expires_in_days kwarg
            assert call_args[1]["storage_preference"] == "keyring_only"  # Check storage preference

            mock_auth_manager.clear_cached_headers.assert_called_once()

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["y"])  # Yes to using keyring
    def test_add_update_token_gnome_keyring(
        self, mock_input, mock_print, command, mock_secure_token_manager, mock_auth_manager
    ):
        """Test adding token to GNOME keyring."""
        # Setup
        with (
            patch.object(command, "_get_token_expiration_days", return_value=30) as mock_get_days,
            patch.object(command, "_validate_token", return_value=True) as mock_validate,
        ):
            # Execute
            command._save_to_keyring()

            # Verify
            mock_secure_token_manager.get_token.assert_called_once()
            mock_get_days.assert_called_once()
            mock_secure_token_manager.get_keyring_status.assert_called_once()
            mock_secure_token_manager.save_token.assert_called_once_with(
                SAFE_MOCK_TOKEN,
                expires_in_days=30,
                storage_preference="keyring_only",
                metadata=mock_secure_token_manager.save_token.call_args[1].get("metadata"),
            )
            mock_auth_manager.clear_cached_headers.assert_called_once()

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["y"])  # Say yes to storing in keyring
    def test_save_to_keyring(
        self, mock_input, mock_print, command, mock_secure_token_manager, mock_auth_manager
    ):
        """Test saving token to keyring."""
        # Setup - Getting existing token
        with patch.object(command, "_get_token_expiration_days", return_value=30) as mock_get_days:
            # Execute
            command._save_to_keyring()

            # Verify
            mock_secure_token_manager.get_token.assert_called_once()
            mock_secure_token_manager.get_keyring_status.assert_called_once()
            mock_get_days.assert_called_once()
            mock_secure_token_manager.save_token.assert_called_once_with(
                SAFE_MOCK_TOKEN,
                expires_in_days=30,
                storage_preference="keyring_only",
                metadata=mock_secure_token_manager.save_token.call_args[1].get("metadata"),
            )
            mock_auth_manager.clear_cached_headers.assert_called_once()

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["y"])  # Confirm rotation
    def test_rotate_token(
        self, mock_input, mock_print, command, mock_secure_token_manager, mock_auth_manager
    ):
        """Test rotating a token."""
        # Setup
        with patch.object(command, "_get_token_expiration_days", return_value=30) as mock_get_days:
            with patch.object(command, "_validate_token", return_value=True) as mock_validate:
                # Execute
                command._rotate_token()

                # Verify
                mock_secure_token_manager.get_token_metadata.assert_called_once()
                mock_secure_token_manager.prompt_for_token.assert_called_once()
                mock_get_days.assert_called_once()
                mock_validate.assert_called_once()
                mock_secure_token_manager.save_token.assert_called_once()
                mock_secure_token_manager.audit_log_token_usage.assert_called_once_with(
                    "token_rotation", source_ip="localhost"
                )
                mock_auth_manager.clear_cached_headers.assert_called_once()

    @patch("builtins.print")
    def test_view_storage_details(self, mock_print, command, mock_secure_token_manager):
        """Test viewing storage details."""
        # Execute
        command._view_storage_details()

        # Verify
        mock_secure_token_manager.token_exists.assert_called_once()
        mock_secure_token_manager.get_keyring_status.assert_called_once()
        mock_secure_token_manager.get_token_metadata.assert_called_once()
        # Should print storage details header
        mock_print.assert_any_call("\n--- Token Storage Details ---")

    @patch("builtins.print")
    def test_view_storage_details_no_token(self, mock_print, command, mock_secure_token_manager):
        """Test viewing storage details when no token exists."""
        # Setup
        mock_secure_token_manager.token_exists.return_value = False

        # Execute
        command._view_storage_details()

        # Verify
        mock_secure_token_manager.token_exists.assert_called_once()
        # Should not try to get details for non-existent token
        mock_secure_token_manager.get_token_metadata.assert_not_called()
        # Should print no token message
        mock_print.assert_any_call("\n❌ No token configured")

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["invalid", "8"])  # Invalid input then exit
    def test_execute_with_invalid_input(
        self, mock_input, mock_print, command, mock_secure_token_manager
    ):
        """Test handling invalid menu input."""
        # Execute
        command.execute()

        # Verify
        # Should print invalid choice message
        mock_print.assert_any_call("Invalid input. Please enter a number.")

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["y"])  # Mock the confirmation input
    def test_not_exposing_real_tokens_in_exceptions(
        self, mock_input, mock_print, command, mock_secure_token_manager
    ):
        """Ensure that if a real token is used, it's not exposed in exceptions."""
        # Setup - create a token that looks like a real GitHub token
        real_looking_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        mock_secure_token_manager.save_token.side_effect = Exception("Failed to save token")

        # Make sure we use a token-like value for testing
        mock_secure_token_manager.get_token.return_value = real_looking_token

        # Make sure the exception doesn't contain the token
        with pytest.raises(Exception) as exc_info:
            # Call validate_token with a value that looks like a real token
            with patch.object(command, "_validate_token", return_value=True):
                # This would normally save the token which would fail with our mock side_effect
                command._save_to_keyring()

        # The exception shouldn't contain the token value
        assert real_looking_token not in str(exc_info.value)
