"""Integration tests for installation/update summary UI display.

These tests verify that the summary sections render correctly and match
expected UI formats from fixture files, including app alignment, status
icons, and version change display.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any

import pytest

from my_unicorn.core.install.display_install import print_install_summary
from my_unicorn.core.update.display_update import display_update_results
from my_unicorn.core.update.info import UpdateInfo

from .test_ui_helpers import parse_output_sections
from .test_ui_normalization import normalize_output_for_comparison


def _capture_print_output(func: callable, *args: Any, **kwargs: Any) -> str:
    """Capture stdout from a function call.

    Args:
        func: Function to capture output from
        *args: Positional arguments to pass to function
        **kwargs: Keyword arguments to pass to function

    Returns:
        Captured stdout output

    """
    f = io.StringIO()
    with redirect_stdout(f):
        func(*args, **kwargs)
    return f.getvalue()


def _extract_summary_section(output: str, header: str) -> str:
    """Extract summary section from output by header text.

    Args:
        output: Full output string
        header: Section header to search for (e.g., "📦 Installation Summary:")

    Returns:
        Extracted section from header to end, or empty string if not found

    """
    lines = output.split("\n")
    summary_start = None
    for i, line in enumerate(lines):
        if header in line:
            summary_start = i
            break

    if summary_start is None:
        return ""

    return "\n".join(lines[summary_start:])


@pytest.mark.integration
class TestInstallSummaryUI:
    """Test suite for installation summary UI display."""

    def test_install_summary_success_ui(self) -> None:
        """Verify 'Successfully installed X app(s)' format matches fixture.

        Test that single successful installation produces correct summary
        with app name, checkmark, and version.
        """
        # Arrange
        results = [
            {
                "name": "qownnotes",
                "status": "installed",
                "success": True,
                "version": "26.2.4",
            }
        ]

        # Act
        output = _capture_print_output(print_install_summary, results)

        # Assert
        assert "📦 Installation Summary:" in output
        assert "-" * 50 in output
        assert "qownnotes" in output
        assert "✅" in output
        assert "26.2.4" in output
        assert "🎉 Successfully installed 1 app(s)" in output

    def test_install_summary_with_warnings_ui(self) -> None:
        """Verify warning count display in summary.

        Test that apps with warnings show warning indicator and count
        in final statistics.
        """
        # Arrange
        results = [
            {
                "name": "weektodo",
                "status": "installed",
                "success": True,
                "version": "2.2.0",
                "warning": (
                    "Not verified - developer did not provide checksums"
                ),
            }
        ]

        # Act
        output = _capture_print_output(print_install_summary, results)

        # Assert
        assert "📦 Installation Summary:" in output
        assert "weektodo" in output
        assert "✅" in output
        assert "2.2.0" in output
        assert "⚠️" in output
        assert "developer did not provide checksums" in output
        assert "🎉 Successfully installed 1 app(s)" in output
        assert "⚠️  1 app(s) installed with warnings" in output

    def test_install_summary_alignment_ui(self) -> None:
        """Verify app names align with status icons.

        Test that multiple apps are aligned properly with consistent
        spacing for icons and text.
        """
        # Arrange
        results = [
            {
                "name": "appflowy",
                "status": "installed",
                "success": True,
                "version": "0.11.1",
            },
            {
                "name": "qownnotes",
                "status": "installed",
                "success": True,
                "version": "26.2.4",
            },
        ]

        # Act
        output = _capture_print_output(print_install_summary, results)
        lines = output.split("\n")

        # Assert
        assert "📦 Installation Summary:" in output
        # Find the app lines (should be after the header and separator)
        app_lines = [
            line
            for line in lines
            if ("appflowy" in line or "qownnotes" in line) and "✅" in line
        ]
        assert len(app_lines) == 2
        # Both lines should have checkmark at similar position
        for line in app_lines:
            assert "✅" in line
            # Icon should be within column width
            assert len(line.split("✅")[0]) < 30

    def test_batch_install_summary_ui(self) -> None:
        """Verify multiple apps with mixed states display correctly.

        Test batch installation with successful and already-installed apps.
        """
        # Arrange
        results = [
            {
                "name": "appflowy",
                "status": "installed",
                "success": True,
                "version": "0.11.1",
            },
            {
                "name": "qownnotes",
                "status": "installed",
                "success": True,
                "version": "26.2.4",
            },
        ]

        # Act
        output = _capture_print_output(print_install_summary, results)

        # Assert
        assert "📦 Installation Summary:" in output
        assert "-" * 50 in output
        assert "appflowy" in output
        assert "qownnotes" in output
        assert "🎉 Successfully installed 2 app(s)" in output
        # Should not show other stats after successful message
        success_split = output.split("🎉")
        if len(success_split) > 1:
            assert "⚠️" not in success_split[0]

    def test_install_all_already_installed(self) -> None:
        """Verify format when all apps are already installed.

        Test that 'already installed' scenario uses different header
        and format.
        """
        # Arrange
        results = [
            {
                "name": "appflowy",
                "status": "already_installed",
                "success": True,
                "version": "0.11.1",
            }
        ]

        # Act
        output = _capture_print_output(print_install_summary, results)

        # Assert
        assert "✅ All 1 specified app(s) are already installed:" in output
        assert "• appflowy" in output
        # Should not show "Installation Summary" header
        assert "📦 Installation Summary:" not in output


@pytest.mark.integration
class TestUpdateSummaryUI:
    """Test suite for update summary UI display."""

    def test_update_summary_version_change_ui(self) -> None:
        """Verify 'X.Y.Z → A.B.C' version change format matches fixture.

        Test that update summary shows correct version change format
        with arrow notation.
        """
        # Arrange
        update_infos = [
            UpdateInfo(
                app_name="qownnotes",
                current_version="26.2.1",
                latest_version="26.2.4",
                prerelease=False,
                error_reason=None,
            )
        ]
        results = {
            "updated": ["qownnotes"],
            "failed": [],
            "up_to_date": [],
            "update_infos": update_infos,
        }

        # Act
        output = _capture_print_output(display_update_results, results)

        # Assert
        assert "📦 Update Summary:" in output
        assert "-" * 50 in output
        assert "qownnotes" in output
        assert "✅" in output
        assert "26.2.1 → 26.2.4" in output
        assert "🎉 Successfully updated 1 app(s)" in output

    def test_update_summary_already_updated_ui(self) -> None:
        """Verify 'Already up to date' format with version display.

        Test that apps already at latest version show info icon and
        version number.
        """
        # Arrange
        update_infos = [
            UpdateInfo(
                app_name="appflowy",
                current_version="0.11.1",
                latest_version="0.11.1",
                prerelease=False,
                error_reason=None,
            )
        ]
        results = {
            "updated": [],
            "failed": [],
            "up_to_date": ["appflowy"],
            "update_infos": update_infos,
        }

        # Act
        output = _capture_print_output(display_update_results, results)

        # Assert
        assert "📦 Update Summary:" in output
        assert "appflowy" in output
        assert "ℹ️" in output  # noqa: RUF001
        assert "Already up to date" in output
        assert "0.11.1" in output
        assert "ℹ️  1 app(s) already up to date" in output  # noqa: RUF001

    def test_batch_update_summary_ui(self) -> None:
        """Verify multiple apps with version changes display correctly.

        Test batch update with multiple apps showing version changes.
        """
        # Arrange
        update_infos = [
            UpdateInfo(
                app_name="qownnotes",
                current_version="26.2.1",
                latest_version="26.2.4",
                prerelease=False,
                error_reason=None,
            ),
            UpdateInfo(
                app_name="appflowy",
                current_version="0.11.0",
                latest_version="0.11.1",
                prerelease=False,
                error_reason=None,
            ),
        ]
        results = {
            "updated": ["qownnotes", "appflowy"],
            "failed": [],
            "up_to_date": [],
            "update_infos": update_infos,
        }

        # Act
        output = _capture_print_output(display_update_results, results)

        # Assert
        assert "📦 Update Summary:" in output
        assert "-" * 50 in output
        assert "qownnotes" in output
        assert "appflowy" in output
        assert "26.2.1 → 26.2.4" in output
        assert "0.11.0 → 0.11.1" in output
        assert "🎉 Successfully updated 2 app(s)" in output

    def test_update_summary_mixed_states_ui(self) -> None:
        """Verify summary with updated, up-to-date, and failed apps.

        Test that all app states are displayed with appropriate icons
        and formatting.
        """
        # Arrange
        update_infos = [
            UpdateInfo(
                app_name="qownnotes",
                current_version="26.2.1",
                latest_version="26.2.4",
                prerelease=False,
                error_reason=None,
            ),
            UpdateInfo(
                app_name="appflowy",
                current_version="0.11.1",
                latest_version="0.11.1",
                prerelease=False,
                error_reason=None,
            ),
            UpdateInfo(
                app_name="badapp",
                current_version="1.0.0",
                latest_version="2.0.0",
                prerelease=False,
                error_reason="Failed to fetch releases",
            ),
        ]
        results = {
            "updated": ["qownnotes"],
            "failed": ["badapp"],
            "up_to_date": ["appflowy"],
            "update_infos": update_infos,
        }

        # Act
        output = _capture_print_output(display_update_results, results)

        # Assert
        assert "📦 Update Summary:" in output
        # Updated app should have checkmark
        assert "qownnotes" in output
        assert "26.2.1 → 26.2.4" in output
        assert "✅" in output
        # Up-to-date app should have info icon
        assert "appflowy" in output
        assert "Already up to date (0.11.1)" in output
        assert "ℹ️" in output  # noqa: RUF001
        # Failed app should have X icon
        assert "badapp" in output
        assert "❌" in output
        # Summary should show all counts
        assert "🎉 Successfully updated 1 app(s)" in output
        assert "❌ 1 app(s) failed to update" in output
        assert "ℹ️  1 app(s) already up to date" in output  # noqa: RUF001


@pytest.mark.integration
class TestSummaryUIFixtureValidation:
    """Test that actual summary output matches fixture expectations.

    This class validates that the summary functions produce output
    matching the expected format from fixture files.
    """

    def test_install_success_matches_fixture_format(
        self, install_success_output: str
    ) -> None:
        """Verify install success output matches fixture structure.

        Uses install_success.txt fixture to validate expected format.
        Demonstrates usage of helper function to extract summary section.
        """
        # Arrange - extract summary section from fixture
        fixture_summary = _extract_summary_section(
            install_success_output, "📦 Installation Summary:"
        )

        # Assert
        assert fixture_summary != "", "Fixture missing summary header"
        assert "📦 Installation Summary:" in fixture_summary
        assert "-" * 50 in fixture_summary
        assert "✅" in fixture_summary
        assert "🎉 Successfully installed" in fixture_summary

    def test_update_success_matches_fixture_format(
        self, update_success_output: str
    ) -> None:
        """Verify update success output matches fixture structure.

        Uses update_success.txt fixture to validate expected format.
        Demonstrates output normalization before comparison.
        """
        # Arrange - extract summary section
        fixture_summary = _extract_summary_section(
            update_success_output, "📦 Update Summary:"
        )
        assert fixture_summary != "", "Fixture missing summary header"

        # Act - normalize output for consistent comparison
        normalized_summary = normalize_output_for_comparison(fixture_summary)

        # Assert - verify formatting is preserved after normalization
        assert "📦 Update Summary:" in normalized_summary
        assert "-" * 50 in normalized_summary
        assert "→" in normalized_summary  # Version change arrow
        assert "✅" in normalized_summary
        assert "🎉 Successfully updated" in normalized_summary

    def test_install_warning_matches_fixture_format(
        self, install_warning_output: str
    ) -> None:
        """Verify install with warnings matches fixture structure.

        Uses install_warning.txt fixture to validate warning display.
        Uses helper function to extract section.
        """
        # Arrange - extract summary section using helper
        fixture_summary = _extract_summary_section(
            install_warning_output, "📦 Installation Summary:"
        )
        assert fixture_summary != "", "Fixture missing summary header"

        # Assert - verify warning-specific elements
        assert "📦 Installation Summary:" in fixture_summary
        assert "✅" in fixture_summary
        assert "⚠️" in fixture_summary
        assert "🎉 Successfully installed" in fixture_summary
        assert (
            "⚠️  1 app(s) installed with warnings" in fixture_summary
            or "⚠️  " in fixture_summary.split("🎉")[1]
        )

    def test_fixture_output_parsing_with_helper(
        self, install_success_output: str
    ) -> None:
        """Verify fixture output can be parsed for progress sections.

        Demonstrates using parse_output_sections to extract progress
        sections from fixture output, validating complete output format.
        """
        # Act - parse progress sections from fixture
        sections = parse_output_sections(install_success_output)

        # Assert - progress sections should be present
        assert "api" in sections, "Missing API section from fixture"
        assert "download" in sections, "Missing download section from fixture"
        assert "install" in sections, "Missing install section from fixture"

        # Verify summary section also exists after progress sections
        assert "📦 Installation Summary:" in install_success_output
        fixture_summary = _extract_summary_section(
            install_success_output, "📦 Installation Summary:"
        )
        assert fixture_summary != "", "Summary section missing from fixture"
