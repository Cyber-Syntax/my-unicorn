"""Tests for ConfigurationValidator.

This test suite validates the configuration validation logic,
particularly for security-critical GitHub identifiers.
"""

import pytest

from my_unicorn.config.validation import ConfigurationValidator


class TestConfigurationValidator:
    """Test cases for ConfigurationValidator."""

    def test_validate_app_config_valid(self) -> None:
        """Test validation with valid configuration."""
        config = {
            "source": {
                "owner": "valid-owner",
                "repo": "valid-repo",
            }
        }

        # Should not raise any exception
        ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_valid_with_numbers(self) -> None:
        """Test validation with valid owner/repo containing numbers."""
        config = {
            "source": {
                "owner": "owner123",
                "repo": "repo456",
            }
        }

        ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_valid_with_hyphens(self) -> None:
        """Test validation with valid owner/repo containing hyphens."""
        config = {
            "source": {
                "owner": "my-owner",
                "repo": "my-repo",
            }
        }

        ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_valid_underscores(self) -> None:
        """Test validation with valid owner/repo containing underscores."""
        config = {
            "source": {
                "owner": "my_owner",
                "repo": "my_repo",
            }
        }

        ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_invalid_owner_empty(self) -> None:
        """Test validation fails with empty owner."""
        config = {
            "source": {
                "owner": "",
                "repo": "valid-repo",
            }
        }

        with pytest.raises(ValueError, match="GitHub owner"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_invalid_repo_empty(self) -> None:
        """Test validation fails with empty repo."""
        config = {
            "source": {
                "owner": "valid-owner",
                "repo": "",
            }
        }

        with pytest.raises(ValueError, match="GitHub repo"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_invalid_owner_special_chars(self) -> None:
        """Test validation fails with invalid special characters in owner."""
        config = {
            "source": {
                "owner": "invalid@owner",
                "repo": "valid-repo",
            }
        }

        with pytest.raises(ValueError, match="GitHub owner"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_invalid_repo_special_chars(self) -> None:
        """Test validation fails with invalid special characters in repo."""
        config = {
            "source": {
                "owner": "valid-owner",
                "repo": "invalid$repo",
            }
        }

        with pytest.raises(ValueError, match="GitHub repo"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_invalid_owner_spaces(self) -> None:
        """Test validation fails with spaces in owner."""
        config = {
            "source": {
                "owner": "invalid owner",
                "repo": "valid-repo",
            }
        }

        with pytest.raises(ValueError, match="GitHub owner"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_invalid_repo_spaces(self) -> None:
        """Test validation fails with spaces in repo."""
        config = {
            "source": {
                "owner": "valid-owner",
                "repo": "invalid repo",
            }
        }

        with pytest.raises(ValueError, match="GitHub repo"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_missing_source(self) -> None:
        """Test validation with missing source section."""
        config: dict = {}

        # Should use empty strings as defaults and fail validation
        with pytest.raises(ValueError):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_missing_owner(self) -> None:
        """Test validation with missing owner field."""
        config = {
            "source": {
                "repo": "valid-repo",
            }
        }

        with pytest.raises(ValueError, match="GitHub owner"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_missing_repo(self) -> None:
        """Test validation with missing repo field."""
        config = {
            "source": {
                "owner": "valid-owner",
            }
        }

        with pytest.raises(ValueError, match="GitHub repo"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_path_traversal_attempt(self) -> None:
        """Test validation fails with path traversal attempts."""
        config = {
            "source": {
                "owner": "../../../etc",
                "repo": "passwd",
            }
        }

        with pytest.raises(ValueError, match="GitHub owner"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_command_injection_attempt(self) -> None:
        """Test validation fails with command injection attempts."""
        config = {
            "source": {
                "owner": "owner; rm -rf /",
                "repo": "repo",
            }
        }

        with pytest.raises(ValueError, match="GitHub owner"):
            ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_long_names(self) -> None:
        """Test validation with very long but valid names."""
        config = {
            "source": {
                "owner": "a" * 100,
                "repo": "b" * 100,
            }
        }

        # Should pass - no length limit currently
        ConfigurationValidator.validate_app_config(config)

    def test_validate_app_config_single_character_names(self) -> None:
        """Test validation with single character names."""
        config = {
            "source": {
                "owner": "a",
                "repo": "b",
            }
        }

        ConfigurationValidator.validate_app_config(config)
