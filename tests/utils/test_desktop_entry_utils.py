"""Tests for desktop entry filename utilities.

Tests cover filename sanitization and desktop entry name generation.
"""

from my_unicorn.utils.desktop_utils import (
    create_desktop_entry_name,
    sanitize_filename,
)


class TestSanitizeFilename:
    """Test sanitize_filename function."""

    def test_valid_filename(self) -> None:
        """Test already valid filename."""
        assert sanitize_filename("myfile.txt") == "myfile.txt"

    def test_filename_with_spaces(self) -> None:
        """Test filename with spaces."""
        assert sanitize_filename("my file.txt") == "my file.txt"

    def test_filename_with_invalid_chars(self) -> None:
        """Test filename with invalid characters."""
        result = sanitize_filename('file<>:"/\\|?*.txt')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "|" not in result

    def test_filename_with_control_chars(self) -> None:
        """Test filename with control characters."""
        result = sanitize_filename("file\x00\x01\x1f.txt")
        assert "\x00" not in result
        assert "\x01" not in result

    def test_empty_filename(self) -> None:
        """Test empty filename."""
        assert sanitize_filename("") == ""

    def test_long_filename(self) -> None:
        """Test filename longer than 255 characters."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_filename_with_extension_long(self) -> None:
        """Test long filename preserves extension."""
        long_name = "a" * 300 + ".AppImage"
        result = sanitize_filename(long_name)
        assert result.endswith(".AppImage")
        assert len(result) <= 255

    def test_filename_strips_whitespace(self) -> None:
        """Test filename strips leading/trailing whitespace."""
        result = sanitize_filename("  file.txt  ")
        assert result == "file.txt"

    def test_sanitize_filename_unicode(self) -> None:
        """Test sanitizing filename with unicode."""
        result = sanitize_filename("file_世界.txt")
        assert "世界" in result


class TestCreateDesktopEntryName:
    """Test create_desktop_entry_name function."""

    def test_simple_name(self) -> None:
        """Test simple app name."""
        result = create_desktop_entry_name("Firefox")
        assert result == "firefox.desktop"

    def test_name_with_spaces(self) -> None:
        """Test name with spaces."""
        result = create_desktop_entry_name("My App")
        assert result == "myapp.desktop"

    def test_name_with_hyphens(self) -> None:
        """Test name with hyphens."""
        result = create_desktop_entry_name("my-app")
        assert result == "my-app.desktop"

    def test_name_with_underscores(self) -> None:
        """Test name with underscores."""
        result = create_desktop_entry_name("my_app")
        assert result == "my-app.desktop"

    def test_name_with_special_chars(self) -> None:
        """Test name with special characters."""
        result = create_desktop_entry_name("My@App!")
        assert result == "myapp.desktop"

    def test_multiple_consecutive_hyphens(self) -> None:
        """Test name with multiple consecutive hyphens."""
        result = create_desktop_entry_name("my---app")
        assert result == "my-app.desktop"

    def test_leading_trailing_hyphens(self) -> None:
        """Test name with leading/trailing hyphens."""
        result = create_desktop_entry_name("-myapp-")
        assert result == "myapp.desktop"

    def test_empty_name(self) -> None:
        """Test empty name."""
        result = create_desktop_entry_name("")
        assert result == "appimage.desktop"

    def test_only_special_chars(self) -> None:
        """Test name with only special characters."""
        result = create_desktop_entry_name("!@#$%")
        assert result == "appimage.desktop"

    def test_uppercase_name(self) -> None:
        """Test uppercase name."""
        result = create_desktop_entry_name("MYAPP")
        assert result == "myapp.desktop"

    def test_desktop_entry_normalization(self) -> None:
        """Test desktop entry name normalization."""
        # Multiple hyphens and underscores
        result = create_desktop_entry_name("app__--__name")
        assert "--" not in result
        assert "__" not in result
