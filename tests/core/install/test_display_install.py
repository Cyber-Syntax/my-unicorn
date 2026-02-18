"""Unit tests for install display formatting functions.

Tests the output formatting of installation results including success,
failure, warnings, and various result combinations using capsys fixture.
"""

from typing import Any

import pytest

from my_unicorn.core.install.display_install import (
    _categorize_results,
    _print_result_line,
    display_no_targets_error,
    print_install_summary,
)

# ============================================================================
# Fixtures for various result dictionaries
# ============================================================================


@pytest.fixture
def successful_install_result() -> dict[str, Any]:
    """Successful install result with version."""
    return {
        "name": "qownnotes",
        "version": "v24.12.5",
        "success": True,
        "status": "newly_installed",
    }


@pytest.fixture
def successful_install_no_version() -> dict[str, Any]:
    """Successful install result without version."""
    return {
        "name": "appflowy",
        "success": True,
        "status": "newly_installed",
    }


@pytest.fixture
def failed_install_result() -> dict[str, Any]:
    """Failed install result with error message."""
    return {
        "name": "zen-browser",
        "success": False,
        "error": "Download failed: Connection timeout",
    }


@pytest.fixture
def already_installed_result() -> dict[str, Any]:
    """Already installed result."""
    return {
        "name": "brave",
        "version": "v1.73.121",
        "success": True,
        "status": "already_installed",
    }


@pytest.fixture
def result_with_warning() -> dict[str, Any]:
    """Successful install with warning."""
    return {
        "name": "inkscape",
        "version": "v1.3.2",
        "success": True,
        "status": "newly_installed",
        "warning": "Desktop entry creation failed but app is installed",
    }


@pytest.fixture
def multiple_successful_results(
    successful_install_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Multiple successful install results."""
    return [
        successful_install_result,
        {
            "name": "inkscape",
            "version": "v1.3.2",
            "success": True,
            "status": "newly_installed",
        },
        {
            "name": "blender",
            "version": "v4.1.0",
            "success": True,
            "status": "newly_installed",
        },
    ]


@pytest.fixture
def multiple_already_installed(
    already_installed_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Multiple already installed results."""
    return [
        already_installed_result,
        {
            "name": "appflowy",
            "version": "v0.6.8",
            "success": True,
            "status": "already_installed",
        },
    ]


@pytest.fixture
def mixed_results(
    successful_install_result: dict[str, Any],
    failed_install_result: dict[str, Any],
    already_installed_result: dict[str, Any],
    result_with_warning: dict[str, Any],
) -> list[dict[str, Any]]:
    """Mixed success, failure, already installed, and warning results."""
    return [
        successful_install_result,
        failed_install_result,
        already_installed_result,
        result_with_warning,
    ]


# ============================================================================
# Test 1: All successful installs
# ============================================================================


def test_print_install_summary_all_successful(
    capsys: pytest.CaptureFixture[str],
    multiple_successful_results: list[dict[str, Any]],
) -> None:
    """Test display when all installations succeed."""
    print_install_summary(multiple_successful_results)
    captured = capsys.readouterr()
    output = captured.out

    # Verify header
    assert "Installation Summary:" in output
    assert "-" * 50 in output

    # Verify all app names appear
    assert "qownnotes" in output
    assert "inkscape" in output
    assert "blender" in output

    # Verify success indicators
    assert "✅ v24.12.5" in output
    assert "✅ v1.3.2" in output
    assert "✅ v4.1.0" in output

    # Verify statistics
    assert "🎉 Successfully installed 3 app(s)" in output


# ============================================================================
# Test 2: All already installed
# ============================================================================


def test_print_install_summary_all_already_installed(
    capsys: pytest.CaptureFixture[str],
    multiple_already_installed: list[dict[str, Any]],
) -> None:
    """Test display when all apps are already installed."""
    print_install_summary(multiple_already_installed)
    captured = capsys.readouterr()
    output = captured.out

    # Verify all already installed message
    assert "✅ All 2 specified app(s) are already installed:" in output

    # Verify app names appear
    assert "brave" in output
    assert "appflowy" in output

    # Should NOT show summary section
    assert "Installation Summary:" not in output


# ============================================================================
# Test 3: Mixed results (success, failure, already installed, warnings)
# ============================================================================


def test_print_install_summary_mixed_results(
    capsys: pytest.CaptureFixture[str],
    mixed_results: list[dict[str, Any]],
) -> None:
    """Test display with mixed success, failure, and already installed."""
    print_install_summary(mixed_results)
    captured = capsys.readouterr()
    output = captured.out

    # Verify header
    assert "Installation Summary:" in output

    # Verify success indicators
    assert "✅ v24.12.5" in output  # successful

    # Verify failure indicators
    assert "❌ Installation failed" in output
    assert "zen-browser" in output
    assert "Download failed: Connection timeout" in output

    # Verify already installed indicators
    assert "ℹ️  Already installed" in output  # noqa: RUF001
    assert "brave" in output

    # Verify warning indicators
    assert "⚠️" in output
    assert "Desktop entry creation failed but app is installed" in output

    # Verify statistics
    assert "🎉 Successfully installed 2 app(s)" in output
    assert "❌ 1 app(s) failed to install" in output
    assert "ℹ️  1 app(s) already installed" in output  # noqa: RUF001


# ============================================================================
# Test 4: All failed
# ============================================================================


def test_print_install_summary_all_failed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test display when all installations fail."""
    results = [
        {
            "name": "app1",
            "success": False,
            "error": "Network error",
        },
        {
            "name": "app2",
            "success": False,
            "error": "Hash verification failed",
        },
    ]
    print_install_summary(results)
    captured = capsys.readouterr()
    output = captured.out

    # Verify header
    assert "Installation Summary:" in output

    # Verify all failure indicators
    assert "❌ Installation failed" in output
    assert "app1" in output
    assert "app2" in output
    assert "Network error" in output
    assert "Hash verification failed" in output

    # Verify statistics
    assert "❌ 2 app(s) failed to install" in output


# ============================================================================
# Test 5: Some with warnings
# ============================================================================


def test_print_install_summary_with_warnings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test display with some apps installed with warnings."""
    results = [
        {
            "name": "app-with-warning",
            "version": "v1.0.0",
            "success": True,
            "status": "newly_installed",
            "warning": "Failed to create desktop entry",
        },
        {
            "name": "app-no-warning",
            "version": "v2.0.0",
            "success": True,
            "status": "newly_installed",
        },
        {
            "name": "another-warning",
            "version": "v3.0.0",
            "success": True,
            "status": "newly_installed",
            "warning": "Custom warning message",
        },
    ]
    print_install_summary(results)
    captured = capsys.readouterr()
    output = captured.out

    # Verify warnings are displayed
    assert "⚠️  Failed to create desktop entry" in output
    assert "⚠️  Custom warning message" in output

    # Verify warning count in statistics
    assert "⚠️  2 app(s) installed with warnings" in output


# ============================================================================
# Test 6: Empty results
# ============================================================================


def test_print_install_summary_empty_results(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test display with empty results list."""
    print_install_summary([])
    captured = capsys.readouterr()
    output = captured.out

    assert "No installations completed" in output
    assert "Installation Summary:" not in output


# ============================================================================
# Test 7: Categorize results logic
# ============================================================================


def test_categorize_results_logic(
    successful_install_result: dict[str, Any],
    failed_install_result: dict[str, Any],
    already_installed_result: dict[str, Any],
    result_with_warning: dict[str, Any],
) -> None:
    """Test that results are correctly categorized by status."""
    results = [
        successful_install_result,
        failed_install_result,
        already_installed_result,
        result_with_warning,
    ]
    categories = _categorize_results(results)

    # Verify keys exist
    assert "newly_installed" in categories
    assert "failed" in categories
    assert "already_installed" in categories
    assert "with_warnings" in categories

    # Verify correct categorization
    assert len(categories["newly_installed"]) == 2
    assert len(categories["failed"]) == 1
    assert len(categories["already_installed"]) == 1
    assert len(categories["with_warnings"]) == 1

    # Verify the warnings category is subset of newly_installed
    assert all(
        result in categories["newly_installed"]
        for result in categories["with_warnings"]
    )

    # Verify failed result is categorized correctly
    assert failed_install_result in categories["failed"]


# ============================================================================
# Test 8: Print result line formatting
# ============================================================================


def test_print_result_line_formatting(
    capsys: pytest.CaptureFixture[str],
    successful_install_result: dict[str, Any],
) -> None:
    """Test individual result line formatting."""
    _print_result_line(successful_install_result)
    captured = capsys.readouterr()
    output = captured.out

    # Verify formatting: name (left-aligned, 25 chars) + status
    assert "qownnotes" in output
    assert "✅ v24.12.5" in output


def test_print_result_line_with_warning(
    capsys: pytest.CaptureFixture[str],
    result_with_warning: dict[str, Any],
) -> None:
    """Test result line formatting with warning."""
    _print_result_line(result_with_warning)
    captured = capsys.readouterr()
    output = captured.out

    # Verify app name and success
    assert "inkscape" in output
    assert "✅ v1.3.2" in output

    # Verify warning on second line
    assert "⚠️" in output
    assert "Desktop entry creation failed but app is installed" in output


def test_print_result_line_already_installed(
    capsys: pytest.CaptureFixture[str],
    already_installed_result: dict[str, Any],
) -> None:
    """Test result line for already installed app."""
    _print_result_line(already_installed_result)
    captured = capsys.readouterr()
    output = captured.out

    assert "brave" in output
    assert "ℹ️  Already installed" in output  # noqa: RUF001


def test_print_result_line_failed(
    capsys: pytest.CaptureFixture[str],
    failed_install_result: dict[str, Any],
) -> None:
    """Test result line for failed installation."""
    _print_result_line(failed_install_result)
    captured = capsys.readouterr()
    output = captured.out

    # Verify failure indicator and error message
    assert "zen-browser" in output
    assert "❌ Installation failed" in output
    assert "Download failed: Connection timeout" in output


# ============================================================================
# Test 9: Display no targets error
# ============================================================================


def test_display_no_targets_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test error display when no installation targets specified."""
    display_no_targets_error()

    # Verify error log entry
    assert any(
        "❌ No targets specified." in record.message
        for record in caplog.records
        if record.levelname == "ERROR"
    )

    # Verify info log entry with hint
    assert any(
        "💡 Use 'my-unicorn catalog'" in record.message
        for record in caplog.records
        if record.levelname == "INFO"
    )


# ============================================================================
# Additional edge cases
# ============================================================================


def test_print_install_summary_result_without_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test handling of result without name field."""
    results = [
        {
            "success": True,
            "status": "newly_installed",
            "version": "v1.0.0",
        }
    ]
    print_install_summary(results)
    captured = capsys.readouterr()
    output = captured.out

    # Should show "Unknown" as fallback
    assert "Unknown" in output
    assert "✅ v1.0.0" in output


def test_categorize_results_empty() -> None:
    """Test categorization with empty results."""
    categories = _categorize_results([])

    assert categories["newly_installed"] == []
    assert categories["failed"] == []
    assert categories["already_installed"] == []
    assert categories["with_warnings"] == []
