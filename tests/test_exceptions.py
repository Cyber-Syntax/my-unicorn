"""Tests for exception classes."""

import pytest

from my_unicorn.exceptions import (
    ConfigurationError,
    DownloadError,
    GitHubAPIError,
    HashComputationError,
    HashMismatchError,
    HashUnavailableError,
    InstallationError,
    InstallError,
    MyUnicornError,
    NetworkError,
    PostProcessingError,
    UpdateError,
    ValidationError,
    VerificationError,
    WorkflowError,
)


class TestMyUnicornError:
    """Test base MyUnicornError class."""

    def test_basic_initialization(self):
        """Test basic error initialization."""
        error = MyUnicornError("Test error")
        assert error.message == "Test error"
        assert error.target is None
        assert error.context == {}
        assert error.is_retryable is False
        assert error.retry_after is None

    def test_initialization_with_target(self):
        """Test initialization with target parameter for backward compat."""
        error = MyUnicornError("Test error", target="myapp")
        assert error.message == "Test error"
        assert error.target == "myapp"
        assert "myapp" in str(error)

    def test_initialization_with_context(self):
        """Test initialization with context dictionary."""
        error = MyUnicornError(
            "Test error",
            context={"app_name": "test", "version": "1.0"},
        )
        assert error.context == {"app_name": "test", "version": "1.0"}
        assert "app_name=test" in str(error)
        assert "version=1.0" in str(error)

    def test_initialization_with_retry_metadata(self):
        """Test initialization with retry metadata."""
        error = MyUnicornError(
            "Network error",
            is_retryable=True,
            retry_after=5,
        )
        assert error.is_retryable is True
        assert error.retry_after == 5

    def test_initialization_with_cause(self):
        """Test exception chaining with cause parameter."""
        original = ValueError("Original error")
        error = MyUnicornError("Wrapped error", cause=original)
        assert error.__cause__ is original

    def test_str_representation(self):
        """Test string representation with various configurations."""
        # Basic
        error = MyUnicornError("Test")
        assert str(error) == "Operation failed: Test"

        # With target
        error = MyUnicornError("Test", target="app")
        assert str(error) == "Operation failed for 'app': Test"

        # With context
        error = MyUnicornError("Test", context={"key": "value"})
        assert "key=value" in str(error)


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
        assert isinstance(error, MyUnicornError)

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
        expected = "Validation failed for 'config.json': Invalid format"
        assert str(error) == expected

    def test_inheritance(self):
        """Test that ValidationError inherits from Exception."""
        error = ValidationError("Test")
        assert isinstance(error, Exception)
        assert isinstance(error, MyUnicornError)

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

        assert not isinstance(validation_error, InstallationError)
        assert not isinstance(installation_error, ValidationError)
        assert isinstance(validation_error, Exception)
        assert isinstance(installation_error, Exception)


class TestVerificationErrors:
    """Test verification exception hierarchy."""

    def test_verification_error_base(self):
        """Test VerificationError base class."""
        error = VerificationError("Hash check failed")
        assert isinstance(error, MyUnicornError)
        assert error.error_prefix == "Verification failed"
        assert error.is_retryable is False

    def test_hash_mismatch_error(self):
        """Test HashMismatchError with all attributes."""
        error = HashMismatchError(
            expected="abc123",
            actual="def456",
            algorithm="sha256",
            file_path="/tmp/test.AppImage",
        )
        assert error.expected == "abc123"
        assert error.actual == "def456"
        assert error.algorithm == "sha256"
        assert error.file_path == "/tmp/test.AppImage"
        assert error.is_retryable is False
        assert isinstance(error, VerificationError)

        # Check context
        assert error.context["expected_hash"] == "abc123"
        assert error.context["actual_hash"] == "def456"
        assert error.context["algorithm"] == "sha256"

    def test_hash_unavailable_error(self):
        """Test HashUnavailableError with app context."""
        error = HashUnavailableError(app_name="myapp", version="1.0.0")
        assert error.app_name == "myapp"
        assert error.version == "1.0.0"
        assert error.is_retryable is False
        assert isinstance(error, VerificationError)
        assert "myapp" in str(error)
        assert "1.0.0" in str(error)

    def test_hash_computation_error(self):
        """Test HashComputationError with cause chaining."""
        original = OSError("File not found")
        error = HashComputationError(
            file_path="/tmp/test.AppImage",
            algorithm="sha256",
            cause=original,
        )
        assert error.file_path == "/tmp/test.AppImage"
        assert error.algorithm == "sha256"
        assert error.__cause__ is original
        assert error.is_retryable is True
        assert error.retry_after == 1
        assert isinstance(error, VerificationError)


class TestWorkflowErrors:
    """Test workflow exception hierarchy."""

    def test_workflow_error_base(self):
        """Test WorkflowError base class."""
        error = WorkflowError("Workflow failed")
        assert isinstance(error, MyUnicornError)
        assert error.error_prefix == "Workflow failed"

    def test_install_error(self):
        """Test InstallError class."""
        error = InstallError("Could not install app")
        assert isinstance(error, WorkflowError)
        assert error.error_prefix == "Install failed"

    def test_update_error(self):
        """Test UpdateError class."""
        error = UpdateError("Could not update app")
        assert isinstance(error, WorkflowError)
        assert error.error_prefix == "Update failed"

    def test_post_processing_error(self):
        """Test PostProcessingError with step and cause."""
        original = ValueError("Icon format not supported")
        error = PostProcessingError(
            step="icon_extraction",
            app_name="myapp",
            cause=original,
        )
        assert error.step == "icon_extraction"
        assert error.app_name == "myapp"
        assert error.__cause__ is original
        assert error.is_retryable is False
        assert isinstance(error, WorkflowError)
        assert "icon_extraction" in str(error)
        assert "myapp" in str(error)


class TestNetworkErrors:
    """Test network exception hierarchy."""

    def test_network_error_base(self):
        """Test NetworkError base class with default retry."""
        error = NetworkError("Connection failed")
        assert isinstance(error, MyUnicornError)
        assert error.is_retryable is True
        assert error.retry_after == 5  # default
        assert error.url is None
        assert error.status_code is None

    def test_network_error_with_details(self):
        """Test NetworkError with URL and status code."""
        error = NetworkError(
            "Server error",
            url="https://api.github.com/repos",
            status_code=503,
            retry_after=10,
        )
        assert error.url == "https://api.github.com/repos"
        assert error.status_code == 503
        assert error.retry_after == 10
        assert error.context["url"] == "https://api.github.com/repos"
        assert error.context["status_code"] == 503

    def test_download_error(self):
        """Test DownloadError class."""
        error = DownloadError(
            "File not found",
            url="https://github.com/releases/v1.0/app.AppImage",
            status_code=404,
        )
        assert isinstance(error, NetworkError)
        assert error.error_prefix == "Download failed"
        assert error.is_retryable is True

    def test_github_api_error(self):
        """Test GitHubAPIError class."""
        error = GitHubAPIError(
            "Rate limit exceeded",
            url="https://api.github.com",
            status_code=429,
            retry_after=60,
        )
        assert isinstance(error, NetworkError)
        assert error.error_prefix == "GitHub API error"
        assert error.retry_after == 60


class TestConfigurationError:
    """Test ConfigurationError class."""

    def test_basic_initialization(self):
        """Test basic error initialization."""
        error = ConfigurationError("Invalid config")
        assert error.message == "Invalid config"
        assert error.error_prefix == "Configuration error"
        assert error.is_retryable is False

    def test_with_config_path_and_field(self):
        """Test with config_path and field specified."""
        error = ConfigurationError(
            "Missing required field",
            config_path="/home/user/.config/my-unicorn/settings.conf",
            field="appimage_download_folder_path",
        )
        assert error.config_path == (
            "/home/user/.config/my-unicorn/settings.conf"
        )
        assert error.field == "appimage_download_folder_path"
        assert "config_path" in error.context
        assert "field" in error.context

    def test_with_cause(self):
        """Test with exception cause."""
        original = KeyError("missing_key")
        error = ConfigurationError("Parse failed", cause=original)
        assert error.__cause__ is original


class TestExceptionHierarchy:
    """Test exception hierarchy relationships."""

    def test_all_inherit_from_base(self):
        """Test that all exceptions inherit from MyUnicornError."""
        exceptions = [
            InstallationError("test"),
            ValidationError("test"),
            VerificationError("test"),
            HashMismatchError("a", "b", "sha256", "/path"),
            HashUnavailableError("app", "1.0"),
            HashComputationError("/path", "sha256", ValueError()),
            WorkflowError("test"),
            InstallError("test"),
            UpdateError("test"),
            PostProcessingError("step", "app", ValueError()),
            NetworkError("test"),
            DownloadError("test"),
            GitHubAPIError("test"),
            ConfigurationError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, MyUnicornError), f"{type(exc)} failed"
            assert isinstance(exc, Exception), f"{type(exc)} failed"

    def test_verification_hierarchy(self):
        """Test verification exception hierarchy."""
        assert issubclass(HashMismatchError, VerificationError)
        assert issubclass(HashUnavailableError, VerificationError)
        assert issubclass(HashComputationError, VerificationError)
        assert issubclass(VerificationError, MyUnicornError)

    def test_workflow_hierarchy(self):
        """Test workflow exception hierarchy."""
        assert issubclass(InstallError, WorkflowError)
        assert issubclass(UpdateError, WorkflowError)
        assert issubclass(PostProcessingError, WorkflowError)
        assert issubclass(WorkflowError, MyUnicornError)

    def test_network_hierarchy(self):
        """Test network exception hierarchy."""
        assert issubclass(DownloadError, NetworkError)
        assert issubclass(GitHubAPIError, NetworkError)
        assert issubclass(NetworkError, MyUnicornError)

    def test_catch_by_base_class(self):
        """Test catching exceptions by base class."""
        # Catch verification errors
        with pytest.raises(VerificationError):
            raise HashMismatchError("a", "b", "sha256", "/path")

        # Catch workflow errors
        with pytest.raises(WorkflowError):
            raise InstallError("test")

        # Catch network errors
        with pytest.raises(NetworkError):
            raise DownloadError("test")

        # Catch all by base class
        with pytest.raises(MyUnicornError):
            raise GitHubAPIError("test")
