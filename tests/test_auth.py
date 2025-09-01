"""Tests for GitHubAuthManager: token management and rate limit logic."""

from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.auth import GitHubAuthManager


@pytest.fixture
def auth_manager():
    """Fixture for GitHubAuthManager instance."""
    return GitHubAuthManager()


def test_save_token_valid(monkeypatch, auth_manager):
    """Test save_token saves a valid token."""
    monkeypatch.setattr("getpass.getpass", lambda prompt: "valid_token")
    keyring_set = MagicMock()
    monkeypatch.setattr("keyring.set_password", keyring_set)
    auth_manager.save_token()
    keyring_set.assert_called_with(auth_manager.GITHUB_KEY_NAME, "token", "valid_token")


def test_save_token_empty(monkeypatch, auth_manager):
    """Test save_token raises ValueError for empty token."""
    monkeypatch.setattr("getpass.getpass", lambda prompt: "   ")
    with pytest.raises(ValueError):
        auth_manager.save_token()


def test_remove_token_success(monkeypatch, auth_manager, capsys):
    """Test remove_token removes token successfully."""
    keyring_delete = MagicMock()
    monkeypatch.setattr("keyring.delete_password", keyring_delete)
    auth_manager.remove_token()
    keyring_delete.assert_called_with(auth_manager.GITHUB_KEY_NAME, "token")
    captured = capsys.readouterr()
    assert "Token removed from keyring" in captured.out


def test_remove_token_failure(monkeypatch, auth_manager, capsys):
    """Test remove_token handles general Exception when deleting token."""

    class DummyError(Exception):
        """Dummy exception for simulating keyring delete failure."""

    monkeypatch.setattr("keyring.delete_password", MagicMock(side_effect=DummyError))
    auth_manager.remove_token()
    captured = capsys.readouterr()
    assert "Error removing token from keyring" in captured.out


def test_get_token(monkeypatch, auth_manager):
    """Test get_token returns token from keyring."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: "abc123")
    assert auth_manager.get_token() == "abc123"


def test_get_token_none(monkeypatch, auth_manager):
    """Test get_token returns None if not found."""
    monkeypatch.setattr("keyring.get_password", lambda k, u: None)
    assert auth_manager.get_token() is None


def test_apply_auth_with_token(monkeypatch, auth_manager):
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
    headers = {"X-RateLimit-Remaining": "42", "X-RateLimit-Reset": "1234567890"}
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
    """Test get_wait_time returns correct wait time if reset_in_seconds is set."""
    now = 1000
    auth_manager._rate_limit_reset = now + 50
    auth_manager._remaining_requests = 0
    with patch("time.time", return_value=now):
        wait = auth_manager.get_wait_time()
    assert wait == 60  # 50 + 10 = 60


def test_get_wait_time_default(auth_manager):
    """Test get_wait_time returns default if no reset time."""
    auth_manager._rate_limit_reset = None
    wait = auth_manager.get_wait_time()
    assert wait == 60


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
