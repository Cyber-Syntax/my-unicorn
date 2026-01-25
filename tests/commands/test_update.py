"""Tests for update command handler."""

from argparse import Namespace
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from my_unicorn.cli.commands.update import UpdateHandler


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Fixture for a mock config manager."""
    mock = MagicMock()
    mock.list_installed_apps.return_value = ["app1", "app2"]
    return mock


@pytest.fixture
def mock_update_manager() -> MagicMock:
    """Fixture for a mock update manager."""
    return MagicMock()


@pytest.fixture
def update_handler(
    mock_config_manager: Any, mock_update_manager: Any
) -> UpdateHandler:
    """Fixture for an UpdateHandler instance with mocks."""
    return UpdateHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=mock_update_manager,
    )


@pytest.mark.asyncio
async def test_update_handler_check_only_mode(
    update_handler: UpdateHandler,
    mock_update_manager: Any,
    mock_config_manager: Any,
) -> None:
    """Test UpdateHandler executes check-only mode successfully."""
    # Mock the service's check_for_updates method
    mock_results = {
        "available_updates": [
            {
                "app_name": "app1",
                "current_version": "1.0.0",
                "latest_version": "1.1.0",
            }
        ],
        "up_to_date": [],
        "invalid_apps": [],
    }

    # Mock progress_session context manager
    mock_progress = MagicMock()
    mock_progress_ctx = AsyncMock()
    mock_progress_ctx.__aenter__ = AsyncMock(return_value=mock_progress)
    mock_progress_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "my_unicorn.cli.commands.update.UpdateApplicationService"
        ) as mock_service_class,
        patch(
            "my_unicorn.cli.commands.update.progress_session",
            return_value=mock_progress_ctx,
        ),
    ):
        mock_service = MagicMock()
        mock_service.check_for_updates = AsyncMock(return_value=mock_results)
        mock_service_class.return_value = mock_service

        args = Namespace(apps=["app1"], check_only=True, refresh_cache=False)
        await update_handler.execute(args)

        # Verify service was created with correct dependencies
        mock_service_class.assert_called_once_with(
            config_manager=mock_config_manager,
            update_manager=ANY,  # UpdateManager created in execute()
            progress_service=mock_progress,
        )

        # Verify check_for_updates was called
        mock_service.check_for_updates.assert_awaited_once_with(
            app_names=["app1"],
            refresh_cache=False,
        )


@pytest.mark.asyncio
async def test_update_handler_perform_updates(
    update_handler: UpdateHandler,
    mock_update_manager: Any,
    mock_config_manager: Any,
) -> None:
    """Test UpdateHandler performs updates successfully."""
    # Mock the service's perform_updates method
    mock_results = {
        "updated": ["app1"],
        "failed": [],
        "up_to_date": [],
        "invalid_apps": [],
        "update_infos": [],
    }

    # Mock progress_session context manager
    mock_progress = MagicMock()
    mock_progress_ctx = AsyncMock()
    mock_progress_ctx.__aenter__ = AsyncMock(return_value=mock_progress)
    mock_progress_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "my_unicorn.cli.commands.update.UpdateApplicationService"
        ) as mock_service_class,
        patch(
            "my_unicorn.cli.commands.update.progress_session",
            return_value=mock_progress_ctx,
        ),
    ):
        mock_service = MagicMock()
        mock_service.perform_updates = AsyncMock(return_value=mock_results)
        mock_service_class.return_value = mock_service

        args = Namespace(apps=["app1"], check_only=False, refresh_cache=False)
        await update_handler.execute(args)

        # Verify service was created
        mock_service_class.assert_called_once_with(
            config_manager=mock_config_manager,
            update_manager=ANY,  # UpdateManager created in execute()
            progress_service=mock_progress,
        )

        # Verify perform_updates was called
        mock_service.perform_updates.assert_awaited_once_with(
            app_names=["app1"],
            refresh_cache=False,
            force=False,
        )


@pytest.mark.asyncio
async def test_update_handler_exception_handling(
    update_handler: UpdateHandler,
    mock_config_manager: Any,
) -> None:
    """Test UpdateHandler handles exceptions and displays error."""
    with (
        patch(
            "my_unicorn.cli.commands.update.UpdateApplicationService",
            side_effect=Exception("Boom"),
        ),
        patch(
            "my_unicorn.cli.commands.update.display_update_error"
        ) as mock_display_error,
        patch("my_unicorn.cli.commands.update.logger") as mock_logger,
    ):
        args = Namespace(apps=["app1"], check_only=False, refresh_cache=False)
        await update_handler.execute(args)

        mock_display_error.assert_called_once()
        mock_logger.exception.assert_called_once()
        assert (
            "Update operation failed: Boom"
            in mock_display_error.call_args[0][0]
        )


def test_parse_targets_handles_comma_separated() -> None:
    """Test parse_targets expands comma-separated app names."""
    from my_unicorn.cli.commands.helpers import parse_targets

    expanded = parse_targets(["foo,bar", "baz"])
    assert expanded == ["foo", "bar", "baz"]
