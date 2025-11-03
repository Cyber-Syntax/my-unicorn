"""Tests for AuthHandler command."""

from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses

from my_unicorn.commands.auth import AuthHandler


@pytest.mark.asyncio
class TestAuthHandler:
    """Test cases for AuthHandler command."""

    @pytest.fixture
    def auth_handler(self):
        """Fixture for AuthHandler with mocked dependencies."""
        config_manager = MagicMock()
        auth_manager = MagicMock(is_authenticated=MagicMock(return_value=True))
        update_manager = MagicMock()
        handler = AuthHandler(
            config_manager=config_manager,
            auth_manager=auth_manager,
            update_manager=update_manager,
        )
        handler.auth_manager = auth_manager  # Link the mock properly
        return handler

    @patch("my_unicorn.commands.auth.GitHubAuthManager.save_token")
    async def test_save_token(self, mock_save_token, auth_handler):
        """Test saving a GitHub token."""
        mock_save_token.return_value = None
        args = Namespace(save_token=True, remove_token=False, status=False)

        await auth_handler.execute(args)

        mock_save_token.assert_called_once()

    @patch("my_unicorn.commands.auth.GitHubAuthManager.remove_token")
    async def test_remove_token(self, mock_remove_token, auth_handler):
        """Test removing a GitHub token."""
        mock_remove_token.return_value = None
        args = Namespace(save_token=False, remove_token=True, status=False)

        await auth_handler.execute(args)

        mock_remove_token.assert_called_once()

    @patch(
        "my_unicorn.commands.auth.AuthHandler._fetch_fresh_rate_limit",
        new_callable=AsyncMock,
    )
    @patch("my_unicorn.commands.auth.GitHubAuthManager.is_authenticated")
    async def test_show_status_authenticated(
        self, mock_is_authenticated, mock_fetch_fresh_rate_limit, auth_handler
    ):
        """Test showing status when authenticated."""
        mock_is_authenticated.return_value = True
        mock_fetch_fresh_rate_limit.return_value = {"rate_limit": "mock_data"}
        auth_handler.auth_manager.get_rate_limit_status.return_value = {
            "remaining": 500,
            "reset_time": 1700000000,
            "reset_in_seconds": 3600,
        }
        mock_is_authenticated.return_value = True
        auth_handler.auth_manager.is_authenticated = mock_is_authenticated
        auth_handler.auth_manager.get_rate_limit_status.return_value = {
            "remaining": 500,
            "reset_time": 1700000000,
            "reset_in_seconds": 3600,
        }

        args = Namespace(save_token=False, remove_token=False, status=True)

        with patch("builtins.print") as mock_print:
            await auth_handler.execute(args)

        mock_is_authenticated.assert_called_once()
        mock_fetch_fresh_rate_limit.assert_called_once()
        mock_print.assert_any_call("✅ GitHub token is configured")
        mock_print.assert_any_call("\n📊 GitHub API Rate Limit Status:")

    @patch(
        "my_unicorn.commands.auth.AuthHandler._fetch_fresh_rate_limit",
        new_callable=AsyncMock,
    )
    async def test_show_status_not_authenticated(
        self, mock_fetch_fresh_rate_limit, auth_handler
    ):
        """Test showing status when not authenticated."""
        # Mock the auth_manager instance method, not the static method
        auth_handler.auth_manager.is_authenticated.return_value = False
        auth_handler.auth_manager.get_rate_limit_status.return_value = {
            "remaining": 60,
            "reset_time": 1700000000,
            "reset_in_seconds": 3600,
        }
        mock_fetch_fresh_rate_limit.return_value = {"rate": {"limit": 60}}

        args = Namespace(save_token=False, remove_token=False, status=True)

        with patch("builtins.print") as mock_print:
            await auth_handler.execute(args)

        auth_handler.auth_manager.is_authenticated.assert_called_once()
        mock_print.assert_any_call("❌ No GitHub token configured")
        mock_print.assert_any_call(
            "Use 'my-unicorn auth --save-token' to set a token"
        )

    @patch("my_unicorn.commands.auth.GitHubAuthManager.apply_auth")
    async def test_fetch_fresh_rate_limit(self, mock_apply_auth, auth_handler):
        """Test fetching fresh rate limit information."""
        # Set up safe mock headers
        test_token = "test_token_safe_123"
        mock_apply_auth.return_value = {
            "Authorization": f"Bearer {test_token}"
        }

        # Mock the API response
        expected_response = {"rate_limit": "mock_data"}
        expected_headers = {"X-RateLimit-Remaining": "500"}

        with aioresponses() as m:
            m.get(
                "https://api.github.com/rate_limit",
                payload=expected_response,
                headers=expected_headers,
            )

            result = await auth_handler._fetch_fresh_rate_limit()

        mock_apply_auth.assert_called_once_with({})
        assert result == expected_response
