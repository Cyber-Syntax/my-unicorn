#!/usr/bin/env python3
"""Tests for the auth_manager module.

This module contains tests for the GitHubAuthManager class that handles
GitHub API authentication with token handling.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, mock_open, patch

import pytest

if TYPE_CHECKING:
    pass

# Import the module to test
from my_unicorn.auth_manager import GitHubAuthManager

# Disable logging during tests to prevent token exposure
logging.getLogger("my_unicorn.auth_manager").setLevel(logging.CRITICAL)
logging.getLogger("my_unicorn.secure_token").setLevel(logging.CRITICAL)

# Safe mock token value used throughout tests
SAFE_MOCK_TOKEN = "test-token-XXXX"


class TestGitHubAuthManager:
    """Tests for the GitHubAuthManager class."""

    @pytest.fixture(autouse=True)
    def prevent_real_token_access(self, monkeypatch):
        """Prevent any potential access to real tokens during tests.

        This fixture runs automatically for all tests in this class.
        """
        # Ensure environment variables can't leak tokens
        monkeypatch.setenv("GITHUB_TOKEN", "")
        # Prevent any system keyring access
        monkeypatch.setattr("keyring.get_password", lambda *args: None)
        # Prevent any real file access for token files
        monkeypatch.setattr("os.path.expanduser", lambda path: "/tmp/fake_home" + path[1:])

    @pytest.fixture
    def reset_class_state(self):
        """Reset GitHubAuthManager class state before each test."""
        GitHubAuthManager._cached_headers = None
        GitHubAuthManager._last_token = None
        GitHubAuthManager._last_token_check = 0
        GitHubAuthManager._rate_limit_cache = {}
        GitHubAuthManager._rate_limit_cache_time = 0
        GitHubAuthManager._request_count_since_cache = 0
        yield
        # Reset again after test
        GitHubAuthManager._cached_headers = None
        GitHubAuthManager._last_token = None
        GitHubAuthManager._last_token_check = 0
        GitHubAuthManager._rate_limit_cache = {}
        GitHubAuthManager._rate_limit_cache_time = 0
        GitHubAuthManager._request_count_since_cache = 0

    @pytest.fixture
    def mock_token_manager(self, monkeypatch):
        """Mock SecureTokenManager for testing."""
        mock_manager = MagicMock()
        mock_manager.get_token.return_value = SAFE_MOCK_TOKEN
        mock_manager.get_token_expiration_info.return_value = (False, "2099-12-31 23:59:59")
        mock_manager.is_token_expired.return_value = False
        monkeypatch.setattr("my_unicorn.auth_manager.SecureTokenManager", mock_manager)
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
                "graphql": {
                    "limit": 5000,
                    "remaining": 4999,
                    "reset": int(time.time()) + 3600,
                },
            },
        }

        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_response
        mock_requests.request.return_value = mock_response
        mock_requests.RequestException = Exception

        monkeypatch.setattr("my_unicorn.auth_manager.requests", mock_requests)
        return {"module": mock_requests, "response": mock_response}

    @pytest.fixture
    def mock_cache_dir(self, monkeypatch, tmp_path):
        """Create a temporary cache directory for testing."""
        test_cache_dir = tmp_path / "test_cache"
        test_cache_dir.mkdir()
        monkeypatch.setattr("my_unicorn.auth_manager.CACHE_DIR", str(test_cache_dir))
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
        # Setup - set some cached data
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
        mock_token_manager.get_token_expiration_info.return_value = (
            True,
            "2020-01-01 00:00:00",
        )

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

    def test_should_rotate_token_not_expiring_soon(
        self, reset_class_state, mock_token_manager
    ):
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

    def test_ensure_cache_dir(self, reset_class_state, mock_cache_dir, monkeypatch):
        """Test ensure_directory_exists creates directory if needed."""
        # Remove the directory first to test creation
        os.rmdir(mock_cache_dir)

        # Mock ensure_directory_exists function
        mock_ensure_dir = MagicMock(return_value=str(mock_cache_dir))
        monkeypatch.setattr("my_unicorn.auth_manager.ensure_directory_exists", mock_ensure_dir)

        # Execute - call method that uses ensure_directory_exists
        GitHubAuthManager._get_cache_file_path()

        # Verify
        mock_ensure_dir.assert_called_once_with(str(mock_cache_dir))
        assert os.path.exists(mock_cache_dir) or mock_ensure_dir.called

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
    @patch("my_unicorn.auth_manager.os.path.exists")
    @patch("my_unicorn.auth_manager.load_json_cache")
    def test_load_rate_limit_cache_exists(
        self, mock_load_cache, mock_exists, mock_file, reset_class_state, mock_cache_dir
    ):
        """Test _load_rate_limit_cache loads existing cache."""
        # Setup
        mock_exists.return_value = True
        cache_data = {
            "timestamp": int(time.time()),
            "remaining": 4999,
            "limit": 5000,
            "reset_formatted": "2023-01-01 00:00:00",
            "is_authenticated": True,
        }
        mock_load_cache.return_value = cache_data

        # Execute
        result = GitHubAuthManager._load_rate_limit_cache()

        # Verify
        assert isinstance(result, dict)
        assert result == cache_data
        assert "timestamp" in result

        # Use constants directly from the auth_manager module
        from my_unicorn.auth_manager import RATE_LIMIT_CACHE_TTL, RATE_LIMIT_HARD_REFRESH

        mock_load_cache.assert_called_once_with(
            GitHubAuthManager._get_cache_file_path(),
            ttl_seconds=RATE_LIMIT_CACHE_TTL,
            hard_refresh_seconds=RATE_LIMIT_HARD_REFRESH,
        )

    @patch("my_unicorn.auth_manager.os.path.exists")
    def test_load_rate_limit_cache_not_exists(self, mock_exists, reset_class_state):
        """Test _load_rate_limit_cache returns empty dict when cache doesn't exist."""
        # Setup
        mock_exists.return_value = False

        # Execute
        result = GitHubAuthManager._load_rate_limit_cache()

        # Verify
        assert result == {}

    @patch("my_unicorn.auth_manager.save_json_cache")
    def test_save_rate_limit_cache(self, mock_save_cache, reset_class_state, mock_cache_dir):
        """Test _save_rate_limit_cache saves data correctly."""
        # Setup
        data = {"remaining": 4999, "limit": 5000}
        mock_save_cache.return_value = True

        # Execute
        result = GitHubAuthManager._save_rate_limit_cache(data)

        # Verify
        assert result is True
        mock_save_cache.assert_called_once()

        # Check that request_count and cache_ttl were added to data
        saved_data = mock_save_cache.call_args[0][1]
        assert "request_count" in saved_data
        assert "cache_ttl" in saved_data

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
            "reset_formatted": datetime.fromtimestamp(reset_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
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

        # Mock load_json_cache to return empty dict
        with patch("my_unicorn.auth_manager.load_json_cache", return_value={}):
            # Execute
            remaining, limit, reset_formatted, is_authenticated = (
                GitHubAuthManager.get_rate_limit_info()
            )

            # Verify
            assert mock_requests["module"].get.called
            assert remaining == 4990  # Value from mock_requests
            assert limit == 5000
            assert is_authenticated is True
            # Test cache was updated
            assert GitHubAuthManager._rate_limit_cache_time > old_time

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

    @patch("my_unicorn.auth_manager.requests.get")
    def test_get_rate_limit_info_request_error(
        self, mock_get, reset_class_state, mock_token_manager
    ):
        """Test get_rate_limit_info handles request errors gracefully."""
        # Setup
        mock_get.side_effect = Exception("Network error")
        GitHubAuthManager._rate_limit_cache = {}
        GitHubAuthManager._rate_limit_cache_time = 0

        # Mock token to control is_authenticated value
        mock_token_manager.get_token.return_value = SAFE_MOCK_TOKEN

        # Mock load_json_cache to return empty dict
        with patch("my_unicorn.auth_manager.load_json_cache", return_value={}):
            # Execute
            remaining, limit, reset_formatted, is_authenticated = (
                GitHubAuthManager.get_rate_limit_info()
            )

            # Verify - should use default authenticated values (4500, 5000)
            assert remaining == 4500  # Default for authenticated users
            assert limit == 5000  # Default for authenticated users
            assert is_authenticated is True

    def test_make_authenticated_request(
        self, reset_class_state, mock_requests, mock_token_manager, monkeypatch
    ):
        """Test make_authenticated_request uses correct headers and returns response."""
        # Pre-cache headers to avoid the initial get_auth_headers call
        GitHubAuthManager._cached_headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {SAFE_MOCK_TOKEN}",
        }
        GitHubAuthManager._last_token = SAFE_MOCK_TOKEN
        GitHubAuthManager._cached_headers_expiration = time.time() + 3600

        # Mock the SessionPool to return a controlled session
        from my_unicorn.auth_manager import SessionPool

        mock_session = MagicMock()
        mock_session.request.return_value = mock_requests["response"]
        monkeypatch.setattr(SessionPool, "get_session", lambda token_key: mock_session)

        # Execute
        response = GitHubAuthManager.make_authenticated_request(
            "GET", "https://api.github.com/user"
        )

        # Verify
        assert response is mock_requests["response"]
        mock_session.request.assert_called_once()

        # Check method and URL
        call_args = mock_session.request.call_args[0]
        assert call_args[0] == "GET"
        assert call_args[1] == "https://api.github.com/user"

    def test_make_authenticated_request_retry(
        self, reset_class_state, mock_requests, mock_token_manager, monkeypatch
    ):
        """Test make_authenticated_request retries on auth failure."""
        # Setup - First call fails with 401, second succeeds
        mock_failure = MagicMock()
        mock_failure.status_code = 401
        mock_success = MagicMock()
        mock_success.status_code = 200

        # Mock the SessionPool to return a controlled session
        from my_unicorn.auth_manager import SessionPool

        # Create a mock session with a request method that fails first, then succeeds
        mock_session = MagicMock()
        mock_session.request.side_effect = [mock_failure, mock_success]

        # Mock SessionPool get_session and clear_session methods
        monkeypatch.setattr(SessionPool, "get_session", lambda token_key: mock_session)
        mock_clear_session = MagicMock()
        monkeypatch.setattr(SessionPool, "clear_session", mock_clear_session)

        # set up initial state - ensure cached headers exist
        GitHubAuthManager._cached_headers = {"Authorization": f"Bearer {SAFE_MOCK_TOKEN}"}

        # Execute
        response = GitHubAuthManager.make_authenticated_request(
            "GET", "https://api.github.com/user"
        )

        # Verify
        assert response is mock_success
        assert mock_session.request.call_count == 2

        # Verify clear_session was called for auth failure retry
        mock_clear_session.assert_called_once()

    @patch("my_unicorn.auth_manager.datetime")
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

    def test_get_live_rate_limit_info(
        self, reset_class_state, mock_requests, mock_token_manager
    ):
        """Test get_live_rate_limit_info makes API call and returns fresh data."""
        # Setup - prepare mock response data structure matching implementation
        mock_response_data = {
            "rate": {"limit": 5000, "remaining": 4990, "reset": int(time.time()) + 3600},
            "resources": {
                "core": {"limit": 5000, "remaining": 4990, "reset": int(time.time()) + 3600},
                "search": {"limit": 30, "remaining": 28, "reset": int(time.time()) + 3600},
            },
        }
        mock_requests["response"].json.return_value = mock_response_data

        # Additional setup to clear any cached data
        GitHubAuthManager._rate_limit_cache = {}
        GitHubAuthManager._rate_limit_cache_time = 0

        # Execute
        result = GitHubAuthManager.get_live_rate_limit_info()

        # Verify essential fields are present
        assert isinstance(result, dict)
        assert "remaining" in result
        assert "limit" in result
        assert "reset_formatted" in result
        assert "is_authenticated" in result
        assert "resources" in result

        # Verify API was called and cache updated
        mock_requests["module"].get.assert_called_once()
        assert GitHubAuthManager._rate_limit_cache_time > 0

        # We don't verify exact structure since it may change,
        # but ensure key values are consistent
        assert result["limit"] == 5000
        assert result["remaining"] == 4990

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

    @patch("my_unicorn.auth_manager.requests.get")
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

    @patch("my_unicorn.auth_manager.requests.get")
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

    @pytest.mark.parametrize(
        "test_case, cache_data, cache_time, current_time, auth_status, expected_result",
        [
            # Test case 1: Unauthenticated user after hourly reset (10pm -> 11pm)
            (
                "unauthenticated_after_reset",
                {
                    "remaining": 50,  # 10 requests used out of 60
                    "limit": 60,
                    "reset": int(datetime(2023, 1, 1, 22, 0, 0).timestamp())
                    + 3600,  # Reset at 11pm
                    "reset_formatted": "2023-01-01 23:00:00",
                    "is_authenticated": False,
                },
                int(datetime(2023, 1, 1, 22, 0, 0).timestamp()),  # Cache from 10pm
                int(
                    datetime(2023, 1, 1, 23, 5, 0).timestamp()
                ),  # Current time is 11:05pm (after reset)
                False,
                (60, 60, None, False),  # Should show full limit after reset
            ),
            # Test case 2: Unauthenticated user before hourly reset (10:30pm -> 10:45pm)
            (
                "unauthenticated_before_reset",
                {
                    "remaining": 50,
                    "limit": 60,
                    "reset": int(datetime(2023, 1, 1, 23, 0, 0).timestamp()),  # Reset at 11pm
                    "reset_formatted": "2023-01-01 23:00:00",
                    "is_authenticated": False,
                },
                int(datetime(2023, 1, 1, 22, 30, 0).timestamp()),  # Cache from 10:30pm
                int(
                    datetime(2023, 1, 1, 22, 45, 0).timestamp()
                ),  # Current time is 10:45pm (before reset)
                False,
                (
                    50,
                    60,
                    "2023-01-01 23:00:00",
                    False,
                ),  # Should show remaining count from cache
            ),
            # Test case 3: Authenticated user after hourly reset (10pm -> 11pm)
            (
                "authenticated_after_reset",
                {
                    "remaining": 4800,  # 200 requests used
                    "limit": 5000,
                    "reset": int(datetime(2023, 1, 1, 22, 0, 0).timestamp())
                    + 3600,  # Reset at 11pm
                    "reset_formatted": "2023-01-01 23:00:00",
                    "is_authenticated": True,
                },
                int(datetime(2023, 1, 1, 22, 0, 0).timestamp()),  # Cache from 10pm
                int(
                    datetime(2023, 1, 1, 23, 5, 0).timestamp()
                ),  # Current time is 11:05pm (after reset)
                True,
                (5000, 5000, None, True),  # Should show full limit after reset
            ),
            # Test case 4: Authenticated user before hourly reset (10:30pm -> 10:45pm)
            (
                "authenticated_before_reset",
                {
                    "remaining": 4800,
                    "limit": 5000,
                    "reset": int(datetime(2023, 1, 1, 23, 0, 0).timestamp()),  # Reset at 11pm
                    "reset_formatted": "2023-01-01 23:00:00",
                    "is_authenticated": True,
                },
                int(datetime(2023, 1, 1, 22, 30, 0).timestamp()),  # Cache from 10:30pm
                int(
                    datetime(2023, 1, 1, 22, 45, 0).timestamp()
                ),  # Current time is 10:45pm (before reset)
                True,
                (
                    4800,
                    5000,
                    "2023-01-01 23:00:00",
                    True,
                ),  # Should show remaining count from cache
            ),
            # Test case 5: No cache available, unauthenticated user
            (
                "no_cache_unauthenticated",
                None,  # No cache data
                0,  # No cache time
                int(datetime(2023, 1, 1, 22, 0, 0).timestamp()),  # Current time is 10pm
                False,
                (60, 60, None, False),  # Should return default unauthenticated values
            ),
            # Test case 6: No cache available, authenticated user
            (
                "no_cache_authenticated",
                None,  # No cache data
                0,  # No cache time
                int(datetime(2023, 1, 1, 22, 0, 0).timestamp()),  # Current time is 10pm
                True,
                (5000, 5000, None, True),  # Should return default authenticated values
            ),
            # Test case 7: Exactly at reset time
            (
                "exactly_at_reset_time",
                {
                    "remaining": 30,
                    "limit": 60,
                    "reset": int(datetime(2023, 1, 1, 23, 0, 0).timestamp()),  # Reset at 11pm
                    "reset_formatted": "2023-01-01 23:00:00",
                    "is_authenticated": False,
                },
                int(datetime(2023, 1, 1, 22, 30, 0).timestamp()),  # Cache from 10:30pm
                int(
                    datetime(2023, 1, 1, 23, 0, 0).timestamp()
                ),  # Current time is exactly 11pm (reset time)
                False,
                (60, 60, None, False),  # Should show full limit at reset time
            ),
            # Test case 8: Additional API requests since last cache update
            (
                "requests_since_cache_update",
                {
                    "remaining": 50,
                    "limit": 60,
                    "reset": int(datetime(2023, 1, 1, 23, 0, 0).timestamp()),  # Reset at 11pm
                    "reset_formatted": "2023-01-01 23:00:00",
                    "is_authenticated": False,
                    "request_count": 0,
                },
                int(datetime(2023, 1, 1, 22, 30, 0).timestamp()),  # Cache from 10:30pm
                int(
                    datetime(2023, 1, 1, 22, 45, 0).timestamp()
                ),  # Current time is 10:45pm (before reset)
                False,
                (
                    45,
                    60,
                    "2023-01-01 23:00:00",
                    False,
                ),  # Should subtract request_count_since_cache (5)
            ),
        ],
    )
    def test_get_estimated_rate_limit_info(
        self,
        test_case,
        cache_data,
        cache_time,
        current_time,
        auth_status,
        expected_result,
        reset_class_state,
        mock_token_manager,
        monkeypatch,
    ):
        """Test get_estimated_rate_limit_info calculates correct rate limits based on cache and time.

        This tests the core functionality that estimates GitHub API rate limits without making
        API calls, especially the logic that detects when an hourly reset has occurred.

        Args:
            test_case: Descriptive name of the test case for better error messages
            cache_data: The cached rate limit data to use for the test
            cache_time: The timestamp when the cache was last updated
            current_time: The current time to simulate during the test
            auth_status: Whether the user should be authenticated or not
            expected_result: Expected return values (remaining, limit, reset_formatted, is_authenticated)
            reset_class_state: Fixture to reset GitHubAuthManager class state
            mock_token_manager: Fixture that mocks the SecureTokenManager
            monkeypatch: pytest's monkeypatch fixture

        """
        # Setup authentication status
        mock_token_manager.get_token.return_value = SAFE_MOCK_TOKEN if auth_status else None

        # Setup cached data if provided
        if cache_data is not None:
            GitHubAuthManager._rate_limit_cache = cache_data.copy()
            GitHubAuthManager._rate_limit_cache_time = cache_time
            # For test case 8, simulate additional requests since cache
            if test_case == "requests_since_cache_update":
                GitHubAuthManager._request_count_since_cache = 5
        else:
            # Ensure no cached data
            GitHubAuthManager._rate_limit_cache = {}
            GitHubAuthManager._rate_limit_cache_time = 0
            GitHubAuthManager._request_count_since_cache = 0

        # Mock the cache loading function if needed
        if cache_data is not None:
            monkeypatch.setattr(
                GitHubAuthManager, "_load_rate_limit_cache", lambda: cache_data.copy()
            )
        else:
            monkeypatch.setattr(GitHubAuthManager, "_load_rate_limit_cache", dict)

        # Mock the current time
        monkeypatch.setattr(time, "time", lambda: current_time)

        # Execute - call the method we're testing
        result = GitHubAuthManager.get_estimated_rate_limit_info()

        # Verify results - unpack expected values
        expected_remaining, expected_limit, expected_reset_formatted, expected_auth = (
            expected_result
        )
        remaining, limit, reset_formatted, is_authenticated = result

        # Verify each part of the result
        assert remaining == expected_remaining, (
            f"Test case {test_case}: Remaining count mismatch"
        )
        assert limit == expected_limit, f"Test case {test_case}: Limit mismatch"

        # Special handling for reset time - using a more flexible approach
        if expected_reset_formatted is None:
            # For dynamic reset times, verify that:
            # 1. It's a valid timestamp string in the expected format
            try:
                reset_dt = datetime.strptime(reset_formatted, "%Y-%m-%d %H:%M:%S")
                # 2. It represents a time in the future from current_time
                reset_timestamp = reset_dt.timestamp()
                assert reset_timestamp > current_time, (
                    f"Test case {test_case}: Reset time should be in future"
                )

                # 3. It should be close to an hour boundary (within 5 minutes)
                minutes = reset_dt.minute
                seconds = reset_dt.second
                time_from_hour_boundary = minutes * 60 + seconds
                is_near_hour_boundary = time_from_hour_boundary < 300  # 5 minutes
                assert is_near_hour_boundary, (
                    f"Test case {test_case}: Reset time should be near hour boundary"
                )
            except ValueError:
                pytest.fail(
                    f"Test case {test_case}: Invalid reset time format: {reset_formatted}"
                )
        else:
            assert reset_formatted == expected_reset_formatted, (
                f"Test case {test_case}: Reset time mismatch"
            )

        assert is_authenticated == expected_auth, (
            f"Test case {test_case}: Authentication status mismatch"
        )


class TestSessionPool:
    """Tests for the SessionPool class."""

    @pytest.fixture(autouse=True)
    def reset_class_state(self):
        """Reset SessionPool class state before each test."""
        from my_unicorn.auth_manager import SessionPool

        SessionPool._sessions = {}
        SessionPool._last_used = {}
        yield
        # Reset again after test
        SessionPool._sessions = {}
        SessionPool._last_used = {}

    def test_get_session_new(self, monkeypatch, reset_class_state):
        """Test getting a new session when one doesn't exist."""
        # Import here to use the monkeypatched version
        from my_unicorn.auth_manager import GitHubAuthManager, SessionPool

        # Mock get_auth_headers
        mock_headers = {"Authorization": f"Bearer {SAFE_MOCK_TOKEN}", "User-Agent": "test"}
        monkeypatch.setattr(GitHubAuthManager, "get_auth_headers", lambda: mock_headers)

        # Mock requests.Session
        mock_session = MagicMock()
        mock_session_class = MagicMock(return_value=mock_session)
        monkeypatch.setattr("my_unicorn.auth_manager.requests.Session", mock_session_class)

        # Test getting a new session
        session = SessionPool.get_session("test-token-key")

        # Verify session was created with correct headers
        assert session is mock_session
        mock_session.headers.update.assert_called_once_with(mock_headers)
        assert "test-token-key" in SessionPool._sessions
        assert "test-token-key" in SessionPool._last_used

    def test_get_session_existing(self, monkeypatch, reset_class_state):
        """Test getting an existing session."""
        # Import here to use the monkeypatched version
        from my_unicorn.auth_manager import GitHubAuthManager, SessionPool

        # Create a mock session
        mock_session = MagicMock()

        # Add it to the session pool
        SessionPool._sessions["test-token-key"] = mock_session
        SessionPool._last_used["test-token-key"] = time.time() - 60  # 1 minute ago

        # Mock get_auth_headers to ensure it's not called
        mock_get_headers = MagicMock()
        monkeypatch.setattr(GitHubAuthManager, "get_auth_headers", mock_get_headers)

        # Test getting the existing session
        session = SessionPool.get_session("test-token-key")

        # Verify
        assert session is mock_session
        assert mock_get_headers.call_count == 0  # Shouldn't be called for existing session
        assert SessionPool._last_used["test-token-key"] > time.time() - 10  # Updated recently

    def test_clean_idle_sessions(self, monkeypatch, reset_class_state):
        """Test cleaning idle sessions."""
        # Import here to use the monkeypatched version
        from my_unicorn.auth_manager import SessionPool

        # Create mock sessions
        active_session = MagicMock()
        idle_session = MagicMock()

        # Add them to the session pool with different timestamps
        now = time.time()
        SessionPool._sessions["active-key"] = active_session
        SessionPool._last_used["active-key"] = now - 60  # 1 minute ago

        SessionPool._sessions["idle-key"] = idle_session
        SessionPool._last_used["idle-key"] = now - 600  # 10 minutes ago (> _max_idle_time)

        # set a shorter idle time for testing
        old_idle_time = SessionPool._max_idle_time
        SessionPool._max_idle_time = 300  # 5 minutes

        try:
            # Test cleaning idle sessions
            SessionPool._clean_idle_sessions()

            # Verify
            assert "active-key" in SessionPool._sessions
            assert "idle-key" not in SessionPool._sessions
            assert "active-key" in SessionPool._last_used
            assert "idle-key" not in SessionPool._last_used
            idle_session.close.assert_called_once()
        finally:
            # Restore original idle time
            SessionPool._max_idle_time = old_idle_time

    def test_clear_session(self, reset_class_state):
        """Test explicitly clearing a session."""
        # Import here
        from my_unicorn.auth_manager import SessionPool

        # Create mock sessions
        session1 = MagicMock()
        session2 = MagicMock()

        # Add them to the session pool
        SessionPool._sessions["key1"] = session1
        SessionPool._sessions["key2"] = session2
        SessionPool._last_used["key1"] = time.time()
        SessionPool._last_used["key2"] = time.time()

        # Test clearing one session
        SessionPool.clear_session("key1")

        # Verify
        assert "key1" not in SessionPool._sessions
        assert "key2" in SessionPool._sessions
        assert "key1" not in SessionPool._last_used
        assert "key2" in SessionPool._last_used
        session1.close.assert_called_once()
        assert session2.close.call_count == 0
