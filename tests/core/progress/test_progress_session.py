"""Tests for progress_session() context manager.

Tests verify the progress_session() function behavior, including session
lifecycle, ProgressDisplay creation, cleanup on exceptions, and integration
with the backend.
"""

import pytest

from my_unicorn.core.progress.display import ProgressDisplay
from my_unicorn.core.progress.progress import ProgressType, progress_session


class TestProgressSession:
    """Test suite for progress_session() context manager."""

    @pytest.mark.asyncio
    async def test_progress_session_basic_lifecycle(self) -> None:
        """Test that progress session starts and stops correctly."""
        async with progress_session() as progress:
            assert isinstance(progress, ProgressDisplay)
            assert progress.is_active()

    @pytest.mark.asyncio
    async def test_progress_session_creates_progress_display(self) -> None:
        """Test that progress_session creates a ProgressDisplay instance."""
        async with progress_session() as progress1:
            assert isinstance(progress1, ProgressDisplay)

        async with progress_session() as progress2:
            assert isinstance(progress2, ProgressDisplay)
            assert progress1 is not progress2

    @pytest.mark.asyncio
    async def test_progress_session_cleanup_on_exception(self) -> None:
        """Test that session properly cleans up when exception occurs."""
        with pytest.raises(ValueError, match="Test exception"):
            async with progress_session():
                raise ValueError("Test exception")

    @pytest.mark.asyncio
    async def test_progress_session_context_manager_protocol(self) -> None:
        """Test async context manager protocol implementation."""
        context_manager = progress_session()
        progress = await context_manager.__aenter__()

        assert isinstance(progress, ProgressDisplay)
        assert progress.is_active()

        await context_manager.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_progress_session_integration_with_backend(self) -> None:
        """Test progress_session integration with session backend."""
        async with progress_session(total_operations=5) as progress:
            assert isinstance(progress, ProgressDisplay)
            assert progress.is_active()

            task_id = await progress.add_task(
                "Test Task",
                ProgressType.DOWNLOAD,
                total=100,
            )
            assert task_id is not None

            task_info = progress.get_task_info(task_id)
            assert task_info is not None
            assert "Test Task" in task_info.get("description", "")

    @pytest.mark.asyncio
    async def test_progress_session_with_zero_operations(self) -> None:
        """Test progress_session with zero operations (default)."""
        async with progress_session() as progress:
            assert isinstance(progress, ProgressDisplay)
            assert progress.is_active()

        async with progress_session(total_operations=0) as progress:
            assert isinstance(progress, ProgressDisplay)
            assert progress.is_active()
