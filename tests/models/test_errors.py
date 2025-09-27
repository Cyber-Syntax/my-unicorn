"""Tests for error classes."""

import pytest
from my_unicorn.models.errors import InstallationError, ValidationError


class TestInstallationError:
    """Test InstallationError class."""

    def test_basic_initialization(self):
        """Test basic error initialization."""
        error = InstallationError("Test error")
        assert str(error) == "Test error"
        assert error.target is None

    def test_initialization_with_target(self):
        """Test error initialization with target."""
        error = InstallationError("Test error", target="test_app")
        assert str(error) == "Test error"
        assert error.target == "test_app"

    def test_inheritance(self):
        """Test that InstallationError inherits from Exception."""
        error = InstallationError("Test error")
        assert isinstance(error, Exception)

    def test_raise_and_catch(self):
        """Test raising and catching the error."""
        with pytest.raises(InstallationError) as exc_info:
            raise InstallationError("Test error", target="test_app")
        
        assert str(exc_info.value) == "Test error"
        assert exc_info.value.target == "test_app"


class TestValidationError:
    """Test ValidationError class."""

    def test_basic_initialization(self):
        """Test basic error initialization."""
        error = ValidationError("Validation failed")
        assert str(error) == "Validation failed"
        assert error.target is None

    def test_initialization_with_target(self):
        """Test error initialization with target."""
        error = ValidationError("Validation failed", target="invalid_url")
        assert str(error) == "Validation failed"
        assert error.target == "invalid_url"

    def test_inheritance(self):
        """Test that ValidationError inherits from Exception."""
        error = ValidationError("Validation failed")
        assert isinstance(error, Exception)

    def test_raise_and_catch(self):
        """Test raising and catching the error."""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Invalid target", target="bad_url")
        
        assert str(exc_info.value) == "Invalid target"
        assert exc_info.value.target == "bad_url"

    def test_different_error_types(self):
        """Test that the error types are distinct."""
        install_error = InstallationError("Install failed")
        validation_error = ValidationError("Validation failed")
        
        assert type(install_error) != type(validation_error)
        assert isinstance(install_error, Exception)
        assert isinstance(validation_error, Exception)
