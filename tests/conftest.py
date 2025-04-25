import pytest
import requests_mock
from httmock import HTTMock, all_requests
import sys
import io
from typing import Dict, Any, Generator
import time
import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from src.progress_manager import DynamicProgressManager
from src.secure_token import (
    SecureTokenManager,
    DEFAULT_TOKEN_EXPIRATION_DAYS,
)  # Import the constant directly

# Add the project root to sys.path so that the 'src' package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add the project root directory to Python's path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

@pytest.fixture
def mock_requests_get():
    with requests_mock.Mocker() as m:
        yield m


@pytest.fixture
def httmock():
    @all_requests
    def response_content(url, request):
        return {"status_code": 200, "content": "mocked response"}

    with HTTMock(response_content):
        yield


# New fixtures for secure token and auth tests
@pytest.fixture
def mock_keyring_config():
    """Return a configuration for basic keyring testing."""
    return {
        "keyring_module_installed": True,
        "any_keyring_available": True,
        "gnome_keyring_available": True,
        "kde_wallet_available": False,
        "crypto_available": True,
    }


@pytest.fixture
def token_metadata():
    """Return sample token metadata for testing."""
    from datetime import datetime, timedelta

    now = datetime.now()
    return {
        "created_at": now.timestamp(),
        "expires_at": (now + timedelta(days=30)).timestamp(),
        "last_used_at": now.timestamp(),
        "storage_method": "Encrypted file",
        "storage_location": "keyring",
        "storage_status": "active",
    }


@pytest.fixture
def github_rate_limit_response():
    """Return a sample GitHub API rate limit response."""
    import time

    reset_time = int(time.time()) + 3600  # 1 hour from now

    return {
        "resources": {
            "core": {"limit": 5000, "remaining": 4990, "reset": reset_time, "used": 10},
            "search": {"limit": 30, "remaining": 28, "reset": reset_time, "used": 2},
            "graphql": {"limit": 5000, "remaining": 4999, "reset": reset_time, "used": 1},
        },
        "rate": {"limit": 5000, "remaining": 4990, "reset": reset_time, "used": 10},
    }


# Fixtures specifically for progress_manager tests


@pytest.fixture
def captured_stdout() -> Generator[io.StringIO, None, None]:
    """Capture stdout for testing terminal output.

    Returns:
        Generator[io.StringIO, None, None]: A StringIO object containing captured stdout
    """
    stdout = io.StringIO()
    with patch("sys.stdout", stdout):
        yield stdout


@pytest.fixture(autouse=True)
def cleanup_progress_manager() -> None:
    """Reset the DynamicProgressManager singleton between tests."""
    # Reset before test
    DynamicProgressManager._instance = None

    # Run the test
    yield

    # Reset after test
    if DynamicProgressManager._instance is not None:
        with DynamicProgressManager._instance._lock:
            DynamicProgressManager._instance = None


@pytest.fixture
def download_fixture() -> Dict[str, Any]:
    """Create a simulated download for testing progress tracking.

    Returns:
        Dict[str, Any]: Dictionary with download metadata
    """
    return {
        "filename": "test_file.AppImage",
        "total_size": 1024000,  # 1MB
        "chunks": [
            102400,  # 100KB
            204800,  # 200KB
            307200,  # 300KB
            409600,  # 400KB
        ],
    }

@pytest.fixture
def simulated_time() -> Generator[None, None, None]:
    """Simulate time passing for progress bar speed/ETA calculations."""
    current_time = [time.time()]

    def mock_time():
        return current_time[0]

    def mock_sleep(seconds):
        current_time[0] += seconds

    with patch("time.time", mock_time), patch("time.sleep", mock_sleep):
        yield


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    # ensure keyring and crypto paths are disabled by default
    monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
    monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", False)
    yield

@pytest.fixture
def sample_token():
    # a valid GitHub token format: prefix + 40 chars
    return "ghp_" + "X" * 40

@pytest.fixture
def future_metadata():
    # ISO timestamp DEFAULT_TOKEN_EXPIRATION_DAYS days in the future
    future = datetime.utcnow() + timedelta(days=DEFAULT_TOKEN_EXPIRATION_DAYS)
    return {"expires_at": future.isoformat()}

@pytest.fixture
def past_metadata():
    # ISO timestamp 1 day in the past
    past = datetime.utcnow() - timedelta(days=1)
    return {"expires_at": past.isoformat()}

@pytest.fixture(autouse=True)
def set_consts(monkeypatch):
    monkeypatch.setattr("src.secure_token.KEYRING_AVAILABLE", False)
    monkeypatch.setattr("src.secure_token.CRYPTO_AVAILABLE", True)