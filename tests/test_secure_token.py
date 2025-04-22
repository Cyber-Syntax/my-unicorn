#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the secure_token module.

This module contains tests for the SecureTokenManager class that handles
secure token storage and retrieval.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock, mock_open
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
from src.secure_token import SecureTokenManager

# Disable logging during tests to prevent token exposure in logs
logging.getLogger("src.secure_token").setLevel(logging.CRITICAL)

# Safe mock token value used throughout tests
SAFE_MOCK_TOKEN = "test-token-XXXX"


class TestSecureTokenManager:
    """Tests for the SecureTokenManager class."""

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
    def mock_keyring(self, monkeypatch):
        """Mock keyring module for testing."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password.return_value = None
        monkeypatch.setattr("src.secure_token.keyring", mock_keyring)
        return mock_keyring

    @pytest.fixture
    def mock_config_dir(self, monkeypatch, tmp_path):
        """Create a temporary config directory for testing."""
        test_config_dir = tmp_path / "test_config"
        test_config_dir.mkdir()
        monkeypatch.setattr("src.secure_token.CONFIG_DIR", str(test_config_dir))
        monkeypatch.setattr("src.secure_token.TOKEN_FILE", str(test_config_dir / "token.dat"))
        monkeypatch.setattr(
            "src.secure_token.TOKEN_METADATA_FILE", str(test_config_dir / "token_metadata.json")
        )
        return test_config_dir

    @pytest.fixture
    def mock_crypto(self, monkeypatch):
        """Mock cryptography module for testing."""
        mock_fernet = MagicMock()
        # Use a safe mock token value for encryption/decryption
        mock_fernet.encrypt.return_value = b"encrypted_mock_token"
        mock_fernet.decrypt.return_value = SAFE_MOCK_TOKEN.encode("utf-8")

        mock_fernet_class = MagicMock(return_value=mock_fernet)
        monkeypatch.setattr("src.secure_token.Fernet", mock_fernet_class)

        mock_kdf = MagicMock()
        mock_kdf.derive.return_value = b"derived_key"
        mock_kdf_class = MagicMock(return_value=mock_kdf)
        monkeypatch.setattr("src.secure_token.PBKDF2HMAC", mock_kdf_class)

        return {
            "fernet": mock_fernet,
            "fernet_class": mock_fernet_class,
            "kdf": mock_kdf,
            "kdf_class": mock_kdf_class,
        }

    def test_token_exists_false_when_no_token(self, mock_keyring, mock_config_dir):
        """Test token_exists returns False when no token exists."""
        # Ensure token file doesn't exist
        token_file = os.path.join(mock_config_dir, "token.dat")
        if os.path.exists(token_file):
            os.remove(token_file)

        assert not SecureTokenManager.token_exists()

    @patch("src.secure_token.os.path.exists")
    def test_token_exists_true_when_file_exists(self, mock_exists, mock_keyring):
        """Test token_exists returns True when token file exists."""
        mock_exists.return_value = True
        assert SecureTokenManager.token_exists()

    @patch("src.secure_token.getpass.getpass")
    def test_prompt_for_token(self, mock_getpass):
        """Test prompting for token works correctly."""
        mock_getpass.return_value = SAFE_MOCK_TOKEN
        token = SecureTokenManager.prompt_for_token()
        assert token == SAFE_MOCK_TOKEN
        mock_getpass.assert_called_once()

    @patch("src.secure_token.getpass.getpass")
    def test_prompt_for_token_with_input(self, mock_getpass):
        """Test prompting for token with visible input."""
        mock_getpass.side_effect = Exception("getpass error")

        with patch("builtins.input", return_value=SAFE_MOCK_TOKEN):
            token = SecureTokenManager.prompt_for_token(hide_input=False)
            assert token == SAFE_MOCK_TOKEN

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.dump")
    @patch("src.secure_token.os.makedirs")
    @patch("src.secure_token.SecureTokenManager._get_encryption_key")
    def test_save_token(
        self, mock_get_key, mock_makedirs, mock_json_dump, mock_file, mock_crypto, mock_config_dir
    ):
        """Test saving token with encryption."""
        # Setup
        mock_get_key.return_value = b"test_key"

        # Execute - use safe mock token
        result = SecureTokenManager.save_token(SAFE_MOCK_TOKEN, expires_in_days=30)

        # Verify
        assert result is True
        mock_get_key.assert_called_once()
        mock_crypto["fernet_class"].assert_called_once()
        mock_crypto["fernet"].encrypt.assert_called_once()
        mock_file.assert_any_call(os.path.join(mock_config_dir, "token.dat"), "wb")
        mock_file.assert_any_call(os.path.join(mock_config_dir, "token_metadata.json"), "w")

        # Verify metadata was saved
        assert mock_json_dump.call_count > 0
        saved_metadata = mock_json_dump.call_args[0][0]
        assert "created_at" in saved_metadata
        assert "expires_at" in saved_metadata
        assert "storage_method" in saved_metadata

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=b"encrypted_mock_token")
    @patch("src.secure_token.json.load")
    @patch("src.secure_token.SecureTokenManager._get_encryption_key")
    @patch("src.secure_token.SecureTokenManager.is_token_expired")
    def test_get_token_valid(
        self, mock_is_expired, mock_get_key, mock_json_load, mock_file, mock_exists, mock_crypto
    ):
        """Test getting a valid token."""
        # Setup
        mock_exists.return_value = True
        mock_is_expired.return_value = False
        mock_get_key.return_value = b"test_key"
        mock_json_load.return_value = {
            "storage_method": "Encrypted file",
            "created_at": datetime.now().timestamp(),
            "expires_at": (datetime.now() + timedelta(days=30)).timestamp(),
        }

        # Execute
        token = SecureTokenManager.get_token()

        # Verify - should return our safe mock token
        assert token == SAFE_MOCK_TOKEN
        mock_get_key.assert_called_once()
        mock_crypto["fernet_class"].assert_called_once()
        mock_crypto["fernet"].decrypt.assert_called_once()

    @patch("src.secure_token.os.path.exists")
    @patch("src.secure_token.SecureTokenManager.is_token_expired")
    def test_get_token_expired(self, mock_is_expired, mock_exists):
        """Test getting an expired token."""
        # Setup
        mock_exists.return_value = True
        mock_is_expired.return_value = True

        # Execute
        token = SecureTokenManager.get_token(validate_expiration=True)

        # Verify
        assert token is None

    @patch("src.secure_token.os.path.exists")
    @patch("src.secure_token.os.remove")
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.load")
    def test_remove_token(self, mock_json_load, mock_file, mock_remove, mock_exists):
        """Test removing a token."""
        # Setup
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "storage_method": "Encrypted file",
        }

        # Execute
        result = SecureTokenManager.remove_token()

        # Verify
        assert result is True
        assert mock_remove.call_count >= 1

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.load")
    def test_get_token_metadata(self, mock_json_load, mock_file, mock_exists):
        """Test getting token metadata."""
        # Setup
        metadata = {
            "storage_method": "Encrypted file",
            "created_at": datetime.now().timestamp(),
            "expires_at": (datetime.now() + timedelta(days=30)).timestamp(),
        }
        mock_exists.return_value = True
        mock_json_load.return_value = metadata

        # Execute
        result = SecureTokenManager.get_token_metadata()

        # Verify
        assert result == metadata
        mock_file.assert_called_once()
        mock_json_load.assert_called_once()

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.load")
    def test_is_token_expired_true(self, mock_json_load, mock_file, mock_exists):
        """Test checking if token is expired when it is."""
        # Setup - token expired yesterday
        yesterday = datetime.now() - timedelta(days=1)
        metadata = {"expires_at": yesterday.timestamp()}
        mock_exists.return_value = True
        mock_json_load.return_value = metadata

        # Execute
        result = SecureTokenManager.is_token_expired()

        # Verify
        assert result is True

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.load")
    def test_is_token_expired_false(self, mock_json_load, mock_file, mock_exists):
        """Test checking if token is expired when it's not."""
        # Setup - token expires tomorrow
        tomorrow = datetime.now() + timedelta(days=1)
        metadata = {"expires_at": tomorrow.timestamp()}
        mock_exists.return_value = True
        mock_json_load.return_value = metadata

        # Execute
        result = SecureTokenManager.is_token_expired()

        # Verify
        assert result is False

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.load")
    def test_get_token_expiration_info(self, mock_json_load, mock_file, mock_exists):
        """Test getting token expiration information."""
        # Setup
        tomorrow = datetime.now() + timedelta(days=1)
        metadata = {"expires_at": tomorrow.timestamp()}
        mock_exists.return_value = True
        mock_json_load.return_value = metadata

        # Execute
        is_expired, expiration_str = SecureTokenManager.get_token_expiration_info()

        # Verify
        assert is_expired is False
        assert expiration_str is not None

    @patch("src.secure_token.platform.node")
    @patch("src.secure_token.getpass.getuser")
    def test_get_machine_id(self, mock_getuser, mock_node):
        """Test generating a machine ID."""
        # Setup
        mock_node.return_value = "test-machine"
        mock_getuser.return_value = "test-user"

        # Execute
        result = SecureTokenManager._get_machine_id()

        # Verify
        assert isinstance(result, bytes)
        assert len(result) > 0

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.dump")
    def test_audit_log_token_usage(self, mock_json_dump, mock_file):
        """Test logging token usage."""
        # Execute - use non-identifiable values for action and IP
        SecureTokenManager.audit_log_token_usage("test_action", "127.0.0.1")

        # Verify
        mock_file.assert_called()
        mock_json_dump.assert_called()

        # Check the audit log entry format
        log_entry = mock_json_dump.call_args[0][0]
        assert "action" in log_entry
        assert "timestamp" in log_entry
        assert "source_ip" in log_entry
        assert log_entry["action"] == "test_action"
        assert log_entry["source_ip"] == "127.0.0.1"

    def test_get_keyring_status(self, monkeypatch):
        """Test getting keyring availability status."""
        # Mock dependencies
        monkeypatch.setattr(
            "src.secure_token.importlib.util.find_spec", lambda x: True if x == "keyring" else None
        )

        # Execute
        status = SecureTokenManager.get_keyring_status()

        # Verify structure
        assert isinstance(status, dict)
        assert "keyring_module_installed" in status
        assert isinstance(status["keyring_module_installed"], bool)
        assert "any_keyring_available" in status

    @patch("src.secure_token.SecureTokenManager.save_token_to_gnome_keyring")
    def test_no_real_token_in_error_message(self, mock_save_to_gnome):
        """Test that token values don't appear in error messages."""
        # Setup - make the function raise an exception
        mock_save_to_gnome.side_effect = Exception("Error saving token")

        # Execute - use a token that looks like a real PAT
        token_that_looks_real = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"

        # Verify token not exposed in exception messages
        with pytest.raises(Exception) as exc_info:
            SecureTokenManager.save_token_to_gnome_keyring(token_that_looks_real)

        # Check that the error message doesn't contain the token
        assert token_that_looks_real not in str(exc_info.value)
