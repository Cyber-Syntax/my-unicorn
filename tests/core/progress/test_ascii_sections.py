"""Tests for ASCII section rendering module.

Tests section rendering functions extracted from AsciiProgressBackend,
including SectionRenderConfig dataclass and pure rendering functions.
"""

from __future__ import annotations

from my_unicorn.core.progress.ascii_sections import (
    SectionRenderConfig,
    calculate_dynamic_name_width,
    compute_max_name_width,
    format_download_lines,
    format_processing_task_lines,
    render_api_section,
    render_downloads_section,
    render_processing_section,
    select_current_task,
)
from my_unicorn.core.progress.progress_types import (
    DEFAULT_MIN_NAME_WIDTH,
    ProgressType,
    TaskState,
)


class TestSectionRenderConfig:
    """Test cases for SectionRenderConfig dataclass."""

    def test_section_render_config_creation(self) -> None:
        """Test creating SectionRenderConfig with all fields."""
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=True,
        )

        assert config.bar_width == 30
        assert config.min_name_width == 15
        assert config.spinner_fps == 4
        assert config.interactive is True

    def test_section_render_config_default_values(self) -> None:
        """Test SectionRenderConfig respects provided values."""
        config = SectionRenderConfig(
            bar_width=20,
            min_name_width=10,
            spinner_fps=2,
            interactive=False,
        )

        assert config.bar_width == 20
        assert config.min_name_width == 10


class TestSelectCurrentTask:
    """Test cases for select_current_task function."""

    def test_select_current_task_returns_first_unfinished(self) -> None:
        """Test that first unfinished task is selected."""
        task1 = TaskState(
            task_id="t1",
            name="Task 1",
            progress_type=ProgressType.VERIFICATION,
            is_finished=False,
        )
        task2 = TaskState(
            task_id="t2",
            name="Task 2",
            progress_type=ProgressType.VERIFICATION,
            is_finished=False,
        )

        result = select_current_task([task1, task2])
        assert result == task1

    def test_select_current_task_returns_failed_when_all_finished(
        self,
    ) -> None:
        """Test that failed task is selected when all finished."""
        task1 = TaskState(
            task_id="t1",
            name="Task 1",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=True,
        )
        task2 = TaskState(
            task_id="t2",
            name="Task 2",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=False,
        )

        result = select_current_task([task1, task2])
        assert result == task2

    def test_select_current_task_returns_last_when_all_completed(self) -> None:
        """Test that last task is selected when all completed successfully."""
        task1 = TaskState(
            task_id="t1",
            name="Task 1",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=True,
        )
        task2 = TaskState(
            task_id="t2",
            name="Task 2",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=True,
        )

        result = select_current_task([task1, task2])
        assert result == task2

    def test_select_current_task_empty_list_returns_none(self) -> None:
        """Test that None is returned for empty list."""
        result = select_current_task([])
        assert result is None


class TestCalculateDynamicNameWidth:
    """Test cases for calculate_dynamic_name_width function."""

    def test_calculate_dynamic_name_width_interactive_mode(self) -> None:
        """Test dynamic name width calculation in interactive mode."""
        # In interactive mode, it should try to use terminal width
        width = calculate_dynamic_name_width(
            interactive=True,
            min_name_width=DEFAULT_MIN_NAME_WIDTH,
        )
        assert width >= DEFAULT_MIN_NAME_WIDTH

    def test_calculate_dynamic_name_width_non_interactive_mode(self) -> None:
        """Test dynamic name width calculation in non-interactive mode."""
        # In non-interactive mode, it should use fixed width
        width = calculate_dynamic_name_width(
            interactive=False,
            min_name_width=15,
        )
        # fixed_width is 46 (10+10+5+30+2+6+1+6), terminal is 80
        # available_width = 80 - 46 = 34
        assert width >= 15


class TestComputeMaxNameWidth:
    """Test cases for compute_max_name_width function."""

    def test_compute_max_name_width_single_name(self) -> None:
        """Test max name width with single display name."""
        result = compute_max_name_width(
            display_names=["test.AppImage"],
            interactive=False,
            min_name_width=15,
        )
        assert isinstance(result, int)
        assert result >= 0

    def test_compute_max_name_width_multiple_names(self) -> None:
        """Test max name width with multiple display names."""
        result = compute_max_name_width(
            display_names=["short.app", "much-longer-app-name.AppImage"],
            interactive=False,
            min_name_width=15,
        )
        assert isinstance(result, int)
        assert result >= 15


class TestFormatDownloadLines:
    """Test cases for format_download_lines function."""

    def test_format_download_lines_in_progress(self) -> None:
        """Test formatting download lines for in-progress download."""
        task = TaskState(
            task_id="dl1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=500.0,
            speed=100.0,
        )

        lines = format_download_lines(task, max_name_width=20, bar_width=30)

        assert len(lines) >= 1
        # Check that line has progress bar and percentage
        assert "%" in lines[0]
        assert "[" in lines[0] and "]" in lines[0]

    def test_format_download_lines_with_error(self) -> None:
        """Test formatting download lines with error message."""
        task = TaskState(
            task_id="dl1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=0.0,
            is_finished=True,
            success=False,
            error_message="Network timeout",
        )

        lines = format_download_lines(task, max_name_width=20, bar_width=30)

        assert len(lines) >= 2
        assert "Error:" in lines[1]
        assert "Network timeout" in lines[1]

    def test_format_download_lines_completed_successfully(self) -> None:
        """Test formatting completed download."""
        task = TaskState(
            task_id="dl1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=1000.0,
            is_finished=True,
            success=True,
        )

        lines = format_download_lines(task, max_name_width=20, bar_width=30)

        assert len(lines) >= 1
        assert "✓" in lines[0]


class TestFormatProcessingTaskLines:
    """Test cases for format_processing_task_lines function."""

    def test_format_processing_task_lines_in_progress(self) -> None:
        """Test formatting processing task in progress."""
        task = TaskState(
            task_id="v1",
            name="test.AppImage",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=False,
        )
        spinner = "⠋"

        lines = format_processing_task_lines(
            task, name_width=20, spinner=spinner
        )

        assert len(lines) >= 1
        assert "(1/2)" in lines[0]
        assert "Verifying" in lines[0]

    def test_format_processing_task_lines_with_error(self) -> None:
        """Test formatting processing task with error."""
        task = TaskState(
            task_id="v1",
            name="test.AppImage",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=False,
            error_message="Hash mismatch",
        )
        spinner = "⠋"

        lines = format_processing_task_lines(
            task, name_width=20, spinner=spinner
        )

        assert len(lines) >= 2
        assert "Error:" in lines[1]

    def test_format_processing_task_lines_installation(self) -> None:
        """Test formatting installation task."""
        task = TaskState(
            task_id="i1",
            name="test.AppImage",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=False,
        )
        spinner = "⠋"

        lines = format_processing_task_lines(
            task, name_width=20, spinner=spinner
        )

        assert len(lines) >= 1
        assert "(2/2)" in lines[0]
        assert "Installing" in lines[0]


class TestRenderApiSection:
    """Test cases for render_api_section function."""

    def test_render_api_section_empty(self) -> None:
        """Test rendering empty API section."""
        result = render_api_section(tasks={}, order=[])
        assert result == []

    def test_render_api_section_with_api_tasks(self) -> None:
        """Test rendering API section with tasks."""
        task = TaskState(
            task_id="api1",
            name="AppFlowy",
            progress_type=ProgressType.API_FETCHING,
            total=1.0,
            completed=1.0,
            is_finished=True,
            success=True,
            description="Retrieved",
        )

        tasks = {"api1": task}
        order = ["api1"]

        result = render_api_section(tasks=tasks, order=order)

        assert len(result) > 0
        assert "Fetching from API:" in result[0]

    def test_render_api_section_with_cached_response(self) -> None:
        """Test rendering API section with cached response."""
        task = TaskState(
            task_id="api1",
            name="ZenBrowser",
            progress_type=ProgressType.API_FETCHING,
            total=1.0,
            completed=1.0,
            is_finished=True,
            success=True,
            description="Retrieved from cached data",
        )

        tasks = {"api1": task}
        order = ["api1"]

        result = render_api_section(tasks=tasks, order=order)

        assert len(result) > 0
        assert "cache" in result[1].lower()


class TestRenderDownloadsSection:
    """Test cases for render_downloads_section function."""

    def test_render_downloads_section_empty(self) -> None:
        """Test rendering empty downloads section."""
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        result = render_downloads_section(tasks={}, order=[], config=config)

        assert result == []

    def test_render_downloads_section_with_download_tasks(self) -> None:
        """Test rendering downloads section with tasks."""
        task = TaskState(
            task_id="dl1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=500.0,
            speed=100.0,
        )

        tasks = {"dl1": task}
        order = ["dl1"]

        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        result = render_downloads_section(
            tasks=tasks, order=order, config=config
        )

        assert len(result) > 0
        assert "Downloads" in result[0] or "Download" in result[0]


class TestRenderProcessingSection:
    """Test cases for render_processing_section function."""

    def test_render_processing_section_empty(self) -> None:
        """Test rendering empty processing section."""
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        result = render_processing_section(tasks={}, order=[], config=config)

        assert result == []

    def test_render_processing_section_verifying(self) -> None:
        """Test rendering processing section with verification tasks."""
        task = TaskState(
            task_id="v1",
            name="test.AppImage",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=False,
        )

        tasks = {"v1": task}
        order = ["v1"]

        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        result = render_processing_section(
            tasks=tasks, order=order, config=config
        )

        assert len(result) > 0
        assert "Verifying:" in result[0]

    def test_render_processing_section_installing(self) -> None:
        """Test rendering processing section with installation tasks."""
        task = TaskState(
            task_id="i1",
            name="test.AppImage",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=False,
        )

        tasks = {"i1": task}
        order = ["i1"]

        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        result = render_processing_section(
            tasks=tasks, order=order, config=config
        )

        assert len(result) > 0
        assert "Installing:" in result[0]
