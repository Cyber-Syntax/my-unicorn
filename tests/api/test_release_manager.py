"""Tests for the ReleaseManager class."""

from unittest.mock import MagicMock, patch
import pytest

from my_unicorn.api.release_manager import ReleaseManager

# Fixtures like mock_release_data, mock_beta_release_data, mock_all_releases_data
# are available from tests/api/conftest.py


@pytest.fixture
def release_manager_instance() -> ReleaseManager:
    """Provides a ReleaseManager instance for testing."""
    return ReleaseManager(owner="test-owner", repo="test-repo")


class TestReleaseManager:
    """Tests for the ReleaseManager's fetching capabilities."""

    def test_get_latest_release_data_success_stable(
        self, release_manager_instance: ReleaseManager, mock_release_data: dict
    ):
        """Test successful fetch of latest stable release data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_release_data
        headers = {"Authorization": "token test_token"}

        with patch(
            "my_unicorn.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response,
        ) as mock_auth_request:
            success, data = release_manager_instance.get_latest_release_data(headers=headers)

            assert success is True
            assert data == mock_release_data
            mock_auth_request.assert_called_once_with(
                "GET",
                f"https://api.github.com/repos/{release_manager_instance.owner}/{release_manager_instance.repo}/releases/latest",
                headers=headers,
                timeout=30,
                audit_action="fetch_latest_stable_release_raw",
            )

    def test_get_latest_release_data_fallback_to_all_releases(
        self, release_manager_instance: ReleaseManager, mock_all_releases_data: list
    ):
        """Test fallback to fetching all releases when /latest returns 404."""
        mock_response_latest_404 = MagicMock()
        mock_response_latest_404.status_code = 404
        mock_response_latest_404.text = "Not Found"

        mock_response_all_200 = MagicMock()
        mock_response_all_200.status_code = 200
        # mock_all_releases_data is [beta, stable], so [0] is the beta (latest overall)
        mock_response_all_200.json.return_value = mock_all_releases_data
        headers = {"Authorization": "token test_token"}

        # Simulate 404 for /latest, then 200 for /releases
        mock_auth_request = MagicMock(side_effect=[mock_response_latest_404, mock_response_all_200])

        with patch(
            "my_unicorn.auth_manager.GitHubAuthManager.make_authenticated_request", mock_auth_request
        ):
            success, data = release_manager_instance.get_latest_release_data(headers=headers)

            assert success is True
            assert data == mock_all_releases_data[0]  # Should be the first item from all releases
            assert mock_auth_request.call_count == 2
            # Check first call (to /latest)
            mock_auth_request.assert_any_call(
                "GET",
                f"https://api.github.com/repos/{release_manager_instance.owner}/{release_manager_instance.repo}/releases/latest",
                headers=headers,
                timeout=30,
                audit_action="fetch_latest_stable_release_raw",
            )
            # Check second call (to /releases)
            mock_auth_request.assert_any_call(
                "GET",
                f"https://api.github.com/repos/{release_manager_instance.owner}/{release_manager_instance.repo}/releases",
                headers=headers,
                timeout=30,
                audit_action="fetch_all_releases_for_fallback",
            )

    def test_get_latest_release_data_fallback_no_releases_at_all(
        self, release_manager_instance: ReleaseManager
    ):
        """Test fallback when /latest is 404 and /releases returns an empty list."""
        mock_response_latest_404 = MagicMock()
        mock_response_latest_404.status_code = 404

        mock_response_all_empty = MagicMock()
        mock_response_all_empty.status_code = 200
        mock_response_all_empty.json.return_value = []  # No releases
        headers = {"Authorization": "token test_token"}

        mock_auth_request = MagicMock(
            side_effect=[mock_response_latest_404, mock_response_all_empty]
        )
        with patch(
            "my_unicorn.auth_manager.GitHubAuthManager.make_authenticated_request", mock_auth_request
        ):
            success, message = release_manager_instance.get_latest_release_data(headers=headers)

            assert success is False
            assert "no releases found" in str(message).lower()
            assert mock_auth_request.call_count == 2

    def test_get_latest_release_data_rate_limit_on_latest(
        self, release_manager_instance: ReleaseManager
    ):
        """Test rate limit error when fetching /latest."""
        mock_response_rate_limit = MagicMock()
        mock_response_rate_limit.status_code = 403
        mock_response_rate_limit.text = "API rate limit exceeded"
        headers = {"Authorization": "token test_token"}

        with patch(
            "my_unicorn.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response_rate_limit,
        ) as mock_auth_request:
            success, message = release_manager_instance.get_latest_release_data(headers=headers)

            assert success is False
            assert "rate limit exceeded" in str(message).lower()
            mock_auth_request.assert_called_once()  # Should not proceed to fallback

    def test_get_latest_release_data_rate_limit_on_fallback(
        self, release_manager_instance: ReleaseManager
    ):
        """Test rate limit error during fallback to /releases."""
        mock_response_latest_404 = MagicMock()
        mock_response_latest_404.status_code = 404

        mock_response_rate_limit_all = MagicMock()
        mock_response_rate_limit_all.status_code = 403
        mock_response_rate_limit_all.text = "API rate limit exceeded"
        headers = {"Authorization": "token test_token"}

        mock_auth_request = MagicMock(
            side_effect=[mock_response_latest_404, mock_response_rate_limit_all]
        )
        with patch(
            "my_unicorn.auth_manager.GitHubAuthManager.make_authenticated_request", mock_auth_request
        ):
            success, message = release_manager_instance.get_latest_release_data(headers=headers)

            assert success is False
            assert "rate limit exceeded" in str(message).lower()
            assert mock_auth_request.call_count == 2

    def test_get_latest_release_data_other_error_on_latest(
        self, release_manager_instance: ReleaseManager
    ):
        """Test other HTTP error when fetching /latest."""
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.text = "Server Error"
        headers = {"Authorization": "token test_token"}

        with patch(
            "my_unicorn.auth_manager.GitHubAuthManager.make_authenticated_request",
            return_value=mock_response_error,
        ) as mock_auth_request:
            success, message = release_manager_instance.get_latest_release_data(headers=headers)

            assert success is False
            assert "failed to fetch latest stable release" in str(message).lower()
            assert "500" in str(message)
            mock_auth_request.assert_called_once()

    def test_get_latest_release_data_other_error_on_fallback(
        self, release_manager_instance: ReleaseManager
    ):
        """Test other HTTP error during fallback to /releases."""
        mock_response_latest_404 = MagicMock()
        mock_response_latest_404.status_code = 404

        mock_response_error_all = MagicMock()
        mock_response_error_all.status_code = 503
        mock_response_error_all.text = "Service Unavailable"
        headers = {"Authorization": "token test_token"}

        mock_auth_request = MagicMock(
            side_effect=[mock_response_latest_404, mock_response_error_all]
        )
        with patch(
            "my_unicorn.auth_manager.GitHubAuthManager.make_authenticated_request", mock_auth_request
        ):
            success, message = release_manager_instance.get_latest_release_data(headers=headers)

            assert success is False
            assert "failed to fetch all releases" in str(message).lower()
            assert "503" in str(message)
            assert mock_auth_request.call_count == 2

    # Consider adding tests for network exceptions (requests.exceptions.RequestException)
    # if GitHubAuthManager.make_authenticated_request can propagate them and ReleaseManager should handle them.
    # Based on ReleaseManager's current code, it doesn't explicitly catch requests.exceptions.
    # GitHubAuthManager.make_authenticated_request seems to handle them and return a Response-like object or raise.
    # If GitHubAuthManager returns a custom error object or specific status codes for network issues,
    # those could be tested here. For now, assuming HTTP status codes are the primary interface.
