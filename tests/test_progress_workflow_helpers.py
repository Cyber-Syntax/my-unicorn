"""Tests for progress workflow helper utilities."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.progress.progress import (
    github_api_progress_task,
    operation_progress_session,
)


@asynccontextmanager
async def mock_session(_total_operations):
    """Mock async context manager for progress session."""
    yield


@pytest.mark.asyncio
async def test_github_api_progress_task_with_progress_success():
    """Test GitHub API progress task lifecycle with progress service and success."""
    mock_progress = AsyncMock()
    mock_progress.create_api_fetching_task.return_value = "task-123"

    async with github_api_progress_task(
        mock_progress, task_name="Fetching releases", total=5
    ) as task_id:
        assert task_id == "task-123"
        mock_progress.create_api_fetching_task.assert_called_once_with(
            name="Fetching releases",
            description="🌐 Fetching release information...",
        )
        mock_progress.update_task.assert_called_once_with(
            "task-123", total=5.0, completed=0.0
        )

    mock_progress.finish_task.assert_called_once_with("task-123", success=True)


@pytest.mark.asyncio
async def test_github_api_progress_task_with_progress_failure():
    """Test GitHub API progress task lifecycle with progress service and failure."""
    mock_progress = AsyncMock()
    mock_progress.create_api_fetching_task.return_value = "task-456"

    with pytest.raises(ValueError, match="Test error"):
        async with github_api_progress_task(
            mock_progress, task_name="Fetching releases", total=3
        ) as task_id:
            assert task_id == "task-456"
            raise ValueError("Test error")

    mock_progress.finish_task.assert_called_once_with(
        "task-456", success=False
    )


@pytest.mark.asyncio
async def test_github_api_progress_task_without_progress():
    """Test GitHub API progress task when progress service is None."""
    async with github_api_progress_task(
        None, task_name="Test", total=5
    ) as task_id:
        assert task_id is None


@pytest.mark.asyncio
async def test_github_api_progress_task_with_zero_total():
    """Test GitHub API progress task with zero total operations."""
    mock_progress = AsyncMock()
    mock_progress.create_api_fetching_task.return_value = "task-789"

    async with github_api_progress_task(
        mock_progress, task_name="Empty task", total=0
    ) as task_id:
        assert task_id == "task-789"
        mock_progress.update_task.assert_called_once_with(
            "task-789", total=0.0, completed=0.0
        )


@pytest.mark.asyncio
async def test_operation_progress_session_with_progress():
    """Test operation progress session with progress service."""
    mock_progress = AsyncMock()
    # Use MagicMock to return an async context manager (not an async call)
    mock_progress.session = MagicMock(return_value=mock_session(10))

    async with operation_progress_session(
        mock_progress, total_operations=10
    ) as prog:
        assert prog is mock_progress
        mock_progress.session.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_operation_progress_session_without_progress():
    """Test operation progress session when progress service is None."""
    async with operation_progress_session(None, total_operations=10) as prog:
        assert prog is None


@pytest.mark.asyncio
async def test_operation_progress_session_with_zero_operations():
    """Test operation progress session with zero total operations."""
    mock_progress = AsyncMock()

    async with operation_progress_session(
        mock_progress, total_operations=0
    ) as prog:
        assert prog is mock_progress
        mock_progress.session.assert_not_called()


@pytest.mark.asyncio
async def test_operation_progress_session_exception_handling():
    """Test operation progress session properly propagates exceptions."""
    mock_progress = AsyncMock()
    # Use MagicMock to return an async context manager (not an async call)
    mock_progress.session = MagicMock(return_value=mock_session(5))

    with pytest.raises(RuntimeError, match="Session error"):
        async with operation_progress_session(
            mock_progress, total_operations=5
        ) as prog:
            assert prog is mock_progress
            msg = "Session error"
            raise RuntimeError(msg)


@pytest.mark.asyncio
async def test_github_api_progress_task_async_context_manager():
    """Test that github_api_progress_task properly implements async context manager."""
    mock_progress = AsyncMock()
    mock_progress.create_api_fetching_task.return_value = "task-async"

    context_manager = github_api_progress_task(
        mock_progress, task_name="Async test", total=1
    )

    assert hasattr(context_manager, "__aenter__")
    assert hasattr(context_manager, "__aexit__")


@pytest.mark.asyncio
async def test_operation_progress_session_async_context_manager():
    """Test that operation_progress_session properly implements async context manager."""
    mock_progress = AsyncMock()

    context_manager = operation_progress_session(
        mock_progress, total_operations=1
    )

    assert hasattr(context_manager, "__aenter__")
    assert hasattr(context_manager, "__aexit__")


@pytest.mark.asyncio
async def test_github_api_progress_task_multiple_operations():
    """Test GitHub API progress task with multiple simulated operations."""
    mock_progress = AsyncMock()
    mock_progress.create_api_fetching_task.return_value = "task-multi"

    async with github_api_progress_task(
        mock_progress, task_name="Multi ops", total=3
    ) as task_id:
        assert task_id == "task-multi"
        # Simulate multiple operations
        for i in range(3):
            # In real usage, progress would be updated here
            pass

    # Verify finish was called with success
    mock_progress.finish_task.assert_called_once_with(
        "task-multi", success=True
    )
