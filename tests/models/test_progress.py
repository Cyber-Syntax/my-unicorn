"""Tests for progress tracking classes."""

import pytest
from unittest.mock import Mock, AsyncMock
from my_unicorn.models.progress import ProgressSteps, ProgressTracker


class TestProgressSteps:
    """Test ProgressSteps constants."""

    def test_constants_are_floats(self):
        """Test that all progress constants are floats."""
        assert isinstance(ProgressSteps.INIT, float)
        assert isinstance(ProgressSteps.VALIDATION, float)
        assert isinstance(ProgressSteps.FETCHING_DATA, float)
        assert isinstance(ProgressSteps.DOWNLOADING, float)
        assert isinstance(ProgressSteps.VERIFICATION, float)
        assert isinstance(ProgressSteps.PROCESSING, float)
        assert isinstance(ProgressSteps.FINALIZING, float)
        assert isinstance(ProgressSteps.COMPLETED, float)

    def test_progress_sequence(self):
        """Test that progress constants are in ascending order."""
        steps = [
            ProgressSteps.INIT,
            ProgressSteps.VALIDATION,
            ProgressSteps.FETCHING_DATA,
            ProgressSteps.DOWNLOADING,
            ProgressSteps.VERIFICATION,
            ProgressSteps.PROCESSING,
            ProgressSteps.FINALIZING,
            ProgressSteps.COMPLETED,
        ]
        
        # Check that each step is greater than or equal to the previous
        for i in range(1, len(steps)):
            assert steps[i] >= steps[i - 1]

    def test_specific_values(self):
        """Test specific expected values."""
        assert ProgressSteps.INIT == 0.0
        assert ProgressSteps.COMPLETED == 100.0
        assert ProgressSteps.VALIDATION == 10.0
        assert ProgressSteps.FETCHING_DATA == 20.0
        assert ProgressSteps.DOWNLOADING == 40.0
        assert ProgressSteps.VERIFICATION == 60.0
        assert ProgressSteps.PROCESSING == 75.0
        assert ProgressSteps.FINALIZING == 90.0


class TestProgressTracker:
    """Test ProgressTracker class."""

    def test_initialization_with_progress_service(self):
        """Test initialization with a download service that has progress service."""
        mock_progress_service = Mock()
        mock_download_service = Mock()
        mock_download_service.progress_service = mock_progress_service
        
        tracker = ProgressTracker(mock_download_service)
        assert tracker.download_service == mock_download_service
        assert tracker.progress_service == mock_progress_service

    def test_initialization_without_progress_service(self):
        """Test initialization with a download service without progress service."""
        mock_download_service = Mock()
        # Delete progress_service attribute if it exists
        if hasattr(mock_download_service, 'progress_service'):
            delattr(mock_download_service, 'progress_service')
        
        tracker = ProgressTracker(mock_download_service)
        assert tracker.download_service == mock_download_service
        assert tracker.progress_service is None

    @pytest.mark.asyncio
    async def test_update_progress_with_service(self):
        """Test update_progress with progress service."""
        mock_progress_service = AsyncMock()
        mock_download_service = Mock()
        mock_download_service.progress_service = mock_progress_service
        
        tracker = ProgressTracker(mock_download_service)
        
        await tracker.update_progress("task123", 50.0, "Installing...")
        
        mock_progress_service.update_task.assert_called_once_with(
            "task123",
            completed=50.0,
            description="Installing..."
        )

    @pytest.mark.asyncio
    async def test_update_progress_without_service(self):
        """Test update_progress without progress service."""
        mock_download_service = Mock()
        if hasattr(mock_download_service, 'progress_service'):
            delattr(mock_download_service, 'progress_service')
        
        tracker = ProgressTracker(mock_download_service)
        
        # Should not raise any exception
        await tracker.update_progress("task123", 50.0, "Installing...")

    @pytest.mark.asyncio
    async def test_update_progress_without_task_id(self):
        """Test update_progress without task ID."""
        mock_progress_service = AsyncMock()
        mock_download_service = Mock()
        mock_download_service.progress_service = mock_progress_service
        
        tracker = ProgressTracker(mock_download_service)
        
        await tracker.update_progress(None, 50.0, "Installing...")
        
        # Should not call update_task when task_id is None
        mock_progress_service.update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_finish_progress_with_service(self):
        """Test finish_progress with progress service."""
        mock_progress_service = AsyncMock()
        mock_download_service = Mock()
        mock_download_service.progress_service = mock_progress_service
        
        tracker = ProgressTracker(mock_download_service)
        
        await tracker.finish_progress("task123", True, "Installation complete")
        
        mock_progress_service.finish_task.assert_called_once_with(
            "task123",
            success=True,
            final_description="Installation complete",
            final_total=ProgressSteps.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_finish_progress_with_custom_total(self):
        """Test finish_progress with custom final total."""
        mock_progress_service = AsyncMock()
        mock_download_service = Mock()
        mock_download_service.progress_service = mock_progress_service
        
        tracker = ProgressTracker(mock_download_service)
        
        await tracker.finish_progress("task123", False, "Installation failed", 50.0)
        
        mock_progress_service.finish_task.assert_called_once_with(
            "task123",
            success=False,
            final_description="Installation failed",
            final_total=50.0
        )

    @pytest.mark.asyncio
    async def test_finish_progress_without_service(self):
        """Test finish_progress without progress service."""
        mock_download_service = Mock()
        if hasattr(mock_download_service, 'progress_service'):
            delattr(mock_download_service, 'progress_service')
        
        tracker = ProgressTracker(mock_download_service)
        
        # Should not raise any exception
        await tracker.finish_progress("task123", True, "Installation complete")

    @pytest.mark.asyncio
    async def test_finish_progress_without_task_id(self):
        """Test finish_progress without task ID."""
        mock_progress_service = AsyncMock()
        mock_download_service = Mock()
        mock_download_service.progress_service = mock_progress_service
        
        tracker = ProgressTracker(mock_download_service)
        
        await tracker.finish_progress(None, True, "Installation complete")
        
        # Should not call finish_task when task_id is None
        mock_progress_service.finish_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete progress workflow."""
        mock_progress_service = AsyncMock()
        mock_download_service = Mock()
        mock_download_service.progress_service = mock_progress_service
        
        tracker = ProgressTracker(mock_download_service)
        
        # Update progress multiple times
        await tracker.update_progress("task123", ProgressSteps.VALIDATION, "Validating...")
        await tracker.update_progress("task123", ProgressSteps.DOWNLOADING, "Downloading...")
        await tracker.update_progress("task123", ProgressSteps.VERIFICATION, "Verifying...")
        
        # Finish with success
        await tracker.finish_progress("task123", True, "Installation complete")
        
        # Verify all calls were made
        assert mock_progress_service.update_task.call_count == 3
        mock_progress_service.finish_task.assert_called_once()
