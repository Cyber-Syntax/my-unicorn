#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the secure_token module.

This module contains tests for the SecureTokenManager class that handles
secure token storage and retrieval.
"""

import os
import tempfile
import time
import builtins
import pytest
import sys
from pathlib import Path
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

# Ensure the project root is in sys.path
project_root = str(Path(__file__).parent.parent.absolute())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import constants directly
from src.utils.datetime_utils import parse_timestamp, format_timestamp

# We'll access SecureTokenManager through fixtures and patches instead of importing directly
# This avoids import issues when running in the global test context

# Define constants from the module (avoids direct imports)
DEFAULT_TOKEN_EXPIRATION_DAYS = 90  # Match the value in secure_token.py

# Disable logging during tests to prevent token exposure in logs
logging.getLogger("src.secure_token").setLevel(logging.CRITICAL)

# Safe mock token value used throughout tests
SAFE_MOCK_TOKEN = "ghp_mocktokenfortesting123456789abcdefghijklmnopq"


@pytest.fixture
def secure_token_manager(monkeypatch):
    """Fixture to provide access to the SecureTokenManager class."""
    # Import the module here to avoid import issues at module level
    import src.secure_token

    return src.secure_token.SecureTokenManager


def monkeypatch_path_exists():
    """Helper function to patch Path.exists() methods for tests."""
    return patch.multiple(
        "src.secure_token",
        **{"TOKEN_FILE.exists.return_value": True, "TOKEN_METADATA_FILE.exists.return_value": True},
    )


@pytest.fixture(autouse=True)
def set_consts(monkeypatch):
    # override constants via monkeypatch, not via patch()
    monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
    monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)


class TestSecureTokenManager:
    """Tests for the SecureTokenManager class."""

    def test_remove_token(self, monkeypatch, secure_token_manager):
        """Test removing a token."""
        # Create mock Path objects that return True for exists()
        mock_token_file = MagicMock()
        mock_token_file.exists.return_value = True

        mock_token_metadata_file = MagicMock()
        mock_token_metadata_file.exists.return_value = True

        # Patch the TOKEN_FILE and TOKEN_METADATA_FILE attributes with our mock objects
        monkeypatch.setattr("src.secure_token.TOKEN_FILE", mock_token_file)
        monkeypatch.setattr("src.secure_token.TOKEN_METADATA_FILE", mock_token_metadata_file)

        # Disable keyring for this test
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)

        # Mock os.remove
        with patch("os.remove") as mock_remove:
            # Execute
            result = secure_token_manager.remove_token()

            # Verify
            assert result is True
            # Should attempt to remove both token and metadata files
            assert mock_remove.call_count >= 1

    def test_get_token_valid(self, monkeypatch, secure_token_manager):
        """Test getting a valid token."""
        # Create mock Path objects that return True for exists()
        mock_token_file = MagicMock()
        mock_token_file.exists.return_value = True

        mock_token_metadata_file = MagicMock()
        mock_token_metadata_file.exists.return_value = True

        # Patch the TOKEN_FILE and TOKEN_METADATA_FILE attributes with our mock objects
        monkeypatch.setattr("src.secure_token.TOKEN_FILE", mock_token_file)
        monkeypatch.setattr("src.secure_token.TOKEN_METADATA_FILE", mock_token_metadata_file)

        # Patch other dependencies
        monkeypatch.setattr("src.secure_token.os.path.exists", lambda *args: True)
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)

        # Mock the encryption key retrieval
        mock_get_key = MagicMock(return_value=b"test_key")
        monkeypatch.setattr("src.secure_token.SecureTokenManager._get_encryption_key", mock_get_key)

        # Mock the file reading
        mock_file = mock_open(read_data=b"encrypted_mock_token")
        monkeypatch.setattr("builtins.open", mock_file)

        # Mock JSON loading for metadata
        metadata = {
            "storage_method": "Encrypted file",
            "created_at": datetime.now().timestamp(),
            "expires_at": (datetime.now() + timedelta(days=30)).timestamp(),
        }
        mock_json_load = MagicMock(return_value=metadata)
        monkeypatch.setattr("src.secure_token.json.load", mock_json_load)

        # Mock Fernet for decryption
        mock_fernet = MagicMock()
        mock_fernet.decrypt.return_value = SAFE_MOCK_TOKEN.encode("utf-8")
        mock_fernet_class = MagicMock(return_value=mock_fernet)
        monkeypatch.setattr("src.secure_token.Fernet", mock_fernet_class)

        # Execute
        token = secure_token_manager.get_token()

        # Verify - should return our safe mock token
        assert token == SAFE_MOCK_TOKEN
        mock_get_key.assert_called_once()
        mock_fernet_class.assert_called_once()
        mock_fernet.decrypt.assert_called_once()

    def test_get_token_expired(self, monkeypatch, secure_token_manager):
        """Test getting an expired token."""
        # Create mock Path objects that return True for exists()
        mock_token_file = MagicMock()
        mock_token_file.exists.return_value = True

        mock_token_metadata_file = MagicMock()
        mock_token_metadata_file.exists.return_value = True

        # Patch the TOKEN_FILE and TOKEN_METADATA_FILE attributes with our mock objects
        monkeypatch.setattr("src.secure_token.TOKEN_FILE", mock_token_file)
        monkeypatch.setattr("src.secure_token.TOKEN_METADATA_FILE", mock_token_metadata_file)

        # Patch other dependencies
        monkeypatch.setattr("src.secure_token.os.path.exists", lambda *args: True)
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)

        # Mock the encryption key retrieval
        mock_get_key = MagicMock(return_value=b"test_key")
        monkeypatch.setattr("src.secure_token.SecureTokenManager._get_encryption_key", mock_get_key)

        # Mock the file reading
        mock_file = mock_open(read_data=b"encrypted_mock_token")
        monkeypatch.setattr("builtins.open", mock_file)

        # Mock JSON loading for metadata with expired timestamp
        metadata = {
            "storage_method": "Encrypted file",
            "created_at": datetime.now().timestamp(),
            "expires_at": (datetime.now() - timedelta(days=1)).timestamp(),
        }
        mock_json_load = MagicMock(return_value=metadata)
        monkeypatch.setattr("src.secure_token.json.load", mock_json_load)

        # Mock Fernet for decryption
        mock_fernet = MagicMock()
        mock_fernet.decrypt.return_value = SAFE_MOCK_TOKEN.encode("utf-8")
        mock_fernet_class = MagicMock(return_value=mock_fernet)
        monkeypatch.setattr("src.secure_token.Fernet", mock_fernet_class)

        # Execute
        token = secure_token_manager.get_token(validate_expiration=True)

        # Verify - implementation returns empty string for expired token
        assert token == ""

    @patch("os.replace")
    @patch("os.chmod")
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.dump")
    @patch("src.secure_token.os.makedirs")
    @patch("src.secure_token.SecureTokenManager._get_encryption_key")
    @patch("src.secure_token.TOKEN_FILE")
    @patch("src.secure_token.TOKEN_METADATA_FILE")
    def test_save_token(
        self,
        mock_token_metadata_file,
        mock_token_file,
        mock_get_key,
        mock_makedirs,
        mock_dump,
        mock_open,
        mock_chmod,
        mock_replace,
        secure_token_manager,
    ):
        """Test saving token with encryption."""
        # Import Path class
        from pathlib import Path

        # Setup file path mocks
        mock_token_file.with_suffix.return_value = Path("/tmp/token.tmp")
        mock_token_metadata_file.with_suffix.return_value = Path("/tmp/token_metadata.tmp")

        # Arrange: stub encryption key and Fernet
        mock_get_key.return_value = b"test_key"
        with patch("src.secure_token.Fernet") as mock_fernet_class:
            inst = MagicMock()
            inst.encrypt.return_value = b"encrypted"
            mock_fernet_class.return_value = inst

            # Act
            with patch("src.secure_token.CRYPTO_AVAILABLE", True):
                with patch("src.secure_token.KEYRING_AVAILABLE", False):
                    ok = secure_token_manager.save_token(
                        SAFE_MOCK_TOKEN,
                        expires_in_days=30,
                        storage_preference="file",
                        ask_for_fallback=False,
                    )

        # Assert
        assert ok is True
        mock_get_key.assert_called_once()
        mock_fernet_class.assert_called_once()
        inst.encrypt.assert_called_once()
        mock_open.assert_any_call(mock_token_file.with_suffix.return_value, "wb")
        mock_open.assert_any_call(mock_token_metadata_file.with_suffix.return_value, "w")
        assert mock_dump.call_count > 0
        meta = mock_dump.call_args[0][0]
        for key in ("created_at", "expires_at", "storage_method"):
            assert key in meta
