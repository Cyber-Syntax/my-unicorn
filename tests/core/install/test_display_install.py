"""Unit tests for install display formatting functions.

Tests the output formatting of installation results including success,
failure, warnings, and various result combinations using caplog fixture.

Note on capsys vs caplog:
    print()        → captured by capsys (stdout/stderr)
    logger.info()  → captured by caplog (Python logging system)

    Since the display helpers use logger.*, all assertions must check
    caplog.text (or caplog.records), not capsys.readouterr().out.
"""

import logging
from typing import Any

import pytest

from my_unicorn.core.install import (
    _categorize_results,
    _print_result_line,
    display_no_targets_error,
    print_install_summary,
)


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


def test_print_install_summary_all_successful(
    caplog: pytest.LogCaptureFixture,
    multiple_successful_results: list[dict[str, Any]],
) -> None:
    """Test display when all installations succeed."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        print_install_summary(multiple_successful_results)

    output = caplog.text

    # Verify header
    assert "Installation Summary:" in output
    assert "-" * 50 in output

    # Verify all app names appear
    assert "qownnotes" in output
    assert "inkscape" in output
    assert "blender" in output

    # Verify success indicators
    assert "✓ v24.12.5" in output
    assert "✓ v1.3.2" in output
    assert "✓ v4.1.0" in output


def test_print_install_summary_all_already_installed(
    caplog: pytest.LogCaptureFixture,
    multiple_already_installed: list[dict[str, Any]],
) -> None:
    """Test display when all apps are already installed."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        print_install_summary(multiple_already_installed)

    output = caplog.text

    # Verify all already installed message
    assert "✓ All 2 specified app(s) are already installed:" in output

    # Verify app names appear
    assert "brave" in output
    assert "appflowy" in output

    # Should NOT show summary section
    assert "Installation Summary:" not in output


def test_print_install_summary_mixed_results(
    caplog: pytest.LogCaptureFixture,
    mixed_results: list[dict[str, Any]],
) -> None:
    """Test display with mixed success, failure, and already installed."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        print_install_summary(mixed_results)

    output = caplog.text

    # Verify header
    assert "Installation Summary:" in output

    # Verify success indicators
    assert "✓ v24.12.5" in output  # successful

    # Verify failure indicators
    assert "× Installation failed" in output
    assert "zen-browser" in output
    assert "Download failed: Connection timeout" in output

    # Verify already installed indicators
    assert "Already installed" in output  # noqa: RUF001
    assert "brave" in output

    # Verify warning indicators
    assert "!" in output
    assert "Desktop entry creation failed but app is installed" in output


def test_print_install_summary_all_failed(
    caplog: pytest.LogCaptureFixture,
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
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        print_install_summary(results)

    output = caplog.text

    # Verify header
    assert "Installation Summary:" in output

    # Verify all failure indicators
    assert "× Installation failed" in output
    assert "app1" in output
    assert "app2" in output
    assert "Network error" in output
    assert "Hash verification failed" in output


def test_print_install_summary_with_warnings(
    caplog: pytest.LogCaptureFixture,
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
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        print_install_summary(results)

    output = caplog.text

    # Verify warnings are displayed
    assert "! Failed to create desktop entry" in output
    assert "! Custom warning message" in output


def test_print_install_summary_empty_results(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test display with empty results list."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        print_install_summary([])

    output = caplog.text

    assert "No installations completed" in output
    assert "Installation Summary:" not in output


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


def test_print_result_line_formatting(
    caplog: pytest.LogCaptureFixture,
    successful_install_result: dict[str, Any],
) -> None:
    """Test individual result line formatting."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        _print_result_line(successful_install_result)

    output = caplog.text

    # Verify formatting: name (left-aligned, 25 chars) + status
    assert "qownnotes" in output
    assert "✓ v24.12.5" in output


def test_print_result_line_with_warning(
    caplog: pytest.LogCaptureFixture,
    result_with_warning: dict[str, Any],
) -> None:
    """Test result line formatting with warning."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        _print_result_line(result_with_warning)

    output = caplog.text

    # Verify app name and success
    assert "inkscape" in output
    assert "✓ v1.3.2" in output

    # Verify warning on second line
    assert "!" in output
    assert "Desktop entry creation failed but app is installed" in output


def test_print_result_line_already_installed(
    caplog: pytest.LogCaptureFixture,
    already_installed_result: dict[str, Any],
) -> None:
    """Test result line for already installed app."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        _print_result_line(already_installed_result)

    output = caplog.text

    assert "brave" in output
    assert "Already installed" in output  # noqa: RUF001


def test_print_result_line_failed(
    caplog: pytest.LogCaptureFixture,
    failed_install_result: dict[str, Any],
) -> None:
    """Test result line for failed installation."""
    with caplog.at_level(logging.ERROR, logger="my_unicorn"):
        _print_result_line(failed_install_result)

    output = caplog.text

    # Verify failure indicator and error message
    assert "zen-browser" in output
    assert "× Installation failed" in output
    assert "Download failed: Connection timeout" in output


def test_display_no_targets_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test error display when no installation targets specified."""
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        display_no_targets_error()

    # Verify error log entry
    assert any(
        "× No targets specified." in record.message
        for record in caplog.records
        if record.levelname == "ERROR"
    )

    # Verify info log entry with hint
    assert any(
        "💡 Use 'my-unicorn catalog'" in record.message
        for record in caplog.records
        if record.levelname == "INFO"
    )


def test_print_install_summary_result_without_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of result without name field."""
    results = [
        {
            "success": True,
            "status": "newly_installed",
            "version": "v1.0.0",
        }
    ]
    with caplog.at_level(logging.INFO, logger="my_unicorn"):
        print_install_summary(results)

    output = caplog.text

    # Should show "Unknown" as fallback
    assert "Unknown" in output
    assert "✓ v1.0.0" in output


def test_categorize_results_empty() -> None:
    """Test categorization with empty results."""
    categories = _categorize_results([])

    assert categories["newly_installed"] == []
    assert categories["failed"] == []
    assert categories["already_installed"] == []
    assert categories["with_warnings"] == []
