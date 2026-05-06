import logging

import pytest

from my_unicorn.core.install import (
    display_no_targets_error,
    print_install_summary,
)


@pytest.fixture(autouse=True)
def _caplog_setup(caplog):
    caplog.set_level(logging.INFO, logger="my_unicorn")


def test_display_no_targets_error():
    """Test display_no_targets_error shows error and help message."""
    from unittest.mock import patch

    with patch("my_unicorn.core.install.logger") as mock_logger:
        display_no_targets_error()

        mock_logger.error.assert_called_once_with("❌ No targets specified.")
        mock_logger.info.assert_called_once_with(
            "💡 Use 'my-unicorn catalog' to see available catalog apps."
        )


def test_print_install_summary_all_already_installed(caplog):

    results = [
        {
            "target": "app1",
            "success": True,
            "name": "app1",
            "status": "already_installed",
        }
    ]
    print_install_summary(results)
    captured = caplog.text
    assert "All 1 specified app(s) are already installed" in captured
    assert "• app1" in captured


def test_print_install_summary_mixed(caplog):

    results = [
        {
            "target": "app1",
            "success": True,
            "name": "app1",
            "status": "installed",
            "version": "1.0.0",
        },
        {
            "target": "app2",
            "success": False,
            "name": "app2",
            "error": "Download failed",
        },
        {
            "target": "app3",
            "success": True,
            "name": "app3",
            "status": "already_installed",
        },
    ]
    print_install_summary(results)
    captured = caplog.text

    # Summary header
    assert "Installation Summary" in captured
    # Installed app with version
    assert "app1" in captured and "1.0.0" in captured
    # Failed app shows error message
    assert "app2" in captured and "Download failed" in captured
    # Already installed shown as info
    assert "app3" in captured
