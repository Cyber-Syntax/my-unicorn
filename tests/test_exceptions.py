"""Tests for exception classes."""

import pytest

from my_unicorn.exceptions import (
    ConfigurationError,
    InstallationError,
    InstallError,
    LockError,
    MyUnicornError,
    UpdateError,
    VerificationError,
)


class TestMyUnicornError:
    """Test base MyUnicornError class."""

    def test_basic_initialization(self) -> None:
        """Test basic error initialization."""
        error: MyUnicornError = MyUnicornError("Test error")
        assert error.message == "Test error"
        assert error.target is None
        assert error.context == {}
        assert error.is_retryable is False
        assert error.retry_after is None

    def test_initialization_with_target(self) -> None:
        """Test initialization with target parameter for backward compat."""
        error: MyUnicornError = MyUnicornError("Test error", target="myapp")
        assert error.message == "Test error"
        assert error.target == "myapp"
        assert "myapp" in str(error)

    def test_initialization_with_context(self) -> None:
        """Test initialization with context dictionary."""
        error = MyUnicornError(
            "Test error",
            context={"app_name": "test", "version": "1.0"},
        )
        assert error.context == {"app_name": "test", "version": "1.0"}
        assert "app_name=test" in str(error)
        assert "version=1.0" in str(error)

    def test_initialization_with_retry_metadata(self) -> None:
        """Test initialization with retry metadata."""
        error = MyUnicornError(
            "Network error",
            is_retryable=True,
            retry_after=5,
        )
        assert error.is_retryable is True
        assert error.retry_after == 5

    def test_initialization_with_cause(self) -> None:
        """Test exception chaining with cause parameter."""
        original: ValueError = ValueError("Original error")
        error: MyUnicornError = MyUnicornError("Wrapped error", cause=original)
        assert error.__cause__ is original

    def test_str_representation(self) -> None:
        """Test string representation with various configurations."""
        # Basic
        error: MyUnicornError = MyUnicornError("Test")
        assert str(error) == "Operation failed: Test"

        # With target
        error: MyUnicornError = MyUnicornError("Test", target="app")
        assert str(error) == "Operation failed for 'app': Test"

        # With context
        error: MyUnicornError = MyUnicornError(
            "Test", context={"key": "value"}
        )
        assert "key=value" in str(error)


class TestInstallationError:
    """Test InstallationError class."""

    def test_basic_initialization(self) -> None:
        """Test basic error initialization."""
        error: InstallationError = InstallationError("Test error")
        assert error.message == "Test error"
        assert error.target is None
        assert str(error) == "Installation failed: Test error"

    def test_initialization_with_target(self) -> None:
        """Test initialization with target parameter."""
        error: InstallationError = InstallationError(
            "Download failed", target="app1"
        )
        assert error.message == "Download failed"
        assert error.target == "app1"
        assert str(error) == "Installation failed for 'app1': Download failed"

    def test_inheritance(self) -> None:
        """Test that InstallationError inherits from Exception."""
        error: InstallationError = InstallationError("Test")
        assert isinstance(error, Exception)
        assert isinstance(error, MyUnicornError)

    def test_raise_and_catch(self) -> None:
        """Test raising and catching the error."""
        with pytest.raises(InstallationError) as exc_info:
            raise InstallationError("Test error", target="myapp")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.target == "myapp"
        assert "myapp" in str(exc_info.value)


class TestVerificationErrors:
    """Test verification exception hierarchy."""

    def test_verification_error_base(self) -> None:
        """Test VerificationError base class."""
        error: VerificationError = VerificationError("Hash check failed")
        assert isinstance(error, MyUnicornError)
        assert error.error_prefix == "Verification failed"
        assert error.is_retryable is False


class TestConfigurationError:
    """Test ConfigurationError class."""

    def test_basic_initialization(self) -> None:
        """Test basic error initialization."""
        error: ConfigurationError = ConfigurationError("Invalid config")
        assert error.message == "Invalid config"
        assert error.error_prefix == "Configuration error"
        assert error.is_retryable is False

    def test_with_cause(self) -> None:
        """Test with exception cause."""
        original: KeyError = KeyError("missing_key")
        error: ConfigurationError = ConfigurationError(
            "Parse failed", cause=original
        )
        assert error.__cause__ is original


class TestLockError:
    """Test LockError class."""

    def test_basic_initialization(self) -> None:
        """Test basic error initialization."""
        error: LockError = LockError("Lock acquisition failed")
        assert error.message == "Lock acquisition failed"
        assert error.error_prefix == "Lock acquisition failed"
        assert error.target is None

    def test_inheritance_from_myunicornerror(self) -> None:
        """Test that LockError inherits from MyUnicornError."""
        error: LockError = LockError("Lock failed")
        assert isinstance(error, MyUnicornError)
        assert isinstance(error, Exception)

    def test_lock_error_message_formatting(self) -> None:
        """Test error message formatting works correctly."""
        msg: str = "Another my-unicorn instance is already running"
        error: LockError = LockError(msg)
        assert "Lock acquisition failed" in str(error)
        assert msg in str(error)

    def test_lock_error_with_target(self) -> None:
        """Test LockError with target parameter."""
        error: LockError = LockError("Lock failed", target="my-unicorn")
        assert error.target == "my-unicorn"
        assert "my-unicorn" in str(error)
        assert "Lock acquisition failed" in str(error)

    def test_lock_error_with_context(self) -> None:
        """Test LockError with context data."""
        error: LockError = LockError(
            "Could not acquire lock",
            context={"lock_path": "/run/my-unicorn.lock"},
        )
        assert error.context["lock_path"] == "/run/my-unicorn.lock"
        assert "lock_path=" in str(error)

    def test_raise_and_catch(self) -> None:
        """Test raising and catching the error."""
        with pytest.raises(LockError) as exc_info:
            raise LockError("Lock already held")

        assert exc_info.value.message == "Lock already held"
        assert "Lock acquisition failed" in str(exc_info.value)

    def test_catch_by_base_class(self) -> None:
        """Test catching LockError by base MyUnicornError class."""
        with pytest.raises(MyUnicornError):
            raise LockError("Lock failed")


class TestExceptionHierarchy:
    """Test exception hierarchy relationships."""

    def test_all_inherit_from_base(self) -> None:
        """Test that all exceptions inherit from MyUnicornError."""
        exceptions: list[Exception] = [
            InstallationError("test"),
            VerificationError("test"),
            InstallError("test"),
            UpdateError("test"),
            ConfigurationError("test"),
            LockError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, MyUnicornError), f"{type(exc)} failed"
            assert isinstance(exc, Exception), f"{type(exc)} failed"

    def test_verification_hierarchy(self) -> None:
        """Test verification exception hierarchy."""
        assert issubclass(VerificationError, MyUnicornError)
