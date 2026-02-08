"""Tests for logger suppression context manager."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.core.progress.display_logger import LoggerSuppression


class TestLoggerSuppressionContext:
    """Test logger suppression context manager."""

    def test_logger_suppression_suppresses_on_enter(self) -> None:
        """Test that entering context suppresses console handlers."""
        # Arrange
        mock_handler = MagicMock(spec=logging.StreamHandler)
        mock_handler.level = logging.INFO

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [mock_handler]

            # Act
            with LoggerSuppression():
                pass

            # Assert - handler should have been set to WARNING
            assert mock_handler.setLevel.called
            calls = mock_handler.setLevel.call_args_list
            # First call should be to WARNING
            assert calls[0][0][0] == logging.WARNING

    def test_logger_suppression_restores_on_exit(self) -> None:
        """Test that exiting context restores original handler levels."""
        # Arrange
        mock_handler = MagicMock(spec=logging.StreamHandler)
        mock_handler.level = logging.INFO

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [mock_handler]

            # Act
            with LoggerSuppression():
                pass

            # Assert - handler should be restored to original level
            assert mock_handler.setLevel.called
            calls = mock_handler.setLevel.call_args_list
            # Last call should restore to original level (INFO)
            assert calls[-1][0][0] == logging.INFO

    def test_logger_suppression_exception_safety(self) -> None:
        """Test that handlers are restored even when exception occurs."""
        # Arrange
        mock_handler = MagicMock(spec=logging.StreamHandler)
        mock_handler.level = logging.INFO

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [mock_handler]

            # Act & Assert
            with pytest.raises(ValueError), LoggerSuppression():
                raise ValueError("Test exception")

            # Handler should still be restored
            assert mock_handler.setLevel.called
            calls = mock_handler.setLevel.call_args_list
            # Last call should restore to original level
            assert calls[-1][0][0] == logging.INFO

    def test_logger_suppression_skips_file_handlers(self) -> None:
        """Test that file handlers are not suppressed."""
        # Arrange
        file_handler = MagicMock(spec=logging.handlers.RotatingFileHandler)
        file_handler.level = logging.INFO

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [file_handler]

            # Act
            with LoggerSuppression():
                pass

            # Assert - file handler should not be modified
            assert not file_handler.setLevel.called

    def test_logger_suppression_handles_multiple_handlers(self) -> None:
        """Test that multiple console handlers are all suppressed/restored."""
        # Arrange
        handler1 = MagicMock(spec=logging.StreamHandler)
        handler1.level = logging.INFO
        handler2 = MagicMock(spec=logging.StreamHandler)
        handler2.level = logging.DEBUG

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [handler1, handler2]

            # Act
            with LoggerSuppression():
                pass

            # Assert - both handlers should be modified
            assert handler1.setLevel.called
            assert handler2.setLevel.called
            # Both should be restored to original levels
            calls1 = handler1.setLevel.call_args_list
            calls2 = handler2.setLevel.call_args_list
            assert calls1[-1][0][0] == logging.INFO
            assert calls2[-1][0][0] == logging.DEBUG

    def test_logger_suppression_when_queue_listener_is_none(self) -> None:
        """Test that context manager handles None queue_listener gracefully."""
        # Arrange
        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = None

            # Act & Assert - should not raise
            with LoggerSuppression():
                pass


class TestLoggerSuppressionAsyncContext:
    """Test async logger suppression using async context manager protocol."""

    @pytest.mark.asyncio
    async def test_async_logger_suppression_suppresses_on_enter(self) -> None:
        """Test that entering async context suppresses console handlers."""
        # Arrange
        mock_handler = MagicMock(spec=logging.StreamHandler)
        mock_handler.level = logging.INFO

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [mock_handler]

            # Act
            async with LoggerSuppression():
                pass

            # Assert
            assert mock_handler.setLevel.called
            calls = mock_handler.setLevel.call_args_list
            assert calls[0][0][0] == logging.WARNING

    @pytest.mark.asyncio
    async def test_async_logger_suppression_restores_on_exit(self) -> None:
        """Test that exiting async context restores original handler levels."""
        # Arrange
        mock_handler = MagicMock(spec=logging.StreamHandler)
        mock_handler.level = logging.INFO

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [mock_handler]

            # Act
            async with LoggerSuppression():
                pass

            # Assert
            assert mock_handler.setLevel.called
            calls = mock_handler.setLevel.call_args_list
            assert calls[-1][0][0] == logging.INFO

    @pytest.mark.asyncio
    async def test_async_logger_suppression_exception_safety(self) -> None:
        """Test that handlers are restored even when async exception occurs."""
        # Arrange
        mock_handler = MagicMock(spec=logging.StreamHandler)
        mock_handler.level = logging.INFO

        with patch("my_unicorn.logger._state") as mock_state:
            mock_state.queue_listener = MagicMock()
            mock_state.queue_listener.handlers = [mock_handler]

            # Act & Assert
            with pytest.raises(ValueError):
                async with LoggerSuppression():
                    raise ValueError("Test exception")

            # Handler should still be restored
            assert mock_handler.setLevel.called
            calls = mock_handler.setLevel.call_args_list
            assert calls[-1][0][0] == logging.INFO
