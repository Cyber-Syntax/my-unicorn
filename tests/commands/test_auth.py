"""Tests for AuthHandler command."""

from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses

from my_unicorn.cli.commands.auth import AuthHandler


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

    @patch(
        "my_unicorn.cli.commands.auth.AuthHandler._fetch_fresh_rate_limit",
        new_callable=AsyncMock,
    )
    async def test_show_status_authenticated(
        self, mock_fetch_fresh_rate_limit, auth_handler
    ):
        """Test showing status when authenticated."""
        auth_handler.auth_manager.is_authenticated.return_value = True
        mock_fetch_fresh_rate_limit.return_value = {"rate_limit": "mock_data"}
        auth_handler.auth_manager.get_rate_limit_status.return_value = {
            "remaining": 500,
            "reset_time": 1700000000,
            "reset_in_seconds": 3600,
        }

        args = Namespace(status=False)

        with patch("my_unicorn.cli.commands.auth.logger") as mock_logger:
            await auth_handler.execute(args)

        auth_handler.auth_manager.is_authenticated.assert_called_once()
        mock_fetch_fresh_rate_limit.assert_called_once()
        mock_logger.info.assert_any_call("✅ GitHub token is configured")
        mock_logger.info.assert_any_call("")
        mock_logger.info.assert_any_call("📊 GitHub API Rate Limit Status:")

    @patch(
        "my_unicorn.cli.commands.auth.AuthHandler._fetch_fresh_rate_limit",
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

        args = Namespace(status=False)

        with patch("my_unicorn.cli.commands.auth.logger") as mock_logger:
            await auth_handler.execute(args)

        auth_handler.auth_manager.is_authenticated.assert_called_once()
        mock_logger.info.assert_any_call("❌ No GitHub token configured")
        mock_logger.info.assert_any_call(
            "Use 'my-unicorn token --save' to set a token"
        )

    async def test_fetch_fresh_rate_limit(self, auth_handler):
        """Test fetching fresh rate limit information."""
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

        assert result == expected_response
