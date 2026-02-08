"""Tests for workflows.py - Progress Tracking Function.

This module tests cached progress tracking functionality within the
update workflow orchestration.
"""

from unittest.mock import MagicMock

import pytest

from my_unicorn.core.update.workflows import update_cached_progress


class TestUpdateCachedProgress:
    """Tests for update_cached_progress function."""

    @pytest.mark.asyncio
    async def test_update_cached_progress_active_reporter(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_cached_progress with active progress reporter.

        Verifies that when progress reporter is active and task exists,
        the task is updated with correct progress information.
        """
        task_id = "test-task-123"
        mock_progress_reporter.is_active.return_value = True
        mock_progress_reporter.get_task_info.return_value = {
            "completed": 0,
            "total": 5,
        }

        await update_cached_progress(
            app_name="test-app",
            shared_api_task_id=task_id,
            progress_reporter=mock_progress_reporter,
        )

        mock_progress_reporter.get_task_info.assert_called_once_with(task_id)
        mock_progress_reporter.update_task.assert_called_once()
        call_kwargs = mock_progress_reporter.update_task.call_args[1]
        assert call_kwargs["completed"] == 1.0
        assert "test-app" in call_kwargs["description"]
        assert "1/5" in call_kwargs["description"]

    @pytest.mark.asyncio
    async def test_update_cached_progress_inactive_reporter(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_cached_progress with inactive progress reporter.

        Verifies that when reporter is inactive (is_active returns False),
        no progress update is attempted.
        """
        mock_progress_reporter.is_active.return_value = False

        await update_cached_progress(
            app_name="test-app",
            shared_api_task_id="test-task-123",
            progress_reporter=mock_progress_reporter,
        )

        mock_progress_reporter.get_task_info.assert_not_called()
        mock_progress_reporter.update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_cached_progress_task_not_found(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_cached_progress when task info is not found.

        Verifies that when get_task_info returns None, the function
        returns gracefully without attempting an update.
        """
        task_id = "missing-task"
        mock_progress_reporter.is_active.return_value = True
        mock_progress_reporter.get_task_info.return_value = None

        await update_cached_progress(
            app_name="test-app",
            shared_api_task_id=task_id,
            progress_reporter=mock_progress_reporter,
        )

        mock_progress_reporter.update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_cached_progress_no_task_id(
        self,
        mock_progress_reporter: MagicMock,
    ) -> None:
        """Test update_cached_progress with None task ID.

        Verifies that when task_id is None, function returns early
        without any reporter interactions.
        """
        await update_cached_progress(
            app_name="test-app",
            shared_api_task_id=None,
            progress_reporter=mock_progress_reporter,
        )

        mock_progress_reporter.is_active.assert_not_called()
        mock_progress_reporter.get_task_info.assert_not_called()
        mock_progress_reporter.update_task.assert_not_called()
