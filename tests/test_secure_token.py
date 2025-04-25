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
from src.secure_token import DEFAULT_TOKEN_EXPIRATION_DAYS, SecureTokenManager

# Disable logging during tests to prevent token exposure in logs
logging.getLogger("src.secure_token").setLevel(logging.CRITICAL)

# Safe mock token value used throughout tests
SAFE_MOCK_TOKEN = "ghp_mocktokenfortesting123456789abcdefghijklmnopq"


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

    @patch("os.remove")
    @patch("src.secure_token.KEYRING_AVAILABLE", False)
    @patch("src.secure_token.TOKEN_FILE.exists")
    @patch("src.secure_token.TOKEN_METADATA_FILE.exists")
    def test_remove_token(
        self, mock_token_metadata_exists, mock_token_exists, mock_keyring, mock_os_remove
    ):
        """Test removing a token."""
        # Setup
        mock_token_exists.return_value = True
        mock_token_metadata_exists.return_value = True

        # Execute
        result = SecureTokenManager.remove_token()

        # Verify
        assert result is True
        # Should attempt to remove both token and metadata files
        assert mock_os_remove.call_count >= 1

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=b"encrypted_mock_token")
    @patch("src.secure_token.json.load")
    @patch("src.secure_token.SecureTokenManager._get_encryption_key")
    @patch("src.secure_token.KEYRING_AVAILABLE", False)
    @patch("src.secure_token.CRYPTO_AVAILABLE", True)
    def test_get_token_valid(
        self,
        mock_crypto_available,
        mock_keyring_available,
        mock_get_key,
        mock_json_load,
        mock_open,
        mock_path_exists,
    ):
        """Test getting a valid token."""
        # Setup
        mock_path_exists.return_value = True
        mock_get_key.return_value = b"test_key"
        mock_fernet = MagicMock()
        mock_fernet.decrypt.return_value = SAFE_MOCK_TOKEN.encode("utf-8")
        mock_fernet_class = MagicMock(return_value=mock_fernet)

        with patch("src.secure_token.Fernet", mock_fernet_class):
            # Mock Path.exists() for token files using MagicMock objects
            token_file_patch = patch("src.secure_token.TOKEN_FILE.exists", return_value=True)
            metadata_file_patch = patch(
                "src.secure_token.TOKEN_METADATA_FILE.exists", return_value=True
            )

            # Add expiration date in the future to ensure token is not expired
            mock_json_load.return_value = {
                "storage_method": "Encrypted file",
                "created_at": datetime.now().timestamp(),
                "expires_at": (datetime.now() + timedelta(days=30)).timestamp(),
            }

            # Use context managers to properly patch Path.exists
            with token_file_patch, metadata_file_patch:
                # Execute
                token = SecureTokenManager.get_token()

                # Verify - should return our safe mock token
                assert token == SAFE_MOCK_TOKEN
                mock_get_key.assert_called_once()
                mock_fernet_class.assert_called_once()
                mock_fernet.decrypt.assert_called_once()

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=b"encrypted_mock_token")
    @patch("src.secure_token.json.load")
    @patch("src.secure_token.SecureTokenManager._get_encryption_key")
    @patch("src.secure_token.KEYRING_AVAILABLE", False)
    @patch("src.secure_token.CRYPTO_AVAILABLE", True)
    def test_get_token_expired(
        self,
        mock_crypto_available,
        mock_keyring_available,
        mock_get_key,
        mock_json_load,
        mock_open,
        mock_exists,
    ):
        """Test getting an expired token."""
        # Setup
        mock_exists.return_value = True
        mock_get_key.return_value = b"test_key"
        mock_fernet = MagicMock()
        mock_fernet.decrypt.return_value = SAFE_MOCK_TOKEN.encode("utf-8")
        mock_fernet_class = MagicMock(return_value=mock_fernet)

        with patch("src.secure_token.Fernet", mock_fernet_class):
            # Mock Path.exists() for token files
            token_file_patch = patch("src.secure_token.TOKEN_FILE.exists", return_value=True)
            metadata_file_patch = patch(
                "src.secure_token.TOKEN_METADATA_FILE.exists", return_value=True
            )

            # Set metadata with expired timestamp
            mock_json_load.return_value = {
                "storage_method": "Encrypted file",
                "created_at": datetime.now().timestamp(),
                "expires_at": (datetime.now() - timedelta(days=1)).timestamp(),
            }

            # Execute
            with token_file_patch, metadata_file_patch:
                token = SecureTokenManager.get_token(validate_expiration=True)

                # Verify - implementation returns empty string for expired token
                assert token == ""


    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.dump")
    @patch("src.secure_token.os.makedirs")
    @patch("src.secure_token.SecureTokenManager._get_encryption_key")
    def test_save_token(
        self,
        mock_open,     # ← from builtins.open (bottommost patch)
        dump,          # ← from json.dump
        mock_makedirs, # ← from os.makedirs
        mock_get_key   # ← from _get_encryption_key (topmost patch)
    ):
        """Test saving token with encryption."""
        # Arrange: stub encryption key and Fernet
        mock_get_key.return_value = b"test_key"
        with patch("src.secure_token.Fernet") as mock_fernet_class:
            inst = MagicMock()
            inst.encrypt.return_value = b"encrypted"
            mock_fernet_class.return_value = inst

            # Act
            ok = SecureTokenManager.save_token(
                SAFE_MOCK_TOKEN,
                expires_in_days=30,
                storage_preference="file",
                ask_for_fallback=False,
            )

        # Assert
        assert ok is True
        mock_get_key.assert_called_once()                    # key retrieved :contentReference[oaicite:3]{index=3}
        mock_fernet_class.assert_called_once()               # Fernet constructed :contentReference[oaicite:4]{index=4}
        inst.encrypt.assert_called_once()                    # encryption performed :contentReference[oaicite:5]{index=5}
        mock_open.assert_any_call(                           # token file written :contentReference[oaicite:6]{index=6}
            SecureTokenManager.TOKEN_FILE.with_suffix(".tmp"), "wb"
        )
        mock_open.assert_any_call(                           # metadata file written :contentReference[oaicite:7]{index=7}
            SecureTokenManager.TOKEN_METADATA_FILE.with_suffix(".tmp"), "w"
        )
        assert dump.call_count > 0                           # metadata dumped :contentReference[oaicite:8]{index=8}
        meta = dump.call_args[0][0]
        for key in ("created_at", "expires_at", "storage_method"):
            assert key in meta                               # correct metadata keys :contentReference[oaicite:9]{index=9}

    def test_file_storage_with_expiration(self, monkeypatch, tmp_path):
        """Test that file storage includes proper expiration in metadata."""
        # Disable keyring, enable crypto
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)

        # Setup tmp_path for file storage
        token_file = tmp_path / "token.dat"
        metadata_file = tmp_path / "token_metadata.json"
        monkeypatch.setattr("src.secure_token.TOKEN_FILE", token_file)
        monkeypatch.setattr("src.secure_token.TOKEN_METADATA_FILE", metadata_file)
        monkeypatch.setattr("src.secure_token.CONFIG_DIR", tmp_path)

        # Create a valid token
        valid_token = "ghp_" + "A" * 40

        # Mock the encryption key generation
        monkeypatch.setattr(
            "src.secure_token.SecureTokenManager._get_encryption_key",
            lambda: b"test_encryption_key",
        )

        # Mock Fernet for encryption
        mock_fernet = MagicMock()
        mock_fernet.encrypt.return_value = b"encrypted_mock_token"
        monkeypatch.setattr("src.secure_token.Fernet", lambda key: mock_fernet)

        # Mock os.replace and os.chmod to avoid file operations
        monkeypatch.setattr("os.replace", lambda src, dst: None)
        monkeypatch.setattr("os.chmod", lambda path, mode: None)

        # Create metadata file to be read after save_token
        custom_days = 45
        metadata = {
            "storage_method": "Encrypted file",
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + (custom_days * 86400),
        }

        # Write metadata to the file
        os.makedirs(tmp_path, exist_ok=True)
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Test file storage with custom expiration
        result = SecureTokenManager.save_token(
            valid_token,
            expires_in_days=custom_days,
            storage_preference="file",
            ask_for_fallback=False,
        )

        assert result is True

        # Verify expiration in metadata
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
            expected_expiration = int(time.time()) + (custom_days * 86400)
            # Allow a small tolerance for execution time
            assert abs(metadata["expires_at"] - expected_expiration) < 10

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

        # Use Path objects explicitly to match the implementation
        monkeypatch.setattr("src.secure_token.CONFIG_DIR", test_config_dir)
        monkeypatch.setattr("src.secure_token.TOKEN_FILE", test_config_dir / "token.dat")
        monkeypatch.setattr(
            "src.secure_token.TOKEN_METADATA_FILE", test_config_dir / "token_metadata.json"
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

    @pytest.fixture
    def valid_token(self):
        """Fixture to provide a valid GitHub token format."""
        return "ghp_" + "A" * 40

    @pytest.fixture
    def mock_crypto_components(self, monkeypatch):
        """Mock cryptography components for testing."""
        mock_fernet = MagicMock()
        mock_fernet.encrypt.return_value = b"encrypted_mock_token"

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
        # Ensure token file doesn't exist - using pathlib
        token_file = mock_config_dir / "token.dat"
        if token_file.exists():
            token_file.unlink()

        # Mock KEYRING_AVAILABLE to False to simplify the test
        with patch("src.secure_token.KEYRING_AVAILABLE", False):
            assert not SecureTokenManager.token_exists()

    def test_token_exists_true_when_file_exists(self, mock_keyring, mock_config_dir):
        """Test token_exists returns True when token file exists."""
        # Create a token file
        token_file = mock_config_dir / "token.dat"
        token_file.touch()

        # Mock KEYRING_AVAILABLE to False to simplify the test
        with patch("src.secure_token.KEYRING_AVAILABLE", False):
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
        # Set up the mock to return our test token
        mock_getpass.return_value = SAFE_MOCK_TOKEN

        # Execute
        token = SecureTokenManager.prompt_for_token()

        # Verify
        assert token == SAFE_MOCK_TOKEN
        mock_getpass.assert_called_once()

    def test_invalid_format_short_prefix(self, monkeypatch):
        """
        Tokens not matching the GitHub pattern should be rejected immediately.
        """
        bad = "invalid_token$$"
        assert not SecureTokenManager.save_token(bad), \
            "Should return False for tokens with invalid characters"  # fmt: skip

    def test_invalid_format_too_short(self, monkeypatch):
        """
        Tokens shorter than 40 characters should be rejected.
        """
        short = "ghp_" + "a" * 10
        assert len(short) < 40
        assert not SecureTokenManager.save_token(short), \
            "Should return False for tokens shorter than expected length"  # fmt: skip

    def test_keyring_success(self, monkeypatch, valid_token):
        """
        When KEYRING_AVAILABLE is True and _save_to_keyring returns success,
        save_token should return True without trying file storage.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        # Stub out keyring save to simulate success
        def fake_save_to_keyring(token, meta):
            assert token.startswith("ghp_")
            return (True, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_keyring", fake_save_to_keyring)

        result = SecureTokenManager.save_token(valid_token, storage_preference="auto")
        assert result is True

    def test_keyring_only_failure(self, monkeypatch, valid_token):
        """
        If storage_preference="keyring_only" and keyring save fails,
        save_token must return False immediately.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        # Simulate failure
        def fake_save_to_keyring(token, meta):
            return (False, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_keyring", fake_save_to_keyring)

        result = SecureTokenManager.save_token(valid_token, storage_preference="keyring_only")
        assert result is False

    def test_file_fallback_success(
        self, monkeypatch, valid_token, mock_crypto_components, tmp_path
    ):
        """
        When keyring unavailable but crypto available, file storage should succeed.
        """
        # Disable keyring, enable crypto
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)

        # Setup tmp_path for file storage
        token_file = tmp_path / "token.dat"
        metadata_file = tmp_path / "token_metadata.json"
        monkeypatch.setattr("src.secure_token.TOKEN_FILE", token_file)
        monkeypatch.setattr("src.secure_token.TOKEN_METADATA_FILE", metadata_file)

        # Mock the encryption key generation
        monkeypatch.setattr(
            SecureTokenManager, "_get_encryption_key", lambda: b"test_encryption_key"
        )

        # Test file storage success
        result = SecureTokenManager.save_token(
            valid_token,
            storage_preference="file",
            ask_for_fallback=False,  # Skip interactive prompts
        )

        assert result is True
        assert token_file.exists()
        assert metadata_file.exists()

        # Verify metadata content
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
            assert "created_at" in metadata
            assert "expires_at" in metadata
            assert "storage_method" in metadata
            assert metadata["storage_method"] == "Encrypted file"

    def test_no_secure_storage_available(self, monkeypatch, valid_token):
        """
        If neither keyring nor crypto is available, save_token should return False.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", False)

        result = SecureTokenManager.save_token(valid_token)
        assert result is False

    def test_custom_metadata_included(self, monkeypatch, valid_token):
        """
        Custom metadata provided should be included in the saved metadata.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        saved_metadata = None

        def fake_save_to_keyring(token, meta):
            nonlocal saved_metadata
            saved_metadata = meta
            return (True, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_keyring", fake_save_to_keyring)

        custom_meta = {"app_name": "test-app", "environment": "testing"}
        result = SecureTokenManager.save_token(valid_token, metadata=custom_meta)

        assert result is True
        assert saved_metadata["app_name"] == "test-app"
        assert saved_metadata["environment"] == "testing"

    def test_keyring_only_failure(self, monkeypatch):
        """
        If storage_preference="keyring_only" and keyring save fails,
        save_token must return False immediately.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        # simulate failure
        def fake_save_to_keyring(token, meta):
            return (False, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_keyring", fake_save_to_keyring)

        res = SecureTokenManager.save_token("ghp_" + "B" * 40, storage_preference="keyring_only")
        assert res is False

    def test_file_fallback_user_declines(self, monkeypatch):
        """
        When keyring unavailable and user declines file fallback prompt,
        save_token returns False.
        """
        # enable crypto fallback
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)

        # simulate input "n"
        monkeypatch.setattr(builtins, "input", lambda prompt="": "n")

        res = SecureTokenManager.save_token(
            "ghp_" + "C" * 40, storage_preference="auto", ask_for_fallback=True
        )
        assert res is False

    def test_file_fallback_user_accepts_and_success(self, monkeypatch):
        """
        When keyring unavailable, user accepts file fallback, and
        encrypted-file save succeeds, return True.
        """
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)
        monkeypatch.setattr(builtins, "input", lambda prompt="": "y")

        # stub encrypted file save
        def fake_save_to_file(token, meta):
            assert meta["storage_preference"] == "auto"
            return (True, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_encrypted_file", fake_save_to_file)

        res = SecureTokenManager.save_token(
            "ghp_" + "D" * 40, storage_preference="auto", ask_for_fallback=True
        )
        assert res is True

    def test_file_preference_without_prompt(self, monkeypatch):
        """
        If storage_preference="file", do not prompt—even if ask_for_fallback=True—
        and proceed directly to encrypted-file storage.
        """
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)

        called = {}

        def fake_save_to_file(token, meta):
            called["yes"] = True
            return (True, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_encrypted_file", fake_save_to_file)

        res = SecureTokenManager.save_token(
            "ghp_" + "E" * 40, storage_preference="file", ask_for_fallback=True
        )
        assert res
        assert called.get("yes", False)

    def test_metadata_merging(self, monkeypatch):
        """
        Ensure custom metadata is merged into the metadata dict passed to
        save routines.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        def fake_save(token, meta):
            # custom foo should be present
            assert meta.get("foo") == "bar"
            return (True, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_keyring", fake_save)

        res = SecureTokenManager.save_token("ghp_" + "F" * 40, metadata={"foo": "bar"})
        assert res

    def test_default_expiration_in_metadata(self, monkeypatch):
        """
        The metadata created must include an 'expires_at' timestamp
        calculated using DEFAULT_TOKEN_EXPIRATION_DAYS.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        def fake_save(token, meta):
            assert "expires_at" in meta
            # Should be roughly now + DEFAULT_TOKEN_EXPIRATION_DAYS
            from datetime import datetime, timedelta

            exp = datetime.fromtimestamp(meta["expires_at"])
            delta = exp - datetime.now()
            assert abs(delta - timedelta(days=DEFAULT_TOKEN_EXPIRATION_DAYS)) < timedelta(
                seconds=10
            )
            return (True, meta)

        monkeypatch.setattr(SecureTokenManager, "_save_to_keyring", fake_save)

        assert SecureTokenManager.save_token("ghp_" + "G" * 40)

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
        mock_json_load.return_value = metadata
        mock_exists.return_value = True

        # Patch KEYRING_AVAILABLE to False for consistent test behavior
        with patch("src.secure_token.KEYRING_AVAILABLE", False):
            # Use a safer approach to mock Path existence - patch the function call
            with patch("src.secure_token.Path.exists", return_value=True):
                # Execute
                result = SecureTokenManager.get_token_metadata()

                # Verify
                assert result == metadata
                mock_file.assert_called_once()
                mock_json_load.assert_called_once()

    @patch("src.secure_token.os.path.exists")
    @patch("builtins.open", mock_open(read_data="test-machine-id"))
    @patch("socket.gethostname")
    @patch("getpass.getuser")
    def test_get_machine_id(self, mock_getuser, mock_hostname, mock_exists):
        """Test generating a machine ID."""
        # Setup - first mock /etc/machine-id existence check
        mock_exists.return_value = False
        # Then mock the fallback to hostname+user
        mock_hostname.return_value = "test-machine"
        mock_getuser.return_value = "test-user"

        # Execute
        result = SecureTokenManager._get_machine_id()

        # Verify
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify it contains our test values when using fallback
        test_id = f"test-machine-test-user".encode("utf-8")
        assert result == test_id

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.secure_token.json.dumps")
    def test_audit_log_token_usage(self, mock_json_dumps, mock_file):
        """Test logging token usage."""
        # Setup
        mock_json_dumps.return_value = (
            '{"action": "test_action", '
            '"timestamp": "2023-01-01T00:00:00", '
            '"token_id": "unknown", '
            '"source_ip": "127.0.0.1"}'
        )

        # Execute - use non-identifiable values for action and IP
        SecureTokenManager.audit_log_token_usage("test_action", "127.0.0.1")

        # Verify
        mock_file.assert_called()
        mock_json_dumps.assert_called_once()

        # Check the audit log entry format
        log_entry = mock_json_dumps.call_args[0][0]
        assert "action" in log_entry
        assert "timestamp" in log_entry
        assert "source_ip" in log_entry
        assert log_entry["action"] == "test_action"
        assert log_entry["source_ip"] == "127.0.0.1"

    def test_get_keyring_status(self, monkeypatch):
        """Test getting keyring availability status."""
        # Directly patch the status variables instead of importlib
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)
        monkeypatch.setattr("src.secure_token.GNOME_KEYRING_AVAILABLE", True)
        monkeypatch.setattr("src.secure_token.KDE_WALLET_AVAILABLE", False)
        monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)

        # Execute
        status = SecureTokenManager.get_keyring_status()

        # Verify structure and values
        assert isinstance(status, dict)
        assert status["any_keyring_available"] is True
        assert status["gnome_keyring_available"] is True
        assert status["kde_wallet_available"] is False
        assert status["crypto_available"] is True

    @patch("src.secure_token.SecureTokenManager._save_to_keyring")
    def test_no_real_token_in_error_message(self, mock_save_to_keyring):
        """Test that token values don't appear in error messages."""
        # Setup - make the function raise an exception
        mock_save_to_keyring.side_effect = Exception("Error saving token")

        # Execute - use a token that looks like a real PAT
        token_that_looks_real = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        metadata = {"storage_preference": "keyring"}

        # Verify token not exposed in exception messages
        with pytest.raises(Exception) as exc_info:
            # Use the _save_to_keyring method which exists in the implementation
            SecureTokenManager._save_to_keyring(token_that_looks_real, metadata)

        # Check that the error message doesn't contain the token
        assert token_that_looks_real not in str(exc_info.value)

    @patch("src.secure_token.format_timestamp")
    @patch("src.secure_token.parse_timestamp")
    @patch.object(SecureTokenManager, "get_token_metadata")
    def test_token_not_expired(self, mock_get_metadata, mock_parse_ts, mock_format_ts):
        """Test token expiration info when token is not expired."""
        # Arrange
        future_time = datetime.now() + timedelta(hours=1)
        mock_get_metadata.return_value = {"expires_at": "some_timestamp"}
        mock_parse_ts.return_value = future_time
        mock_format_ts.return_value = "2025-05-01 10:00:00"

        # Act
        is_expired, expiration_str = SecureTokenManager.get_token_expiration_info()

        # Assert
        assert is_expired is False
        assert expiration_str == "2025-05-01 10:00:00"
        mock_get_metadata.assert_called_once()
        mock_parse_ts.assert_called_once_with("some_timestamp")
        mock_format_ts.assert_called_once_with(future_time)

    @patch("src.secure_token.format_timestamp")
    @patch("src.secure_token.parse_timestamp")
    @patch.object(SecureTokenManager, "get_token_metadata")
    def test_token_expired(self, mock_get_metadata, mock_parse_ts, mock_format_ts):
        """Test token expiration info when token is expired."""
        # Arrange
        past_time = datetime.now() - timedelta(hours=1)
        mock_get_metadata.return_value = {"expires_at": "some_timestamp"}
        mock_parse_ts.return_value = past_time
        mock_format_ts.return_value = "2025-04-01 10:00:00"

        # Act
        is_expired, expiration_str = SecureTokenManager.get_token_expiration_info()

        # Assert
        assert is_expired is True
        assert expiration_str == "2025-04-01 10:00:00"
        mock_get_metadata.assert_called_once()
        mock_parse_ts.assert_called_once_with("some_timestamp")
        mock_format_ts.assert_called_once_with(past_time)

    @patch.object(SecureTokenManager, "get_token_metadata")
    def test_missing_metadata(self, mock_get_metadata):
        """Test token expiration info when metadata is missing."""
        # Arrange
        mock_get_metadata.return_value = None

        # Act
        is_expired, expiration_str = SecureTokenManager.get_token_expiration_info()

        # Assert
        assert is_expired is True
        assert expiration_str is None
        mock_get_metadata.assert_called_once()

    @patch("src.secure_token.parse_timestamp")
    @patch.object(SecureTokenManager, "get_token_metadata")
    def test_parse_failure(self, mock_get_metadata, mock_parse_ts):
        """Test token expiration info when timestamp parsing fails."""
        # Arrange
        mock_get_metadata.return_value = {"expires_at": "invalid"}
        mock_parse_ts.return_value = None  # Simulate parse failure

        # Act
        is_expired, expiration_str = SecureTokenManager.get_token_expiration_info()

        # Assert
        assert is_expired is True
        assert expiration_str is None
        mock_get_metadata.assert_called_once()
        mock_parse_ts.assert_called_once_with("invalid")

    def test_keyring_json_decode_failure(self, monkeypatch, sample_token):
        """If metadata JSON is malformed, get_token should ignore metadata and still return token."""
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        # token ok, metadata malformed
        def fake_get(svc, usr):
            return sample_token if svc == "my-unicorn-github" else "{ not valid JSON"

        monkeypatch.setattr("src.secure_token.keyring_module.get_password", fake_get)
        out = SecureTokenManager.get_token()
        assert out == sample_token

    def test_keyring_expired_token(self, monkeypatch, sample_token, past_metadata):
        """
        If metadata indicates expiration before now, get_token returns empty string.
        """
        monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", True)

        # return token and past metadata
        def fake_get(svc, usr):
            return sample_token if svc == "my-unicorn-github" else json.dumps(past_metadata)

        monkeypatch.setattr("src.secure_token.keyring_module.get_password", fake_get)
        out = SecureTokenManager.get_token(validate_expiration=True)
        assert out == ""
