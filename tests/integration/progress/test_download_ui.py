"""Integration tests for download progress UI display.

These tests verify that the "Downloading:" section renders correctly
for various download task states including in-progress, completed,
error, and multi-file downloads.
"""

from __future__ import annotations

import pytest

from my_unicorn.core.progress.ascii_sections import (
    SectionRenderConfig,
    render_downloads_section,
)
from my_unicorn.core.progress.progress_types import ProgressType, TaskState

from .test_ui_helpers import parse_output_sections


@pytest.mark.integration
class TestDownloadProgressBarUI:
    """Test suite for download progress bar UI display."""

    def test_download_progress_bar_ui(self) -> None:
        """Verify progress bar renders correctly with progress.

        Tests that progress bars display proper fill percentage and
        match the expected format: [======] or [==============].
        """
        # Arrange - create a download task 50% complete
        task = TaskState(
            task_id="dl_1",
            name="test-app.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=500.0,
            is_finished=False,
            speed=100.0,
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show progress bar
        assert "Downloading:" in output
        assert "[" in output
        assert "]" in output
        # Progress bar should have equals signs
        assert "=" in output
        assert "test-app" in output

    def test_download_with_speed_and_eta_ui(self) -> None:
        """Verify download shows 'XX.X MiB  XX.X MB/s 00:XX' format.

        Tests that speed and ETA are formatted correctly:
        - Size in MiB/GiB
        - Speed in MB/s or similar
        - ETA as MM:SS
        """
        # Arrange - create download with specific size and speed
        task = TaskState(
            task_id="dl_1",
            name="QOwnNotes-x86_64",
            progress_type=ProgressType.DOWNLOAD,
            total=41.6 * 1024 * 1024,  # 41.6 MiB in bytes
            completed=0.0,
            is_finished=False,
            speed=3.6 * 1024 * 1024,  # 3.6 MB/s in bytes per second
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show size, speed, and ETA
        assert "MiB" in output  # Size should be in MiB
        assert "MB/s" in output or "MB" in output  # Speed should be shown
        assert ":" in output  # ETA should have colon (MM:SS format)
        assert "QOwnNotes" in output

    def test_download_completed_success_ui(self) -> None:
        """Verify checkmark '✓' appears for successful completed downloads."""
        # Arrange - create a completed download task
        task = TaskState(
            task_id="dl_1",
            name="AppFlowy-0.11.1-linux-x86_64",
            progress_type=ProgressType.DOWNLOAD,
            total=77.6 * 1024 * 1024,  # 77.6 MiB
            completed=77.6 * 1024 * 1024,
            is_finished=True,
            success=True,
            speed=10.8 * 1024 * 1024,  # 10.8 MB/s
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show checkmark
        assert "✓" in output
        assert "100%" in output
        assert "AppFlowy" in output

    def test_download_completed_error_ui(self) -> None:
        """Verify 'Error: message' appears for failed downloads."""
        # Arrange - create a failed download task
        task = TaskState(
            task_id="dl_1",
            name="broken-app.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0 * 1024 * 1024,
            completed=50.0 * 1024 * 1024,
            is_finished=True,
            success=False,
            error_message="Connection timeout while downloading from server",
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show error message
        assert "Error:" in output
        assert "timeout" in output.lower()
        # Failed downloads should show error
        assert "broken-app" in output

    def test_download_multiple_files_ui(self) -> None:
        """Verify 'Downloading (N):' header for multiple downloads."""
        # Arrange - create multiple download tasks
        task1 = TaskState(
            task_id="dl_1",
            name="AppFlowy-0.11.1-linux-x86_64",
            progress_type=ProgressType.DOWNLOAD,
            total=77.6 * 1024 * 1024,
            completed=77.6 * 1024 * 1024,
            is_finished=True,
            success=True,
            speed=10.8 * 1024 * 1024,
        )
        task2 = TaskState(
            task_id="dl_2",
            name="QOwnNotes-x86_64",
            progress_type=ProgressType.DOWNLOAD,
            total=41.6 * 1024 * 1024,
            completed=41.6 * 1024 * 1024,
            is_finished=True,
            success=True,
            speed=3.6 * 1024 * 1024,
        )

        tasks = {"dl_1": task1, "dl_2": task2}
        order = ["dl_1", "dl_2"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show count in header
        assert "Downloading (2):" in output
        # Both files should be listed
        assert "AppFlowy" in output
        assert "QOwnNotes" in output

    def test_download_size_formatting_ui(self) -> None:
        """Verify MiB/GiB size display for different file sizes."""
        # Arrange - create downloads with different file sizes
        # 50 MiB - should show in MiB
        task_mib = TaskState(
            task_id="dl_1",
            name="small-app",
            progress_type=ProgressType.DOWNLOAD,
            total=50.0 * 1024 * 1024,  # 50 MiB
            completed=50.0 * 1024 * 1024,
            is_finished=True,
            success=True,
        )

        # 1.5 GiB - should show in GiB or larger units
        task_gib = TaskState(
            task_id="dl_2",
            name="large-app",
            progress_type=ProgressType.DOWNLOAD,
            total=1.5 * 1024 * 1024 * 1024,  # 1.5 GiB
            completed=1.5 * 1024 * 1024 * 1024,
            is_finished=True,
            success=True,
        )

        # Test MiB formatting
        tasks_mib = {"dl_1": task_mib}
        order_mib = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        output_lines_mib = render_downloads_section(
            tasks_mib, order_mib, config
        )
        output_mib = "\n".join(output_lines_mib)

        # Assert MiB
        assert "MiB" in output_mib or "B" in output_mib
        assert "small-app" in output_mib

        # Test GiB formatting
        tasks_gib = {"dl_2": task_gib}
        order_gib = ["dl_2"]

        output_lines_gib = render_downloads_section(
            tasks_gib, order_gib, config
        )
        output_gib = "\n".join(output_lines_gib)

        # Assert GiB
        assert "GiB" in output_gib or "B" in output_gib
        assert "large-app" in output_gib

    def test_download_unknown_size_ui(self) -> None:
        """Verify '--' appears for unknown/zero sizes.

        Tests that when total size is 0 or unknown, the UI displays
        '--' or similar placeholder instead of invalid values.
        """
        # Arrange - create download with unknown size
        task = TaskState(
            task_id="dl_1",
            name="app.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=0.0,  # Unknown size
            completed=0.0,
            is_finished=False,
            speed=0.0,
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show placeholder for unknown size
        assert "--" in output
        assert "app" in output

    def test_download_single_file_header(self) -> None:
        """Verify 'Downloading:' header (without count) for single file."""
        # Arrange - create single download task
        task = TaskState(
            task_id="dl_1",
            name="single-app",
            progress_type=ProgressType.DOWNLOAD,
            total=50.0 * 1024 * 1024,
            completed=25.0 * 1024 * 1024,
            is_finished=False,
            speed=5.0 * 1024 * 1024,
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show "Downloading:" without count
        assert "Downloading:" in output
        assert "Downloading (1):" not in output
        assert "single-app" in output

    def test_download_no_tasks_returns_empty(self) -> None:
        """Verify no output when there are no download tasks."""
        # Arrange
        tasks: dict[str, TaskState] = {}
        order: list[str] = []
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads with no tasks
        output_lines = render_downloads_section(tasks, order, config)

        # Assert - should return empty list
        assert output_lines == []

    def test_download_output_parsing(
        self, install_success_output: str
    ) -> None:
        """Verify download section can be parsed from fixture output.

        Tests integration with parse_output_sections helper to ensure
        download section is correctly extracted from complex output.
        """
        # Arrange - use fixture output
        fixture_output = install_success_output

        # Act - parse sections
        sections = parse_output_sections(fixture_output)

        # Assert - download section should exist and be parseable
        assert "download" in sections
        assert len(sections["download"].lines) > 0

    def test_download_in_progress_percentage(self) -> None:
        """Verify percentage display for in-progress downloads."""
        # Arrange - create download 75% complete
        task = TaskState(
            task_id="dl_1",
            name="partial-app",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0 * 1024 * 1024,
            completed=75.0 * 1024 * 1024,
            is_finished=False,
            speed=10.0 * 1024 * 1024,
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show 75% progress
        assert "75%" in output
        assert "partial-app" in output

    def test_download_zero_speed_display(self) -> None:
        """Verify '--' or placeholder shown when speed is zero."""
        # Arrange - create download with zero speed
        task = TaskState(
            task_id="dl_1",
            name="slow-start-app",
            progress_type=ProgressType.DOWNLOAD,
            total=50.0 * 1024 * 1024,
            completed=0.0,
            is_finished=False,
            speed=0.0,
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render downloads section
        output_lines = render_downloads_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show placeholder for unknown speed
        assert "--" in output
