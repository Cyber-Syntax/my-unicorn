"""Tests for exception classes."""

import pytest

from my_unicorn.exceptions import InstallationError, ValidationError


class TestInstallationError:
    """Test InstallationError class."""

    def test_basic_initialization(self):
        """Test basic error initialization."""
        error = InstallationError("Test error")
        assert error.message == "Test error"
        assert error.target is None
        assert str(error) == "Installation failed: Test error"

    def test_initialization_with_target(self):
        """Test initialization with target parameter."""
        error = InstallationError("Download failed", target="app1")
        assert error.message == "Download failed"
        assert error.target == "app1"
        assert str(error) == "Installation failed for 'app1': Download failed"

    def test_inheritance(self):
        """Test that InstallationError inherits from Exception."""
        error = InstallationError("Test")
        assert isinstance(error, Exception)

    def test_raise_and_catch(self):
        """Test raising and catching the error."""
        with pytest.raises(InstallationError) as exc_info:
            raise InstallationError("Test error", target="myapp")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.target == "myapp"
        assert "myapp" in str(exc_info.value)


class TestValidationError:
    """Test ValidationError class."""

    def test_basic_initialization(self):
        """Test basic error initialization."""
        error = ValidationError("Invalid input")
        assert error.message == "Invalid input"
        assert error.target is None
        assert str(error) == "Validation failed: Invalid input"

    def test_initialization_with_target(self):
        """Test initialization with target parameter."""
        error = ValidationError("Invalid format", target="config.json")
        assert error.message == "Invalid format"
        assert error.target == "config.json"
        assert str(error) == "Validation failed for 'config.json': Invalid format"

    def test_inheritance(self):
        """Test that ValidationError inherits from Exception."""
        error = ValidationError("Test")
        assert isinstance(error, Exception)

    def test_raise_and_catch(self):
        """Test raising and catching the error."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Test error", target="input")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.target == "input"
        assert "input" in str(exc_info.value)

    def test_different_error_types(self):
        """Test that ValidationError and InstallationError are distinct."""
        validation_error = ValidationError("Validation failed")
        installation_error = InstallationError("Installation failed")

        assert type(validation_error) != type(installation_error)
        assert isinstance(validation_error, Exception)
        assert isinstance(installation_error, Exception)
