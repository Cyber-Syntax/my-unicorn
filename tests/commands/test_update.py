from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.commands.update import UpdateHandler


@pytest.fixture
def mock_config_manager():
    """Fixture for a mock config manager."""
    return MagicMock()


@pytest.fixture
def mock_update_manager():
    """Fixture for a mock update manager."""
    return MagicMock()


@pytest.fixture
def update_handler(mock_config_manager, mock_update_manager):
    """Fixture for an UpdateHandler instance with mocks."""
    return UpdateHandler(
        config_manager=mock_config_manager,
        auth_manager=MagicMock(),
        update_manager=mock_update_manager,
    )


@pytest.mark.asyncio
async def test_update_handler_check_only_mode(
    update_handler, mock_update_manager
):
    """Test UpdateHandler executes check-only mode successfully."""
    from my_unicorn.update import UpdateInfo

    mock_update_infos = [
        UpdateInfo(
            app_name="app1",
            current_version="1.0.0",
            latest_version="1.1.0",
            has_update=True,
        )
    ]
    mock_update_manager.check_updates = AsyncMock(
        return_value=mock_update_infos
    )

    with patch(
        "my_unicorn.commands.update.UpdateHandler._get_target_apps",
        return_value=["app1"],
    ):
        args = Namespace(apps=["app1"], check_only=True, refresh_cache=False)
        await update_handler.execute(args)

        mock_update_manager.check_updates.assert_awaited_once_with(
            app_names=["app1"],
            refresh_cache=False,
        )


@pytest.mark.asyncio
async def test_update_handler_perform_updates(
    update_handler, mock_update_manager
):
    """Test UpdateHandler performs updates successfully."""
    from my_unicorn.update import UpdateInfo

    mock_update_infos = [
        UpdateInfo(
            app_name="app1",
            current_version="1.0.0",
            latest_version="1.1.0",
            has_update=True,
        )
    ]
    mock_update_manager.check_updates = AsyncMock(
        return_value=mock_update_infos
    )
    mock_update_manager.update_multiple_apps = AsyncMock(
        return_value=({"app1": True}, {})
    )

    # Create proper async context manager mock
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=None)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "my_unicorn.commands.update.UpdateHandler._get_target_apps",
            return_value=["app1"],
        ),
        patch(
            "my_unicorn.commands.update.progress_session",
            return_value=mock_session,
        ),
        patch(
            "my_unicorn.commands.update.get_progress_service"
        ) as mock_progress,
        patch("my_unicorn.commands.update.UpdateHandler._display_update_plan"),
    ):
        mock_progress_instance = MagicMock()
        mock_progress_instance.create_api_fetching_task = AsyncMock(
            return_value="task_id"
        )
        mock_progress_instance.update_task = AsyncMock()
        mock_progress_instance.finish_task = AsyncMock()
        mock_progress.return_value = mock_progress_instance

        args = Namespace(apps=["app1"], check_only=False, refresh_cache=False)
        await update_handler.execute(args)

        mock_update_manager.check_updates.assert_awaited_once()
        mock_update_manager.update_multiple_apps.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_handler_exception_handling(update_handler):
    """Test UpdateHandler handles exceptions and displays error."""
    with (
        patch(
            "my_unicorn.commands.update.UpdateHandler._get_target_apps",
            side_effect=Exception("Boom"),
        ),
        patch(
            "my_unicorn.commands.update.display_update_error"
        ) as mock_display_error,
        patch("my_unicorn.commands.update.logger") as mock_logger,
    ):
        args = Namespace(apps=["app1"], check_only=False, refresh_cache=False)
        await update_handler.execute(args)

        mock_display_error.assert_called_once()
        mock_logger.error.assert_called_once()
        assert (
            "Update operation failed: Boom"
            in mock_display_error.call_args[0][0]
        )


def test_parse_app_names_handles_comma_separated(update_handler):
    """Test _parse_app_names expands comma-separated app names."""
    args = Namespace(apps=["foo,bar", "baz"])
    expanded = update_handler._parse_app_names(args)
    assert expanded == ["foo", "bar", "baz"]


def test_get_target_apps_validates_installed(
    update_handler, mock_config_manager
):
    """Test _get_target_apps validates apps are installed."""
    mock_config_manager.list_installed_apps.return_value = ["app1", "app2"]

    # Test with no specific apps - should return all
    result = update_handler._get_target_apps(None)
    assert result == ["app1", "app2"]

    # Test with specific valid apps
    result = update_handler._get_target_apps(["app1"])
    assert result == ["app1"]

    # Test with case-insensitive matching
    result = update_handler._get_target_apps(["APP1"])
    assert result == ["app1"]
