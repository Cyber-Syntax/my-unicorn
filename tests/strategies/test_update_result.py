"""Tests for UpdateResultDisplay: display_summary and display_detailed_results."""

from unittest.mock import MagicMock

from my_unicorn.strategies.update import UpdateResult
from my_unicorn.strategies.update_result import UpdateResultDisplay
from my_unicorn.update import UpdateInfo


def make_update_info(app_name, has_update, current_version="1.0", latest_version="1.0"):
    info = MagicMock(spec=UpdateInfo)
    info.app_name = app_name
    info.has_update = has_update
    info.current_version = current_version
    info.latest_version = latest_version
    return info


def make_result(
    updated_apps=None,
    failed_apps=None,
    up_to_date_apps=None,
    update_infos=None,
    message="",
    success=True,
):
    return UpdateResult(
        success=success,
        updated_apps=updated_apps or [],
        failed_apps=failed_apps or [],
        up_to_date_apps=up_to_date_apps or [],
        update_infos=update_infos or [],
        message=message,
    )


def test_display_summary_no_updates(capsys):
    """Test display_summary prints message when no update_infos."""
    result = make_result(message="Nothing to do")
    UpdateResultDisplay.display_summary(result)
    captured = capsys.readouterr()
    assert "Nothing to do" in captured.out


def test_display_summary_check_only(capsys):
    """Test display_summary prints check summary for check-only results."""
    infos = [
        make_update_info("AppOne", False, "1.0", "1.0"),
        make_update_info("AppTwo", True, "2.0", "2.1"),
    ]
    result = make_result(update_infos=infos, message="Check complete")
    UpdateResultDisplay.display_summary(result)
    captured = capsys.readouterr()
    assert "Check Summary" in captured.out
    assert "Total apps checked: 2" in captured.out
    assert "Updates available: 1" in captured.out
    assert "Up to date: 1" in captured.out
    assert "Check complete" in captured.out


def test_display_summary_update_success(capsys):
    """Test display_summary prints update summary for successful updates."""
    infos = [
        make_update_info("AppOne", True, "1.0", "2.0"),
        make_update_info("AppTwo", False, "2.0", "2.0"),
    ]
    result = make_result(
        updated_apps=["AppOne"],
        failed_apps=[],
        up_to_date_apps=["AppTwo"],
        update_infos=infos,
        message="Update complete",
    )
    UpdateResultDisplay.display_summary(result)
    captured = capsys.readouterr()
    assert "Update Summary" in captured.out
    assert "AppOne" in captured.out
    assert "Updated to 2.0" in captured.out
    assert "Successfully updated 1 app(s)" in captured.out


def test_display_summary_update_failure(capsys):
    """Test display_summary prints update summary for failed updates."""
    infos = [
        make_update_info("AppOne", True, "1.0", "2.0"),
        make_update_info("AppTwo", True, "2.0", "2.1"),
    ]
    result = make_result(
        updated_apps=["AppOne"],
        failed_apps=["AppTwo"],
        up_to_date_apps=[],
        update_infos=infos,
        message="Some failed",
    )
    UpdateResultDisplay.display_summary(result)
    captured = capsys.readouterr()
    assert "Update Summary" in captured.out
    assert "AppOne" in captured.out
    assert "Updated to 2.0" in captured.out
    assert "AppTwo" in captured.out
    assert "Update failed" in captured.out
    assert "Successfully updated 1 app(s)" in captured.out
    assert "1 app(s) failed to update" in captured.out


def test_display_detailed_results(capsys):
    """Test display_detailed_results prints detailed table."""
    infos = [
        make_update_info("AppOne", True, "1.0", "2.0"),
        make_update_info("AppTwo", False, "2.0", "2.0"),
        make_update_info("AppThree", True, "3.0", "3.1"),
    ]
    result = make_result(
        updated_apps=["AppOne"],
        failed_apps=["AppThree"],
        up_to_date_apps=["AppTwo"],
        update_infos=infos,
        message="Detailed",
    )
    UpdateResultDisplay.display_detailed_results(result)
    captured = capsys.readouterr()
    assert "Detailed Results" in captured.out
    assert "App Name" in captured.out
    assert "Status" in captured.out
    assert "Version Info" in captured.out
    assert "AppOne" in captured.out
    assert "✅ Updated" in captured.out
    assert "AppTwo" in captured.out
    assert "✅ Up to date" in captured.out
    assert "AppThree" in captured.out
    assert "❌ Failed" in captured.out
    assert "3.0 → 3.1" in captured.out


def test_display_summary_no_apps_to_check(capsys):
    """Test display_summary prints 'No apps to check.' for empty update_infos."""
    result = make_result(update_infos=[], message="No apps to check.")
    UpdateResultDisplay.display_summary(result)
    captured = capsys.readouterr()
    assert "No apps to check." in captured.out
