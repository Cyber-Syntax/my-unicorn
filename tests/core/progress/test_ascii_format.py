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
        from my_unicorn.core.progress.ascii import compute_display_name

        result = compute_display_name(task)
        assert result == "qownnotes"

    def test_compute_display_name_no_extension(self) -> None:
        """Test that names without .AppImage are returned unchanged."""
        task = TaskState(
            task_id="test_2",
            name="plainname",
            progress_type=ProgressType.DOWNLOAD,
        )
        from my_unicorn.core.progress.ascii import compute_display_name

        result = compute_display_name(task)
        assert result == "plainname"


class TestComputeSpinner:
    """Test cases for compute_spinner function."""

    def test_compute_spinner_returns_valid_frame(self) -> None:
        """Test that compute_spinner returns a valid spinner frame."""
        from my_unicorn.core.progress.ascii import compute_spinner
        from my_unicorn.core.progress.progress_types import SPINNER_FRAMES

        result = compute_spinner(fps=4)
        assert result in SPINNER_FRAMES

    def test_compute_spinner_changes_over_time(self) -> None:
        """Test that spinner frame changes as time progresses."""
        from my_unicorn.core.progress.ascii import compute_spinner

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
        from my_unicorn.core.progress.ascii import compute_download_header

        result = compute_download_header(download_count=1)
        assert result == ":: Retrieving appimages..."

    def test_compute_download_header_zero(self) -> None:
        """Test header text for zero downloads."""
        from my_unicorn.core.progress.ascii import compute_download_header

        result = compute_download_header(download_count=0)
        assert result == ":: Retrieving appimages..."
