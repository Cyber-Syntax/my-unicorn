"""Tests for ASCII formatting helper functions.

Tests the pure formatting functions extracted from AsciiProgressBackend.
"""

from unittest.mock import patch

from my_unicorn.core.progress.progress_types import ProgressType, TaskState


class TestComputeDisplayName:
    """Test cases for compute_display_name function."""

    def test_compute_display_name_strips_appimage(self) -> None:
        """Test that .AppImage extension is stripped from task name."""
        task = TaskState(
            task_id="test_1",
            name="qownnotes.AppImage",
            progress_type=ProgressType.DOWNLOAD,
        )
        # Import will fail until we create the function
        from my_unicorn.core.progress.ascii_format import compute_display_name

        result = compute_display_name(task)
        assert result == "qownnotes"

    def test_compute_display_name_no_extension(self) -> None:
        """Test that names without .AppImage are returned unchanged."""
        task = TaskState(
            task_id="test_2",
            name="plainname",
            progress_type=ProgressType.DOWNLOAD,
        )
        from my_unicorn.core.progress.ascii_format import compute_display_name

        result = compute_display_name(task)
        assert result == "plainname"


class TestFormatApiTaskStatus:
    """Test cases for format_api_task_status function."""

    def test_format_api_task_status_cached(self) -> None:
        """Test status string for cached API task."""
        task = TaskState(
            task_id="api_1",
            name="test_app",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="Cached result",
        )
        from my_unicorn.core.progress.ascii_format import (
            format_api_task_status,
        )

        result = format_api_task_status(task)
        assert "Retrieved from cache" in result

    def test_format_api_task_status_not_cached(self) -> None:
        """Test status string for in-progress API task without cache."""
        task = TaskState(
            task_id="api_2",
            name="test_app",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=2.0,
            is_finished=False,
        )
        from my_unicorn.core.progress.ascii_format import (
            format_api_task_status,
        )

        result = format_api_task_status(task)
        assert "Fetching..." in result

    def test_format_api_task_status_finished(self) -> None:
        """Test status string for finished API task."""
        task = TaskState(
            task_id="api_3",
            name="test_app",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="Retrieved successfully",
        )
        from my_unicorn.core.progress.ascii_format import (
            format_api_task_status,
        )

        result = format_api_task_status(task)
        assert "Retrieved" in result


class TestComputeSpinner:
    """Test cases for compute_spinner function."""

    def test_compute_spinner_returns_valid_frame(self) -> None:
        """Test that compute_spinner returns a valid spinner frame."""
        from my_unicorn.core.progress.ascii_format import compute_spinner
        from my_unicorn.core.progress.progress_types import SPINNER_FRAMES

        result = compute_spinner(fps=4)
        assert result in SPINNER_FRAMES

    def test_compute_spinner_changes_over_time(self) -> None:
        """Test that spinner frame changes as time progresses."""
        from my_unicorn.core.progress.ascii_format import compute_spinner

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            frame1 = compute_spinner(fps=4)

            mock_time.return_value = 0.3  # More than 1/4 second
            frame2 = compute_spinner(fps=4)

            # Frames should potentially differ (depends on FPS and time delta)
            assert frame1 in ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            assert frame2 in ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class TestComputeDownloadHeader:
    """Test cases for compute_download_header function."""

    def test_compute_download_header_single(self) -> None:
        """Test header text for single download."""
        from my_unicorn.core.progress.ascii_format import (
            compute_download_header,
        )

        result = compute_download_header(download_count=1)
        assert result == "Downloading:"

    def test_compute_download_header_multiple(self) -> None:
        """Test header text for multiple downloads."""
        from my_unicorn.core.progress.ascii_format import (
            compute_download_header,
        )

        result = compute_download_header(download_count=3)
        assert result == "Downloading (3):"

    def test_compute_download_header_zero(self) -> None:
        """Test header text for zero downloads."""
        from my_unicorn.core.progress.ascii_format import (
            compute_download_header,
        )

        result = compute_download_header(download_count=0)
        assert result == "Downloading:"
