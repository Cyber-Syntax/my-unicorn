"""Terminal output writer for ASCII progress display.

This module provides the `TerminalWriter` class which encapsulates terminal
I/O operations and manages output-related state. It handles both interactive
mode (with cursor control for in-place updates) and non-interactive mode
(with section deduplication to minimize output).
"""

from __future__ import annotations

from typing import TextIO


class TerminalWriter:
    """Manages terminal output for progress display.

    Handles both interactive (with cursor control) and non-interactive
    (with section deduplication) output modes. Tracks output state to
    enable proper clearing and avoid duplicate section headers.

    Attributes:
        output: Output stream (typically sys.stdout or StringIO for tests)
        interactive: Whether to use interactive mode with cursor control
        _last_output_lines: Number of lines written (interactive mode)
        _written_sections: Set of section signatures written (non-interactive)
        _last_noninteractive_output: Cached output (non-interactive)
        _last_noninteractive_write_time: Timestamp of last write (non-interactive)
    """

    def __init__(self, output: TextIO, interactive: bool) -> None:
        """Initialize terminal writer.

        Args:
            output: Output stream for writing
            interactive: Whether to use interactive mode

        """
        self.output = output
        self.interactive = interactive

        # State for interactive mode
        self._last_output_lines = 0

        # State for non-interactive mode
        self._written_sections: set[str] = set()
        self._last_noninteractive_output = ""
        self._last_noninteractive_write_time = 0.0

    def _clear_previous_output(self) -> None:
        """Clear previously written lines in interactive mode."""
        if not self.interactive or self._last_output_lines == 0:
            return

        # Move cursor up to start of previous output
        self.output.write(f"\033[{self._last_output_lines}A")
        # Clear from cursor to end of screen
        self.output.write("\033[J")

        # Ensure output is written immediately
        self.output.flush()

    def _write_output_safe(self, text: str) -> None:
        """Write text to output stream, suppressing IO errors."""
        try:
            self.output.write(text)
            self.output.flush()
        except Exception:
            pass

    @staticmethod
    def _find_new_sections(
        output: str, known_sections: set[str]
    ) -> tuple[list[str], set[str]]:
        """Parse output and find sections not in known_sections.

        Args:
            output: Output string containing sections separated by blank lines
            known_sections: Set of section signatures already written

        Returns:
            Tuple of (new_sections_list, new_signatures_set)

        """
        sections = output.split("\n\n")
        new_sections: list[str] = []
        new_signatures: set[str] = set()

        for section in sections:
            section_sig = section.strip()
            if section_sig and section_sig not in known_sections:
                new_sections.append(section)
                new_signatures.add(section_sig)

        return new_sections, new_signatures

    def write_interactive(self, output: str) -> int:
        """Write output in interactive mode with cursor control.

        Args:
            output: Output string to write

        Returns:
            Number of lines written

        """
        self._clear_previous_output()

        if output:
            lines = output.split("\n")
            # Filter out trailing empty string from split to get accurate count
            if lines and lines[-1] == "":
                lines = lines[:-1]

            # Write all lines at once to minimize flickering
            output_text = "\n".join(lines) + "\n"
            try:
                self.output.write(output_text)
                self.output.flush()
            except Exception:
                # swallow IO errors
                pass

            # Return number of lines written and update writer state
            lines_written = len(lines)
            self._last_output_lines = lines_written

            return lines_written

        # Ensure last output lines is zero when nothing was written
        self._last_output_lines = 0
        return 0

    def write_noninteractive(
        self, output: str, known_sections: set[str] | None = None
    ) -> set[str]:
        """Write output in non-interactive mode (minimal output).

        Args:
            output: Output string to write
            known_sections: Optional set of already-written section signatures
                used to detect new/updated sections. If ``None``, the
                internal `_written_sections` set is used.

        Returns:
            Set of section signatures that were written

        """
        if not hasattr(self.output, "write"):
            return set()

        if "Summary:" in output:
            self._write_output_safe(output + "\n")
            return {output.strip()}

        if not output.strip():
            return set()

        if known_sections is None:
            known_sections = set(self._written_sections)

        new_sections, added_signatures = self._find_new_sections(
            output, known_sections
        )

        if new_sections:
            self._write_output_safe("\n\n".join(new_sections) + "\n")

        return added_signatures
