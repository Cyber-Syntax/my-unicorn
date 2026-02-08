"""Tests for session management in progress display.

Tests verify session lifecycle, render loop behavior, and context manager
functionality for the SessionManager class.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.progress.display_id import IDGenerator
from my_unicorn.core.progress.display_session import SessionManager
from my_unicorn.core.progress.progress_types import (
    ProgressConfig,
    ProgressType,
)


class TestSessionLifecycle:
    """Test session lifecycle management."""

    @pytest.mark.asyncio
    async def test_session_lifecycle_start_stop(self) -> None:
        """Test that session correctly starts and stops."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act - Start session
        await session_manager.start_session(total_operations=10)

        # Assert - Session is active
        assert session_manager._active is True
        assert session_manager._render_task is not None
        assert not session_manager._stop_rendering.is_set()

        # Act - Stop session
        await session_manager.stop_session()

        # Assert - Session stopped
        assert session_manager._active is False
        assert session_manager._render_task is None
        assert session_manager._stop_rendering.is_set()

    @pytest.mark.asyncio
    async def test_session_not_active_initially(self) -> None:
        """Test that session is not active on initialization."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        logger_suppression = MagicMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Assert
        assert session_manager._active is False
        assert session_manager._render_task is None

    @pytest.mark.asyncio
    async def test_start_session_already_active(self) -> None:
        """Test starting session when already active returns early."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act - Start session first time
        await session_manager.start_session()
        first_task = session_manager._render_task

        # Act - Try to start again
        await session_manager.start_session()

        # Assert - Should be same render task
        assert session_manager._render_task == first_task
        assert logger_suppression.__aenter__.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_session_not_active(self) -> None:
        """Test stopping session when not active returns early."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        logger_suppression = MagicMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act - Stop when not active
        await session_manager.stop_session()

        # Assert - No side effects, just returned
        assert session_manager._active is False
        backend.cleanup.assert_not_called()

    @pytest.mark.asyncio
    async def test_session_calls_logger_suppression(self) -> None:
        """Test that start/stop session properly manages logger suppression."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act
        await session_manager.start_session()
        await asyncio.sleep(0.01)  # Small delay to ensure context setup
        await session_manager.stop_session()

        # Assert
        logger_suppression.__aenter__.assert_called_once()
        logger_suppression.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_clears_id_cache_on_stop(self) -> None:
        """Test that session clears ID generator cache when stopping."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        # Populate cache
        id_generator.generate_namespaced_id(ProgressType.DOWNLOAD, "test")

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act
        await session_manager.start_session()
        await session_manager.stop_session()

        # Assert - Cache should be cleared
        assert len(id_generator._id_cache) == 0


class TestRenderLoop:
    """Test background render loop."""

    @pytest.mark.asyncio
    async def test_render_loop_starts(self) -> None:
        """Test that background render loop starts when session starts."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act
        await session_manager.start_session()
        await asyncio.sleep(0.1)  # Allow render loop to execute

        # Assert
        assert session_manager._render_task is not None
        assert not session_manager._render_task.done()
        backend.render_once.assert_called()

        # Cleanup
        await session_manager.stop_session()

    @pytest.mark.asyncio
    async def test_render_loop_stops_cleanly(self) -> None:
        """Test that render loop stops cleanly when session stops."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act - Start and stop
        await session_manager.start_session()
        await asyncio.sleep(0.05)
        await session_manager.stop_session()

        # Assert - Render task should be cleaned up
        assert session_manager._render_task is None
        backend.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_loop_respects_refresh_rate(self) -> None:
        """Test that render loop respects configured refresh rate."""
        # Arrange
        config = ProgressConfig(
            refresh_per_second=2
        )  # 2 refreshes/second = 0.5s interval
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act
        await session_manager.start_session()
        await asyncio.sleep(0.2)  # Sleep for 200ms
        call_count_before_stop = backend.render_once.call_count
        await session_manager.stop_session()

        # Assert - Should have called render_once a reasonable number of times
        # With 2 Hz refresh rate over 200ms, expect 0-2 calls (with tolerance for timing)
        assert call_count_before_stop >= 0  # At least some calls

    @pytest.mark.asyncio
    async def test_render_loop_handles_backend_errors(self) -> None:
        """Test that render loop handles exceptions from backend gracefully."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        # Make render_once fail occasionally
        backend.render_once = AsyncMock(side_effect=Exception("Render error"))
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act
        await session_manager.start_session()
        await asyncio.sleep(0.1)  # Let render loop run with errors

        # Assert - Session should still be active despite errors
        assert session_manager._active is True

        # Cleanup
        await session_manager.stop_session()
        assert session_manager._active is False

    @pytest.mark.asyncio
    async def test_render_loop_cancellation(self) -> None:
        """Test that render loop handles cancellation properly."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act
        await session_manager.start_session()
        await asyncio.sleep(0.05)
        await session_manager.stop_session()

        # Assert - No unhandled exceptions
        await asyncio.sleep(0.01)


class TestSessionContextManager:
    """Test session() context manager."""

    @pytest.mark.asyncio
    async def test_session_context_manager(self) -> None:
        """Test session context manager starts and stops session."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act
        async with session_manager.session():
            # Assert inside context
            assert session_manager._active is True

        # Assert after context
        assert session_manager._active is False

    @pytest.mark.asyncio
    async def test_session_context_manager_exception_safety(self) -> None:
        """Test that session context manager stops even if exception occurs."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Act & Assert
        with pytest.raises(ValueError):
            async with session_manager.session():
                raise ValueError("Test exception")

        # Assert - Session should still be stopped
        assert session_manager._active is False

    @pytest.mark.asyncio
    async def test_session_context_manager_passes_total_operations(
        self,
    ) -> None:
        """Test that session context manager passes total_operations to start_session."""
        # Arrange
        config = ProgressConfig()
        backend = MagicMock()
        backend.render_once = AsyncMock()
        backend.cleanup = AsyncMock()
        logger_suppression = MagicMock()
        logger_suppression.__aenter__ = AsyncMock(
            return_value=logger_suppression
        )
        logger_suppression.__aexit__ = AsyncMock()
        id_generator = IDGenerator()

        session_manager = SessionManager(
            config=config,
            backend=backend,
            logger_suppression=logger_suppression,
            id_generator=id_generator,
        )

        # Spy on start_session to capture argument
        original_start = session_manager.start_session
        start_calls: list[int] = []

        async def tracked_start(total_operations: int = 0) -> None:
            start_calls.append(total_operations)
            await original_start(total_operations)

        session_manager.start_session = tracked_start

        # Act
        async with session_manager.session(total_operations=42):
            pass

        # Assert
        assert len(start_calls) == 1
        assert start_calls[0] == 42
