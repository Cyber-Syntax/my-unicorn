"""Tests for asset validation utilities.

Tests cover file type validation functions used across multiple modules
for detecting AppImage and checksum files.
"""

from my_unicorn.utils.asset_validation import (
    CHECKSUM_FILE_PATTERNS,
    SPECIFIC_CHECKSUM_EXTENSIONS,
    get_checksum_file_format_type,
    is_appimage_file,
    is_checksum_file,
)


class TestConstants:
    """Test asset validation module constants."""

    def test_checksum_patterns_exist(self) -> None:
        """Test that checksum file patterns are defined."""
        assert len(CHECKSUM_FILE_PATTERNS) > 0
        assert isinstance(CHECKSUM_FILE_PATTERNS, list)

    def test_specific_extensions_exist(self) -> None:
        """Test that specific checksum extensions are defined."""
        assert len(SPECIFIC_CHECKSUM_EXTENSIONS) > 0
        assert isinstance(SPECIFIC_CHECKSUM_EXTENSIONS, list)


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

    def test_checksum_case_insensitive(self) -> None:
        """Test checksum file detection is case-insensitive."""
        assert is_checksum_file("CHECKSUMS.TXT")
        assert is_checksum_file("sha256sums")

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
