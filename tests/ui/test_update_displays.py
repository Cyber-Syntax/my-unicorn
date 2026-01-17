"""Tests for display_update utility module."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch


@dataclass
class MockUpdateInfo:
    """Mock UpdateInfo for testing."""

    app_name: str
    current_version: str
    latest_version: str
    has_update: bool
    error_reason: str | None = None


class TestDisplayUpdateSummary:
    """Tests for display_update_summary function."""

    def test_display_update_summary_no_apps(self, capsys):
        """Test display_update_summary with no apps."""
        from my_unicorn.ui.display_update import display_update_summary

        display_update_summary([], [], [], [], check_only=False)

        captured = capsys.readouterr()
        assert "No apps to process." in captured.out

    def test_display_update_summary_check_only(self, capsys):
        """Test display_update_summary in check-only mode."""
        from my_unicorn.ui.display_update import display_update_summary

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
            MockUpdateInfo("app2", "1.0.0", "1.0.0", has_update=False),
        ]

        display_update_summary([], [], [], update_infos, check_only=True)

        captured = capsys.readouterr()
        assert "Check Summary:" in captured.out
        assert "Total apps checked: 2" in captured.out
        assert "Updates available: 1" in captured.out
        assert "Up to date: 1" in captured.out
        assert "app1: 1.0.0 → 2.0.0" in captured.out

    def test_display_update_summary_update_operation(self, capsys):
        """Test display_update_summary for update operation."""
        from my_unicorn.ui.display_update import display_update_summary

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
            MockUpdateInfo("app2", "1.0.0", "1.0.0", has_update=False),
        ]
        updated_apps = ["app1"]
        failed_apps = []
        up_to_date_apps = ["app2"]

        display_update_summary(
            updated_apps,
            failed_apps,
            up_to_date_apps,
            update_infos,
            check_only=False,
        )

        captured = capsys.readouterr()
        assert "Update Summary:" in captured.out
        assert "app1" in captured.out
        assert "✅" in captured.out
        assert "1.0.0 → 2.0.0" in captured.out
        assert "Successfully updated 1 app(s)" in captured.out

    def test_display_update_summary_with_failures(self, capsys):
        """Test display_update_summary with failed updates."""
        from my_unicorn.ui.display_update import display_update_summary

        update_infos = [
            MockUpdateInfo(
                "app1",
                "1.0.0",
                "2.0.0",
                has_update=True,
                error_reason="Network error",
            ),
        ]
        updated_apps = []
        failed_apps = ["app1"]
        up_to_date_apps = []

        display_update_summary(
            updated_apps,
            failed_apps,
            up_to_date_apps,
            update_infos,
            check_only=False,
        )

        captured = capsys.readouterr()
        assert "Update Summary:" in captured.out
        assert "app1" in captured.out
        assert "❌ Update failed" in captured.out
        assert "Network error" in captured.out
        assert "1 app(s) failed to update" in captured.out


class TestDisplayCheckOnlySummary:
    """Tests for _display_check_only_summary function."""

    def test_display_check_only_summary_no_apps(self, capsys):
        """Test _display_check_only_summary with no apps."""
        from my_unicorn.ui.display_update import _display_check_only_summary

        _display_check_only_summary([])

        captured = capsys.readouterr()
        assert "No apps to check." in captured.out

    def test_display_check_only_summary_with_updates(self, capsys):
        """Test _display_check_only_summary with apps having updates."""
        from my_unicorn.ui.display_update import _display_check_only_summary

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
            MockUpdateInfo("app2", "1.5.0", "2.5.0", has_update=True),
            MockUpdateInfo("app3", "1.0.0", "1.0.0", has_update=False),
        ]

        _display_check_only_summary(update_infos)

        captured = capsys.readouterr()
        assert "Check Summary:" in captured.out
        assert "Total apps checked: 3" in captured.out
        assert "Updates available: 2" in captured.out
        assert "Up to date: 1" in captured.out
        assert "Apps with updates available:" in captured.out
        assert "app1: 1.0.0 → 2.0.0" in captured.out
        assert "app2: 1.5.0 → 2.5.0" in captured.out

    def test_display_check_only_summary_no_updates(self, capsys):
        """Test _display_check_only_summary with no updates available."""
        from my_unicorn.ui.display_update import _display_check_only_summary

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "1.0.0", has_update=False),
            MockUpdateInfo("app2", "2.0.0", "2.0.0", has_update=False),
        ]

        _display_check_only_summary(update_infos)

        captured = capsys.readouterr()
        assert "Total apps checked: 2" in captured.out
        assert "Updates available: 0" in captured.out
        assert "Up to date: 2" in captured.out
        # Should not show "Apps with updates available" section
        assert "Apps with updates available:" not in captured.out


class TestDisplayUpdateDetails:
    """Tests for display_update_details function."""

    def test_display_update_details_no_info(self, capsys):
        """Test display_update_details with no information."""
        from my_unicorn.ui.display_update import display_update_details

        display_update_details([], [], [])

        captured = capsys.readouterr()
        assert "No update information available." in captured.out

    def test_display_update_details_with_data(self, capsys):
        """Test display_update_details with complete data."""
        from my_unicorn.ui.display_update import display_update_details

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
            MockUpdateInfo("app2", "1.0.0", "1.0.0", has_update=False),
            MockUpdateInfo("app3", "1.0.0", "2.0.0", has_update=True),
        ]
        updated_apps = ["app1"]
        failed_apps = ["app3"]

        display_update_details(updated_apps, failed_apps, update_infos)

        captured = capsys.readouterr()
        assert "Detailed Results:" in captured.out
        assert "App Name" in captured.out
        assert "Status" in captured.out
        assert "Version Info" in captured.out
        assert "app1" in captured.out
        assert "app2" in captured.out
        assert "app3" in captured.out


class TestGetUpdateStatus:
    """Tests for _get_update_status function."""

    def test_get_update_status_updated(self):
        """Test _get_update_status for updated app."""
        from my_unicorn.ui.display_update import _get_update_status

        info = MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True)
        status = _get_update_status(info, ["app1"], [])

        assert status == "✅ Updated"

    def test_get_update_status_failed(self):
        """Test _get_update_status for failed app."""
        from my_unicorn.ui.display_update import _get_update_status

        info = MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True)
        status = _get_update_status(info, [], ["app1"])

        assert status == "❌ Failed"

    def test_get_update_status_update_available(self):
        """Test _get_update_status for app with update available."""
        from my_unicorn.ui.display_update import _get_update_status

        info = MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True)
        status = _get_update_status(info, [], [])

        assert status == "📦 Update available"

    def test_get_update_status_up_to_date(self):
        """Test _get_update_status for up-to-date app."""
        from my_unicorn.ui.display_update import _get_update_status

        info = MockUpdateInfo("app1", "1.0.0", "1.0.0", has_update=False)
        status = _get_update_status(info, [], [])

        assert status == "✅ Up to date"


class TestFormatUpdateVersionInfo:
    """Tests for _format_update_version_info function."""

    def test_format_update_version_info_with_update(self):
        """Test _format_update_version_info with update available."""
        from my_unicorn.ui.display_update import _format_update_version_info

        info = MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True)
        version_str = _format_update_version_info(info)

        assert version_str == "1.0.0 → 2.0.0"

    def test_format_update_version_info_no_update(self):
        """Test _format_update_version_info without update."""
        from my_unicorn.ui.display_update import _format_update_version_info

        info = MockUpdateInfo("app1", "1.0.0", "1.0.0", has_update=False)
        version_str = _format_update_version_info(info)

        assert version_str == "1.0.0"

    def test_format_update_version_info_long_string(self):
        """Test _format_update_version_info with long version string."""
        from my_unicorn.ui.display_update import _format_update_version_info

        long_version = "1.0.0-very-long-version-string-that-exceeds-limit"
        info = MockUpdateInfo(
            "app1", long_version, long_version, has_update=False
        )
        version_str = _format_update_version_info(info)

        assert len(version_str) <= 40
        assert version_str.endswith("...")


class TestFindUpdateInfo:
    """Tests for _find_update_info function."""

    def test_find_update_info_found(self):
        """Test _find_update_info when app is found."""
        from my_unicorn.ui.display_update import _find_update_info

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
            MockUpdateInfo("app2", "1.0.0", "1.0.0", has_update=False),
        ]

        info = _find_update_info("app1", update_infos)

        assert info is not None
        assert info.app_name == "app1"
        assert info.current_version == "1.0.0"

    def test_find_update_info_not_found(self):
        """Test _find_update_info when app is not found."""
        from my_unicorn.ui.display_update import _find_update_info

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
        ]

        info = _find_update_info("nonexistent", update_infos)

        assert info is None


class TestDisplayMessageFunctions:
    """Tests for display message functions."""

    def test_display_update_progress(self, capsys):
        """Test display_update_progress function."""
        from my_unicorn.ui.display_update import display_update_progress

        display_update_progress("Processing app1...")

        captured = capsys.readouterr()
        assert "🔄 Processing app1..." in captured.out

    def test_display_update_success(self, capsys):
        """Test display_update_success function."""
        from my_unicorn.ui.display_update import display_update_success

        display_update_success("App updated successfully")

        captured = capsys.readouterr()
        assert "✅ App updated successfully" in captured.out

    def test_display_update_error(self, capsys):
        """Test display_update_error function."""
        from my_unicorn.ui.display_update import display_update_error

        display_update_error("Update failed")

        captured = capsys.readouterr()
        assert "❌ Update failed" in captured.out

    def test_display_update_warning(self, capsys):
        """Test display_update_warning function."""
        from my_unicorn.ui.display_update import display_update_warning

        display_update_warning("Low disk space")

        captured = capsys.readouterr()
        assert "⚠️  Low disk space" in captured.out


class TestDisplayCheckResults:
    """Tests for display_check_results function."""

    def test_display_check_results_with_updates(self):
        """Test display_check_results with available updates."""
        from my_unicorn.ui.display_update import display_check_results

        results = {
            "available_updates": [
                {
                    "app_name": "app1",
                    "current_version": "1.0.0",
                    "latest_version": "2.0.0",
                },
                {
                    "app_name": "app2",
                    "current_version": "1.5.0",
                    "latest_version": "2.5.0",
                },
            ]
        }

        with patch("my_unicorn.ui.display_update.logger") as mock_logger:
            display_check_results(results)

            assert mock_logger.info.call_count >= 3
            mock_logger.info.assert_any_call("Updates available:")
            mock_logger.info.assert_any_call(
                "  %s: %s → %s", "app1", "1.0.0", "2.0.0"
            )

    def test_display_check_results_no_updates(self):
        """Test display_check_results with no updates."""
        from my_unicorn.ui.display_update import display_check_results

        results = {"available_updates": []}

        with patch("my_unicorn.ui.display_update.logger") as mock_logger:
            display_check_results(results)

            mock_logger.info.assert_called_once_with(
                "✅ All apps are up to date"
            )


class TestDisplayUpdateResults:
    """Tests for display_update_results function."""

    def test_display_update_results_with_infos(self, capsys):
        """Test display_update_results with update_infos."""
        from my_unicorn.ui.display_update import display_update_results

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
        ]
        results = {
            "updated": ["app1"],
            "failed": [],
            "up_to_date": [],
            "update_infos": update_infos,
        }

        display_update_results(results)

        captured = capsys.readouterr()
        assert "📦 Update Summary:" in captured.out
        assert "app1" in captured.out
        assert "✅" in captured.out
        assert "1.0.0 → 2.0.0" in captured.out
        assert "Successfully updated 1 app(s)" in captured.out

    def test_display_update_results_with_failures(self, capsys):
        """Test display_update_results with failed updates."""
        from my_unicorn.ui.display_update import display_update_results

        update_infos = [
            MockUpdateInfo(
                "app1",
                "1.0.0",
                "2.0.0",
                has_update=True,
                error_reason="Network timeout",
            ),
        ]
        results = {
            "updated": [],
            "failed": ["app1"],
            "up_to_date": [],
            "update_infos": update_infos,
        }

        display_update_results(results)

        captured = capsys.readouterr()
        assert "app1" in captured.out
        assert "❌ Update failed" in captured.out
        assert "Network timeout" in captured.out
        assert "1 app(s) failed to update" in captured.out

    def test_display_update_results_with_up_to_date(self, capsys):
        """Test display_update_results with up-to-date apps."""
        from my_unicorn.ui.display_update import display_update_results

        update_infos = [
            MockUpdateInfo("app1", "2.0.0", "2.0.0", has_update=False),
        ]
        results = {
            "updated": [],
            "failed": [],
            "up_to_date": ["app1"],
            "update_infos": update_infos,
        }

        display_update_results(results)

        captured = capsys.readouterr()
        assert "app1" in captured.out
        assert "Already up to date" in captured.out
        assert "2.0.0" in captured.out

    def test_display_update_results_fallback_without_infos(self):
        """Test display_update_results fallback when no update_infos."""
        from my_unicorn.ui.display_update import display_update_results

        results = {
            "updated": ["app1"],
            "failed": ["app2"],
            "up_to_date": ["app3"],
            "update_infos": [],
        }

        with patch("my_unicorn.ui.display_update.logger") as mock_logger:
            display_update_results(results)

            mock_logger.info.assert_any_call(
                "✅ Successfully updated: %s", "app1"
            )
            mock_logger.error.assert_any_call(
                "❌ Failed to update: %s", "app2"
            )
            mock_logger.info.assert_any_call("Already up to date: %s", "app3")

    def test_display_update_results_mixed(self, capsys):
        """Test display_update_results with mixed results."""
        from my_unicorn.ui.display_update import display_update_results

        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
            MockUpdateInfo("app2", "1.5.0", "2.5.0", has_update=True),
            MockUpdateInfo("app3", "3.0.0", "3.0.0", has_update=False),
        ]
        results = {
            "updated": ["app1"],
            "failed": ["app2"],
            "up_to_date": ["app3"],
            "update_infos": update_infos,
        }

        display_update_results(results)

        captured = capsys.readouterr()
        assert "app1" in captured.out and "✅" in captured.out
        assert "app2" in captured.out and "❌" in captured.out
        assert "app3" in captured.out and "Already up to date" in captured.out


class TestDisplayInvalidApps:
    """Tests for display_invalid_apps function."""

    def test_display_invalid_apps_with_suggestions(self):
        """Test display_invalid_apps with installed apps for suggestions."""
        from my_unicorn.ui.display_update import display_invalid_apps

        mock_config_manager = MagicMock()
        mock_config_manager.list_installed_apps.return_value = [
            "firefox",
            "chrome",
        ]

        with patch("my_unicorn.ui.display_update.logger") as mock_logger:
            display_invalid_apps(["unknown"], mock_config_manager)

            mock_logger.warning.assert_called_once_with(
                "⚠️  Apps not found: %s", "unknown"
            )
            mock_logger.info.assert_called_once_with(
                "   Installed apps: %s", "firefox, chrome"
            )

    def test_display_invalid_apps_no_installed(self):
        """Test display_invalid_apps with no installed apps."""
        from my_unicorn.ui.display_update import display_invalid_apps

        mock_config_manager = MagicMock()
        mock_config_manager.list_installed_apps.return_value = []

        with patch("my_unicorn.ui.display_update.logger") as mock_logger:
            display_invalid_apps(["unknown"], mock_config_manager)

            mock_logger.warning.assert_called_once()
            assert mock_logger.info.call_count == 0

    def test_display_invalid_apps_empty_list(self):
        """Test display_invalid_apps with empty list."""
        from my_unicorn.ui.display_update import display_invalid_apps

        mock_config_manager = MagicMock()

        with patch("my_unicorn.ui.display_update.logger") as mock_logger:
            display_invalid_apps([], mock_config_manager)

            mock_logger.warning.assert_not_called()
            mock_logger.info.assert_not_called()
