"""Tests for input validation utilities."""

import pytest

from my_unicorn.utils.validation import (
    validate_app_name,
    validate_github_identifier,
)


class TestValidateGitHubIdentifier:
    """Tests for validate_github_identifier function."""

    def test_valid_identifiers(self):
        """Test valid identifiers pass without error."""
        # These should not raise any exceptions
        validate_github_identifier("Cyber-Syntax", "GitHub owner")
        validate_github_identifier("my-unicorn", "GitHub repo")
        validate_github_identifier("test_repo", "GitHub repo")
        validate_github_identifier("Test.Repo", "GitHub repo")
        validate_github_identifier("abc123", "GitHub owner")

    def test_empty_identifier(self):
        """Test empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            validate_github_identifier("", "GitHub owner")

    def test_path_traversal_attack(self):
        """Test path traversal patterns are blocked."""
        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("../etc", "GitHub owner")

        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("..\\windows", "GitHub repo")

        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("test/../etc", "GitHub owner")

    def test_directory_separator_attack(self):
        """Test directory separators are blocked."""
        with pytest.raises(ValueError, match="contains '/'"):
            validate_github_identifier("path/to/file", "GitHub owner")

        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("path\\to\\file", "GitHub repo")

    def test_null_byte_injection(self):
        """Test null byte injection is blocked."""
        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("evil\x00payload", "GitHub owner")

    def test_newline_injection(self):
        """Test newline characters are blocked."""
        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("test\nowner", "GitHub owner")

        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("test\rrepo", "GitHub repo")

    def test_tab_injection(self):
        """Test tab characters are blocked."""
        with pytest.raises(ValueError, match="contains"):
            validate_github_identifier("test\trepo", "GitHub repo")

    def test_length_limit(self):
        """Test length limit is enforced."""
        # 100 chars should pass
        valid_long = "a" * 100
        validate_github_identifier(valid_long, "GitHub owner")

        # 101 chars should fail
        invalid_long = "a" * 101
        with pytest.raises(ValueError, match="too long"):
            validate_github_identifier(invalid_long, "GitHub owner")

    def test_invalid_characters(self):
        """Test invalid characters are rejected."""
        with pytest.raises(ValueError, match="must be alphanumeric"):
            validate_github_identifier("test@repo", "GitHub repo")

        with pytest.raises(ValueError, match="must be alphanumeric"):
            validate_github_identifier("test repo", "GitHub owner")

        with pytest.raises(ValueError, match="must be alphanumeric"):
            validate_github_identifier("test#repo", "GitHub repo")

    def test_error_messages_include_name(self):
        """Test error messages include the identifier name."""
        with pytest.raises(ValueError, match="GitHub owner"):
            validate_github_identifier("", "GitHub owner")

        with pytest.raises(ValueError, match="GitHub repo"):
            validate_github_identifier("invalid/path", "GitHub repo")


class TestValidateAppName:
    """Tests for validate_app_name function."""

    def test_valid_app_names(self):
        """Test valid app names pass without error."""
        validate_app_name("qownnotes")
        validate_app_name("zen-browser")
        validate_app_name("my_app")
        validate_app_name("App.Name")
        validate_app_name("app123")

    def test_empty_app_name(self):
        """Test empty app name raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            validate_app_name("")

    def test_path_traversal_in_app_name(self):
        """Test path traversal patterns are blocked in app names."""
        with pytest.raises(ValueError, match="contains"):
            validate_app_name("../etc")

        with pytest.raises(ValueError, match="contains"):
            validate_app_name("app/../config")

    def test_directory_separator_in_app_name(self):
        """Test directory separators are blocked in app names."""
        with pytest.raises(ValueError, match="contains"):
            validate_app_name("path/to/app")

        with pytest.raises(ValueError, match="contains"):
            validate_app_name("path\\to\\app")

    def test_null_byte_in_app_name(self):
        """Test null byte injection is blocked in app names."""
        with pytest.raises(ValueError, match="contains"):
            validate_app_name("app\x00name")

    def test_newline_in_app_name(self):
        """Test newline characters are blocked in app names."""
        with pytest.raises(ValueError, match="contains"):
            validate_app_name("app\nname")

        with pytest.raises(ValueError, match="contains"):
            validate_app_name("app\rname")

    def test_tab_in_app_name(self):
        """Test tab characters are blocked in app names."""
        with pytest.raises(ValueError, match="contains"):
            validate_app_name("app\tname")

    def test_app_name_length_limit(self):
        """Test app name length limit is enforced."""
        # 255 chars should pass
        valid_long = "a" * 255
        validate_app_name(valid_long)

        # 256 chars should fail
        invalid_long = "a" * 256
        with pytest.raises(ValueError, match="too long"):
            validate_app_name(invalid_long)
