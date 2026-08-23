"""Tests for display_update utility module."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from my_unicorn.core.update import (
    _find_update_info,
    display_check_results,
    display_invalid_apps,
    display_update_error,
    display_update_results,
)


@dataclass
class MockUpdateInfo:
    """Mock UpdateInfo for testing."""

    app_name: str
    current_version: str
    latest_version: str
    has_update: bool
    error_reason: str | None = None

    @property
    def is_success(self) -> bool:
        """Return whether the mock represents a successful update check."""
        return self.error_reason is None


class TestFindUpdateInfo:
    """Tests for _find_update_info function."""

    def test_find_update_info_found(self):
        """Test _find_update_info when app is found."""
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
        update_infos = [
            MockUpdateInfo("app1", "1.0.0", "2.0.0", has_update=True),
        ]

        info = _find_update_info("nonexistent", update_infos)

        # Now returns UpdateInfo with error instead of None
        assert info is not None
        assert info.app_name == "nonexistent"
        assert info.error_reason == "Update info not found"


class TestDisplayMessageFunctions:
    """Tests for display message functions."""

    def test_display_update_error(self, caplog):
        """Test display_update_error function."""
        display_update_error("Update failed")

        captured = caplog.text
        assert "× Update failed" in captured


class TestDisplayCheckResults:
    """Tests for display_check_results function."""

    def test_display_check_results_with_updates(self):
        """Test display_check_results with available updates."""
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

        with patch("my_unicorn.core.update.logger") as mock_logger:
            display_check_results(results)

            assert mock_logger.info.call_count >= 3
            mock_logger.info.assert_any_call("Updates available:")
            mock_logger.info.assert_any_call(
                "  %s: %s → %s", "app1", "1.0.0", "2.0.0"
            )

    def test_display_check_results_no_updates(self):
        """Test display_check_results with no updates."""
        results = {"available_updates": []}

        with patch("my_unicorn.core.update.logger") as mock_logger:
            display_check_results(results)

            mock_logger.info.assert_called_once_with(
                "✓ All apps are up to date"
            )


class TestDisplayUpdateResults:
    """Tests for display_update_results function."""

    def test_display_update_results_with_infos(self, caplog):
        """Test display_update_results with update_infos."""
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

        captured = caplog.text
        assert ":: Creating transaction summary..." in captured
        assert "app1" in captured
        assert "✓" in captured
        assert "1.0.0 → 2.0.0" in captured

    def test_display_update_results_with_failures(self, caplog):
        """Test display_update_results with failed updates."""
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

        captured = caplog.text
        assert "app1" in captured
        assert "× Update failed" in captured
        assert "Network timeout" in captured

    def test_display_update_results_with_up_to_date(self, caplog):
        """Test display_update_results with up-to-date apps."""
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

        captured = caplog.text
        assert "app1" in captured
        assert "Already up to date" in captured
        assert "2.0.0" in captured

    def test_display_update_results_fallback_without_infos(self, caplog):
        """Test display_update_results fallback when no update_infos."""
        results = {
            "updated": ["app1"],
            "failed": ["app2"],
            "up_to_date": ["app3"],
            "update_infos": [],
        }

        with patch("my_unicorn.core.update.logger") as mock_logger:
            display_update_results(results)

            mock_logger.info.assert_any_call(
                "✓ Successfully updated: %s", "app1"
            )
            mock_logger.error.assert_any_call("× Failed to update: %s", "app2")
            mock_logger.info.assert_any_call("Already up to date: %s", "app3")

    def test_display_update_results_mixed(self, caplog):
        """Test display_update_results with mixed results."""
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

        captured = caplog.text
        assert "app1" in captured
        assert "✓" in captured
        assert "app2" in captured
        assert "×" in captured
        assert "app3" in captured
        assert "Already up to date" in captured


class TestDisplayInvalidApps:
    """Tests for display_invalid_apps function."""

    def test_display_invalid_apps_with_suggestions(self):
        """Test display_invalid_apps with installed apps for suggestions."""
        mock_config_manager = MagicMock()
        mock_config_manager.list_installed_apps.return_value = [
            "firefox",
            "chrome",
        ]

        with patch("my_unicorn.core.update.logger") as mock_logger:
            display_invalid_apps(["unknown"], mock_config_manager)

            mock_logger.warning.assert_called_once_with(
                "! Apps not found: %s", "unknown"
            )
            mock_logger.info.assert_called_once_with(
                "   Installed apps: %s", "firefox, chrome"
            )

    def test_display_invalid_apps_no_installed(self):
        """Test display_invalid_apps with no installed apps."""
        mock_config_manager = MagicMock()
        mock_config_manager.list_installed_apps.return_value = []

        with patch("my_unicorn.core.update.logger") as mock_logger:
            display_invalid_apps(["unknown"], mock_config_manager)

            mock_logger.warning.assert_called_once()
            assert mock_logger.info.call_count == 0

    def test_display_invalid_apps_empty_list(self):
        """Test display_invalid_apps with empty list."""
        mock_config_manager = MagicMock()

        with patch("my_unicorn.core.update.logger") as mock_logger:
            display_invalid_apps([], mock_config_manager)

            mock_logger.warning.assert_not_called()
            mock_logger.info.assert_not_called()
