from my_unicorn.utils.install_display import print_install_summary


def test_print_installation_summary_all_already_installed(capsys):
    results = [
        {
            "target": "app1",
            "success": True,
            "name": "app1",
            "status": "already_installed",
        }
    ]
    print_install_summary(results)
    captured = capsys.readouterr()
    assert "All 1 specified app(s) are already installed" in captured.out
    assert "• app1" in captured.out


def test_print_installation_summary_mixed(capsys):
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
    captured = capsys.readouterr()

    # Summary header
    assert "Installation Summary" in captured.out
    # Installed app with version
    assert "app1" in captured.out and "1.0.0" in captured.out
    # Failed app shows error message
    assert "app2" in captured.out and "Download failed" in captured.out
    # Already installed shown as info
    assert "app3" in captured.out
