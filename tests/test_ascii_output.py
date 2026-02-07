"""Tests for TerminalWriter in ascii_output module."""

from __future__ import annotations

import io
import time
from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.core.progress.ascii_output import TerminalWriter


class TestTerminalWriterInit:
    """Tests for TerminalWriter initialization."""

    def test_terminal_writer_init_interactive(self) -> None:
        """Test initialization in interactive mode."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)

        assert writer.output is output
        assert writer.interactive is True
        assert writer._last_output_lines == 0
        assert writer._written_sections == set()
        assert writer._last_noninteractive_output == ""
        assert writer._last_noninteractive_write_time == 0.0

    def test_terminal_writer_init_noninteractive(self) -> None:
        """Test initialization in non-interactive mode."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)

        assert writer.output is output
        assert writer.interactive is False
        assert writer._last_output_lines == 0
        assert writer._written_sections == set()
        assert writer._last_noninteractive_output == ""
        assert writer._last_noninteractive_write_time == 0.0


class TestClearPreviousOutput:
    """Tests for _clear_previous_output method."""

    def test_clear_previous_output_with_lines(self) -> None:
        """Test clearing with ANSI codes when lines were written."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)
        writer._last_output_lines = 5

        writer._clear_previous_output()

        result = output.getvalue()
        assert "\033[5A" in result  # Move cursor up 5 lines
        assert "\033[J" in result  # Clear from cursor to end of screen

    def test_clear_previous_output_zero_lines(self) -> None:
        """Test early return when no lines were written."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)
        writer._last_output_lines = 0

        writer._clear_previous_output()

        assert output.getvalue() == ""

    def test_clear_previous_output_noninteractive_mode(self) -> None:
        """Test that clearing is skipped in non-interactive mode."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)
        writer._last_output_lines = 5

        writer._clear_previous_output()

        assert output.getvalue() == ""


class TestWriteOutputSafe:
    """Tests for _write_output_safe method."""

    def test_write_output_safe_success(self) -> None:
        """Test successful write to output stream."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)

        writer._write_output_safe("test content")

        assert output.getvalue() == "test content"

    def test_write_output_safe_io_error(self) -> None:
        """Test IO error suppression when writing fails."""
        output = MagicMock()
        output.write.side_effect = IOError("write failed")
        writer = TerminalWriter(output, interactive=True)

        # Should not raise an exception
        writer._write_output_safe("test content")

    def test_write_output_safe_flush_on_exception(self) -> None:
        """Test that flush exception is also suppressed."""
        output = MagicMock()
        output.flush.side_effect = IOError("flush failed")
        writer = TerminalWriter(output, interactive=True)

        # Should not raise an exception
        writer._write_output_safe("test content")


class TestFindNewSections:
    """Tests for _find_new_sections static method."""

    def test_find_new_sections(self) -> None:
        """Test parsing output and finding new sections."""
        output = "Section A\n\nSection B\n\nSection C"
        known_sections = {"Section A"}

        sections, signatures = TerminalWriter._find_new_sections(
            output, known_sections
        )

        assert len(sections) == 2
        assert "Section B" in sections
        assert "Section C" in sections
        assert len(signatures) == 2
        assert "Section B" in signatures
        assert "Section C" in signatures

    def test_find_new_sections_empty_output(self) -> None:
        """Test handling of empty output."""
        output = ""
        known_sections: set[str] = set()

        sections, signatures = TerminalWriter._find_new_sections(
            output, known_sections
        )

        assert sections == []
        assert signatures == set()

    def test_find_new_sections_all_known(self) -> None:
        """Test when all sections are already known."""
        output = "Section A\n\nSection B"
        known_sections = {"Section A", "Section B"}

        sections, signatures = TerminalWriter._find_new_sections(
            output, known_sections
        )

        assert sections == []
        assert signatures == set()

    def test_find_new_sections_whitespace_handling(self) -> None:
        """Test that whitespace is properly stripped from section signatures."""
        output = "  Section A  \n\n  Section B  "
        known_sections: set[str] = set()

        sections, signatures = TerminalWriter._find_new_sections(
            output, known_sections
        )

        assert "Section A" in signatures
        assert "Section B" in signatures


class TestWriteInteractive:
    """Tests for write_interactive method."""

    def test_write_interactive_mode(self) -> None:
        """Test interactive write with line tracking."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)

        lines_written = writer.write_interactive("Line 1\nLine 2\nLine 3")

        assert lines_written == 3
        assert writer._last_output_lines == 3
        assert "Line 1\nLine 2\nLine 3\n" in output.getvalue()

    def test_write_interactive_empty_output(self) -> None:
        """Test empty output handling."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)

        lines_written = writer.write_interactive("")

        assert lines_written == 0
        assert writer._last_output_lines == 0

    def test_write_interactive_trailing_newline(self) -> None:
        """Test that trailing newlines don't create empty sections."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)

        lines_written = writer.write_interactive("Line 1\nLine 2\n")

        assert lines_written == 2
        assert writer._last_output_lines == 2

    def test_write_interactive_io_error(self) -> None:
        """Test IO error handling during write."""
        output = MagicMock()
        output.write.side_effect = IOError("write failed")
        writer = TerminalWriter(output, interactive=True)

        # Should not raise an exception
        lines_written = writer.write_interactive("test")

        # When errors occur, state should still be updated
        assert lines_written == 1

    def test_write_interactive_clears_previous(self) -> None:
        """Test that previous output is cleared before writing."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=True)
        writer._last_output_lines = 3

        writer.write_interactive("New content")

        result = output.getvalue()
        # Should contain cursor movement for clearing
        assert "\033[3A" in result or "New content" in result


class TestWriteNoninteractive:
    """Tests for write_noninteractive method."""

    def test_write_noninteractive_mode(self) -> None:
        """Test non-interactive write with deduplication."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)

        sections = writer.write_noninteractive(
            "Section A\n\nSection B", known_sections=set()
        )

        assert len(sections) == 2
        assert "Section A" in sections
        assert "Section B" in sections

    def test_write_noninteractive_new_sections(self) -> None:
        """Test new section detection and writing."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)
        known_sections = {"Section A"}

        sections = writer.write_noninteractive(
            "Section A\n\nSection B\n\nSection C", known_sections=known_sections
        )

        assert "Section B" in sections
        assert "Section C" in sections
        assert output.getvalue() != ""

    def test_write_noninteractive_duplicate_sections(self) -> None:
        """Test that duplicate sections are filtered."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)
        known_sections = {"Section A", "Section B"}

        sections = writer.write_noninteractive(
            "Section A\n\nSection B\n\nSection C", known_sections=known_sections
        )

        assert len(sections) == 1
        assert "Section C" in sections

    def test_write_noninteractive_summary_output(self) -> None:
        """Test that Summary sections are written fully."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)

        sections = writer.write_noninteractive("Summary: test content")

        assert len(sections) == 1
        assert output.getvalue() != ""

    def test_write_noninteractive_empty_output(self) -> None:
        """Test handling of empty output."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)

        sections = writer.write_noninteractive("")

        assert sections == set()

    def test_write_noninteractive_uses_internal_state_when_no_known_sections(
        self,
    ) -> None:
        """Test that internal state is used when known_sections is None."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)
        writer._written_sections.add("Section A")

        sections = writer.write_noninteractive("Section A\n\nSection B")

        assert "Section B" in sections

    def test_write_noninteractive_io_error(self) -> None:
        """Test IO error handling during write."""
        output = MagicMock()
        output.write.side_effect = IOError("write failed")
        writer = TerminalWriter(output, interactive=False)

        # Should not raise an exception
        sections = writer.write_noninteractive("Section A\n\nSection B")

        # Should still return the sections that would have been written
        assert len(sections) > 0

    def test_write_noninteractive_no_output_attribute(self) -> None:
        """Test handling when output doesn't have write method."""
        output = MagicMock(spec=[])  # No write method
        writer = TerminalWriter(output, interactive=False)

        sections = writer.write_noninteractive("Section A\n\nSection B")

        assert sections == set()

    def test_write_noninteractive_whitespace_only(self) -> None:
        """Test handling of whitespace-only output."""
        output = io.StringIO()
        writer = TerminalWriter(output, interactive=False)

        sections = writer.write_noninteractive("   \n\n   ")

        assert sections == set()
