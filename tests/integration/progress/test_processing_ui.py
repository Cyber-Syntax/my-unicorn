"""Integration tests for installation/verification progress UI display.

These tests verify that the "Installing:" or "Verifying:" sections render
correctly for various processing task states including verification success,
warnings, partial verification, installation success, and error conditions.
"""

from __future__ import annotations

import pytest

from my_unicorn.core.progress.ascii_sections import (
    SectionRenderConfig,
    render_processing_section,
)
from my_unicorn.core.progress.progress_types import ProgressType, TaskState

from .test_ui_helpers import capture_progress_output, parse_output_sections


@pytest.mark.integration
class TestVerificationSuccessUI:
    """Test suite for successful verification UI display."""

    def test_verification_success_ui(self) -> None:
        """Verify "(1/2) Verifying app ✓" format.

        Tests successful verification display format.
        """
        # Arrange - create a completed successful verification task
        task = TaskState(
            task_id="v1",
            name="qownnotes",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"v1": task}
        order = ["v1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show verification in correct format
        assert "Verifying:" in output
        assert "(1/2)" in output
        assert "Verifying" in output
        assert "qownnotes" in output
        assert "✓" in output
        # Should have format like "(1/2) Verifying qownnotes ✓"
        assert "(1/2) Verifying qownnotes ✓" in output


@pytest.mark.integration
class TestVerificationWarningUI:
    """Test suite for verification warnings display."""

    def test_verification_warning_ui(self) -> None:
        """Verify '⚠ not verified (dev did not provide checksums)' format."""
        # Arrange - create a verification with warning
        task = TaskState(
            task_id="v1",
            name="weektodo",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
            description="not verified (dev did not provide checksums)",
        )

        tasks = {"v1": task}
        order = ["v1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show warning format
        assert "Verifying:" in output
        assert "(1/2)" in output
        assert "Verifying" in output
        assert "weektodo" in output
        assert "⚠" in output  # Warning symbol
        # Warning message should be on next line with indentation
        assert "not verified (dev did not provide checksums)" in output

    def test_verification_warning_with_next_phase(self) -> None:
        """Verify processing continues after verification warning.

        Tests that when a verification has a warning, the next phase
        (installation) still shows correctly.
        """
        # Arrange - create verification warning + installation success
        task1 = TaskState(
            task_id="v1",
            name="weektodo",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
            description="not verified (dev did not provide checksums)",
        )
        task2 = TaskState(
            task_id="i1",
            name="weektodo",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"v1": task1, "i1": task2}
        order = ["v1", "i1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show both phases
        assert "Installing:" in output
        assert "(1/2) Verifying weektodo ⚠" in output
        assert "(2/2) Installing weektodo ✓" in output


@pytest.mark.integration
class TestInstallationSuccessUI:
    """Test suite for successful installation UI display."""

    def test_installation_success_ui(self) -> None:
        """Verify "(2/2) Installing app ✓" format for successful installation.

        Tests that successful installation displays:
        - Phase number: (2/2)
        - Operation: "Installing"
        - App name
        - Success checkmark: ✓
        """
        # Arrange - create a completed successful installation task
        task = TaskState(
            task_id="i1",
            name="qownnotes",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"i1": task}
        order = ["i1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show installation in correct format
        assert "Installing:" in output
        assert "(2/2)" in output
        assert "Installing" in output
        assert "qownnotes" in output
        assert "✓" in output
        # Should have format like "(2/2) Installing qownnotes ✓"
        assert "(2/2) Installing qownnotes ✓" in output


@pytest.mark.integration
class TestProcessingPhasesSequentialUI:
    """Test suite for processing phase sequence display."""

    def test_processing_phases_sequential_ui(self) -> None:
        """Verify phase numbering (1/2, 2/2) for sequential task phases.

        Tests that verification and installation phases for the same app
        display correctly with proper phase numbers.
        """
        # Arrange - create both verification and installation for one app
        task1 = TaskState(
            task_id="v1",
            name="qownnotes",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
        )
        task2 = TaskState(
            task_id="i1",
            name="qownnotes",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"v1": task1, "i1": task2}
        order = ["v1", "i1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show proper phase sequence
        # Phases should be 1/2 then 2/2 for the same app
        assert "(1/2) Verifying qownnotes ✓" in output
        assert "(2/2) Installing qownnotes ✓" in output

    def test_processing_phases_multiple_apps_sequential_ui(self) -> None:
        """Verify phase numbering for multiple apps in sequence.

        Tests that when multiple apps have both verification and
        installation phases, all phases display correctly.
        """
        # Arrange - create phases for two apps
        task1 = TaskState(
            task_id="v1",
            name="qownnotes",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
        )
        task2 = TaskState(
            task_id="i1",
            name="qownnotes",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )
        task3 = TaskState(
            task_id="v2",
            name="appflowy",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
        )
        task4 = TaskState(
            task_id="i2",
            name="appflowy",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"v1": task1, "i1": task2, "v2": task3, "i2": task4}
        order = ["v1", "i1", "v2", "i2"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show all phases in order
        assert "(1/2) Verifying qownnotes ✓" in output
        assert "(2/2) Installing qownnotes ✓" in output
        assert "(1/2) Verifying appflowy ✓" in output
        assert "(2/2) Installing appflowy ✓" in output


@pytest.mark.integration
class TestProcessingErrorUI:
    """Test suite for processing error display."""

    def test_processing_error_ui(self) -> None:
        """Verify error messages appear correctly in processing section.

        Tests that when a processing task fails, the error message
        is displayed correctly with formatting:
        - Phase and operation
        - Error symbol
        - Error message on next line with indentation
        """
        # Arrange - create a failed task with error message
        task = TaskState(
            task_id="i1",
            name="broken-app",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=False,
            error_message="Failed to create desktop entry: Permission denied",
        )

        tasks = {"i1": task}
        order = ["i1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show error format
        assert "Installing:" in output
        assert "(2/2)" in output
        assert "Installing" in output
        assert "broken-app" in output
        # Error message should appear on next line with indentation
        assert "Error:" in output
        assert "Failed to create desktop entry" in output

    def test_verification_error_ui(self) -> None:
        """Verify error messages appear correctly in verification phase.

        Tests that verification errors display error messages properly.
        """
        # Arrange - create a failed verification task with error
        task = TaskState(
            task_id="v1",
            name="bad-app",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=False,
            error_message="Hash verification failed: SHA256 mismatch",
        )

        tasks = {"v1": task}
        order = ["v1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)
        output = "\n".join(output_lines)

        # Assert - should show error format
        assert "Verifying:" in output
        assert "(1/2)" in output
        assert "Verifying" in output
        assert "bad-app" in output
        # Error message should appear
        assert "Error:" in output
        assert "Hash verification failed" in output


@pytest.mark.integration
class TestProcessingHeaderSelection:
    """Test suite for processing section header selection."""

    def test_header_verifying_only(self) -> None:
        """Verify header is 'Verifying:' when only verification tasks present.

        Tests that the section header is correctly selected based on
        what types of processing tasks are present.
        """
        # Arrange - create only verification tasks
        task = TaskState(
            task_id="v1",
            name="qownnotes",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"v1": task}
        order = ["v1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)

        # Assert - should have "Verifying:" header
        assert len(output_lines) > 0
        assert output_lines[0] == "Verifying:"

    def test_header_installing_with_verification(self) -> None:
        """Verify header is 'Installing:' when both types of tasks present.

        Tests that when both verification and installation tasks are
        present, the header is still 'Installing:'.
        """
        # Arrange - create verification + installation tasks
        task1 = TaskState(
            task_id="v1",
            name="qownnotes",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
        )
        task2 = TaskState(
            task_id="i1",
            name="qownnotes",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"v1": task1, "i1": task2}
        order = ["v1", "i1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)

        # Assert - should have "Installing:" header
        assert len(output_lines) > 0
        assert output_lines[0] == "Installing:"

    def test_header_processing_with_update_only(self) -> None:
        """Verify header is 'Processing:' when only update tasks present.

        Tests that update operations alone use 'Processing:' as header.
        """
        # Arrange - create update tasks only
        task = TaskState(
            task_id="u1",
            name="qownnotes",
            progress_type=ProgressType.UPDATE,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        tasks = {"u1": task}
        order = ["u1"]
        config = SectionRenderConfig(
            bar_width=30,
            min_name_width=15,
            spinner_fps=4,
            interactive=False,
        )

        # Act - render processing section
        output_lines = render_processing_section(tasks, order, config)

        # Assert - should have "Processing:" header (for update-only)
        assert len(output_lines) > 0
        assert output_lines[0] == "Processing:"

    def test_processing_section_with_helper_and_fixture(
        self, install_success_output: str
    ) -> None:
        """Verify processing section using helper and fixture usage."""
        task1 = TaskState(
            task_id="v1",
            name="qownnotes",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=True,
            success=True,
        )
        task2 = TaskState(
            task_id="i1",
            name="qownnotes",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=True,
        )

        output = capture_progress_output(
            {"v1": task1, "i1": task2}, ["v1", "i1"], interactive=False
        )
        sections = parse_output_sections(output)
        assert "install" in sections
        assert "qownnotes" in "\n".join(sections["install"].lines)

        sections = parse_output_sections(install_success_output)
        assert "install" in sections
        text = "\n".join(sections["install"].lines)
        assert "qownnotes" in text
        assert "appflowy" in text
        assert "✓" in text
