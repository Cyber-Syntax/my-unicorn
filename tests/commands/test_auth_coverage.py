"""Additional coverage tests for AuthHandler command."""

from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from my_unicorn.cli.commands.auth import AuthHandler


@pytest.mark.asyncio
class TestAuthHandlerErrorPaths:
    """Test error handling paths in AuthHandler."""

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
        return handler

    async def test_fetch_fresh_rate_limit_client_error(
        self, auth_handler, caplog
    ):
        """Test fetch_fresh_rate_limit handles ClientError."""
        with patch(
            "my_unicorn.cli.commands.auth.aiohttp.ClientSession"
        ) as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value.__aenter__.return_value = (
                mock_session
            )

            # Mock the session.get response to raise ClientError
            mock_session.get.return_value.__aenter__.side_effect = (
                aiohttp.ClientError("Network error")
            )

            result = await auth_handler._fetch_fresh_rate_limit()

            assert result is None
            assert any(
                "Failed to fetch fresh rate limit info" in record.message
                for record in caplog.records
            )
            assert any(
                "Failed to connect to GitHub API" in record.message
                for record in caplog.records
            )

    @patch("my_unicorn.cli.commands.auth.aiohttp.ClientSession")
    async def test_fetch_fresh_rate_limit_os_error(
        self, mock_session_class, auth_handler, caplog
    ):
        """Test fetch_fresh_rate_limit handles OSError."""
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        # Mock the get call to raise OSError
        mock_session.get.side_effect = OSError("Connection refused")

        result = await auth_handler._fetch_fresh_rate_limit()

        assert result is None
        assert any(
            "Failed to fetch fresh rate limit info" in record.message
            for record in caplog.records
        )

    async def test_extract_core_rate_limit_info_invalid_data(
        self, auth_handler
    ):
        """Test _extract_core_rate_limit_info with invalid data."""
        # Test with None
        assert auth_handler._extract_core_rate_limit_info(None) is None

        # Test with non-dict
        assert auth_handler._extract_core_rate_limit_info("not a dict") is None

        # Test with dict but no resources
        assert auth_handler._extract_core_rate_limit_info({}) is None

        # Test with resources but not a dict
        assert (
            auth_handler._extract_core_rate_limit_info(
                {"resources": "not a dict"}
            )
            is None
        )

        # Test with resources dict but no core
        assert (
            auth_handler._extract_core_rate_limit_info({"resources": {}})
            is None
        )

        # Test with core but not a dict
        assert (
            auth_handler._extract_core_rate_limit_info(
                {"resources": {"core": "not a dict"}}
            )
            is None
        )

    async def test_extract_core_rate_limit_info_valid_data(self, auth_handler):
        """Test _extract_core_rate_limit_info with valid data."""
        valid_data = {
            "resources": {
                "core": {"limit": 5000, "remaining": 4999, "reset": 1700000000}
            }
        }
        result = auth_handler._extract_core_rate_limit_info(valid_data)
        assert result == {
            "limit": 5000,
            "remaining": 4999,
            "reset": 1700000000,
        }

    @patch(
        "my_unicorn.cli.commands.auth.AuthHandler._display_rate_limit_warnings"
    )
    @patch(
        "my_unicorn.cli.commands.auth.AuthHandler._display_additional_rate_limit_details"
    )
    async def test_display_rate_limit_info_no_cached_data(
        self, mock_details, mock_warnings, auth_handler, caplog
    ):
        """Test _display_rate_limit_info when no cached data is available."""
        auth_handler.auth_manager.get_rate_limit_status.return_value = {}

        # Test with valid fallback data from payload
        rate_limit_data = {
            "resources": {
                "core": {"limit": 5000, "remaining": 4999, "reset": 1700000000}
            }
        }

        await auth_handler._display_rate_limit_info(rate_limit_data)

        assert any(
            "Remaining requests: 4999" in record.message
            for record in caplog.records
        )
        assert any("Resets at:" in record.message for record in caplog.records)
        mock_warnings.assert_called_once()

    async def test_display_rate_limit_info_no_data_at_all(
        self, auth_handler, caplog
    ):
        """Test _display_rate_limit_info when no data is available at all."""
        auth_handler.auth_manager.get_rate_limit_status.return_value = {}

        await auth_handler._display_rate_limit_info(None)

        assert any(
            "Unable to fetch rate limit information" in record.message
            for record in caplog.records
        )

    async def test_display_reset_time_seconds(self, auth_handler, caplog):
        """Test _display_reset_time with seconds."""
        auth_handler._display_reset_time(45)

        assert any(
            "Resets in: 45 seconds" in record.message
            for record in caplog.records
        )

    async def test_display_reset_time_minutes(self, auth_handler, caplog):
        """Test _display_reset_time with minutes."""
        auth_handler._display_reset_time(125)  # 2m 5s

        assert any(
            "Resets in: 2m 5s" in record.message for record in caplog.records
        )

    async def test_display_reset_time_hours(self, auth_handler, caplog):
        """Test _display_reset_time with hours."""
        auth_handler._display_reset_time(7260)  # 2h 1m

        assert any(
            "Resets in: 2h 1m" in record.message for record in caplog.records
        )

    async def test_display_rate_limit_warnings_critical(
        self, auth_handler, caplog
    ):
        """Test _display_rate_limit_warnings with critical threshold (< 10)."""
        auth_handler._display_rate_limit_warnings(5)

        assert any(
            "WARNING: Very low rate limit remaining!" in record.message
            for record in caplog.records
        )

    async def test_display_rate_limit_warnings_low(self, auth_handler, caplog):
        """Test _display_rate_limit_warnings with low threshold (10-99)."""
        auth_handler._display_rate_limit_warnings(15)

        assert any(
            "Rate limit getting low" in record.message
            for record in caplog.records
        )

    async def test_display_rate_limit_warnings_moderate(
        self, auth_handler, caplog
    ):
        """Test _display_rate_limit_warnings with moderate threshold (< 100 but >= 10)."""
        auth_handler._display_rate_limit_warnings(75)

        assert any(
            "Rate limit getting low" in record.message
            for record in caplog.records
        )

    async def test_display_rate_limit_warnings_plenty(
        self, auth_handler, caplog
    ):
        """Test _display_rate_limit_warnings with plenty of requests."""
        caplog.clear()
        auth_handler._display_rate_limit_warnings(500)

        # Should not log warnings when plenty of requests remain
        assert not any(
            "WARNING" in record.message or "CRITICAL" in record.message
            for record in caplog.records
        )

    async def test_display_additional_rate_limit_details_with_data(
        self, auth_handler, caplog
    ):
        """Test _display_additional_rate_limit_details with valid data."""
        rate_limit_data = {
            "resources": {
                "core": {"limit": 5000, "remaining": 4999, "used": 1}
            }
        }

        auth_handler._display_additional_rate_limit_details(
            rate_limit_data, remaining=4999
        )

        assert any(
            "Rate limit: 4999/5000 requests" in record.message
            for record in caplog.records
        )

    async def test_display_additional_rate_limit_details_no_data(
        self, auth_handler, caplog
    ):
        """Test _display_additional_rate_limit_details with no data."""
        caplog.clear()
        auth_handler._display_additional_rate_limit_details(
            None, remaining=100
        )

        # Should not log anything when no data is provided
        assert not any(
            "Rate limit:" in record.message for record in caplog.records
        )
