"""Tests for UI output normalization.

These tests verify that dynamic content in output can be normalized
reliably for comparing progress output across different runs.
"""

from __future__ import annotations

import re

import pytest

from .test_ui_helpers import parse_output_sections


def normalize_output_for_comparison(output: str) -> str:
    """Normalize dynamic content in output for reliable comparison.

    Replaces:
    - Timestamps with <TIMESTAMP>
    - Download speeds (e.g., "12.5 MB/s") with <SPEED>
    - ETAs (e.g., "00:45") with <ETA>
    - Dynamic spinner characters with <SPINNER>
    - Progress bar content with <BAR>

    Args:
        output: Raw output string

    Returns:
        Normalized output with placeholders

    """
    # Replace speeds like "12.5 MB/s" or "1.2 GiB/s"
    normalized = re.sub(
        r"\d+\.?\d*\s*(?:B|KB|MB|GiB|TB)/s",
        "<SPEED>",
        output,
    )

    # Replace ETAs like "00:45" or "12:34"
    normalized = re.sub(r"\d{2}:\d{2}", "<ETA>", normalized)

    # Replace progress bar (sequences of = within brackets)
    normalized = re.sub(r"\[=+\]", "[<BAR>]", normalized)

    # Replace spinner characters
    spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    for char in spinner_chars:
        normalized = normalized.replace(char, "<SPINNER>")

    # Normalize percentage values (keep structure but replace numbers)
    normalized = re.sub(r"\d+%", "<PERCENT>", normalized)

    # Normalize size values like "41.6 MiB"
    return re.sub(
        r"\d+\.?\d*\s*(?:B|KB|MB|MiB|GiB|TiB)",
        "<SIZE>",
        normalized,
    )


@pytest.mark.integration
class TestNormalizeOutputForComparison:
    """Test suite for output normalization."""

    def test_normalize_speeds(self) -> None:
        """Test normalization of download speeds."""
        output = "test-app  1024 MB  12.5 MB/s 00:45 [====]"

        normalized = normalize_output_for_comparison(output)

        assert "<SPEED>" in normalized
        assert "12.5 MB/s" not in normalized

    def test_normalize_eta(self) -> None:
        """Test normalization of ETA values."""
        output = "Downloading: 00:45 remaining"

        normalized = normalize_output_for_comparison(output)

        assert "<ETA>" in normalized
        assert "00:45" not in normalized

    def test_normalize_progress_bar(self) -> None:
        """Test normalization of progress bars."""
        output = "Progress: [==============================] 100%"

        normalized = normalize_output_for_comparison(output)

        assert "<BAR>" in normalized
        # Bar characters should be replaced
        assert "======" not in normalized

    def test_normalize_spinner(self) -> None:
        """Test normalization of spinner characters."""
        output = "Installing app ⠋"

        normalized = normalize_output_for_comparison(output)

        assert "<SPINNER>" in normalized
        assert "⠋" not in normalized

    def test_normalize_sizes(self) -> None:
        """Test normalization of file sizes."""
        output = "QOwnNotes-x86_64   41.6 MiB  19.8 MB/s 00:00"

        normalized = normalize_output_for_comparison(output)

        assert "<SIZE>" in normalized
        # Sizes should be normalized
        assert "41.6 MiB" not in normalized
        assert "19.8 MB/s" not in normalized

    def test_normalize_percentages(self) -> None:
        """Test normalization of percentage values."""
        output = "Progress: 50% complete, 100% downloaded"

        normalized = normalize_output_for_comparison(output)

        assert normalized.count("<PERCENT>") == 2
        assert "50%" not in normalized
        assert "100%" not in normalized

    def test_normalize_preserves_structure(self) -> None:
        """Test that normalization preserves output structure."""
        output = """Downloading:
app-1  100 MB  12.5 MB/s 00:08 [=====] 50% ✓
app-2  200 MB  8.0 MB/s 00:25 [===] 25%
"""

        normalized = normalize_output_for_comparison(output)

        # Should still have section header
        assert "Downloading:" in normalized
        # Should still have app names
        assert "app-1" in normalized
        assert "app-2" in normalized
        # Should have normalized values
        assert "<SPEED>" in normalized
        assert "<ETA>" in normalized
        assert "<PERCENT>" in normalized

    def test_normalize_complex_output(
        self, install_success_output: str
    ) -> None:
        """Test normalization of complex realistic output."""
        output = install_success_output

        normalized = normalize_output_for_comparison(output)

        # Structure should be preserved
        assert "Fetching from API:" in normalized
        assert "Downloading (" in normalized or "Downloading:" in normalized
        assert "Installing:" in normalized
        # Dynamic values should be normalized
        assert "<SIZE>" in normalized
        assert "<SPEED>" in normalized
        assert "<BAR>" in normalized
        # Static values should remain
        assert "qownnotes" in normalized
        assert "Retrieved" in normalized

    def test_normalize_version_arrows(self) -> None:
        """Test normalization of version change arrows.

        Version numbers are static content (don't change between runs),
        so they should be preserved as-is.
        """
        output = "qownnotes                 ✅ 26.2.1 → 26.2.4"

        normalized = normalize_output_for_comparison(output)

        # Arrow and versions should be preserved (static content)
        assert "→" in normalized
        assert "26.2.1" in normalized
        assert "26.2.4" in normalized

    def test_normalize_separator_lines(self) -> None:
        """Test normalization of separator lines."""
        output = """📦 Update Summary:
--------------------------------------------------
qownnotes                 ✅ 26.2.1 → 26.2.4
"""

        normalized = normalize_output_for_comparison(output)

        # Separator line should be preserved but normalized
        assert "Update Summary:" in normalized
        assert "qownnotes" in normalized

    def test_normalize_indented_warning_messages(self) -> None:
        """Test normalization of indented warning/error messages."""
        output = """(1/2) Verifying weektodo ⚠
    not verified (dev did not provide checksums)
(2/2) Installing weektodo ✓"""

        normalized = normalize_output_for_comparison(output)

        # Structure should be preserved
        assert "Verifying weektodo" in normalized
        assert "not verified" in normalized
        assert "Installing weektodo" in normalized

    def test_normalize_install_warning_fixture(
        self, install_warning_output: str
    ) -> None:
        """Test normalization of complex warning fixture."""
        fixture_content = install_warning_output

        sections = parse_output_sections(fixture_content)

        # Should parse all sections
        assert "api" in sections
        assert "download" in sections
        assert "install" in sections

        # Install section should include warning message
        install_lines = "\n".join(sections["install"].lines)
        assert "weektodo" in install_lines
        assert "not verified" in install_lines

        # Normalization should preserve structure
        normalized = normalize_output_for_comparison(fixture_content)
        assert "Fetching from API:" in normalized
        assert "Downloading (3):" in normalized
        assert "Installing:" in normalized
        assert "Installation Summary:" in normalized

    def test_normalize_update_summary_fixture(
        self, update_success_output: str
    ) -> None:
        """Test normalization of update fixture with version changes."""
        fixture_content = update_success_output

        sections = parse_output_sections(fixture_content)

        # Should parse all sections
        assert "api" in sections
        assert "download" in sections
        assert "install" in sections

        # Install section should include Updating operations
        install_lines = "\n".join(sections["install"].lines)
        assert "Updating appflowy" in install_lines
        assert "Updating qownnotes" in install_lines

        # Normalization should preserve version arrows and summaries
        normalized = normalize_output_for_comparison(fixture_content)
        assert "Update Summary:" in normalized
        assert "→" in normalized
        assert "Updating appflowy" in normalized
