from my_unicorn.core.install import print_install_summary
import pytest


def test_print_installation_summary_all_already_installed(caplog):
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


def test_print_installation_summary_mixed(caplog):
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
