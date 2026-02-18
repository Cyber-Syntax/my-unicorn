"""Pytest fixtures for progress UI integration tests."""

from pathlib import Path

import pytest

FIXTURES_DIR = (
    Path(__file__).parent.parent.parent / "fixtures" / "expected_ui_output"
)


@pytest.fixture
def install_success_output() -> str:
    """Load install success expected output from fixture file.

    Returns:
        Content of install_success.txt

    """
    return (FIXTURES_DIR / "install_success.txt").read_text()


@pytest.fixture
def install_warning_output() -> str:
    """Load install warning expected output from fixture file.

    Returns:
        Content of install_warning.txt

    """
    return (FIXTURES_DIR / "install_warning.txt").read_text()


@pytest.fixture
def update_success_output() -> str:
    """Load update success expected output from fixture file.

    Returns:
        Content of update_success.txt

    """
    return (FIXTURES_DIR / "update_success.txt").read_text()
