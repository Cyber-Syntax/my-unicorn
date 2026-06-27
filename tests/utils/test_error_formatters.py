"""Tests for error formatting utilities."""

from my_unicorn.exceptions import InstallationError
from my_unicorn.utils.error_formatters import (
    build_install_error_result,
    get_user_friendly_error,
)


class TestGetUserFriendlyError:
    """Tests for get_user_friendly_error function."""

    def test_not_found_in_catalog(self):
        """Test error mapping for catalog not found."""
        error = InstallationError("App not found in catalog")
        result = get_user_friendly_error(error)
        assert result == "App not found in catalog"

    def test_no_assets_found(self):
        """Test error mapping for no assets."""
        error = InstallationError("No assets found in release")
        result = get_user_friendly_error(error)
        assert result == "No assets found in release - may still be building"

    def test_no_suitable_appimage(self):
        """Test error mapping for no suitable AppImage."""
        error = InstallationError("No suitable appimage found")
        result = get_user_friendly_error(error)
        assert (
            result == "AppImage not found in release - may still be building"
        )

    def test_already_installed(self):
        """Test error mapping for already installed."""
        error = InstallationError("App already installed")
        result = get_user_friendly_error(error)
        assert result == "Already installed"

    def test_unmapped_error(self) -> None:
        """Test that unmapped errors return original message."""
        error = InstallationError("Some other error")
        result = get_user_friendly_error(error)
        assert result == "Installation failed: Some other error"

    def test_case_insensitive_matching(self):
        """Test that error matching is case-insensitive."""
        error = InstallationError("NO SUITABLE APPIMAGE FOUND")
        result = get_user_friendly_error(error)
        assert (
            result == "AppImage not found in release - may still be building"
        )


class TestBuildInstallErrorResult:
    """Tests for build_install_error_result function."""

    def test_catalog_error(self):
        """Test building error result for catalog installation."""
        error = InstallationError("App not found in catalog")
        result = build_install_error_result(error, "myapp", is_url=False)

        assert result["success"] is False
        assert result["target"] == "myapp"
        assert result["name"] == "myapp"
        assert result["error"] == "App not found in catalog"
        assert result["source"] == "catalog"

    def test_url_error(self):
        """Test building error result for URL installation."""
        error = InstallationError("No suitable appimage found")
        result = build_install_error_result(
            error, "https://example.com/app.AppImage", is_url=True
        )

        assert result["success"] is False
        assert result["target"] == "https://example.com/app.AppImage"
        assert result["source"] == "url"
        assert (
            result["error"]
            == "AppImage not found in release - may still be building"
        )

    def test_non_installation_error(self):
        """Test handling of non-InstallationError exceptions."""
        error = ValueError("Some generic error")
        result = build_install_error_result(error, "myapp", is_url=False)

        assert result["success"] is False
        assert result["error"] == "Some generic error"

    def test_result_structure(self):
        """Test that result contains all required keys."""
        error = InstallationError("Test error")
        result = build_install_error_result(error, "myapp", is_url=False)

        required_keys = {"success", "target", "name", "error", "source"}
        assert set(result.keys()) == required_keys
