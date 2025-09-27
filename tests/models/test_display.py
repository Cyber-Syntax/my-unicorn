"""Tests for display utility functions."""

import pytest
from unittest.mock import Mock, patch
from io import StringIO
from my_unicorn.models.display import UpdateResultDisplay


class TestUpdateResultDisplay:
    """Test UpdateResultDisplay class."""

    def test_display_progress(self):
        """Test display_progress method."""
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay.display_progress("Installing app...")
            
            mock_print.assert_called_once_with("🔄 Installing app...")

    def test_display_success(self):
        """Test display_success method."""
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay.display_success("Installation completed")
            
            mock_print.assert_called_once_with("✅ Installation completed")

    def test_display_error(self):
        """Test display_error method."""
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay.display_error("Installation failed")
            
            mock_print.assert_called_once_with("❌ Installation failed")

    def test_display_warning(self):
        """Test display_warning method."""
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay.display_warning("Version mismatch detected")
            
            mock_print.assert_called_once_with("⚠️  Version mismatch detected")

    def test_display_summary_empty_infos(self):
        """Test display_summary with empty update_infos."""
        mock_result = Mock()
        mock_result.update_infos = []
        mock_result.message = "No updates available"
        
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay.display_summary(mock_result)
            
            mock_print.assert_called_once_with("No updates available")

    def test_display_summary_with_updates(self):
        """Test display_summary with updated apps."""
        mock_result = Mock()
        mock_result.update_infos = [Mock()]  # Non-empty list
        mock_result.updated_apps = ["app1"]
        mock_result.failed_apps = []
        
        with patch('builtins.print') as mock_print:
            with patch.object(UpdateResultDisplay, '_display_update_summary') as mock_update_summary:
                UpdateResultDisplay.display_summary(mock_result)
                
                mock_update_summary.assert_called_once_with(mock_result)

    def test_display_summary_with_failures(self):
        """Test display_summary with failed apps."""
        mock_result = Mock()
        mock_result.update_infos = [Mock()]  # Non-empty list
        mock_result.updated_apps = []
        mock_result.failed_apps = ["app1"]
        
        with patch('builtins.print') as mock_print:
            with patch.object(UpdateResultDisplay, '_display_update_summary') as mock_update_summary:
                UpdateResultDisplay.display_summary(mock_result)
                
                mock_update_summary.assert_called_once_with(mock_result)

    def test_display_summary_check_only(self):
        """Test display_summary for check-only operations."""
        mock_result = Mock()
        mock_result.update_infos = [Mock()]  # Non-empty list
        mock_result.updated_apps = []
        mock_result.failed_apps = []
        
        with patch('builtins.print') as mock_print:
            with patch.object(UpdateResultDisplay, '_display_check_summary') as mock_check_summary:
                UpdateResultDisplay.display_summary(mock_result)
                
                mock_check_summary.assert_called_once_with(mock_result)

    def test_display_update_summary(self):
        """Test _display_update_summary method."""
        # Create mock app info
        mock_app_info = Mock()
        mock_app_info.latest_version = "2.0.0"
        
        mock_result = Mock()
        mock_result.updated_apps = ["app1"]
        mock_result.failed_apps = ["app2"]
        mock_result.update_infos = [mock_app_info]
        
        with patch('builtins.print') as mock_print:
            with patch.object(UpdateResultDisplay, '_find_app_info', return_value=mock_app_info):
                UpdateResultDisplay._display_update_summary(mock_result)
                
                # Should have multiple print calls for summary display
                assert mock_print.call_count > 0
                
                # Check that at least one call contains the app name
                print_calls = [str(call) for call in mock_print.call_args_list]
                assert any("app1" in call for call in print_calls)
                assert any("app2" in call for call in print_calls)

    def test_display_check_summary_empty(self):
        """Test _display_check_summary with no apps."""
        mock_result = Mock()
        mock_result.update_infos = []
        
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay._display_check_summary(mock_result)
            
            mock_print.assert_called_once_with("No apps to check.")

    def test_display_check_summary_with_apps(self):
        """Test _display_check_summary with apps."""
        # Create mock update infos
        mock_info1 = Mock()
        mock_info1.has_update = True
        
        mock_info2 = Mock()
        mock_info2.has_update = False
        
        mock_result = Mock()
        mock_result.update_infos = [mock_info1, mock_info2]
        mock_result.message = "Check completed"
        
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay._display_check_summary(mock_result)
            
            # Should have multiple print calls
            assert mock_print.call_count > 0
            
            # Check that summary information is printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("Total apps checked: 2" in call for call in print_calls)
            assert any("Updates available: 1" in call for call in print_calls)

    def test_display_detailed_results_empty(self):
        """Test display_detailed_results with empty update_infos."""
        mock_result = Mock()
        mock_result.update_infos = []
        mock_result.message = "No details available"
        
        with patch('builtins.print') as mock_print:
            UpdateResultDisplay.display_detailed_results(mock_result)
            
            mock_print.assert_called_once_with("No details available")

    def test_display_detailed_results_with_infos(self):
        """Test display_detailed_results with update infos."""
        mock_info = Mock()
        mock_info.app_name = "test_app"
        
        mock_result = Mock()
        mock_result.update_infos = [mock_info]
        
        with patch('builtins.print') as mock_print:
            with patch.object(UpdateResultDisplay, '_get_app_status', return_value="✅ Updated"):
                with patch.object(UpdateResultDisplay, '_format_version_info', return_value="1.0.0 → 2.0.0"):
                    UpdateResultDisplay.display_detailed_results(mock_result)
                    
                    # Should print headers and app info
                    assert mock_print.call_count > 0
                    print_calls = [str(call) for call in mock_print.call_args_list]
                    assert any("test_app" in call for call in print_calls)

    def test_get_app_status_updated(self):
        """Test _get_app_status for updated app."""
        mock_info = Mock()
        mock_info.app_name = "test_app"
        
        mock_result = Mock()
        mock_result.updated_apps = ["test_app"]
        mock_result.failed_apps = []
        
        status = UpdateResultDisplay._get_app_status(mock_info, mock_result)
        assert status == "✅ Updated"

    def test_get_app_status_failed(self):
        """Test _get_app_status for failed app."""
        mock_info = Mock()
        mock_info.app_name = "test_app"
        
        mock_result = Mock()
        mock_result.updated_apps = []
        mock_result.failed_apps = ["test_app"]
        
        status = UpdateResultDisplay._get_app_status(mock_info, mock_result)
        assert status == "❌ Failed"

    def test_get_app_status_update_available(self):
        """Test _get_app_status for app with update available."""
        mock_info = Mock()
        mock_info.app_name = "test_app"
        mock_info.has_update = True
        
        mock_result = Mock()
        mock_result.updated_apps = []
        mock_result.failed_apps = []
        
        status = UpdateResultDisplay._get_app_status(mock_info, mock_result)
        assert status == "📦 Update available"

    def test_get_app_status_up_to_date(self):
        """Test _get_app_status for up-to-date app."""
        mock_info = Mock()
        mock_info.app_name = "test_app"
        mock_info.has_update = False
        
        mock_result = Mock()
        mock_result.updated_apps = []
        mock_result.failed_apps = []
        
        status = UpdateResultDisplay._get_app_status(mock_info, mock_result)
        assert status == "✅ Up to date"

    def test_format_version_info_with_update(self):
        """Test _format_version_info for app with update."""
        mock_info = Mock()
        mock_info.has_update = True
        mock_info.current_version = "1.0.0"
        mock_info.latest_version = "2.0.0"
        
        version_info = UpdateResultDisplay._format_version_info(mock_info)
        assert version_info == "1.0.0 → 2.0.0"

    def test_format_version_info_no_update(self):
        """Test _format_version_info for app without update."""
        mock_info = Mock()
        mock_info.has_update = False
        mock_info.current_version = "1.0.0"
        
        version_info = UpdateResultDisplay._format_version_info(mock_info)
        assert version_info == "1.0.0"

    def test_format_version_info_truncation(self):
        """Test _format_version_info with long version string."""
        mock_info = Mock()
        mock_info.has_update = True
        mock_info.current_version = "very-long-version-string-that-exceeds-limits"
        mock_info.latest_version = "another-very-long-version-string-that-exceeds-limits"
        
        version_info = UpdateResultDisplay._format_version_info(mock_info)
        
        # Should be truncated if over 40 characters
        if len(f"{mock_info.current_version} → {mock_info.latest_version}") > 40:
            assert version_info.endswith("...")
            assert len(version_info) <= 40

    def test_find_app_info_found(self):
        """Test _find_app_info when app is found."""
        mock_info1 = Mock()
        mock_info1.app_name = "app1"
        
        mock_info2 = Mock()
        mock_info2.app_name = "app2"
        
        update_infos = [mock_info1, mock_info2]
        
        result = UpdateResultDisplay._find_app_info("app2", update_infos)
        assert result == mock_info2

    def test_find_app_info_not_found(self):
        """Test _find_app_info when app is not found."""
        mock_info1 = Mock()
        mock_info1.app_name = "app1"
        
        update_infos = [mock_info1]
        
        result = UpdateResultDisplay._find_app_info("app2", update_infos)
        assert result is None

    def test_find_app_info_empty_list(self):
        """Test _find_app_info with empty list."""
        result = UpdateResultDisplay._find_app_info("app1", [])
        assert result is None
