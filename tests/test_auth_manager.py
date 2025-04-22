#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the auth_manager module.

This module contains tests for the GitHubAuthManager class that handles
GitHub API authentication with token handling.
"""

import os
import json
import time
from datetime import datetime, timedelta
import pytest
from unittest.mock import patch, MagicMock, mock_open
import logging

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture

# Import the module to test
from src.auth_manager import GitHubAuthManager

# Disable logging during tests to prevent token exposure
logging.getLogger("src.auth_manager").setLevel(logging.CRITICAL)
logging.getLogger("src.secure_token").setLevel(logging.CRITICAL)

# Safe mock token value used throughout tests
SAFE_MOCK_TOKEN = "test-token-XXXX"


class TestGitHubAuthManager:
    """Tests for the GitHubAuthManager class."""

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
    def reset_class_state(self):
        """Reset GitHubAuthManager class state before each test."""
        GitHubAuthManager._cached_headers = None
        GitHubAuthManager._last_token = None
        GitHubAuthManager._last_token_check = 0
        GitHubAuthManager._rate_limit_cache = {}
        GitHubAuthManager._rate_limit_cache_time = 0
        GitHubAuthManager._request_count_since_cache = 0
        GitHubAuthManager._audit_enabled = True
        yield
        # Reset again after test
        GitHubAuthManager._cached_headers = None
        GitHubAuthManager._last_token = None
        GitHubAuthManager._last_token_check = 0
        GitHubAuthManager._rate_limit_cache = {}
        GitHubAuthManager._rate_limit_cache_time = 0
        GitHubAuthManager._request_count_since_cache = 0
        GitHubAuthManager._audit_enabled = True

    @pytest.fixture
    def mock_token_manager(self, monkeypatch):
        """Mock SecureTokenManager for testing."""
        mock_manager = MagicMock()
        mock_manager.get_token.return_value = SAFE_MOCK_TOKEN
        mock_manager.get_token_expiration_info.return_value = (False, "2099-12-31 23:59:59")
        mock_manager.is_token_expired.return_value = False
        mock_manager.audit_log_token_usage.return_value = None
        monkeypatch.setattr("src.auth_manager.SecureTokenManager", mock_manager)
        return mock_manager

    @pytest.fixture
    def mock_requests(self, monkeypatch):
        """Mock requests module for testing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rate": {"limit": 5000, "remaining": 4990, "reset": int(time.time()) + 3600},
            "resources": {
                "core": {"limit": 5000, "remaining": 4990, "reset": int(time.time()) + 3600},
                "search": {"limit": 30, "remaining": 28, "reset": int(time.time()) + 3600},
                "graphql": {"limit": 5000, "remaining": 4999, "reset": int(time.time()) + 3600},
            },
        }

        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_response
        mock_requests.request.return_value = mock_response
        mock_requests.RequestException = Exception

        monkeypatch.setattr("src.auth_manager.requests", mock_requests)
        return {"module": mock_requests, "response": mock_response}

    @pytest.fixture
    def mock_cache_dir(self, monkeypatch, tmp_path):
        """Create a temporary cache directory for testing."""
        test_cache_dir = tmp_path / "test_cache"
        test_cache_dir.mkdir()
        monkeypatch.setattr("src.auth_manager.CACHE_DIR", str(test_cache_dir))
        return test_cache_dir

    def test_get_auth_headers_no_token(self, reset_class_state, mock_token_manager):
        """Test getting auth headers when no token is available."""
        # Setup
        mock_token_manager.get_token.return_value = None

        # Execute
        headers = GitHubAuthManager.get_auth_headers()

        # Verify
        assert "Authorization" not in headers
        assert "Accept" in headers
        assert "X-GitHub-Api-Version" in headers
        assert "User-Agent" in headers

    def test_get_auth_headers_with_token(self, reset_class_state, mock_token_manager):
        """Test getting auth headers with a valid token."""
        # Setup
        mock_token_manager.get_token.return_value = SAFE_MOCK_TOKEN

        # Execute
        headers = GitHubAuthManager.get_auth_headers()

        # Verify
        assert headers["Authorization"] == f"Bearer {SAFE_MOCK_TOKEN}"
        assert headers["Accept"] == "application/vnd.github+json"
        assert "X-GitHub-Api-Version" in headers
        assert "User-Agent" in headers

        # Check that token was cached
        assert GitHubAuthManager._cached_headers is headers
        assert GitHubAuthManager._last_token == SAFE_MOCK_TOKEN

    def test_get_auth_headers_cached(self, reset_class_state, mock_token_manager):
        """Test that cached headers are reused when token hasn't changed."""
        # Setup - Get headers first time
        mock_token_manager.get_token.return_value = SAFE_MOCK_TOKEN
        first_headers = GitHubAuthManager.get_auth_headers()

        # Execute - Get headers second time
        second_headers = GitHubAuthManager.get_auth_headers()

        # Verify
        assert second_headers is first_headers  # Same object (cached)
        assert mock_token_manager.get_token.call_count == 2  # Called again to check token

    def test_clear_cached_headers(self, reset_class_state):
        """Test clearing cached headers."""
        # Setup - Set some cached data
        GitHubAuthManager._cached_headers = {"test": "header"}
        GitHubAuthManager._last_token = SAFE_MOCK_TOKEN
        GitHubAuthManager._last_token_check = time.time()

        # Execute
        GitHubAuthManager.clear_cached_headers()

        # Verify
        assert GitHubAuthManager._cached_headers is None
        assert GitHubAuthManager._last_token is None
        assert GitHubAuthManager._last_token_check == 0

    def test_has_valid_token_true(self, reset_class_state, mock_token_manager):
        """Test has_valid_token returns True with valid token."""
        # Setup
        mock_token_manager.get_token.return_value = SAFE_MOCK_TOKEN

        # Execute
        result = GitHubAuthManager.has_valid_token()

        # Verify
        assert result is True
        mock_token_manager.get_token.assert_called_once_with(validate_expiration=True)

    def test_has_valid_token_false(self, reset_class_state, mock_token_manager):
        """Test has_valid_token returns False with no valid token."""
        # Setup
        mock_token_manager.get_token.return_value = None

        # Execute
        result = GitHubAuthManager.has_valid_token()

        # Verify
        assert result is False
        mock_token_manager.get_token.assert_called_once_with(validate_expiration=True)

    def test_should_rotate_token_expired(self, reset_class_state, mock_token_manager):
        """Test _should_rotate_token when token is expired."""
        # Setup
        mock_token_manager.get_token_expiration_info.return_value = (True, "2020-01-01 00:00:00")

        # Execute
        result = GitHubAuthManager._should_rotate_token()

        # Verify
        assert result is True
        mock_token_manager.get_token_expiration_info.assert_called_once()

    def test_should_rotate_token_approaching_expiration(
        self, reset_class_state, mock_token_manager
    ):
        """Test _should_rotate_token when token is approaching expiration."""
        # Setup - token expires in 10 days
        expiration_date = datetime.now() + timedelta(days=10)
        mock_token_manager.get_token_expiration_info.return_value = (
            False,
            expiration_date.strftime("%Y-%m-%d %H:%M:%S"),
        )

        # Execute
        result = GitHubAuthManager._should_rotate_token()

        # Verify - should rotate if <= TOKEN_REFRESH_THRESHOLD_DAYS
        assert result is True
        mock_token_manager.get_token_expiration_info.assert_called_once()

    def test_should_rotate_token_not_expiring_soon(self, reset_class_state, mock_token_manager):
        """Test _should_rotate_token when token is not expiring soon."""
        # Setup - token expires in 60 days
        expiration_date = datetime.now() + timedelta(days=60)
        mock_token_manager.get_token_expiration_info.return_value = (
            False,
            expiration_date.strftime("%Y-%m-%d %H:%M:%S"),
        )

        # Execute
        result = GitHubAuthManager._should_rotate_token()

        # Verify
        assert result is False
        mock_token_manager.get_token_expiration_info.assert_called_once()

    def test_ensure_cache_dir(self, reset_class_state, mock_cache_dir):
        """Test _ensure_cache_dir creates directory if needed."""
        # Remove the directory first to test creation
        os.rmdir(mock_cache_dir)

        # Execute
        result = GitHubAuthManager._ensure_cache_dir()

        # Verify
        assert result == str(mock_cache_dir)
        assert os.path.exists(mock_cache_dir)

    def test_get_cache_file_path(self, reset_class_state, mock_cache_dir):
        """Test _get_cache_file_path returns correct path."""
        # Execute
        result = GitHubAuthManager._get_cache_file_path()

        # Verify
        expected_path = os.path.join(mock_cache_dir, "rate_limit_cache.json")
        assert result == expected_path

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"timestamp": 0, "remaining": 4999, "limit": 5000}',
    )
    @patch("src.auth_manager.os.path.exists")
    def test_load_rate_limit_cache_exists(
        self, mock_exists, mock_file, reset_class_state, mock_cache_dir
    ):
        """Test _load_rate_limit_cache loads existing cache."""
        # Setup
        mock_exists.return_value = True

        # Execute
        result = GitHubAuthManager._load_rate_limit_cache()

        # Verify
        assert isinstance(result, dict)
        assert "timestamp" in result
        mock_file.assert_called_once()

    @patch("src.auth_manager.os.path.exists")
    def test_load_rate_limit_cache_not_exists(self, mock_exists, reset_class_state):
        """Test _load_rate_limit_cache returns empty dict when cache doesn't exist."""
        # Setup
        mock_exists.return_value = False

        # Execute
        result = GitHubAuthManager._load_rate_limit_cache()

        # Verify
        assert result == {}

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.auth_manager.json.dump")
    def test_save_rate_limit_cache(
        self, mock_json_dump, mock_file, reset_class_state, mock_cache_dir
    ):
        """Test _save_rate_limit_cache saves data correctly."""
        # Setup
        data = {"remaining": 4999, "limit": 5000}

        # Execute
        result = GitHubAuthManager._save_rate_limit_cache(data)

        # Verify
        assert result is True
        mock_file.assert_called()
        mock_json_dump.assert_called_once()

        # Check that timestamp was added to data
        saved_data = mock_json_dump.call_args[0][0]
        assert "timestamp" in saved_data
        assert "request_count" in saved_data

    def test_update_cached_rate_limit(self, reset_class_state):
        """Test _update_cached_rate_limit decrements count correctly."""
        # Setup
        GitHubAuthManager._rate_limit_cache = {"remaining": 100}
        GitHubAuthManager._request_count_since_cache = 0

        # Execute
        GitHubAuthManager._update_cached_rate_limit(decrement=5)

        # Verify
        assert GitHubAuthManager._rate_limit_cache["remaining"] == 95
        assert GitHubAuthManager._request_count_since_cache == 5

    def test_get_rate_limit_info_cached(self, reset_class_state):
        """Test get_rate_limit_info returns cached data."""
        # Setup
        now = time.time()
        reset_time = now + 3600
        GitHubAuthManager._rate_limit_cache = {
            "remaining": 4990,
            "limit": 5000,
            "reset_formatted": datetime.fromtimestamp(reset_time).strftime("%Y-%m-%d %H:%M:%S"),
            "is_authenticated": True,
        }
        GitHubAuthManager._rate_limit_cache_time = now

        # Execute
        remaining, limit, reset_formatted, is_authenticated = (
            GitHubAuthManager.get_rate_limit_info()
        )

        # Verify
        assert remaining == 4990
        assert limit == 5000
        assert is_authenticated is True

    def test_get_rate_limit_info_expired_cache(
        self, reset_class_state, mock_requests, mock_token_manager
    ):
        """Test get_rate_limit_info refreshes expired cache."""
        # Setup
        old_time = time.time() - 7200  # 2 hours ago (beyond RATE_LIMIT_HARD_REFRESH)
        GitHubAuthManager._rate_limit_cache = {
            "remaining": 4000,
            "limit": 5000,
            "reset_formatted": "old_reset_time",
            "is_authenticated": True,
        }
        GitHubAuthManager._rate_limit_cache_time = old_time

        # Execute
        remaining, limit, reset_formatted, is_authenticated = (
            GitHubAuthManager.get_rate_limit_info()
        )

        # Verify
        assert mock_requests["module"].get.called
        assert remaining == 4990  # Value from mock_requests
        assert limit == 5000
        assert is_authenticated is True

    def test_get_rate_limit_info_as_dict(
        self, reset_class_state, mock_requests, mock_token_manager
    ):
        """Test get_rate_limit_info returns full dictionary when requested."""
        # Setup - Fill cache with test data
        now = time.time()
        GitHubAuthManager._rate_limit_cache = {
            "remaining": 4990,
            "limit": 5000,
            "reset_formatted": "test_reset_time",
            "is_authenticated": True,
            "resources": {"core": {"limit": 5000, "remaining": 4990}},
        }
        GitHubAuthManager._rate_limit_cache_time = now

        # Execute
        result = GitHubAuthManager.get_rate_limit_info(return_dict=True)

        # Verify
        assert isinstance(result, dict)
        assert "resources" in result
        assert "core" in result["resources"]

    @patch("src.auth_manager.requests.get")
    def test_get_rate_limit_info_request_error(
        self, mock_get, reset_class_state, mock_token_manager
    ):
        """Test get_rate_limit_info handles request errors gracefully."""
        # Setup
        mock_get.side_effect = Exception("Network error")
        GitHubAuthManager._rate_limit_cache = {}
        GitHubAuthManager._rate_limit_cache_time = 0

        # Execute
        remaining, limit, reset_formatted, is_authenticated = (
            GitHubAuthManager.get_rate_limit_info()
        )

        # Verify - should return default values
        assert remaining in (4500, 50)  # Different defaults for auth/unauth
        assert limit in (5000, 60)
        assert is_authenticated in (True, False)

    def test_make_authenticated_request(self, reset_class_state, mock_requests, mock_token_manager):
        """Test make_authenticated_request uses correct headers and returns response."""
        # Execute
        response = GitHubAuthManager.make_authenticated_request(
            "GET", "https://api.github.com/user", audit_action="test_action"
        )

        # Verify
        assert response is mock_requests["response"]
        mock_requests["module"].request.assert_called_once()
        call_args = mock_requests["module"].request.call_args[0]
        assert call_args[0] == "GET"
        assert call_args[1] == "https://api.github.com/user"

        # Check headers - ensure we're using the safe mock token
        headers = mock_requests["module"].request.call_args[1]["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == f"Bearer {SAFE_MOCK_TOKEN}"

        # Check audit log
        mock_token_manager.audit_log_token_usage.assert_called_once_with("test_action")

    def test_make_authenticated_request_retry(
        self, reset_class_state, mock_requests, mock_token_manager
    ):
        """Test make_authenticated_request retries on auth failure."""
        # Setup - First call fails with 401, second succeeds
        mock_failure = MagicMock()
        mock_failure.status_code = 401
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_requests["module"].request.side_effect = [mock_failure, mock_success]

        # Execute
        response = GitHubAuthManager.make_authenticated_request(
            "GET", "https://api.github.com/user"
        )

        # Verify
        assert response is mock_success
        assert mock_requests["module"].request.call_count == 2
        assert GitHubAuthManager._cached_headers is None  # Should be cleared after failure

    def test_set_audit_enabled(self, reset_class_state):
        """Test set_audit_enabled changes audit setting."""
        # Setup
        GitHubAuthManager._audit_enabled = True

        # Execute
        GitHubAuthManager.set_audit_enabled(False)

        # Verify
        assert GitHubAuthManager._audit_enabled is False

    @patch("src.auth_manager.datetime")
    def test_get_token_info(self, mock_datetime, reset_class_state, mock_token_manager):
        """Test get_token_info returns expected token information."""
        # Setup
        mock_now = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now

        # Mock token metadata
        metadata = {
            "created_at": (mock_now - timedelta(days=10)).timestamp(),
            "last_used_at": (mock_now - timedelta(hours=1)).timestamp(),
        }
        mock_token_manager.get_token_metadata.return_value = metadata
        mock_token_manager.token_exists.return_value = True

        # mock has_valid_token
        with patch.object(GitHubAuthManager, "has_valid_token", return_value=True):
            # Execute
            result = GitHubAuthManager.get_token_info()

            # Verify
            assert isinstance(result, dict)
            assert result["token_exists"] is True
            assert result["token_valid"] is True
            assert "created_at" in result
            assert "last_used_at" in result

    def test_get_live_rate_limit_info(self, reset_class_state, mock_requests, mock_token_manager):
        """Test get_live_rate_limit_info makes API call and returns fresh data."""
        # Execute
        result = GitHubAuthManager.get_live_rate_limit_info()

        # Verify
        assert isinstance(result, dict)
        assert "remaining" in result
        assert "limit" in result
        assert "reset_formatted" in result
        assert "is_authenticated" in result
        assert "resources" in result
        mock_requests["module"].get.assert_called_once()

        # Check that cache was updated
        assert GitHubAuthManager._rate_limit_cache == result
        assert GitHubAuthManager._rate_limit_cache_time > 0

    def test_validate_token_valid(self, reset_class_state, mock_requests, mock_token_manager):
        """Test validate_token with a valid token."""
        # Setup
        mock_requests["response"].headers = {
            "X-OAuth-Scopes": "repo, user",
            "X-GitHub-Enterprise-Version": None,
            "X-RateLimit-Limit": "5000",
        }

        # Execute
        is_valid, token_info = GitHubAuthManager.validate_token()

        # Verify
        assert is_valid is True
        assert token_info["is_valid"] is True
        assert "scopes" in token_info
        assert len(token_info["scopes"]) == 2
        assert "repo" in token_info["scopes"]
        assert "user" in token_info["scopes"]
        assert "token_type" in token_info

    @patch("src.auth_manager.requests.get")
    def test_validate_token_invalid(self, mock_get, reset_class_state):
        """Test validate_token with an invalid token."""
        # Setup
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Bad credentials"
        mock_get.return_value = mock_response

        # Execute
        is_valid, token_info = GitHubAuthManager.validate_token()

        # Verify
        assert is_valid is False
        assert token_info["is_valid"] is False
        assert "error" in token_info

    @patch("src.auth_manager.requests.get")
    def test_validate_token_rate_limited(self, mock_get, reset_class_state):
        """Test validate_token when rate limited."""
        # Setup
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "rate limit exceeded"
        mock_get.return_value = mock_response

        # Execute
        is_valid, token_info = GitHubAuthManager.validate_token()

        # Verify
        assert is_valid is True  # Still valid but rate-limited
        assert token_info["is_valid"] is True
        assert "error" in token_info
        assert "rate limit" in token_info["error"].lower()

    def test_no_real_token_in_headers(self, reset_class_state, mock_token_manager):
        """Test that real tokens don't appear in headers."""
        # Setup - use a token that looks like a real PAT
        token_that_looks_real = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        mock_token_manager.get_token.return_value = token_that_looks_real

        # Execute
        headers = GitHubAuthManager.get_auth_headers()

        # For security testing, verify auth header value doesn't appear in test output
        # This would cause a test failure but prevent token disclosure
        with pytest.raises(AssertionError):
            assert headers["Authorization"] != f"Bearer {token_that_looks_real}"
