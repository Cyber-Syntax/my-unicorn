"""Tests for UI output capture and parsing helpers.

These tests verify that ASCII progress output can be captured and parsed
reliably for integration testing patterns.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from my_unicorn.core.progress.ascii_sections import (
    SectionRenderConfig,
    render_api_section,
    render_downloads_section,
    render_processing_section,
)
from my_unicorn.core.progress.progress_types import ProgressType, TaskState


@dataclass
class OutputSection:
    """Represents a section of progress output."""

    section_type: str  # "api", "download", "install"
    lines: list[str]


def capture_progress_output(
    tasks: dict[str, TaskState],
    order: list[str],
    interactive: bool = False,
    bar_width: int = 30,
    min_name_width: int = 15,
) -> str:
    """Capture progress output from task state.

    Args:
        tasks: Dictionary of task states
        order: Ordered list of task IDs
        interactive: Whether in interactive mode
        bar_width: Width of progress bars
        min_name_width: Minimum width for task names

    Returns:
        Captured output string

    """
    config = SectionRenderConfig(
        bar_width=bar_width,
        min_name_width=min_name_width,
        spinner_fps=4,
        interactive=interactive,
    )

    lines: list[str] = []
    lines.extend(render_api_section(tasks, order))
    lines.extend(render_downloads_section(tasks, order, config))
    lines.extend(render_processing_section(tasks, order, config))

    return "\n".join(lines)


def parse_output_sections(output: str) -> dict[str, OutputSection]:
    """Parse progress output into distinct sections.

    Identifies and extracts:
    - Fetching from API: section
    - Downloading: section (with optional count like "Downloading (2):")
    - Installing/Verifying: section

    Args:
        output: Raw output string

    Returns:
        Dictionary mapping section names to OutputSection objects

    """
    sections: dict[str, OutputSection] = {}
    current_section = None
    current_lines: list[str] = []

    for line in output.split("\n"):
        # Check for section headers
        is_api_section = line.startswith("Fetching from API:")
        is_download_section = line.startswith(
            ("Downloading:", "Downloading (")
        )
        is_install_section = line.startswith(("Installing:", "Verifying:"))

        if is_api_section or is_download_section or is_install_section:
            # Save previous section if exists
            if current_section:
                sections[current_section] = OutputSection(
                    section_type=current_section,
                    lines=current_lines,
                )

            # Determine new section type
            if is_api_section:
                current_section = "api"
            elif is_download_section:
                current_section = "download"
            else:
                current_section = "install"

            current_lines = []
        elif line.strip() == "" and current_section:
            # Empty line marks end of section
            pass
        elif current_section:
            current_lines.append(line)

    # Save last section
    if current_section:
        sections[current_section] = OutputSection(
            section_type=current_section,
            lines=current_lines,
        )

    return sections


@pytest.mark.integration
class TestCaptureProgressOutput:
    """Test suite for output capture functionality."""

    def test_capture_empty_output(self) -> None:
        """Test capturing output with no tasks."""
        tasks: dict[str, TaskState] = {}
        order: list[str] = []

        output = capture_progress_output(tasks, order)

        assert isinstance(output, str)
        # Empty tasks should produce minimal or empty output
        assert output.strip() == ""

    def test_capture_api_task_output(self) -> None:
        """Test capturing output for API fetching task."""
        task = TaskState(
            task_id="api_1",
            name="GitHub Releases",
            progress_type=ProgressType.API_FETCHING,
            total=1,
            completed=1,
            is_finished=True,
            success=True,
            description="Retrieved from cache",
        )

        tasks = {"api_1": task}
        order = ["api_1"]

        output = capture_progress_output(tasks, order, interactive=False)

        assert "Fetching from API:" in output
        assert "GitHub Releases" in output

    def test_capture_download_task_output(self) -> None:
        """Test capturing output for download task."""
        task = TaskState(
            task_id="dl_1",
            name="test-app",
            progress_type=ProgressType.DOWNLOAD,
            total=1024.0,
            completed=512.0,
            is_finished=False,
            speed=128.0,
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]

        output = capture_progress_output(tasks, order, interactive=False)

        assert "Downloading:" in output
        assert "test-app" in output

    def test_capture_interactive_vs_non_interactive(self) -> None:
        """Test that interactive flag is passed to renderer."""
        task = TaskState(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=500.0,
        )

        tasks = {"dl_1": task}
        order = ["dl_1"]

        output_interactive = capture_progress_output(
            tasks, order, interactive=True
        )
        output_non_interactive = capture_progress_output(
            tasks, order, interactive=False
        )

        # Both should have content
        assert len(output_interactive) > 0
        assert len(output_non_interactive) > 0
        # They should both have the downloading header
        assert "Downloading:" in output_interactive
        assert "Downloading:" in output_non_interactive


@pytest.mark.integration
class TestParseOutputSections:
    """Test suite for output section parsing."""

    def test_parse_single_api_section(self) -> None:
        """Test parsing output with only API section."""
        output = """Fetching from API:
GitHub Releases      1/1 Retrieved

"""

        sections = parse_output_sections(output)

        assert "api" in sections
        assert sections["api"].section_type == "api"
        assert len(sections["api"].lines) > 0
        assert "GitHub Releases" in "\n".join(sections["api"].lines)

    def test_parse_multiple_sections(self) -> None:
        """Test parsing output with multiple sections."""
        output = """Fetching from API:
GitHub Releases      1/1 Retrieved

Downloading:
test-app  1.0 MB  10.0 MB/s 00:00 [======] 100% ✓

Installing:
(1/2) Installing test-app ✓

"""

        sections = parse_output_sections(output)

        assert "api" in sections
        assert "download" in sections
        assert "install" in sections

    def test_parse_empty_output(self) -> None:
        """Test parsing empty or no sections."""
        output = ""

        sections = parse_output_sections(output)

        assert len(sections) == 0

    def test_parse_preserves_section_lines(self) -> None:
        """Test that parsed lines are preserved correctly."""
        output = """Downloading:
app-1  10 MB  5.0 MB/s 00:02 [====] 50%
app-2  20 MB  8.0 MB/s 00:02 [========] 75%

"""

        sections = parse_output_sections(output)

        assert "download" in sections
        lines = sections["download"].lines
        # Should have captured the download lines
        assert len(lines) > 0

    def test_parse_download_header_with_count(self) -> None:
        """Test parsing download section with count in header."""

        output = (
            "Fetching from API:\n"
            "GitHub Releases      2/2 Retrieved\n"
            "\n"
            "Downloading (2):\n"
            "AppFlowy-0.11.1-linux-x86_64   77.6 MiB  10.8 MB/s 00:00 "
            "[==============================]   100% ✓\n"
            "QOwnNotes-x86_64               41.6 MiB   3.6 MB/s 00:00 "
            "[==============================]   100% ✓\n"
            "\n"
            "Installing:\n"
            "(1/2) Installing qownnotes ✓\n"
            "\n"
        )

        sections = parse_output_sections(output)

        assert "download" in sections
        assert len(sections["download"].lines) > 0
        # Should have both download lines
        assert any("AppFlowy" in line for line in sections["download"].lines)
        assert any("QOwnNotes" in line for line in sections["download"].lines)

    def test_parse_updating_operation_in_install_section(self) -> None:
        """Test parsing install section with 'Updating' operation."""
        output = """Installing:
(1/2) Verifying appflowy ✓
(2/2) Updating appflowy ✓
(1/2) Verifying qownnotes ✓
(2/2) Updating qownnotes ✓

"""

        sections = parse_output_sections(output)

        assert "install" in sections
        lines_text = "\n".join(sections["install"].lines)
        # Should recognize both Verifying and Updating operations
        assert "Verifying appflowy" in lines_text
        assert "Updating appflowy" in lines_text
        assert "Updating qownnotes" in lines_text
