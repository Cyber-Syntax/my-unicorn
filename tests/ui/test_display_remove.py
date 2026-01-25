"""Tests for display_remove module."""

from unittest.mock import patch

from my_unicorn.core.remove import display_removal_result


class TestDisplayRemovalResult:
    """Tests for display_removal_result function."""

    def test_display_removal_result_failure(self) -> None:
        """Test display when removal fails."""
        result = {"success": False, "error": "App not found"}

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_called_once_with("❌ %s", "App not found")

    def test_display_removal_result_empty_result(self) -> None:
        """Test display with empty/None result."""

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(None, "test_app")

            mock_logger.info.assert_called_once_with(
                "❌ Failed to remove %s", "test_app"
            )

    def test_display_removal_result_success_appimage(self) -> None:
        """Test display when AppImage is removed successfully."""
        result = {
            "success": True,
            "removed_files": ["test_app.AppImage"],
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ Removed AppImage(s): %s", "test_app.AppImage"
            )

    def test_display_removal_result_success_multiple_files(self) -> None:
        """Test display when multiple AppImages are removed."""
        result = {
            "success": True,
            "removed_files": ["test_app.AppImage", "test_app.appimage"],
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ Removed AppImage(s): %s",
                "test_app.AppImage, test_app.appimage",
            )

    def test_display_removal_result_cache_cleared(self) -> None:
        """Test display when cache is cleared."""
        result = {
            "success": True,
            "cache_cleared": True,
            "cache_owner": "test-owner",
            "cache_repo": "test-repo",
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ Removed cache for %s/%s", "test-owner", "test-repo"
            )

    def test_display_removal_result_cache_no_owner_repo(self) -> None:
        """Test display when cache cleared but no owner/repo available."""
        result = {
            "success": True,
            "cache_cleared": True,
            "cache_owner": None,
            "cache_repo": None,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            # Should not log cache removal without owner/repo
            calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert not any("Removed cache" in str(call) for call in calls)

    def test_display_removal_result_backup_removed(self) -> None:
        """Test display when backups are removed."""
        result = {
            "success": True,
            "backup_path": "/path/to/backups",
            "backup_removed": True,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ Removed all backups and metadata for %s", "test_app"
            )

    def test_display_removal_result_backup_not_found(self) -> None:
        """Test display when backup path exists but no backups found."""
        result = {
            "success": True,
            "backup_path": "/path/to/backups",
            "backup_removed": False,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "⚠️  No backups found at: %s", "/path/to/backups"
            )

    def test_display_removal_result_desktop_entry_removed(self) -> None:
        """Test display when desktop entry is removed."""
        result = {
            "success": True,
            "desktop_entry_removed": True,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ Removed desktop entry for %s", "test_app"
            )

    def test_display_removal_result_icon_removed(self) -> None:
        """Test display when icon is removed."""
        result = {
            "success": True,
            "icon_path": "/path/to/icon.png",
            "icon_removed": True,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ Removed icon: %s", "/path/to/icon.png"
            )

    def test_display_removal_result_icon_not_found(self) -> None:
        """Test display when icon path exists but icon not found."""
        result = {
            "success": True,
            "icon_path": "/path/to/icon.png",
            "icon_removed": False,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "⚠️  Icon not found at: %s", "/path/to/icon.png"
            )

    def test_display_removal_result_config_removed(self) -> None:
        """Test display when config is removed."""
        result = {
            "success": True,
            "config_removed": True,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ %s config for %s", "Removed", "test_app"
            )

    def test_display_removal_result_config_kept(self) -> None:
        """Test display when config is kept."""
        result = {
            "success": True,
            "config_removed": False,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            mock_logger.info.assert_any_call(
                "✅ %s config for %s", "Kept", "test_app"
            )

    def test_display_removal_result_complete_removal(self) -> None:
        """Test display with complete successful removal."""
        result = {
            "success": True,
            "removed_files": ["test_app.AppImage"],
            "cache_cleared": True,
            "cache_owner": "owner",
            "cache_repo": "repo",
            "backup_path": "/backups",
            "backup_removed": True,
            "desktop_entry_removed": True,
            "icon_path": "/icons/test.png",
            "icon_removed": True,
            "config_removed": True,
        }

        with patch("my_unicorn.core.remove.logger") as mock_logger:
            display_removal_result(result, "test_app")

            # Verify all success messages are logged
            assert mock_logger.info.call_count >= 6
