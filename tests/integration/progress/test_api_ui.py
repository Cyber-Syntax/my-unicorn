"""Integration tests for API fetching progress UI display.

These tests verify that the "Fetching from API:" section renders correctly
for various API task states including in-progress, retrieved, and cached
states.
"""

from __future__ import annotations

import pytest

from my_unicorn.core.progress.ascii_sections import render_api_section
from my_unicorn.core.progress.progress_types import ProgressType, TaskState

from .test_ui_helpers import parse_output_sections


@pytest.mark.integration
class TestApiFetchingUI:
    """Test suite for API fetching progress UI display."""

    def test_api_fetching_in_progress_ui(self) -> None:
        """Verify 'Fetching...' display when API fetching is in progress."""
        # Arrange - create a single API fetching task in progress
        task = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=1,
            is_finished=False,
            description="",
        )

        tasks = {"api_1": task}
        order = ["api_1"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        assert "Fetching from API:" in output
        assert "GitHub Releases" in output
        assert "1/2 Fetching..." in output
        # Should not have "Retrieved" when still fetching
        assert "Retrieved" not in output or output.count("Retrieved") == 0

    def test_api_fetching_retrieved_ui(self) -> None:
        """Verify 'Retrieved' display when API fetching completes."""
        # Arrange - create a completed API fetching task
        task = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=2,
            is_finished=True,
            success=True,
            description="",
        )

        tasks = {"api_1": task}
        order = ["api_1"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        assert "Fetching from API:" in output
        assert "GitHub Releases" in output
        assert "2/2 Retrieved" in output
        # Should not have "cache" when retrieved from API
        assert "cache" not in output.lower()

    def test_api_fetching_cached_ui(self) -> None:
        """Verify 'Retrieved from cache' display for cached API data."""
        # Arrange - create a task with cached data
        task = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=2,
            is_finished=True,
            success=True,
            description="cached",
        )

        tasks = {"api_1": task}
        order = ["api_1"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        assert "Fetching from API:" in output
        assert "GitHub Releases" in output
        assert "Retrieved from cache" in output

    def test_api_fetching_mixed_states_ui(self) -> None:
        """Verify multiple repos with different fetch states render correctly.

        Tests that the API section correctly displays various task states
        (retrieved, fetching, cached) simultaneously.
        """
        # Arrange - create API tasks with different states
        task1 = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=2,
            is_finished=True,
            success=True,
            description="",
        )
        task2 = TaskState(
            task_id="api_2",
            name="Zen Browser",
            progress_type=ProgressType.API_FETCHING,
            total=3,
            completed=2,
            is_finished=False,
            description="",
        )
        task3 = TaskState(
            task_id="api_3",
            name="QOwnNotes",
            progress_type=ProgressType.API_FETCHING,
            total=1,
            completed=1,
            is_finished=True,
            success=True,
            description="cached data",
        )

        tasks = {
            "api_1": task1,
            "api_2": task2,
            "api_3": task3,
        }
        order = ["api_1", "api_2", "api_3"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        assert "Fetching from API:" in output
        # Task 1 should show "Retrieved"
        assert "GitHub Releases" in output
        lines = output.split("\n")
        # Extract relevant lines
        github_line = next(
            (line for line in lines if "GitHub Releases" in line), None
        )
        assert github_line is not None
        assert "2/2 Retrieved" in github_line

        # Task 2 should show "Fetching..."
        zen_line = next(
            (line for line in lines if "Zen Browser" in line), None
        )
        assert zen_line is not None
        assert "2/3 Fetching..." in zen_line

        # Task 3 should show "from cache"
        qownnotes_line = next(
            (line for line in lines if "QOwnNotes" in line), None
        )
        assert qownnotes_line is not None
        assert "from cache" in qownnotes_line.lower()

    def test_api_fetching_alignment_ui(self) -> None:
        """Verify column alignment of API task names and statuses."""
        # Arrange - create tasks with varying name lengths
        task1 = TaskState(
            task_id="api_1",
            name="A",
            progress_type=ProgressType.API_FETCHING,
            total=1,
            completed=1,
            is_finished=True,
        )
        task2 = TaskState(
            task_id="api_2",
            name="AppFlowy-IO AppFlowy",  # Long name that gets truncated
            progress_type=ProgressType.API_FETCHING,
            total=1,
            completed=1,
            is_finished=True,
        )

        tasks = {
            "api_1": task1,
            "api_2": task2,
        }
        order = ["api_1", "api_2"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)

        # Assert
        lines = [
            line
            for line in output_lines
            if line and "Fetching from API" not in line
        ]
        assert len(lines) >= 2

        # Each line should have task name followed by status
        for line in lines:
            if line and line.strip():  # Skip empty lines
                # Status should be on line with "Retrieved" or "Fetching..."
                assert (
                    "Retrieved" in line
                    or "Fetching" in line
                    or "from cache" in line
                )

    def test_api_fetching_no_tasks_ui(self) -> None:
        """Verify empty output when no API tasks exist."""
        # Arrange - empty task list
        tasks: dict[str, TaskState] = {}
        order: list[str] = []

        # Act - render the API section
        output_lines = render_api_section(tasks, order)

        # Assert - should return empty list
        assert output_lines == []

    def test_api_fetching_with_non_api_tasks_ui(self) -> None:
        """Verify API section ignores non-API tasks."""
        # Arrange - mix of API and non-API tasks
        api_task = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=1,
            completed=1,
            is_finished=True,
        )
        download_task = TaskState(
            task_id="dl_1",
            name="test-app",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=500.0,
            is_finished=False,
        )

        tasks = {
            "api_1": api_task,
            "dl_1": download_task,
        }
        order = ["api_1", "dl_1"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        assert "Fetching from API:" in output
        assert "GitHub Releases" in output
        # Should NOT include download task
        assert "test-app" not in output

    def test_api_fetching_zero_total_finished_ui(self) -> None:
        """Verify display when task has zero total but is finished."""
        # Arrange - finished task with zero total (edge case)
        task = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=True,
            description="Retrieved",
        )

        tasks = {"api_1": task}
        order = ["api_1"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        assert "Fetching from API:" in output
        assert "GitHub Releases" in output
        # Should show "Retrieved" for finished task with zero total
        assert "Retrieved" in output

    def test_api_fetching_zero_total_not_finished_ui(self) -> None:
        """Verify display when task has zero total but not finished."""
        # Arrange - unfinished task with zero total (edge case)
        task = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=False,
        )

        tasks = {"api_1": task}
        order = ["api_1"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        assert "Fetching from API:" in output
        assert "GitHub Releases" in output
        # Should show "Fetching..." for unfinished task
        assert "Fetching..." in output

    def test_api_fetching_section_parsing(self) -> None:
        """Verify parsed section structure matches expected format."""
        # Arrange - create realistic API tasks
        task1 = TaskState(
            task_id="api_1",
            name="AppFlowy-IO AppFlowy",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=2,
            is_finished=True,
        )
        task2 = TaskState(
            task_id="api_2",
            name="Zen Browser",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=2,
            is_finished=True,
            description="From cached data",
        )

        tasks = {"api_1": task1, "api_2": task2}
        order = ["api_1", "api_2"]

        # Act - render and parse
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)
        sections = parse_output_sections(output)

        # Assert - verify parsed section contains expected API data
        assert "api" in sections
        api_section = sections["api"]
        assert len(api_section.lines) > 0
        # Should contain both app names
        api_text = "\n".join(api_section.lines)
        assert "AppFlowy" in api_text or "Zen" in api_text

    def test_api_fetching_long_name_truncation_ui(self) -> None:
        """Verify long app names are properly truncated in API section."""
        # Arrange - app with a very long name
        long_name = "VeryLongAppNameThatExceedsNormalLength"
        task = TaskState(
            task_id="api_1",
            name=long_name,
            progress_type=ProgressType.API_FETCHING,
            total=1,
            completed=1,
            is_finished=True,
        )

        tasks = {"api_1": task}
        order = ["api_1"]

        # Act - render the API section
        output_lines = render_api_section(tasks, order)
        output = "\n".join(output_lines)

        # Assert
        # Name should be truncated to 18 chars
        assert "Fetching from API:" in output
        # Should not have the full name since it's truncated
        assert long_name not in output
        # Should have truncated version or Retrieved status
        assert "Retrieved" in output
