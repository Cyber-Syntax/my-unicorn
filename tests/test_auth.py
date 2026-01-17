"""Tests for GitHubAuthManager: token management and rate limit logic."""

from unittest.mock import patch

import pytest

from my_unicorn.core.auth import GitHubAuthManager, validate_github_token
from my_unicorn.core.token import (
    KeyringAccessError,
    KeyringUnavailableError,
    setup_keyring,
)


class MockTokenStore:
    """Mock token store for testing."""

    def __init__(self, initial_token: str | None = None) -> None:
        """Initialize mock token store.

        Args:
            initial_token: Initial token value for testing.

        """
        self._token = initial_token
        self.get_called = False
        self.set_called = False
        self.delete_called = False

    def get(self) -> str | None:
        """Get stored token."""
        self.get_called = True
        return self._token

    def set(self, token: str) -> None:
        """Set token."""
        self.set_called = True
        self._token = token

    def delete(self) -> None:
        """Delete token."""
        self.delete_called = True
        self._token = None


@pytest.fixture
def mock_token_store():
    """Fixture for mock token store."""
    return MockTokenStore()


@pytest.fixture
def auth_manager(mock_token_store):
    """Fixture for GitHubAuthManager instance with mock token store."""
    return GitHubAuthManager(mock_token_store)


def test_get_token(mock_token_store):
    """Test get_token returns token from store."""
    mock_token_store._token = "abc123"
    auth_manager = GitHubAuthManager(mock_token_store)
    assert auth_manager.get_token() == "abc123"
    assert mock_token_store.get_called


def test_get_token_none(mock_token_store):
    """Test get_token returns None if not found."""
    mock_token_store._token = None
    auth_manager = GitHubAuthManager(mock_token_store)
    assert auth_manager.get_token() is None


def test_apply_auth_adds_auth_header(mock_token_store):
    """Test apply_auth adds Authorization header if token exists."""
    mock_token_store._token = "abc123"
    auth_manager = GitHubAuthManager(mock_token_store)
    headers = {}
    result = auth_manager.apply_auth(headers)
    assert result["Authorization"] == "Bearer abc123"


def test_apply_auth_without_token(mock_token_store):
    """Test apply_auth does not add header if token missing."""
    mock_token_store._token = None
    auth_manager = GitHubAuthManager(mock_token_store)
    headers = {}
    result = auth_manager.apply_auth(headers)
    assert "Authorization" not in result


def test_update_rate_limit_info_valid(auth_manager):
    """Test update_rate_limit_info parses headers correctly."""
    headers = {
        "X-RateLimit-Remaining": "42",
        "X-RateLimit-Reset": "1234567890",
    }
    with patch("time.time", return_value=1234560000):
        auth_manager.update_rate_limit_info(headers)
        status = auth_manager.get_rate_limit_status()
    assert status["remaining"] == 42
    assert status["reset_time"] == 1234567890


def test_update_rate_limit_info_invalid(auth_manager):
    """Test update_rate_limit_info handles invalid headers."""
    headers = {"X-RateLimit-Remaining": "notanint", "X-RateLimit-Reset": None}
    auth_manager.update_rate_limit_info(headers)
    status = auth_manager.get_rate_limit_status()
    assert status["remaining"] is None or status["remaining"] == 0


def test_should_wait_for_rate_limit_true(auth_manager):
    """Test should_wait_for_rate_limit returns True for low remaining."""
    auth_manager._remaining_requests = 5
    assert auth_manager.should_wait_for_rate_limit() is True


def test_should_wait_for_rate_limit_false(auth_manager):
    """Test should_wait_for_rate_limit returns False for enough remaining."""
    auth_manager._remaining_requests = 100
    assert auth_manager.should_wait_for_rate_limit() is False


def test_should_wait_for_rate_limit_none(auth_manager):
    """Test should_wait_for_rate_limit returns False if remaining is None."""
    auth_manager._remaining_requests = None
    assert auth_manager.should_wait_for_rate_limit() is False


def test_get_wait_time_with_reset(auth_manager):
    """Test get_wait_time returns correct wait time if reset_in_seconds set."""
    now = 1000
    auth_manager._rate_limit_reset = now + 50
    auth_manager._remaining_requests = 0
    with patch("time.time", return_value=now):
        wait = auth_manager.get_wait_time()
    assert wait == 60


def test_get_wait_time_default(auth_manager):
    """Test get_wait_time returns default if no reset time."""
    auth_manager._rate_limit_reset = None
    wait = auth_manager.get_wait_time()
    assert wait == 60


def test_is_authenticated_true(mock_token_store):
    """Test is_authenticated returns True if token exists."""
    mock_token_store._token = "abc123"
    auth_manager = GitHubAuthManager(mock_token_store)
    assert auth_manager.is_authenticated() is True


def test_is_authenticated_false(mock_token_store):
    """Test is_authenticated returns False if token missing or empty."""
    mock_token_store._token = ""
    auth_manager = GitHubAuthManager(mock_token_store)
    assert auth_manager.is_authenticated() is False
    mock_token_store._token = None
    assert auth_manager.is_authenticated() is False


# Tests for validate_github_token function
class TestValidateGitHubToken:
    """Test cases for GitHub token validation function."""

    def test_validate_legacy_token_valid(self):
        """Test validation of valid legacy 40-character hex token."""
        legacy_token = "a" * 40  # 40 character hex token
        assert validate_github_token(legacy_token) is True

    def test_validate_legacy_token_invalid_length(self):
        """Test validation fails for incorrect length legacy tokens."""
        assert validate_github_token("a" * 39) is False  # Too short
        assert validate_github_token("a" * 41) is False  # Too long

    def test_validate_legacy_token_invalid_chars(self):
        """Test validation fails for legacy tokens with invalid characters."""
        invalid_token = "g" * 40  # Contains 'g' which is not hex
        assert validate_github_token(invalid_token) is False

    def test_validate_new_format_ghp_token(self):
        """Test validation of new format Personal Access Token."""
        ghp_token = "ghp_" + "A" * 40  # Valid ghp_ token
        assert validate_github_token(ghp_token) is True

    def test_validate_new_format_gho_token(self):
        """Test validation of new format OAuth Access Token."""
        gho_token = "gho_" + "B" * 40  # Valid gho_ token
        assert validate_github_token(gho_token) is True

    def test_validate_new_format_ghu_token(self):
        """Test validation of new format GitHub App user-to-server token."""
        ghu_token = "ghu_" + "C" * 40  # Valid ghu_ token
        assert validate_github_token(ghu_token) is True

    def test_validate_new_format_ghs_token(self):
        """Test validation of new format GitHub App server-to-server token."""
        ghs_token = "ghs_" + "D" * 40  # Valid ghs_ token
        assert validate_github_token(ghs_token) is True

    def test_validate_new_format_ghr_token(self):
        """Test validation of new format GitHub App refresh token."""
        ghr_token = "ghr_" + "E" * 40  # Valid ghr_ token
        assert validate_github_token(ghr_token) is True

    def test_validate_github_pat_token(self):
        """Test validation of GitHub CLI PAT format."""
        github_pat_token = "github_pat_" + "F" * 40  # Valid github_pat_ token
        assert validate_github_token(github_pat_token) is True

    def test_validate_new_format_invalid_prefix(self):
        """Test validation fails for invalid prefixes."""
        invalid_token = "xyz_" + "A" * 40
        assert validate_github_token(invalid_token) is False

    def test_validate_new_format_too_short(self):
        """Test validation fails for new format tokens that are too short."""
        short_token = "ghp_" + "A" * 20  # Too short
        assert validate_github_token(short_token) is False

    def test_validate_new_format_invalid_chars(self):
        """Test validation fails for new format tokens with invalid chars."""
        invalid_token = "ghp_" + "@" * 40  # Contains invalid character '@'
        assert validate_github_token(invalid_token) is False

    def test_validate_empty_token(self):
        """Test validation fails for empty or None tokens."""
        assert validate_github_token("") is False
        assert validate_github_token("   ") is False
        assert validate_github_token(None) is False

    def test_validate_non_string_token(self):
        """Test validation fails for non-string token types."""
        assert validate_github_token(123) is False
        assert validate_github_token([]) is False
        assert validate_github_token({}) is False

    def test_validate_max_length_token(self):
        """Test validation of tokens at maximum supported length."""
        # Test maximum length for new format tokens (255 characters total)
        max_ghp_token = "ghp_" + "A" * 251  # 4 + 251 = 255 characters
        assert validate_github_token(max_ghp_token) is True

        # Test over maximum length
        over_max_token = "ghp_" + "A" * 252  # 4 + 252 = 256 characters
        assert validate_github_token(over_max_token) is False


def test_is_token_valid_method(mock_token_store):
    """Test is_token_valid method validates stored token format."""
    auth_manager = GitHubAuthManager(mock_token_store)

    # Test with valid legacy token
    mock_token_store._token = "a" * 40
    assert auth_manager.is_token_valid() is True

    # Test with valid new format token
    mock_token_store._token = "ghp_" + "A" * 40
    assert auth_manager.is_token_valid() is True

    # Test with invalid token
    mock_token_store._token = "invalid_token"
    assert auth_manager.is_token_valid() is False

    # Test with no token
    mock_token_store._token = None
    assert auth_manager.is_token_valid() is False


def test_setup_keyring_unavailable_dbus(monkeypatch):
    """Test setup_keyring raises KeyringUnavailableError for DBUS issues.

    When DBUS is unavailable (headless environment), setup_keyring should
    raise KeyringUnavailableError and log at DEBUG level.
    """
    # Import token module for testing
    from my_unicorn.core import token as token_module

    # Reset the global state
    token_module._keyring_initialized = False

    def mock_set_keyring(backend):
        raise Exception("DBUS_SESSION_BUS_ADDRESS is unset")

    monkeypatch.setattr("keyring.set_keyring", mock_set_keyring)

    # Should raise KeyringUnavailableError and log at DEBUG
    with patch("my_unicorn.core.token.logger") as mock_logger:
        with pytest.raises(KeyringUnavailableError):
            setup_keyring()
        # Verify DEBUG log, not ERROR or WARNING for DBUS errors
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("headless" in call for call in debug_calls)
        assert mock_logger.error.call_count == 0


def test_setup_keyring_access_error(monkeypatch):
    """Test setup_keyring raises KeyringAccessError for other failures.

    When keyring setup fails for reasons other than unavailability
    (e.g., permission issues), should raise KeyringAccessError.
    """
    from my_unicorn.core import token as token_module

    # Reset the global state
    token_module._keyring_initialized = False

    def mock_set_keyring(backend):
        raise Exception("Permission denied accessing keyring")

    monkeypatch.setattr("keyring.set_keyring", mock_set_keyring)

    # Should raise KeyringAccessError and log at WARNING
    with patch("my_unicorn.core.token.logger") as mock_logger:
        with pytest.raises(KeyringAccessError):
            setup_keyring()
        # Verify WARNING log for non-DBUS errors
        assert mock_logger.warning.call_count > 0


def test_get_token_keyring_unavailable():
    """Test get_token returns None when token store unavailable.

    When token store is unavailable, get_token should return None
    without raising an exception.
    """

    class UnavailableTokenStore:
        """Token store that simulates unavailability."""

        def get(self) -> str | None:
            # Simulate keyring unavailable
            return None

        def set(self, token: str) -> None:
            pass

        def delete(self) -> None:
            pass

    auth_manager = GitHubAuthManager(UnavailableTokenStore())
    token = auth_manager.get_token()
    assert token is None


def test_get_token_no_token_stored(mock_token_store):
    """Test get_token returns None when no token stored."""
    mock_token_store._token = None
    auth_manager = GitHubAuthManager(mock_token_store)
    token = auth_manager.get_token()
    assert token is None


def test_get_token_other_exception():
    """Test get_token handles token store exceptions gracefully."""

    class FailingTokenStore:
        """Token store that fails on get."""

        def get(self) -> str | None:
            raise Exception("Some other error")

        def set(self, token: str) -> None:
            pass

        def delete(self) -> None:
            pass

    auth_manager = GitHubAuthManager(FailingTokenStore())
    # Should raise exception (not catch it)
    with pytest.raises(Exception):
        auth_manager.get_token()


def test_apply_auth_no_token(mock_token_store):
    """Test apply_auth works without token.

    When no token is available, apply_auth should return headers unchanged
    (no Authorization header added) and notify user once.
    """
    mock_token_store._token = None
    auth_manager = GitHubAuthManager(mock_token_store)

    # Reset the notification flag (instance variable)
    auth_manager._user_notified = False

    headers = {"User-Agent": "test"}
    result = auth_manager.apply_auth(headers)

    # Should not add Authorization header
    assert "Authorization" not in result
    # Should keep existing headers
    assert result["User-Agent"] == "test"
    # Notification flag should be set on instance
    assert auth_manager._user_notified is True


def test_apply_auth_with_token(mock_token_store):
    """Test apply_auth adds Authorization header when token present.

    When a token is available, apply_auth should add the Authorization
    header with Bearer token and not notify user.
    """
    mock_token_store._token = "ghp_test123"
    auth_manager = GitHubAuthManager(mock_token_store)

    # Reset the notification flag
    auth_manager._user_notified = False

    headers = {"User-Agent": "test"}

    with patch("my_unicorn.core.auth.logger") as mock_logger:
        result = auth_manager.apply_auth(headers)

        # Should add Authorization header
        assert result["Authorization"] == "Bearer ghp_test123"
        # Should not notify user
        assert mock_logger.info.call_count == 0
        # Notification flag should remain False
        assert auth_manager._user_notified is False


def test_apply_auth_notifies_once():
    """Test user notification appears only once per session.

    When no token is available, apply_auth should notify the user about
    rate limits only once, not on subsequent calls.
    """
    mock_store = MockTokenStore(None)

    # Create a new manager instance (starts with _user_notified = False)
    auth_manager = GitHubAuthManager(mock_store)

    with patch("my_unicorn.core.auth.logger") as mock_logger:
        # First call - should notify
        auth_manager.apply_auth({})
        info_calls_first = mock_logger.info.call_count

        # Second call - should NOT notify again
        auth_manager.apply_auth({})
        info_calls_second = mock_logger.info.call_count

        assert info_calls_first == 1
        assert info_calls_second == 1  # Same count (no new notification)


def test_setup_keyring_import_error(monkeypatch):
    """Test setup_keyring raises KeyringUnavailableError for ImportError.

    When SecretService is not available (ImportError), setup_keyring should
    raise KeyringUnavailableError and log at DEBUG level.
    """
    from my_unicorn.core import token as token_module

    # Reset the global state
    token_module._keyring_initialized = False

    def mock_set_keyring(backend):
        raise ImportError("SecretService not available")

    monkeypatch.setattr("keyring.set_keyring", mock_set_keyring)

    # Should raise KeyringUnavailableError and log at DEBUG
    with patch("my_unicorn.core.token.logger") as mock_logger:
        with pytest.raises(KeyringUnavailableError):
            setup_keyring()
        # Verify DEBUG log for ImportError
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("not available" in call for call in debug_calls)
        assert mock_logger.error.call_count == 0
        assert mock_logger.error.call_count == 0
