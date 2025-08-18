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
async def test_update_handler_executes_strategy_success(update_handler):
    """Test UpdateHandler executes strategy and displays summary on success."""
    mock_context = MagicMock()
    mock_strategy = MagicMock()
    mock_result = MagicMock()
    mock_result.message = "Update completed"
    mock_strategy.validate_inputs.return_value = True
    mock_strategy.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "my_unicorn.commands.update.UpdateStrategyFactory.create_strategy",
            return_value=mock_strategy,
        ),
        patch(
            "my_unicorn.commands.update.UpdateStrategyFactory.get_strategy_name",
            return_value="MockStrategy",
        ),
        patch(
            "my_unicorn.commands.update.UpdateHandler._build_context",
            return_value=mock_context,
        ),
        patch(
            "my_unicorn.commands.update.UpdateResultDisplay.display_summary"
        ) as mock_display_summary,
        patch("my_unicorn.commands.update.logger") as mock_logger,
    ):
        args = Namespace(apps=["app1"], check_only=False)
        await update_handler.execute(args)

        mock_strategy.validate_inputs.assert_called_once_with(mock_context)
        mock_strategy.execute.assert_awaited_once_with(mock_context)
        mock_display_summary.assert_called_once_with(mock_result)
        mock_logger.debug.assert_any_call("Selected strategy: MockStrategy")
        mock_logger.debug.assert_any_call("Update operation completed: Update completed")


@pytest.mark.asyncio
async def test_update_handler_invalid_inputs(update_handler):
    """Test UpdateHandler does not execute strategy if inputs are invalid."""
    mock_context = MagicMock()
    mock_strategy = MagicMock()
    mock_strategy.validate_inputs.return_value = False

    with (
        patch(
            "my_unicorn.commands.update.UpdateStrategyFactory.create_strategy",
            return_value=mock_strategy,
        ),
        patch(
            "my_unicorn.commands.update.UpdateStrategyFactory.get_strategy_name",
            return_value="MockStrategy",
        ),
        patch(
            "my_unicorn.commands.update.UpdateHandler._build_context",
            return_value=mock_context,
        ),
    ):
        args = Namespace(apps=["app1"], check_only=False)
        await update_handler.execute(args)

        mock_strategy.validate_inputs.assert_called_once_with(mock_context)
        mock_strategy.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_handler_exception_handling(update_handler):
    """Test UpdateHandler handles exceptions and displays error."""
    with (
        patch(
            "my_unicorn.commands.update.UpdateHandler._build_context",
            side_effect=Exception("Boom"),
        ),
        patch(
            "my_unicorn.commands.update.UpdateResultDisplay.display_error"
        ) as mock_display_error,
        patch("my_unicorn.commands.update.logger") as mock_logger,
    ):
        args = Namespace(apps=["app1"], check_only=False)
        await update_handler.execute(args)

        mock_display_error.assert_called_once()
        mock_logger.error.assert_called_once()
        assert "Update operation failed: Boom" in mock_display_error.call_args[0][0]


def test_parse_app_names_handles_comma_separated(update_handler):
    """Test _parse_app_names expands comma-separated app names."""
    app_args = ["foo,bar", "baz"]
    expanded = update_handler._parse_app_names(app_args)
    assert expanded == ["foo", "bar", "baz"]


def test_build_context_sets_fields(update_handler):
    """Test _build_context sets context fields correctly."""
    args = Namespace(apps=["foo"], check_only=True)
    context = update_handler._build_context(args)
    assert context.app_names == ["foo"]
    assert context.check_only is True
    assert context.config_manager is update_handler.config_manager
    assert context.update_manager is update_handler.update_manager
