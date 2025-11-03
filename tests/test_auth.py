"""Tests for GitHubAuthManager: token management and rate limit logic."""

from unittest.mock import MagicMock, patch

import pytest

from my_unicorn import auth as auth_module
from my_unicorn.auth import (
    GitHubAuthManager,
    KeyringAccessError,
    KeyringUnavailableError,
    setup_keyring,
    validate_github_token,
)


@pytest.fixture
def auth_manager():
    """Fixture for GitHubAuthManager instance."""
    return GitHubAuthManager()


def test_save_token_valid(monkeypatch, auth_manager):
    """Test save_token saves a valid token."""
    valid_token = "a" * 40  # Valid legacy format token
    monkeypatch.setattr("getpass.getpass", lambda prompt: valid_token)
    keyring_set = MagicMock()
    monkeypatch.setattr("keyring.set_password", keyring_set)
    auth_manager.save_token()
    keyring_set.assert_called_with(
        auth_manager.GITHUB_KEY_NAME, "token", valid_token
    )


def test_save_token_empty(monkeypatch, auth_manager):
    """Test save_token raises ValueError for empty token."""
    monkeypatch.setattr("getpass.getpass", lambda prompt: "   ")
    with pytest.raises(ValueError):
        auth_manager.save_token()


def test_save_token_invalid_format(monkeypatch, auth_manager):
    """Test save_token raises ValueError for invalid token format."""
    monkeypatch.setattr(
        "getpass.getpass", lambda prompt: "invalid_token_format"
    )
    with pytest.raises(ValueError, match="Invalid GitHub token format"):
        auth_manager.save_token()


def test_remove_token_success(monkeypatch, auth_manager):
    """Test remove_token removes token successfully."""
    keyring_delete = MagicMock()
    monkeypatch.setattr("keyring.delete_password", keyring_delete)
    auth_manager.remove_token()
    keyring_delete.assert_called_with(auth_manager.GITHUB_KEY_NAME, "token")


def test_remove_token_failure(monkeypatch, auth_manager):
    """Test remove_token handles general Exception when deleting token."""

    class DummyError(Exception):
        """Dummy exception for simulating keyring delete failure."""

    monkeypatch.setattr(
        "keyring.delete_password", MagicMock(side_effect=DummyError)
    )
    with pytest.raises(DummyError):
        auth_manager.remove_token()


def test_get_token(monkeypatch, auth_manager):
    """Test get_token returns token from keyring."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: "abc123")
    assert auth_manager.get_token() == "abc123"


def test_get_token_none(monkeypatch, auth_manager):
    """Test get_token returns None if not found."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)
    assert auth_manager.get_token() is None


def test_apply_auth_adds_auth_header(monkeypatch, auth_manager):
    """Test apply_auth adds Authorization header if token exists."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: "abc123")
    headers = {}
    result = auth_manager.apply_auth(headers)
    assert result["Authorization"] == "Bearer abc123"


def test_apply_auth_without_token(monkeypatch, auth_manager):
    """Test apply_auth does not add header if token missing."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)
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
    assert status["remaining"] == 42  # noqa: PLR2004
    assert status["reset_time"] == 1234567890  # noqa: PLR2004


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
    assert wait == 60  # noqa: PLR2004 - 50 + 10 = 60


def test_get_wait_time_default(auth_manager):
    """Test get_wait_time returns default if no reset time."""
    auth_manager._rate_limit_reset = None
    wait = auth_manager.get_wait_time()
    assert wait == 60  # noqa: PLR2004


def test_is_authenticated_true(monkeypatch, auth_manager):
    """Test is_authenticated returns True if token exists."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: "abc123")
    assert auth_manager.is_authenticated() is True


def test_is_authenticated_false(monkeypatch, auth_manager):
    """Test is_authenticated returns False if token missing or empty."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: "")
    assert auth_manager.is_authenticated() is False
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)
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


def test_is_token_valid_method(monkeypatch, auth_manager):
    """Test is_token_valid method validates stored token format."""
    # Test with valid legacy token
    monkeypatch.setattr("keyring.get_password", lambda k, u: "a" * 40)
    assert auth_manager.is_token_valid() is True

    # Test with valid new format token
    monkeypatch.setattr("keyring.get_password", lambda k, u: "ghp_" + "A" * 40)
    assert auth_manager.is_token_valid() is True

    # Test with invalid token
    monkeypatch.setattr("keyring.get_password", lambda k, u: "invalid_token")
    assert auth_manager.is_token_valid() is False

    # Test with no token
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)
    assert auth_manager.is_token_valid() is False


def test_setup_keyring_unavailable_dbus(monkeypatch):
    """Test setup_keyring raises KeyringUnavailableError for DBUS issues.

    When DBUS is unavailable (headless environment), setup_keyring should
    raise KeyringUnavailableError and log at DEBUG level.
    """
    # Reset the global state
    auth_module._keyring_initialized = False

    def mock_set_keyring(backend):
        raise Exception("DBUS_SESSION_BUS_ADDRESS is unset")

    monkeypatch.setattr("keyring.set_keyring", mock_set_keyring)

    # Should raise KeyringUnavailableError and log at DEBUG
    with patch("my_unicorn.auth.logger") as mock_logger:
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
    # Reset the global state
    auth_module._keyring_initialized = False

    def mock_set_keyring(backend):
        raise Exception("Permission denied accessing keyring")

    monkeypatch.setattr("keyring.set_keyring", mock_set_keyring)

    # Should raise KeyringAccessError and log at WARNING
    with patch("my_unicorn.auth.logger") as mock_logger:
        with pytest.raises(KeyringAccessError):
            setup_keyring()
        # Verify WARNING log for non-DBUS errors
        assert mock_logger.warning.call_count > 0


def test_get_token_keyring_unavailable(monkeypatch, auth_manager):
    """Test get_token returns None when keyring unavailable.

    When keyring is unavailable (DBUS error), get_token should return None
    and log at DEBUG level without raising an exception.
    """

    def mock_get_password(key, username):
        raise Exception("DBUS_SESSION_BUS_ADDRESS is unset")

    monkeypatch.setattr("keyring.get_password", mock_get_password)

    # Should return None, not raise
    with patch("my_unicorn.auth.logger") as mock_logger:
        token = auth_manager.get_token()
        assert token is None
        # Verify DEBUG log, not ERROR
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("headless" in call for call in debug_calls)
        assert mock_logger.error.call_count == 0


def test_get_token_no_token_stored(monkeypatch, auth_manager):
    """Test get_token returns None when no token stored.

    When keyring returns None (no token stored), get_token should return
    None and log at DEBUG level.
    """
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)

    # Should return None and log DEBUG
    with patch("my_unicorn.auth.logger") as mock_logger:
        token = auth_manager.get_token()
        assert token is None
        # Verify DEBUG log about no token stored
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("No token stored" in call for call in debug_calls)
        assert mock_logger.error.call_count == 0


def test_get_token_other_exception(monkeypatch, auth_manager):
    """Test get_token handles non-DBUS exceptions gracefully.

    When keyring access fails for other reasons, get_token should return
    None and log at DEBUG level.
    """

    def mock_get_password(key, username):
        raise Exception("Some other error")

    monkeypatch.setattr("keyring.get_password", mock_get_password)

    # Should return None, not raise
    with patch("my_unicorn.auth.logger") as mock_logger:
        token = auth_manager.get_token()
        assert token is None
        # Verify DEBUG log about keyring access failure
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("Keyring access failed" in call for call in debug_calls)
        assert mock_logger.error.call_count == 0


def test_apply_auth_no_token(monkeypatch, auth_manager):
    """Test apply_auth works without token.

    When no token is available, apply_auth should return headers unchanged
    (no Authorization header added) and notify user once.
    """
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)

    # Reset the notification flag
    GitHubAuthManager._user_notified = False

    headers = {"User-Agent": "test"}
    result = auth_manager.apply_auth(headers)

    # Should not add Authorization header
    assert "Authorization" not in result
    # Should keep existing headers
    assert result["User-Agent"] == "test"
    # Notification flag should be set
    assert GitHubAuthManager._user_notified is True


def test_apply_auth_with_token(monkeypatch, auth_manager):
    """Test apply_auth adds Authorization header when token present.

    When a token is available, apply_auth should add the Authorization
    header with Bearer token and not notify user.
    """
    monkeypatch.setattr("keyring.get_password", lambda k, u: "ghp_test123")

    # Reset the notification flag
    GitHubAuthManager._user_notified = False

    headers = {"User-Agent": "test"}

    with patch("my_unicorn.auth.logger") as mock_logger:
        result = auth_manager.apply_auth(headers)

        # Should add Authorization header
        assert result["Authorization"] == "Bearer ghp_test123"
        # Should not notify user
        assert mock_logger.info.call_count == 0
        # Notification flag should remain False
        assert GitHubAuthManager._user_notified is False


def test_apply_auth_notifies_once(monkeypatch):
    """Test user notification appears only once per session.

    When no token is available, apply_auth should notify the user about
    rate limits only once, not on subsequent calls.
    """
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)

    # Reset the notification flag
    GitHubAuthManager._user_notified = False

    auth_manager = GitHubAuthManager()

    with patch("my_unicorn.auth.logger") as mock_logger:
        # First call - should notify
        auth_manager.apply_auth({})
        info_calls_first = mock_logger.info.call_count

        # Second call - should NOT notify again
        auth_manager.apply_auth({})
        info_calls_second = mock_logger.info.call_count

        assert info_calls_first == 1
        assert info_calls_second == 1  # Same count (no new notification)


def test_save_token_dbus_unavailable(monkeypatch, auth_manager, capsys):
    """Test save_token provides helpful message for DBUS errors."""
    valid_token = "ghp_" + "A" * 40
    monkeypatch.setattr("getpass.getpass", lambda prompt: valid_token)

    class DBusError(Exception):
        """DBUS-related exception for testing."""

    def mock_set_password(key, username, password):
        raise DBusError("DBUS_SESSION_BUS_ADDRESS is unset")

    monkeypatch.setattr("keyring.set_password", mock_set_password)

    with pytest.raises(DBusError):
        auth_manager.save_token()

    # Check that helpful message was printed
    captured = capsys.readouterr()
    assert "Keyring not available in headless environment" in captured.out
    assert "Future: Environment variable support coming soon" in captured.out


def test_setup_keyring_import_error(monkeypatch):
    """Test setup_keyring raises KeyringUnavailableError for ImportError.

    When SecretService is not available (ImportError), setup_keyring should
    raise KeyringUnavailableError and log at DEBUG level.
    """
    # Reset the global state
    auth_module._keyring_initialized = False

    def mock_set_keyring(backend):
        raise ImportError("SecretService not available")

    monkeypatch.setattr("keyring.set_keyring", mock_set_keyring)

    # Should raise KeyringUnavailableError and log at DEBUG
    with patch("my_unicorn.auth.logger") as mock_logger:
        with pytest.raises(KeyringUnavailableError):
            setup_keyring()
        # Verify DEBUG log for ImportError
        assert mock_logger.debug.call_count > 0
        assert mock_logger.error.call_count == 0
