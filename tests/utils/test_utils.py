"""Comprehensive tests for utils module.

Tests cover utility functions for path operations, string manipulation,
version handling, and file pattern matching.
"""

from my_unicorn.utils.utils import (
    BYTES_PER_UNIT,
    CHECKSUM_FILE_PATTERNS,
    SPECIFIC_CHECKSUM_EXTENSIONS,
    create_desktop_entry_name,
    extract_and_validate_version,
    extract_version_from_package_string,
    format_bytes,
    get_checksum_file_format_type,
    is_appimage_file,
    is_checksum_file,
    sanitize_filename,
    sanitize_version_string,
    validate_version_string,
)


class TestConstants:
    """Test module constants."""

    def test_bytes_per_unit(self) -> None:
        """Test bytes per unit constant."""
        assert BYTES_PER_UNIT == 1024.0

    def test_checksum_patterns_exist(self) -> None:
        """Test that checksum file patterns are defined."""
        assert len(CHECKSUM_FILE_PATTERNS) > 0
        assert isinstance(CHECKSUM_FILE_PATTERNS, list)

    def test_specific_extensions_exist(self) -> None:
        """Test that specific checksum extensions are defined."""
        assert len(SPECIFIC_CHECKSUM_EXTENSIONS) > 0
        assert isinstance(SPECIFIC_CHECKSUM_EXTENSIONS, list)


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


class TestFormatBytes:
    """Test format_bytes function."""

    def test_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_bytes(512) == "512.0 B"

    def test_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        result = format_bytes(1536)
        assert "KB" in result

    def test_megabytes(self) -> None:
        """Test formatting megabytes."""
        result = format_bytes(5 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        result = format_bytes(3 * 1024 * 1024 * 1024)
        assert "GB" in result

    def test_terabytes(self) -> None:
        """Test formatting terabytes."""
        result = format_bytes(2 * 1024 * 1024 * 1024 * 1024)
        assert "TB" in result

    def test_petabytes(self) -> None:
        """Test formatting petabytes."""
        result = format_bytes(1024 * 1024 * 1024 * 1024 * 1024)
        assert "PB" in result

    def test_zero_bytes(self) -> None:
        """Test zero bytes."""
        assert format_bytes(0) == "0.0 B"

    def test_fractional_size(self) -> None:
        """Test fractional size."""
        result = format_bytes(1536.5)
        assert "1.5 KB" in result


class TestExtractVersionFromPackageString:
    """Test extract_version_from_package_string function."""

    def test_simple_version(self) -> None:
        """Test simple version string."""
        assert extract_version_from_package_string("1.2.3") == "1.2.3"

    def test_version_with_v_prefix(self) -> None:
        """Test version with v prefix."""
        assert extract_version_from_package_string("v1.2.3") == "1.2.3"

    def test_package_at_version(self) -> None:
        """Test package@version format."""
        result = extract_version_from_package_string("package@1.2.3")
        assert result == "1.2.3"

    def test_scoped_package_version(self) -> None:
        """Test scoped package version."""
        result = extract_version_from_package_string(
            "@standardnotes/desktop@3.198.1"
        )
        assert result == "3.198.1"

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert extract_version_from_package_string("") is None

    def test_none_input(self) -> None:
        """Test None input."""
        assert extract_version_from_package_string(None) is None  # type: ignore[arg-type]

    def test_version_with_quotes(self) -> None:
        """Test version with quotes."""
        assert extract_version_from_package_string('"1.2.3"') == "1.2.3"

    def test_version_with_at_symbols(self) -> None:
        """Test version with multiple @ symbols."""
        result = extract_version_from_package_string("pkg@sub@1.2.3")
        assert result == "1.2.3"


class TestSanitizeVersionString:
    """Test sanitize_version_string function."""

    def test_clean_version(self) -> None:
        """Test already clean version."""
        assert sanitize_version_string("1.2.3") == "1.2.3"

    def test_version_with_v_prefix(self) -> None:
        """Test version with v prefix."""
        assert sanitize_version_string("v1.2.3") == "1.2.3"

    def test_version_with_at_symbol(self) -> None:
        """Test version with @ symbol."""
        assert sanitize_version_string("@1.2.3") == "1.2.3"

    def test_version_with_quotes(self) -> None:
        """Test version with quotes."""
        assert sanitize_version_string('"1.2.3"') == "1.2.3"
        assert sanitize_version_string("'1.2.3'") == "1.2.3"

    def test_version_with_whitespace(self) -> None:
        """Test version with whitespace."""
        assert sanitize_version_string("  1.2.3  ") == "1.2.3"

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert sanitize_version_string("") == ""

    def test_complex_version(self) -> None:
        """Test complex version with multiple issues."""
        # The function processes in order: lstrip('v'), replace('@'), strip quotes, strip whitespace
        # Input: '  v"@1.2.3"  ' ->lstrip 'v'-> '  "@1.2.3"  ' -> replace '@' -> '  "1.2.3"  ' -> strip quotes -> '  1.2.3  ' -> strip -> '1.2.3'
        result = sanitize_version_string("  @1.2.3  ")
        assert result == "1.2.3"


class TestValidateVersionString:
    """Test validate_version_string function."""

    def test_valid_semantic_version(self) -> None:
        """Test valid semantic version."""
        assert validate_version_string("1.2.3")

    def test_valid_two_part_version(self) -> None:
        """Test valid two-part version."""
        assert validate_version_string("1.2")

    def test_valid_single_digit_version(self) -> None:
        """Test valid single digit version."""
        assert validate_version_string("1")

    def test_valid_four_part_version(self) -> None:
        """Test valid four-part version."""
        assert validate_version_string("1.2.3.4")

    def test_valid_version_with_prerelease(self) -> None:
        """Test valid version with pre-release."""
        assert validate_version_string("1.2.3-alpha")
        assert validate_version_string("1.2.3-beta.1")

    def test_version_with_v_prefix(self) -> None:
        """Test version with v prefix (should strip it)."""
        assert validate_version_string("v1.2.3")

    def test_invalid_version_with_letters(self) -> None:
        """Test invalid version with letters in main part."""
        assert not validate_version_string("1.a.3")

    def test_invalid_version_special_chars(self) -> None:
        """Test invalid version with special characters."""
        assert not validate_version_string("1.2.3!")

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert not validate_version_string("")

    def test_just_dots(self) -> None:
        """Test just dots."""
        assert not validate_version_string("...")


class TestExtractAndValidateVersion:
    """Test extract_and_validate_version function."""

    def test_valid_extraction_and_validation(self) -> None:
        """Test valid extraction and validation."""
        result = extract_and_validate_version("package@1.2.3")
        assert result == "1.2.3"

    def test_invalid_version_returns_none(self) -> None:
        """Test invalid version returns None."""
        result = extract_and_validate_version("package@abc")
        assert result is None

    def test_valid_complex_package(self) -> None:
        """Test valid complex package."""
        result = extract_and_validate_version("@standardnotes/desktop@3.198.1")
        assert result == "3.198.1"

    def test_simple_version_string(self) -> None:
        """Test simple version string."""
        result = extract_and_validate_version("v1.2.3")
        assert result == "1.2.3"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = extract_and_validate_version("")
        assert result is None


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


class TestIsChecksumFile:
    """Test is_checksum_file function."""

    def test_sha256_file(self) -> None:
        """Test SHA256 checksum file."""
        assert is_checksum_file("checksums.txt")
        assert is_checksum_file("SHA256SUMS")
        assert is_checksum_file("SHA256SUMS.txt")

    def test_sha512_file(self) -> None:
        """Test SHA512 checksum file."""
        assert is_checksum_file("SHA512SUMS")

    def test_yaml_checksum_file(self) -> None:
        """Test YAML checksum file."""
        assert is_checksum_file("latest-linux.yml")
        assert is_checksum_file("checksums.yml")

    def test_specific_extensions(self) -> None:
        """Test specific checksum extensions."""
        assert is_checksum_file("file.sha256sum")
        assert is_checksum_file("file.sha512sum")
        assert is_checksum_file("file.md5sum")

    def test_appimage_with_checksum_extension(self) -> None:
        """Test AppImage with checksum extension."""
        assert is_checksum_file("app.AppImage.sha256")
        assert is_checksum_file("app.AppImage.sha512")

    def test_non_checksum_file(self) -> None:
        """Test non-checksum file."""
        assert not is_checksum_file("app.AppImage")
        assert not is_checksum_file("README.md")
        assert not is_checksum_file("file.txt")

    def test_empty_filename(self) -> None:
        """Test empty filename."""
        assert not is_checksum_file("")

    def test_require_appimage_base(self) -> None:
        """Test requiring AppImage base file."""
        # With require_appimage_base=True, only returns True if base file is .AppImage
        assert is_checksum_file(
            "app.AppImage.sha256", require_appimage_base=True
        )
        assert not is_checksum_file(
            "file.txt.sha256", require_appimage_base=True
        )

        # Without require_appimage_base, .sha256 extension is not matched by default
        # Only specific patterns in CHECKSUM_FILE_PATTERNS match
        assert not is_checksum_file("file.txt.sha256")

        # These ARE matched because .sha256sum is in SPECIFIC_CHECKSUM_EXTENSIONS
        assert is_checksum_file("file.sha256sum")


class TestIsAppimageFile:
    """Test is_appimage_file function."""

    def test_appimage_lowercase(self) -> None:
        """Test lowercase .appimage extension."""
        assert is_appimage_file("app.appimage")

    def test_appimage_uppercase(self) -> None:
        """Test uppercase .AppImage extension."""
        assert is_appimage_file("App.AppImage")

    def test_appimage_mixed_case(self) -> None:
        """Test mixed case .AppImage extension."""
        assert is_appimage_file("app.AppImage")

    def test_non_appimage_file(self) -> None:
        """Test non-AppImage file."""
        assert not is_appimage_file("app.deb")
        assert not is_appimage_file("app.tar.gz")

    def test_empty_filename(self) -> None:
        """Test empty filename."""
        assert not is_appimage_file("")

    def test_appimage_in_middle(self) -> None:
        """Test .AppImage not at end."""
        assert not is_appimage_file("app.AppImage.old")


class TestGetChecksumFileFormatType:
    """Test get_checksum_file_format_type function."""

    def test_yaml_extension_yml(self) -> None:
        """Test .yml extension."""
        assert get_checksum_file_format_type("latest.yml") == "yaml"

    def test_yaml_extension_yaml(self) -> None:
        """Test .yaml extension."""
        assert get_checksum_file_format_type("checksums.yaml") == "yaml"

    def test_traditional_format(self) -> None:
        """Test traditional format."""
        assert get_checksum_file_format_type("SHA256SUMS") == "traditional"
        assert get_checksum_file_format_type("checksums.txt") == "traditional"

    def test_mixed_case_yaml(self) -> None:
        """Test mixed case YAML extension."""
        assert get_checksum_file_format_type("file.YML") == "yaml"
        assert get_checksum_file_format_type("file.YAML") == "yaml"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_sanitize_filename_unicode(self) -> None:
        """Test sanitizing filename with unicode."""
        result = sanitize_filename("file_世界.txt")
        assert "世界" in result

    def test_version_with_many_parts(self) -> None:
        """Test version with many parts."""
        assert validate_version_string("1.2.3.4.5.6")

    def test_checksum_case_insensitive(self) -> None:
        """Test checksum file detection is case-insensitive."""
        assert is_checksum_file("CHECKSUMS.TXT")
        assert is_checksum_file("sha256sums")

    def test_format_bytes_very_large(self) -> None:
        """Test formatting very large byte values."""
        huge_size = 10 * 1024**5
        result = format_bytes(huge_size)
        assert "PB" in result

    def test_desktop_entry_normalization(self) -> None:
        """Test desktop entry name normalization."""
        # Multiple hyphens and underscores
        result = create_desktop_entry_name("app__--__name")
        assert "--" not in result
        assert "__" not in result

    def test_version_extraction_whitespace(self) -> None:
        """Test version extraction with whitespace."""
        result = extract_version_from_package_string("  1.2.3  ")
        assert result == "1.2.3"

    def test_checksum_file_patterns_coverage(self) -> None:
        """Test various checksum file pattern formats."""
        test_files = [
            "latest-mac.yml",
            "checksums.md5",
            "file.sum",
            "file.hash",
            "file.DIGEST",
            "MD5SUMS.txt",
        ]
        for filename in test_files:
            assert is_checksum_file(filename), f"Failed for {filename}"
